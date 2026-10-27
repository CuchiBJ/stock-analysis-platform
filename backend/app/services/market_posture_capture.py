"""Capture only a fresh, current-session decision after committed pipeline work."""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.market_context_engine import MarketContextEngine
from app.services.market_posture_record_service import (
    KNOWN_STATES,
    market_posture_record_service,
    serialize_posture,
)


class PostureCaptureError(ValueError):
    """An observation cannot be supported by the current pipeline evidence."""


async def capture_current_posture(
    db: AsyncSession, target: date, *, current_session: Callable[[], date]
) -> None:
    ctx = await MarketContextEngine(db).analyze(use_cache=False)
    if ctx is None or ctx.as_of != target or isinstance(ctx.as_of, datetime):
        raise PostureCaptureError("context does not match the target session")
    if not ctx.universe_size or ctx.universe_size < 0:
        raise PostureCaptureError("quality universe is empty")
    payload = serialize_posture(ctx.posture)
    if (
        payload is None
        or payload["state"] not in KNOWN_STATES
        or not isinstance(payload["instruction"], str)
        or not payload["instruction"].strip()
        or not isinstance(payload["reasons"], list)
        or not all(isinstance(reason, str) for reason in payload["reasons"])
        or (payload["unlock"] is not None and not isinstance(payload["unlock"], str))
        or not isinstance(payload["policy"], dict)
    ):
        raise PostureCaptureError("current posture payload is incomplete or invalid")
    # Calculation may be slow enough to cross New York midnight. Do not turn a
    # finished yesterday-cycle into either a backfill or a next-day observation.
    if current_session() != target:
        raise PostureCaptureError("target session ended before posture capture")
    if not await market_posture_record_service.observe(db, target, payload):
        raise PostureCaptureError("posture observation could not be persisted")
