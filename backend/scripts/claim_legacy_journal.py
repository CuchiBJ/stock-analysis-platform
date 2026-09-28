#!/usr/bin/env python3
"""Safely assign legacy unowned journal rows to one explicit administrator.

The command is dry-run by default.  A dry-run performs the same locks, update,
and post-validation as an execution, then rolls the transaction back.  Output
contains only counts, aggregate values, and one-way checksums; it never prints
journal rows, symbols, notes, tokens, or credentials.

Usage:
    python scripts/claim_legacy_journal.py --admin-email admin@example.com
    python scripts/claim_legacy_journal.py --admin-email admin@example.com --execute
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

# Allow the documented ``python scripts/...`` invocation from the backend root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.deps import AsyncSessionLocal
from app.models.stock import JournalStopEvent, JournalTrade, TransitionObservation
from app.models.user import User, UserRole, UserState, normalize_email


class JournalClaimError(RuntimeError):
    """Raised when ownership is ambiguous or journal invariants do not hold."""


@dataclass(frozen=True)
class JournalValidationReport:
    trade_count: int
    unowned_trade_count: int
    open_trade_count: int
    closed_trade_count: int
    trade_ids_checksum: str
    trade_fields_checksum: str
    decision_parent_count: int
    invalid_parent_target_count: int
    stop_event_count: int
    invalid_stop_target_count: int
    stop_events_checksum: str
    linked_observation_count: int
    invalid_linked_observation_count: int
    quantity_sum: str
    pnl_dollars_sum: str
    entry_notional_sum: str


@dataclass(frozen=True)
class JournalClaimResult:
    dry_run: bool
    assigned_trade_count: int
    before: JournalValidationReport
    after: JournalValidationReport


_PRESERVED_REPORT_FIELDS = (
    "trade_count",
    "open_trade_count",
    "closed_trade_count",
    "trade_ids_checksum",
    "trade_fields_checksum",
    "decision_parent_count",
    "invalid_parent_target_count",
    "stop_event_count",
    "invalid_stop_target_count",
    "stop_events_checksum",
    "linked_observation_count",
    "invalid_linked_observation_count",
    "quantity_sum",
    "pnl_dollars_sum",
    "entry_notional_sum",
)


async def lock_journal_tables(db: AsyncSession) -> None:
    """Prevent journal writes while ownership and invariants are inspected."""

    await db.execute(
        text(
            "LOCK TABLE journal_trades, journal_stop_events "
            "IN ACCESS EXCLUSIVE MODE"
        )
    )


async def validate_admin_target(db: AsyncSession, email: str) -> User:
    """Lock and return one explicitly selected verified active administrator."""

    user = await db.scalar(
        select(User)
        .where(User.email == normalize_email(email))
        .with_for_update()
    )
    if user is None:
        raise JournalClaimError("administrator target was not found")
    if user.role != UserRole.ADMIN.value:
        raise JournalClaimError("ownership target is not an administrator")
    if user.state != UserState.ACTIVE.value or user.email_verified_at is None:
        raise JournalClaimError(
            "administrator target must be active and email-verified"
        )
    return user


async def capture_journal_validation(
    db: AsyncSession,
) -> JournalValidationReport:
    """Capture content-safe journal invariants inside the current transaction."""

    trade_rows = await _table_rows(db, JournalTrade.__table__)
    stop_rows = await _table_rows(db, JournalStopEvent.__table__)
    trade_ids = {row["id"] for row in trade_rows}

    parent_links = [
        row["parent_trade_id"]
        for row in trade_rows
        if row.get("parent_trade_id") is not None
    ]
    parent_ids = set(parent_links)
    linked_observation_links = [
        row["linked_observation_id"]
        for row in trade_rows
        if row.get("linked_observation_id") is not None
    ]
    linked_ids = set(linked_observation_links)
    existing_observation_ids: set[int] = set()
    if linked_ids:
        result = await db.execute(
            select(TransitionObservation.id).where(
                TransitionObservation.id.in_(linked_ids)
            )
        )
        existing_observation_ids = set(result.scalars())

    stable_trade_columns = sorted(
        column.name
        for column in JournalTrade.__table__.columns
        if column.name not in {"owner_user_id", "updated_at"}
    )
    stable_stop_columns = sorted(
        column.name
        for column in JournalStopEvent.__table__.columns
        if column.name != "updated_at"
    )

    open_rows = [row for row in trade_rows if row.get("exit_date") is None]
    closed_rows = [row for row in trade_rows if row.get("exit_date") is not None]
    return JournalValidationReport(
        trade_count=len(trade_rows),
        unowned_trade_count=sum(
            row.get("owner_user_id") is None for row in trade_rows
        ),
        open_trade_count=len(open_rows),
        closed_trade_count=len(closed_rows),
        trade_ids_checksum=_checksum_values(sorted(trade_ids)),
        trade_fields_checksum=_checksum_rows(trade_rows, stable_trade_columns),
        decision_parent_count=len(parent_links),
        invalid_parent_target_count=sum(
            parent_id not in trade_ids for parent_id in parent_links
        ),
        stop_event_count=len(stop_rows),
        invalid_stop_target_count=sum(
            row["trade_id"] not in trade_ids for row in stop_rows
        ),
        stop_events_checksum=_checksum_rows(stop_rows, stable_stop_columns),
        linked_observation_count=len(linked_observation_links),
        invalid_linked_observation_count=sum(
            observation_id not in existing_observation_ids
            for observation_id in linked_observation_links
        ),
        quantity_sum=_decimal_sum(row.get("qty") for row in trade_rows),
        pnl_dollars_sum=_decimal_sum(
            row.get("pnl_dollars") for row in trade_rows
        ),
        entry_notional_sum=_decimal_sum(
            _decimal(row.get("entry_price")) * _decimal(row.get("qty"))
            for row in trade_rows
        ),
    )


def validate_report_integrity(report: JournalValidationReport) -> None:
    """Reject dangling relationships before or after an ownership claim."""

    failures = []
    if report.invalid_parent_target_count:
        failures.append("decision parents")
    if report.invalid_stop_target_count:
        failures.append("stop events")
    if report.invalid_linked_observation_count:
        failures.append("linked observations")
    if failures:
        raise JournalClaimError(
            "journal integrity validation failed for: " + ", ".join(failures)
        )


def compare_preserved_reports(
    before: JournalValidationReport,
    after: JournalValidationReport,
) -> None:
    """Prove that claiming ownership changed no journal semantics or links."""

    changed = [
        field
        for field in _PRESERVED_REPORT_FIELDS
        if getattr(before, field) != getattr(after, field)
    ]
    if changed:
        raise JournalClaimError(
            "post-claim validation changed protected invariants: "
            + ", ".join(changed)
        )


async def claim_legacy_journal(
    db: AsyncSession,
    *,
    admin_email: str,
    dry_run: bool = True,
) -> JournalClaimResult:
    """Lock, validate, assign null-owned rows, and verify preserved invariants.

    The caller controls commit/rollback.  :func:`run_claim` is the safe public
    transaction boundary used by the CLI and always rolls back dry-runs and
    failures.
    """

    await lock_journal_tables(db)
    admin = await validate_admin_target(db, admin_email)
    before = await capture_journal_validation(db)
    validate_report_integrity(before)

    ownership_rows = await _table_rows(db, JournalTrade.__table__)
    foreign_owner_count = sum(
        row.get("owner_user_id") not in {None, admin.id}
        for row in ownership_rows
    )
    if foreign_owner_count:
        raise JournalClaimError(
            "journal contains rows owned by a different account; claim aborted"
        )

    result = await db.execute(
        update(JournalTrade)
        .where(JournalTrade.owner_user_id.is_(None))
        .values(owner_user_id=admin.id)
    )
    await db.flush()
    assigned_count = int(result.rowcount or 0)

    after = await capture_journal_validation(db)
    validate_report_integrity(after)
    compare_preserved_reports(before, after)
    if after.unowned_trade_count:
        raise JournalClaimError("post-claim validation found unowned journal rows")
    if assigned_count != before.unowned_trade_count:
        raise JournalClaimError("assigned-row count did not match the locked dry-run count")

    return JournalClaimResult(
        dry_run=dry_run,
        assigned_trade_count=assigned_count,
        before=before,
        after=after,
    )


async def run_claim(
    *,
    admin_email: str,
    dry_run: bool = True,
) -> JournalClaimResult:
    """Execute the claim in one transaction, rolling back dry-runs/failures."""

    async with AsyncSessionLocal() as db:
        try:
            result = await claim_legacy_journal(
                db,
                admin_email=admin_email,
                dry_run=dry_run,
            )
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


async def _table_rows(db: AsyncSession, table: Any) -> list[dict[str, Any]]:
    result = await db.execute(select(*table.c).order_by(table.c.id))
    return [dict(row) for row in result.mappings()]


def _checksum_rows(
    rows: Sequence[Mapping[str, Any]], columns: Sequence[str]
) -> str:
    digest = hashlib.sha256()
    for row in rows:
        payload = [_canonical_value(row.get(column)) for column in columns]
        digest.update(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _checksum_values(values: Sequence[Any]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(
            json.dumps(_canonical_value(value), separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "float:nan"
        if math.isinf(value):
            return "float:+inf" if value > 0 else "float:-inf"
        return f"float:{value.hex()}"
    if isinstance(value, Decimal):
        return f"decimal:{value}"
    if isinstance(value, (date, datetime)):
        return f"datetime:{value.isoformat()}"
    if isinstance(value, UUID):
        return f"uuid:{value}"
    return f"{type(value).__name__}:{value}"


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def _decimal_sum(values: Sequence[Any] | Any) -> str:
    total = sum((_decimal(value) for value in values), Decimal(0))
    return str(total.normalize()) if total else "0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assign all legacy unowned journal rows to one administrator."
    )
    parser.add_argument(
        "--admin-email",
        required=True,
        help="Exact verified active administrator email",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Commit the validated ownership assignment",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and roll back (the default)",
    )
    return parser


def _safe_result_payload(result: JournalClaimResult) -> dict[str, Any]:
    return {
        "mode": "dry-run" if result.dry_run else "execute",
        "assigned_trade_count": result.assigned_trade_count,
        "before": asdict(result.before),
        "after": asdict(result.after),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = not args.execute
    try:
        result = asyncio.run(
            run_claim(admin_email=args.admin_email, dry_run=dry_run)
        )
    except (JournalClaimError, ValueError) as exc:
        print(f"Journal claim failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(_safe_result_payload(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "JournalClaimError",
    "JournalClaimResult",
    "JournalValidationReport",
    "build_parser",
    "capture_journal_validation",
    "claim_legacy_journal",
    "compare_preserved_reports",
    "lock_journal_tables",
    "run_claim",
    "validate_admin_target",
    "validate_report_integrity",
]
