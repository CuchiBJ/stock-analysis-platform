"""Awaited post-close coordination, independent of visits and retryable in-session."""
from __future__ import annotations

import logging
import time as monotonic_time
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from app.services.market_posture_capture import PostureCaptureError, capture_current_posture

logger = logging.getLogger(__name__)
NEW_YORK = ZoneInfo("America/New_York")
RETRY_SECONDS = 300


@dataclass(frozen=True)
class SlowMetricsRun:
    covered: int = 0
    attempted: int = 0
    snapshot_date: date | None = None
    skipped: bool = False


@dataclass(frozen=True)
class PostCloseResult:
    target: date
    success: bool
    error: str | None = None


class PostCloseCycle:
    def __init__(self, clock: Callable[[], datetime] | None = None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.completed_date: date | None = None
        self.last_finished_at: datetime | None = None
        self.running = False

    def _now(self) -> datetime:
        return self.clock().astimezone(NEW_YORK)

    async def run_if_due(self, scheduler) -> PostCloseResult | None:
        now = self._now()
        target = now.date()
        if (
            self.running
            or now.weekday() >= 5
            or now.time() < time(16, 10)
            or self.completed_date == target
            or (
                self.last_finished_at is not None
                and now - self.last_finished_at < timedelta(seconds=RETRY_SECONDS)
            )
        ):
            return None
        self.running = True
        started = monotonic_time.monotonic()
        result = SlowMetricsRun()
        error = None
        try:
            await scheduler._update_prices_polygon_eod(target)
            result = await scheduler._trigger_metrics_run(refresh=True)
            if result.skipped:
                raise PostureCaptureError("SLOW metrics skipped because another run is active")
            if result.attempted <= 0 or result.covered <= 0:
                raise PostureCaptureError("SLOW metrics covered no symbols")
            if result.covered < result.attempted * 0.95:
                raise PostureCaptureError("SLOW metrics coverage is below 95%")
            if result.snapshot_date != target:
                raise PostureCaptureError("SLOW metrics snapshot does not match the target session")
            async with scheduler._get_db() as db:
                await capture_current_posture(
                    db, target, current_session=lambda: self._now().date()
                )
            self.completed_date = target
        except Exception as exc:
            error = str(exc) if isinstance(exc, PostureCaptureError) else type(exc).__name__
            logger.warning("Post-close cycle for %s failed: %s", target, error)
        finally:
            self.last_finished_at = self._now()
            self.running = False
        await scheduler._record_heartbeat(
            "post_close_cycle",
            duration_seconds=monotonic_time.monotonic() - started,
            symbols_processed=result.covered,
            symbols_expected=result.attempted,
            status="ok" if error is None else "failed",
            error_message=error,
        )
        return PostCloseResult(target=target, success=error is None, error=error)
