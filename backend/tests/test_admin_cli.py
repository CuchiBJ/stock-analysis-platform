"""Safety contracts for administrator bootstrap and emergency reset helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

import scripts.bootstrap_admin as bootstrap_cli
import scripts.reset_admin_password as reset_cli
from app.models.user import User, UserProfile, UserRole, UserState
from app.services.auth_service import verify_password


UTC = timezone.utc
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
VALID_PASSWORD = "a strong administrator passphrase 2026!"


def test_bootstrap_module_configures_all_mappers_when_loaded_standalone():
    backend_root = Path(__file__).resolve().parent.parent
    environment = {
        **os.environ,
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/test",
        "POLYGON_API_KEY": "test-only",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import scripts.bootstrap_admin; "
            "from sqlalchemy.orm import configure_mappers; configure_mappers()",
        ],
        cwd=backend_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


class _Database:
    def __init__(self, scalar_result=None):
        self.scalar_result = scalar_result
        self.added = []
        self.flushes = 0

    async def scalar(self, _statement):
        return self.scalar_result

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1
        for value in self.added:
            if value.id is None:
                value.id = uuid4()


def _admin(*, role=UserRole.ADMIN, state=UserState.ACTIVE, verified=True):
    user = User(
        id=uuid4(),
        email="admin@example.com",
        password_hash="existing-hash",
        role=role.value,
        state=state.value,
        email_verified_at=NOW if verified else None,
    )
    user.profile = UserProfile(user_id=user.id, display_name="Admin")
    return user


def test_password_prompt_uses_non_echoing_reader_and_requires_matching_confirmation(
    monkeypatch,
):
    prompts = []
    answers = iter([VALID_PASSWORD, VALID_PASSWORD])

    def fake_getpass(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(bootstrap_cli.getpass, "getpass", fake_getpass)

    assert bootstrap_cli.prompt_new_password() == VALID_PASSWORD
    assert len(prompts) == 2


def test_password_prompt_rejects_mismatched_confirmation(monkeypatch):
    answers = iter([VALID_PASSWORD, "a different valid passphrase 2026!"])
    monkeypatch.setattr(bootstrap_cli.getpass, "getpass", lambda _prompt: next(answers))

    with pytest.raises(bootstrap_cli.AdminBootstrapError):
        bootstrap_cli.prompt_new_password()


def test_bootstrap_creates_exactly_one_verified_active_admin_and_profile():
    db = _Database()

    result = asyncio.run(
        bootstrap_cli.bootstrap_admin(
            db,
            email=" ADMIN@Example.COM ",
            display_name="  Administrator  ",
            password=VALID_PASSWORD,
            now=NOW,
        )
    )

    assert result.created is True
    assert result.email == "admin@example.com"
    assert len(db.added) == 1
    user = db.added[0]
    assert user.role == UserRole.ADMIN
    assert user.state == UserState.ACTIVE
    assert user.email_verified_at == NOW
    assert user.profile.display_name == "Administrator"
    assert verify_password(VALID_PASSWORD, user.password_hash) is True


def test_bootstrap_is_idempotent_for_expected_admin_and_never_promotes_user():
    admin_db = _Database(_admin())
    user_db = _Database(_admin(role=UserRole.USER))

    result = asyncio.run(
        bootstrap_cli.bootstrap_admin(
            admin_db,
            email="admin@example.com",
            display_name="Ignored",
            password=VALID_PASSWORD,
            now=NOW,
        )
    )

    assert result.created is False
    assert admin_db.added == []
    with pytest.raises(bootstrap_cli.AdminBootstrapError):
        asyncio.run(
            bootstrap_cli.bootstrap_admin(
                user_db,
                email="admin@example.com",
                display_name="Ignored",
                password=VALID_PASSWORD,
                now=NOW,
            )
        )
    assert user_db.scalar_result.role == UserRole.USER


def test_emergency_reset_changes_only_admin_hash_and_revokes_every_session(monkeypatch):
    admin = _admin()
    old_hash = admin.password_hash
    db = _Database(admin)
    revoked = []

    async def fake_revoke(_db, user_id):
        revoked.append(user_id)
        return 4

    monkeypatch.setattr(reset_cli, "revoke_all_sessions", fake_revoke)

    result = asyncio.run(
        reset_cli.reset_admin_password(
            db,
            email=" ADMIN@Example.COM ",
            new_password=VALID_PASSWORD,
        )
    )

    assert result.email == "admin@example.com"
    assert result.revoked_sessions == 4
    assert admin.password_hash != old_hash
    assert verify_password(VALID_PASSWORD, admin.password_hash) is True
    assert revoked == [admin.id]
    assert db.flushes == 1


def test_emergency_reset_rejects_missing_or_non_admin_target(monkeypatch):
    called = []

    async def fake_revoke(*_args, **_kwargs):
        called.append(True)
        return 0

    monkeypatch.setattr(reset_cli, "revoke_all_sessions", fake_revoke)

    for target in (None, _admin(role=UserRole.USER)):
        with pytest.raises(reset_cli.AdminPasswordResetError):
            asyncio.run(
                reset_cli.reset_admin_password(
                    _Database(target),
                    email="target@example.com",
                    new_password=VALID_PASSWORD,
                )
            )
    assert called == []
