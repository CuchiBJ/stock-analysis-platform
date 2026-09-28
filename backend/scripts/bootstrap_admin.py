#!/usr/bin/env python3
"""Create or validate the initial administrator account.

Usage:
    python scripts/bootstrap_admin.py --email admin@example.com --display-name Admin

Passwords are accepted only through a non-echoing terminal prompt. The command
never prints a password or password hash.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hmac
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Allow the documented ``python scripts/...`` invocation from the backend root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.deps import AsyncSessionLocal
from app.models.stock import JournalTrade  # noqa: F401 - register ORM relationship
from app.models.user import User, UserProfile, UserRole, UserState, normalize_email
from app.services.auth_service import hash_password, validate_password


class AdminBootstrapError(RuntimeError):
    """Raised when bootstrap would mutate or accept an unsafe identity."""


@dataclass(frozen=True)
class AdminBootstrapResult:
    email: str
    created: bool


def prompt_new_password(
    *,
    password_prompt: str = "Administrator password: ",
    confirmation_prompt: str = "Confirm administrator password: ",
) -> str:
    """Read and confirm a policy-compliant password without terminal echo."""
    password = getpass.getpass(password_prompt)
    confirmation = getpass.getpass(confirmation_prompt)
    if not hmac.compare_digest(password, confirmation):
        raise AdminBootstrapError("password confirmation does not match")
    validate_password(password)
    return password


async def bootstrap_admin(
    db: AsyncSession,
    *,
    email: str,
    display_name: str,
    password: str,
    now: Optional[datetime] = None,
) -> AdminBootstrapResult:
    """Create one verified admin/profile or validate the existing target.

    The caller owns the transaction. An existing non-admin is always rejected;
    this operation never promotes a public account or repairs account state.
    """
    canonical_email = normalize_email(email)
    normalized_display_name = display_name.strip()
    if not 1 <= len(normalized_display_name) <= 80:
        raise AdminBootstrapError(
            "display name must contain between 1 and 80 characters"
        )

    existing = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.email == canonical_email)
        .with_for_update()
    )
    if existing is not None:
        _validate_existing_admin(existing)
        return AdminBootstrapResult(email=canonical_email, created=False)

    verified_at = now or datetime.now(timezone.utc)
    user = User(
        email=canonical_email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN.value,
        state=UserState.ACTIVE.value,
        email_verified_at=verified_at,
    )
    user.profile = UserProfile(display_name=normalized_display_name)
    db.add(user)
    await db.flush()
    return AdminBootstrapResult(email=canonical_email, created=True)


def _validate_existing_admin(user: User) -> None:
    if user.role != UserRole.ADMIN.value:
        raise AdminBootstrapError(
            "target email already belongs to a non-administrator account"
        )
    if user.state != UserState.ACTIVE.value or user.email_verified_at is None:
        raise AdminBootstrapError(
            "existing administrator must already be active and verified"
        )
    if user.profile is None:
        raise AdminBootstrapError("existing administrator has no profile")


async def run_bootstrap(
    *, email: str, display_name: str, password: str
) -> AdminBootstrapResult:
    async with AsyncSessionLocal() as db:
        try:
            result = await bootstrap_admin(
                db,
                email=email,
                display_name=display_name,
                password=password,
            )
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or validate the initial verified administrator."
    )
    parser.add_argument("--email", required=True, help="Exact administrator email")
    parser.add_argument(
        "--display-name", required=True, help="Display name used only when creating"
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        password = prompt_new_password()
        result = asyncio.run(
            run_bootstrap(
                email=args.email,
                display_name=args.display_name,
                password=password,
            )
        )
    except (AdminBootstrapError, ValueError) as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1

    action = "Created" if result.created else "Validated existing"
    print(f"{action} verified administrator: {result.email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
