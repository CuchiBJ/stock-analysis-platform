"""Current-account profile operations with no caller-selectable identity."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile


class ProfileInvariantError(RuntimeError):
    """Raised when an account exists without its required one-to-one profile."""


def get_current_profile(user: User) -> UserProfile:
    """Return the profile already loaded for the authenticated user."""

    profile = user.profile
    if profile is None:
        raise ProfileInvariantError("authenticated account has no profile")
    return profile


async def update_current_display_name(
    db: AsyncSession,
    user: User,
    display_name: str,
) -> UserProfile:
    """Update only the current user's validated display name.

    The caller owns the transaction.  ``UserProfile`` validation trims the
    value and enforces the persistence invariant as a second line of defense.
    """

    profile = get_current_profile(user)
    profile.display_name = display_name
    await db.flush()
    return profile


__all__ = [
    "ProfileInvariantError",
    "get_current_profile",
    "update_current_display_name",
]
