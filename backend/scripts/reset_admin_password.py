#!/usr/bin/env python3
"""Emergency password reset for one explicitly selected administrator.

Usage:
    python scripts/reset_admin_password.py --email admin@example.com

The new password is accepted only through a non-echoing terminal prompt. The
command never prints the password or its hash and revokes all existing sessions.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Allow the documented ``python scripts/...`` invocation from the backend root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.deps import AsyncSessionLocal
from app.models.user import User, UserRole, normalize_email
from app.services.auth_service import hash_password, revoke_all_sessions
from scripts.bootstrap_admin import AdminBootstrapError, prompt_new_password


class AdminPasswordResetError(RuntimeError):
    """Raised when the exact reset target is absent or is not an admin."""


@dataclass(frozen=True)
class AdminPasswordResetResult:
    email: str
    revoked_sessions: int


async def reset_admin_password(
    db: AsyncSession,
    *,
    email: str,
    new_password: str,
) -> AdminPasswordResetResult:
    """Replace one admin hash and revoke all sessions in the caller transaction."""
    canonical_email = normalize_email(email)
    user = await db.scalar(
        select(User)
        .where(User.email == canonical_email)
        .with_for_update()
    )
    if user is None:
        raise AdminPasswordResetError("administrator account was not found")
    if user.role != UserRole.ADMIN.value:
        raise AdminPasswordResetError(
            "target email belongs to a non-administrator account"
        )

    user.password_hash = hash_password(new_password)
    revoked_sessions = await revoke_all_sessions(db, user.id)
    await db.flush()
    return AdminPasswordResetResult(
        email=canonical_email,
        revoked_sessions=revoked_sessions,
    )


async def run_reset(*, email: str, new_password: str) -> AdminPasswordResetResult:
    async with AsyncSessionLocal() as db:
        try:
            result = await reset_admin_password(
                db,
                email=email,
                new_password=new_password,
            )
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reset one administrator password and revoke all sessions."
    )
    parser.add_argument("--email", required=True, help="Exact administrator email")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        password = prompt_new_password(
            password_prompt="New administrator password: ",
            confirmation_prompt="Confirm new administrator password: ",
        )
        result = asyncio.run(run_reset(email=args.email, new_password=password))
    except (AdminBootstrapError, AdminPasswordResetError, ValueError) as exc:
        print(f"Password reset failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Reset password for administrator {result.email}; "
        f"revoked {result.revoked_sessions} session(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
