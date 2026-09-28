"""Authorization and allow-list contracts for the current-user profile."""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.profile import read_profile, router, update_profile
from app.models.user import User, UserProfile, UserRole, UserState
from app.schemas.profile import ProfileUpdate


UTC = timezone.utc
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


class _Database:
    def __init__(self):
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _user(email: str, display_name: str) -> User:
    user = User(
        id=uuid4(),
        email=email,
        password_hash="not-exposed",
        role=UserRole.USER.value,
        state=UserState.ACTIVE.value,
        email_verified_at=NOW,
    )
    profile = UserProfile(user_id=user.id, display_name=display_name)
    profile.created_at = NOW
    profile.updated_at = NOW
    user.profile = profile
    return user


def test_profile_model_is_exactly_one_to_one_with_user_and_has_audit_timestamps():
    relationship = User.profile.property
    user_id = UserProfile.__table__.columns["user_id"]

    assert relationship.uselist is False
    assert user_id.primary_key is True
    assert {foreign_key.target_fullname for foreign_key in user_id.foreign_keys} == {
        "users.id"
    }
    assert "created_at" in UserProfile.__table__.columns
    assert "updated_at" in UserProfile.__table__.columns


def test_profile_routes_have_no_path_or_function_selector_for_another_user():
    route_paths = {route.path for route in router.routes}

    assert route_paths == {"/profile"}
    assert all("{" not in path for path in route_paths)
    assert "user_id" not in inspect.signature(read_profile).parameters
    assert "user_id" not in inspect.signature(update_profile).parameters


def test_get_profile_returns_only_the_authenticated_users_profile():
    owner = _user("owner@example.com", "Owner")

    response = asyncio.run(read_profile(owner))

    assert response.user_id == owner.id
    assert response.email == owner.email
    assert response.role == owner.role
    assert response.display_name == owner.profile.display_name


def test_patch_updates_only_the_authenticated_users_display_name():
    owner = _user("owner@example.com", "Before")
    other = _user("other@example.com", "Other User")
    db = _Database()

    response = asyncio.run(
        update_profile(ProfileUpdate(display_name="  After  "), owner, db)
    )

    assert response.user_id == owner.id
    assert response.display_name == "After"
    assert owner.profile.display_name == "After"
    assert other.profile.display_name == "Other User"
    assert db.flushes == 1
    assert db.commits == 1
    assert db.rollbacks == 0


@pytest.mark.parametrize(
    "field",
    [
        "user_id",
        "email",
        "role",
        "state",
        "email_verified_at",
        "verified",
    ],
)
def test_profile_patch_rejects_identity_and_privileged_fields(field):
    values = {"display_name": "Allowed Name", field: "attacker-controlled"}

    with pytest.raises(ValidationError):
        ProfileUpdate(**values)


@pytest.mark.parametrize("display_name", ["", "   ", "x" * 81])
def test_profile_patch_rejects_display_name_outside_trimmed_1_to_80(display_name):
    with pytest.raises(ValidationError):
        ProfileUpdate(display_name=display_name)


@pytest.mark.parametrize(
    ("submitted", "normalized"),
    [
        ("x", "x"),
        ("  Person Name  ", "Person Name"),
        ("  " + "x" * 80 + "  ", "x" * 80),
    ],
)
def test_profile_patch_accepts_and_trims_display_name_within_1_to_80(
    submitted,
    normalized,
):
    assert ProfileUpdate(display_name=submitted).display_name == normalized
