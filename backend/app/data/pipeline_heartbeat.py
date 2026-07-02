"""Pipeline heartbeat helper — records the state of the last run of each
scheduler cycle (price, fast_metrics, slow_metrics, realtime_discovery,
post_close_cycle) so the operator UI can show always-on freshness.

`last_success_at` is only updated when status == "ok" — partial/failed
runs preserve the previous successful run so "minutes since last good
data" stays meaningful.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import PipelineHeartbeat

logger = logging.getLogger(__name__)

CycleStatus = Literal["ok", "partial", "failed"]


async def record_cycle(
    db: AsyncSession,
    cycle_name: str,
    *,
    duration_seconds: float,
    symbols_processed: Optional[int] = None,
    symbols_expected: Optional[int] = None,
    status: CycleStatus = "ok",
    error_message: Optional[str] = None,
) -> None:
    """Upsert a heartbeat row. Failure to persist is logged, never raised."""
    # Timezone-aware UTC: asyncpg binds a naive datetime to TIMESTAMPTZ using the
    # machine's local zone, shifting every stored timestamp by the local offset.
    # An aware datetime is stored as true UTC regardless of the OS zone.
    now = datetime.now(timezone.utc)
    try:
        stmt = pg_insert(PipelineHeartbeat).values(
            cycle_name=cycle_name,
            last_run_at=now,
            last_success_at=now if status == "ok" else None,
            last_duration_seconds=duration_seconds,
            symbols_processed=symbols_processed,
            symbols_expected=symbols_expected,
            status=status,
            last_error_message=(error_message or None),
            updated_at=now,
        )
        update_set = {
            "last_run_at": stmt.excluded.last_run_at,
            "last_duration_seconds": stmt.excluded.last_duration_seconds,
            "symbols_processed": stmt.excluded.symbols_processed,
            "symbols_expected": stmt.excluded.symbols_expected,
            "status": stmt.excluded.status,
            "last_error_message": stmt.excluded.last_error_message,
            "updated_at": stmt.excluded.updated_at,
        }
        if status == "ok":
            update_set["last_success_at"] = stmt.excluded.last_success_at
        stmt = stmt.on_conflict_do_update(
            index_elements=["cycle_name"],
            set_=update_set,
        )
        await db.execute(stmt)
        await db.commit()
    except Exception as exc:
        logger.warning(
            "pipeline_heartbeat.record_cycle failed for %s: %s",
            cycle_name,
            exc,
        )
        try:
            await db.rollback()
        except Exception:
            pass
