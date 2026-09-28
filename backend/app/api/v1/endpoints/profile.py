"""Authenticated current-user profile routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user, require_authenticated_mutation
from app.core.deps import get_db
from app.models.user import User, UserProfile
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.services.profile_service import (
    ProfileInvariantError,
    get_current_profile,
    update_current_display_name,
)


router = APIRouter(prefix="/profile")


def _response(user: User, profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        display_name=profile.display_name,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _profile_or_500(user: User) -> UserProfile:
    try:
        return get_current_profile(user)
    except ProfileInvariantError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account profile is unavailable.",
        ) from exc


@router.get("", response_model=ProfileResponse)
async def read_profile(
    user: Annotated[User, Depends(get_current_active_user)],
) -> ProfileResponse:
    return _response(user, _profile_or_500(user))


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    user: Annotated[User, Depends(require_authenticated_mutation)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    try:
        profile = await update_current_display_name(
            db,
            user,
            payload.display_name,
        )
    except ProfileInvariantError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account profile is unavailable.",
        ) from exc
    await db.commit()
    return _response(user, profile)
