# Pin the process timezone to UTC before anything else. asyncpg binds a naive
# datetime to a TIMESTAMPTZ column using the OS-local zone, so on a non-UTC host
# every naive datetime.utcnow() write is shifted by the local offset. Forcing the
# process zone to UTC makes "naive == UTC" true, matching how the codebase uses
# utcnow() everywhere.
import os as _os_boot, time as _time_boot
_os_boot.environ["TZ"] = "UTC"
_time_boot.tzset()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.data.ingestors.stock_ingestor import StockIngestor
from app.data.ingestors.price_ingestor import PriceIngestor
from app.data.ingestors.metrics_calculator import MetricsCalculator
from app.core.config import settings
from app.universe.universe_engine import UniverseEngine
from app.universe.tiers.tier_manager import UniverseTier
from app.services.websocket_manager import websocket_manager
from app.services.task_error_tracker import track_task_errors
from app.data.pipeline_heartbeat import record_cycle
from sqlalchemy import func
from datetime import datetime, time, timedelta
import pytz
import logging
import asyncio
import time as _time   # alias to avoid colliding with datetime.time
import uuid
import pandas as pd
import yfinance as yf
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# A cadence marker dated more than this far in the future can only be the result
# of a backward system-clock correction (the marker was stamped while the clock
# was ahead). Anything inside this band is normal jitter and left alone.
_CLOCK_SKEW_TOLERANCE_S = 120


class DataScheduler:
    def __init__(self, database_url=None):
        if database_url:
            # Pool sized for parallel SLOW metrics calc (concurrency 15 + headroom
            # for outcome_tracker / batch_scanner / discovery running in parallel).
            self.engine = create_async_engine(
                database_url, echo=False, pool_size=20, max_overflow=10,
            )
            self.async_session_maker = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
        else:
            self.engine = None
            self.async_session_maker = None
        self._running = False
        self._slow_running = False
        # Symbols the most recent SLOW run attempted (its single snapshot). Read by
        # the heartbeat so processed/expected come from the same set. See
        # trigger_metrics_update.
        self._slow_last_attempted = 0

        # Initialize UniverseEngine for discovery and health monitoring
        self.universe_engine = UniverseEngine(polygon_api_key=settings.polygon_api_key)

    def _get_db(self):
        """Get database session"""
        if self.async_session_maker:
            return self.async_session_maker()
        raise RuntimeError("Database not initialized")

    async def _record_heartbeat(
        self,
        cycle_name: str,
        *,
        duration_seconds: float,
        symbols_processed: Optional[int] = None,
        symbols_expected: Optional[int] = None,
        status: str = "ok",
        error_message: Optional[str] = None,
    ) -> None:
        """Persist last-run state of a scheduler cycle. Never raises."""
        try:
            async with self._get_db() as db:
                await record_cycle(
                    db, cycle_name,
                    duration_seconds=duration_seconds,
                    symbols_processed=symbols_processed,
                    symbols_expected=symbols_expected,
                    status=status,  # type: ignore[arg-type]
                    error_message=error_message,
                )
        except Exception as e:
            logger.warning(f"heartbeat write failed for {cycle_name}: {e}")

    async def _get_slow_symbols_and_date(self, db) -> tuple:
        """All symbols with a stock_price for the latest available date + that date."""
        from sqlalchemy import select, func
        from app.models.stock import StockPrice
        today = (await db.execute(select(func.max(StockPrice.date)))).scalar()
        if not today:
            return [], None
        result = await db.execute(
            select(StockPrice.symbol).where(StockPrice.date == today).distinct()
        )
        symbols = [r[0] for r in result.fetchall()]
        logger.info(f"SLOW cycle: {len(symbols)} symbols with price for {today}")
        return symbols, today

    async def trigger_metrics_update(self, limit=None, symbols=None):
        """SLOW metrics calculation — covers all symbols with today's price.

        Args:
            limit: optional cap on number of symbols (backward compat for manual endpoint).
            symbols: explicit list to process (skips dynamic discovery).
        """
        from sqlalchemy import select
        from app.models.stock import StockMetrics as StockMetricsModel

        if self._slow_running:
            logger.info("SLOW cycle still running — skipping")
            return 0
        self._slow_running = True
        count = 0
        self._slow_last_attempted = 0
        try:
            snapshot_date = None
            if symbols is None:
                async with self._get_db() as db:
                    symbols, snapshot_date = await self._get_slow_symbols_and_date(db)
            if not symbols:
                return 0
            if limit:
                symbols = symbols[:limit]

            # Write-protection window: skip only when a row was touched recently
            # (avoids clobbering fresh FAST writes for TIER 1 symbols, but lets SLOW
            # refresh the rest of the universe every cycle).
            fresh_cutoff = datetime.utcnow() - timedelta(minutes=5)

            t0 = _time.monotonic()
            logger.info(f"Calculating SLOW metrics for {len(symbols)} symbols (parallel, concurrency=15)...")

            semaphore = asyncio.Semaphore(15)

            async def _process_one(sym: str) -> str:
                """Process one symbol with its own session.

                Returns 'written' if metrics were recalculated, 'skipped' if the row
                was already fresh (write-protection window — still covered, just not
                rewritten), or 'failed' on error.
                """
                async with semaphore:
                    try:
                        async with self._get_db() as db:
                            if snapshot_date:
                                existing = await db.execute(
                                    select(StockMetricsModel.updated_at)
                                    .where(
                                        StockMetricsModel.symbol == sym,
                                        StockMetricsModel.date >= snapshot_date,
                                        StockMetricsModel.updated_at >= fresh_cutoff,
                                    )
                                    .limit(1)
                                )
                                if existing.scalar():
                                    return 'skipped'
                            calculator = MetricsCalculator(db)
                            await calculator.calculate_metrics_for_symbol(sym)
                            await db.commit()
                            return 'written'
                    except Exception:
                        return 'failed'

            results = await asyncio.gather(*(_process_one(sym) for sym in symbols), return_exceptions=True)
            written = sum(1 for r in results if r == 'written')
            skipped = sum(1 for r in results if r == 'skipped')
            # "Covered" = up-to-date after this cycle, whether we rewrote it or found it
            # already fresh. Only genuine failures don't count. This is what the heartbeat
            # reports so a healthy cycle isn't flagged partial just for skipping fresh rows.
            covered = written + skipped
            # Expose the attempted workload (this run's single snapshot) so the caller
            # records processed/expected from the SAME set — no second max(date) query.
            self._slow_last_attempted = len(symbols)
            count = covered
            duration = round(_time.monotonic() - t0, 2)
            logger.info(
                f"SLOW metrics: {covered}/{len(symbols)} covered "
                f"({written} written, {skipped} fresh-skip, {len(symbols) - covered} failed) "
                f"in {duration}s ({covered/duration:.0f}/s)"
            )
            asyncio.create_task(self._broadcast_metrics_updated(written, tier='all'))
            # Evaluate pending outcomes after each successful SLOW cycle
            asyncio.create_task(self._evaluate_pending_outcomes())
            # Batch-detect transitions over the quality universe (populates calibration data)
            asyncio.create_task(self._batch_scan_transitions())
        finally:
            self._slow_running = False
        return count

    @track_task_errors(task_name="batch_scan_transitions")
    async def _batch_scan_transitions(self) -> None:
        try:
            from app.services.batch_transition_scanner import BatchTransitionScanner
            from datetime import date
            async with self._get_db() as session:
                scanner = BatchTransitionScanner(session)
                await scanner.scan_universe(date.today())
        except Exception as e:
            logger.error(f"Batch transition scan failed: {e}")

    @track_task_errors(task_name="evaluate_pending_outcomes")
    async def _evaluate_pending_outcomes(self) -> None:
        try:
            from app.services.outcome_tracker import OutcomeTracker
            from datetime import date
            async with self._get_db() as session:
                tracker = OutcomeTracker(session)
                await tracker.evaluate_pending_outcomes(date.today())
            logger.info("Evaluated pending outcomes")
        except Exception as e:
            logger.error(f"Outcome evaluation failed: {e}")

    @track_task_errors(task_name="broadcast_metrics_updated")
    async def _broadcast_metrics_updated(self, count: int, tier: str = 'all') -> None:
        """Broadcast metrics_updated event to all WebSocket subscribers."""
        if websocket_manager.get_connection_count() == 0:
            return
        try:
            await websocket_manager.broadcast('metrics', {
                'channel': 'metrics',
                'event': 'updated',
                'tier': tier,
                'count': count,
                'timestamp': datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.debug(f"WebSocket broadcast skipped: {e}")

    async def _get_fast_symbols(self, db) -> list:
        """TIER 1 base + institutional quality stocks (live transitions candidates)."""
        from sqlalchemy import select, and_, func
        from app.models.stock import StockMetrics
        from app.models.universe import UniverseTier as UniverseTierModel

        latest_date = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
        if not latest_date:
            return []

        # TIER 1: resolve instrument_ids to symbols via stock_metrics
        tier1_result = await db.execute(
            select(StockMetrics.symbol)
            .where(StockMetrics.date == latest_date)
            .where(
                StockMetrics.symbol.in_(
                    select(UniverseTierModel.instrument_id)
                    .where(UniverseTierModel.tier == "tier_1")
                )
            )
            .limit(200)
        )
        tier1_symbols = {r[0] for r in tier1_result.fetchall()}

        # Institutional quality stocks — slightly relaxed vs live feed to capture
        # stocks approaching qualification
        inst_result = await db.execute(
            select(StockMetrics.symbol)
            .where(and_(
                StockMetrics.date == latest_date,
                StockMetrics.avg_volume_10d >= 800_000,
                StockMetrics.adr_percent >= 3.0,
                StockMetrics.current_price >= 5.0,
                StockMetrics.perf_1y > 25,
                StockMetrics.current_price > StockMetrics.ema50,
                StockMetrics.current_price > StockMetrics.sma150,
                StockMetrics.sma150 > StockMetrics.sma200,
            ))
            .limit(200)
        )
        inst_symbols = {r[0] for r in inst_result.fetchall()}

        combined = list(tier1_symbols | inst_symbols)
        logger.info(
            f"FAST cycle: {len(tier1_symbols)} TIER 1 + "
            f"{len(inst_symbols - tier1_symbols)} institutional = {len(combined)} unique symbols"
        )
        return combined

    async def _get_quality_symbols(self, db) -> list:
        """Symbols in the quality universe on the last complete metrics session.

        This is the exact set the coverage metric measures (QUALITY_FILTERS on the
        most recent COMPLETE session, i.e. strictly before today's still-filling
        date). We resolve it here so the priority refresh targets precisely the
        names that define coverage.
        """
        from sqlalchemy import select, func
        from app.models.stock import StockMetrics, StockPrice
        from app.services.universe_filters import QUALITY_FILTERS

        price_latest = (await db.execute(select(func.max(StockPrice.date)))).scalar()
        if not price_latest:
            return []
        ref_date = (
            await db.execute(
                select(func.max(StockMetrics.date)).where(StockMetrics.date < price_latest)
            )
        ).scalar()
        if not ref_date:
            return []
        result = await db.execute(
            select(StockMetrics.symbol)
            .where(StockMetrics.date == ref_date, *QUALITY_FILTERS)
            .distinct()
        )
        return [r[0] for r in result.fetchall()]

    async def trigger_quality_refresh(self) -> int:
        """Priority price + metrics refresh for the quality universe.

        Why this exists: the intraday yfinance bulk pulls all ~7k symbols and gets
        rate-limited partway (observed ~2.6k/7k updated), so a random slice of the
        quality universe misses today's bar every cycle — which is exactly what
        drags the coverage metric down (a real staleness, not a denominator quirk).
        Polygon's grouped-daily fast path can't help intraday on the free tier (it
        403s for the current day before close).

        The quality set is only a few hundred names — small enough to clear the
        yfinance rate limit reliably. Pulling their prices FIRST (before the big
        bulk spends the rate-limit budget) and recomputing their metrics makes
        coverage reflect real freshness within one 5-min cycle instead of waiting
        on the 30-min SLOW pass and yfinance luck.

        Returns the count of quality symbols whose metrics were recomputed.
        """
        async with self._get_db() as db:
            symbols = await self._get_quality_symbols(db)
        if not symbols:
            logger.info("Quality refresh: no quality symbols resolved yet — skipping")
            return 0

        logger.info(f"Quality refresh: priority price pull for {len(symbols)} quality symbols")
        # Reuse the batched/retrying sync downloader — with a few hundred symbols it
        # stays well under the rate limit that throttles the full-universe bulk.
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._bulk_download_prices_sync, symbols
            )
        except Exception as e:
            logger.error(f"Quality refresh price pull failed (continuing to metrics): {e}")

        # Recompute metrics for the quality set (FAST only covers TIER1+momentum, so
        # non-trending quality names would otherwise wait for the 30-min SLOW pass).
        semaphore = asyncio.Semaphore(15)

        async def _one(sym: str) -> bool:
            async with semaphore:
                try:
                    async with self._get_db() as db:
                        calculator = MetricsCalculator(db)
                        # Default lookback (260d) — the calculator needs ≥50 rows to
                        # compute EMA50 etc.; a short window silently no-ops.
                        await calculator.calculate_metrics_for_symbol(sym)
                        await db.commit()
                        return True
                except Exception:
                    return False

        results = await asyncio.gather(*(_one(s) for s in symbols), return_exceptions=True)
        refreshed = sum(1 for r in results if r is True)
        logger.info(f"Quality refresh: recomputed metrics for {refreshed}/{len(symbols)} quality symbols")
        asyncio.create_task(self._broadcast_metrics_updated(refreshed, tier='quality'))
        return refreshed

    async def trigger_fast_metrics_update(self):
        """Trigger FAST metrics update for TIER 1 + institutional quality stocks."""
        try:
            async with self._get_db() as db:
                symbols = (await self._get_fast_symbols(db))[:300]
            if not symbols:
                logger.warning("FAST cycle: no symbols to update")
                return 0

            # Compute in parallel with its own session per symbol. Uses the default
            # lookback (260d): the calculator needs ≥50 rows (and 252 for the 52w
            # window), so the previous days=10 silently no-op'd every symbol.
            semaphore = asyncio.Semaphore(15)

            async def _one(sym: str) -> bool:
                async with semaphore:
                    try:
                        async with self._get_db() as db:
                            calculator = MetricsCalculator(db)
                            await calculator.calculate_metrics_for_symbol(sym)
                            await db.commit()
                            return True
                    except Exception:
                        return False

            results = await asyncio.gather(*(_one(s) for s in symbols), return_exceptions=True)
            updated_symbols = [s for s, r in zip(symbols, results) if r is True]
            count = len(updated_symbols)
            logger.info(f"FAST metrics updated for {count}/{len(symbols)} symbols")

            asyncio.create_task(self._track_state_changes(updated_symbols))
            asyncio.create_task(self._broadcast_metrics_updated(count, tier='tier_1'))
            return count
        except Exception as e:
            logger.error(f"FAST metrics update failed: {e}")
            import traceback
            traceback.print_exc()
            return 0

    async def _track_state_changes(self, symbols: list) -> None:
        """Detect setup state changes for the given symbols and log them."""
        if not symbols:
            return
        try:
            from sqlalchemy import select, and_, text
            from app.models.stock import StockMetrics, SetupStateLog
            from app.services.setup_lifecycle_engine import SetupLifecycleEngine
            from datetime import timezone

            async with self._get_db() as db:
                lifecycle = SetupLifecycleEngine(db)

                # Latest metrics for each symbol
                subq = (
                    select(StockMetrics.symbol, func.max(StockMetrics.date).label('max_date'))
                    .where(StockMetrics.symbol.in_(symbols))
                    .group_by(StockMetrics.symbol)
                    .subquery()
                )
                result = await db.execute(
                    select(StockMetrics).join(
                        subq,
                        and_(StockMetrics.symbol == subq.c.symbol,
                             StockMetrics.date == subq.c.max_date)
                    )
                )
                metrics_list = result.scalars().all()

                # Latest logged state for each symbol
                log_result = await db.execute(text("""
                    SELECT DISTINCT ON (symbol) symbol, state
                    FROM setup_state_log
                    WHERE symbol = ANY(:symbols) AND exited_at IS NULL
                    ORDER BY symbol, entered_at DESC
                """), {"symbols": symbols})
                last_states = {row[0]: row[1] for row in log_result.fetchall()}

                now = datetime.now(timezone.utc)
                changes = 0

                for m in metrics_list:
                    current_state = lifecycle.detect_current_state(m).value
                    last_state = last_states.get(m.symbol)

                    if current_state == last_state:
                        continue

                    # Close the previous open log entry
                    if last_state:
                        await db.execute(text("""
                            UPDATE setup_state_log
                            SET exited_at = :now, updated_at = :now
                            WHERE symbol = :symbol AND exited_at IS NULL
                        """), {"now": now, "symbol": m.symbol})

                    # Open new entry
                    db.add(SetupStateLog(
                        symbol=m.symbol,
                        state=current_state,
                        entered_at=now,
                    ))
                    changes += 1

                if changes:
                    await db.commit()
                    logger.info(f"State changes logged: {changes} symbols transitioned")
        except Exception as e:
            logger.error(f"State tracking failed: {e}")

    @staticmethod
    def _future_dated_markers(
        markers: Dict[str, Optional[datetime]],
        now: datetime,
        tolerance_s: int = _CLOCK_SKEW_TOLERANCE_S,
    ) -> list:
        """Return the names of cadence markers stamped further than tolerance in
        the future relative to `now` — the signature of a backward clock
        correction that would otherwise freeze the loop's interval checks.
        """
        cutoff = now + timedelta(seconds=tolerance_s)
        return [name for name, ts in markers.items() if ts is not None and ts > cutoff]

    async def _scheduler_loop(self):
        """Background scheduler loop that executes jobs based on time"""
        logger.info("Scheduler loop started")
        et_tz = pytz.timezone('US/Eastern')
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        last_price_update = None
        last_metrics_update = None
        last_fast_metrics_update = None
        last_quality_refresh = None
        last_realtime_discovery = None
        last_discovery_scan = None
        last_tier_reevaluation = None
        last_health_check = None
        last_lifecycle_tracking = None
        last_post_close_cycle_date = None  # date — fires once per weekday after close
        post_close_window_start = time(16, 10)  # let yfinance settle for ~10 min
        
        # Load tiers from database
        async with self._get_db() as db:
            await self.universe_engine.tier_manager.load_tiers_from_database(db)
            logger.info("Loaded tier assignments from database")

        # Startup: fetch fresh prices first, then kick off SLOW in background
        # so the loop can start FAST cycles within ~3 min instead of waiting 30+
        logger.info("Startup: fetching fresh prices first")
        try:
            await self._update_prices()
        except Exception as e:
            logger.error(f"Startup price update failed: {e}")
        last_price_update = datetime.now(et_tz)  # prevents double download on first tick

        logger.info("Startup: initial SLOW metrics calculation (background)")
        asyncio.create_task(self.trigger_metrics_update())
        last_metrics_update = datetime.now(et_tz)

        logger.info("Startup: initial quality-universe refresh (background)")
        asyncio.create_task(self.trigger_quality_refresh())
        last_quality_refresh = datetime.now(et_tz)
        
        while self._running:
            now = datetime.now(et_tz)
            current_time = now.time()

            # Clock-skew self-recovery. If the system clock jumps forward (NTP
            # correction, sleep/wake) the cadence markers get stamped in the
            # future; once the clock settles back, (now - last_X) goes negative,
            # the >= interval checks never fire again, and every cycle silently
            # freezes until real time catches up to the stale markers (observed:
            # a ~3h freeze). Detect any future-dated marker and reset the cadence
            # so the loop re-establishes cycles from the corrected clock at once.
            _future = self._future_dated_markers(
                {
                    "price": last_price_update,
                    "fast_metrics": last_fast_metrics_update,
                    "slow_metrics": last_metrics_update,
                    "quality_refresh": last_quality_refresh,
                    "realtime_discovery": last_realtime_discovery,
                },
                now,
            )
            if _future:
                logger.warning(
                    f"Clock anomaly: cadence markers {_future} dated in the future "
                    f"(now={now.isoformat()}). Resetting cadence to self-recover."
                )
                await self._record_heartbeat(
                    "clock_recovery",
                    duration_seconds=0.0,
                    status="failed",
                    error_message=f"future-dated markers reset: {_future}",
                )
                last_price_update = None
                last_fast_metrics_update = None
                last_metrics_update = None
                last_quality_refresh = None
                last_realtime_discovery = None

            # Check if within market hours
            if market_open <= current_time <= market_close:
                # Quality-universe refresh every 5 minutes. Runs BEFORE the big bulk
                # so the quality set claims the yfinance rate-limit budget first —
                # this is what keeps coverage tracking real freshness instead of
                # yfinance luck. Small enough (few hundred names) to always complete.
                if last_quality_refresh is None or (now - last_quality_refresh).total_seconds() >= 300:
                    logger.info(f"Triggering quality-universe refresh (current time: {current_time})")
                    q_t0 = _time.monotonic()
                    q_count = await self.trigger_quality_refresh()
                    await self._record_heartbeat(
                        "quality_refresh",
                        duration_seconds=_time.monotonic() - q_t0,
                        symbols_processed=q_count or None,
                        status="ok" if q_count else "failed",
                    )
                    last_quality_refresh = datetime.now(et_tz)

                # Price update every 15 minutes — awaited so FAST always uses fresh prices.
                # NB: last_price_update is set AFTER the awaits complete (fresh datetime.now)
                # so a slow yfinance pull doesn't cause the next iteration to re-trigger before
                # FAST/SLOW/Realtime get a chance to run.
                if last_price_update is None or (now - last_price_update).total_seconds() >= 900:
                    logger.info(f"Triggering price update (current time: {current_time})")
                    price_t0 = _time.monotonic()
                    price_status = "ok"
                    price_error = None
                    try:
                        await self._update_prices()
                    except Exception as e:
                        logger.error(f"Price update failed (continuing): {e}")
                        price_status = "failed"
                        price_error = str(e)
                    await self._record_heartbeat(
                        "price",
                        duration_seconds=_time.monotonic() - price_t0,
                        status=price_status,
                        error_message=price_error,
                    )
                    # Immediately chain FAST metrics with fresh prices
                    logger.info("Chaining FAST metrics after price update")
                    fast_t0 = _time.monotonic()
                    fast_count = await self.trigger_fast_metrics_update()
                    await self._record_heartbeat(
                        "fast_metrics",
                        duration_seconds=_time.monotonic() - fast_t0,
                        symbols_processed=fast_count or None,
                        status="ok" if fast_count else "failed",
                    )
                    after = datetime.now(et_tz)
                    last_price_update = after
                    last_fast_metrics_update = after
                    await asyncio.sleep(30)
                    continue

                # FAST metrics every 5 minutes (between price updates)
                if last_fast_metrics_update is None or (now - last_fast_metrics_update).total_seconds() >= 300:
                    logger.info(f"Triggering FAST metrics update (current time: {current_time})")
                    fast_t0 = _time.monotonic()
                    fast_count = await self.trigger_fast_metrics_update()
                    await self._record_heartbeat(
                        "fast_metrics",
                        duration_seconds=_time.monotonic() - fast_t0,
                        symbols_processed=fast_count or None,
                        status="ok" if fast_count else "failed",
                    )
                    last_fast_metrics_update = datetime.now(et_tz)

                # SLOW metrics every 30 minutes — all symbols with price for today
                if last_metrics_update is None or (now - last_metrics_update).total_seconds() >= 1800:
                    logger.info(f"Triggering SLOW metrics update (current time: {current_time})")
                    slow_t0 = _time.monotonic()
                    slow_count = await self.trigger_metrics_update()
                    # Expected comes from the SAME snapshot the run used (set inside
                    # trigger_metrics_update), so processed/expected can't disagree due
                    # to prices loading between two separate max(date) queries.
                    slow_expected = self._slow_last_attempted
                    slow_status = "ok"
                    if slow_expected and slow_count < slow_expected * 0.95:
                        slow_status = "partial"
                    elif not slow_count:
                        slow_status = "failed"
                    await self._record_heartbeat(
                        "slow_metrics",
                        duration_seconds=_time.monotonic() - slow_t0,
                        symbols_processed=slow_count,
                        symbols_expected=slow_expected,
                        status=slow_status,
                    )
                    last_metrics_update = datetime.now(et_tz)

                # Realtime discovery every 10 minutes (detect volume explosion, RS acceleration)
                if last_realtime_discovery is None or (now - last_realtime_discovery).total_seconds() >= 600:
                    logger.info(f"Triggering realtime discovery (current time: {current_time})")
                    asyncio.create_task(self._run_realtime_discovery())
                    last_realtime_discovery = datetime.now(et_tz)
            else:
                # After market close: run nightly tasks
                logger.info(f"Outside market hours (current time: {current_time})")

                # Post-close cycle: capture closing prices into a final SLOW so metrics
                # reflect the actual close, not the last 15-min snapshot before 16:00 ET.
                # Uses Polygon Grouped Daily Bars (~3 sec for 6600+ symbols) instead of
                # yfinance bulk (5-28 min). yfinance is the fallback if Polygon fails.
                # Fires once per weekday, ~10 min after close.
                if (now.weekday() < 5
                        and current_time >= post_close_window_start
                        and last_post_close_cycle_date != now.date()):
                    logger.info(f"Post-close cycle (Polygon EOD): current time {current_time}")
                    pc_t0 = _time.monotonic()
                    pc_status = "ok"
                    pc_error = None
                    pc_count: Optional[int] = None
                    try:
                        await self._update_prices_polygon_eod(now.date())
                        pc_count = await self.trigger_metrics_update()
                        after = datetime.now(et_tz)
                        last_price_update = after
                        last_metrics_update = after
                    except Exception as e:
                        logger.error(f"Post-close cycle failed: {e}")
                        pc_status = "failed"
                        pc_error = str(e)
                    await self._record_heartbeat(
                        "post_close_cycle",
                        duration_seconds=_time.monotonic() - pc_t0,
                        symbols_processed=pc_count,
                        status=pc_status,
                        error_message=pc_error,
                    )
                    last_post_close_cycle_date = now.date()

                # Discovery scans - run once daily after market close
                if last_discovery_scan is None or (now - last_discovery_scan).total_seconds() >= 86400:
                    logger.info("Triggering nightly discovery scans")
                    await self._run_discovery_scans()
                    last_discovery_scan = now
                
                # Tier re-evaluation - run once daily after market close
                if last_tier_reevaluation is None or (now - last_tier_reevaluation).total_seconds() >= 86400:
                    logger.info("Triggering tier re-evaluation")
                    await self._reevaluate_tiers()
                    last_tier_reevaluation = now
                
                # Health monitoring - run once daily after market close
                if last_health_check is None or (now - last_health_check).total_seconds() >= 86400:
                    logger.info("Triggering health monitoring")
                    report = await self._run_health_check()
                    # Auto-fill coverage gaps if found
                    if report and len(report.coverage_gaps) > 0:
                        logger.info(f"Found coverage gaps: {report.coverage_gaps}")
                        await self._fill_coverage_gaps(report.coverage_gaps)
                    last_health_check = now
                
                # Lifecycle tracking - run once daily after market close
                if last_lifecycle_tracking is None or (now - last_lifecycle_tracking).total_seconds() >= 86400:
                    logger.info("Triggering lifecycle tracking")
                    await self._run_lifecycle_tracking()
                    last_lifecycle_tracking = now

            # Sleep for 30 seconds before checking again
            await asyncio.sleep(30)

    async def _update_prices_polygon_eod(self, target_date) -> None:
        """Update closing prices via Polygon Grouped Daily Bars.

        ~3 seconds for 6600+ symbols (vs 5-28 min for yfinance bulk).
        Polygon free tier supports this endpoint (1 API call total).
        Falls back to yfinance bulk on Polygon failure.
        """
        try:
            from app.data.ingestors.polygon_eod_ingestor import PolygonEODIngestor
            async with self._get_db() as db:
                ingestor = PolygonEODIngestor(db)
                stats = await ingestor.ingest_eod(target_date)
            if stats["written"] == 0:
                logger.warning(
                    f"Polygon EOD returned 0 rows for {target_date} — falling back to yfinance"
                )
                await self._update_prices()
                return
            logger.info(
                f"Polygon EOD: wrote {stats['written']} prices for {target_date} "
                f"in {stats['duration_sec']}s (Polygon-fetched {stats['fetched']}, "
                f"{stats['fetched'] - stats['in_universe']} outside universe)"
            )
        except Exception as e:
            logger.error(f"Polygon EOD ingestion failed: {e} — falling back to yfinance")
            await self._update_prices()

    async def _update_prices(self):
        """Update prices for all active stocks using yfinance bulk download.

        Downloads the last 5 days in batches of 200 tickers (~3-5 min for 7k stocks).
        Runs in a thread pool to avoid blocking the event loop.
        """
        try:
            async with self._get_db() as db:
                ingestor = StockIngestor(db)
                symbols = await ingestor.get_active_symbols(limit=None)

            logger.info(f"Starting yfinance price update for {len(symbols)} symbols")
            count = await asyncio.get_event_loop().run_in_executor(
                None, self._bulk_download_prices_sync, symbols
            )
            logger.info(f"Price update complete: {count} symbols updated")
        except Exception as e:
            logger.error(f"Price update failed: {e}")

    def _bulk_download_prices_sync(self, symbols: list) -> int:
        """yfinance bulk download with parallel batches + per-batch retry.

        Architecture:
          - Filter non-downloadable suffixes upfront
          - Split into chunks of 100 (vs the old 200 — smaller blast radius)
          - 5 parallel ThreadPoolExecutor workers issuing yf.download concurrently
          - Per-batch timeout (45s) so a hung batch doesn't block forever
          - Failed batches retry ONCE with half-size chunks
          - Each batch commits its own session (no global lock)

        Measured intent:
          - Normal day: ~5min serial → ~1-2 min parallel
          - Bad day (yfinance flaky): ~28 min → ~5-8 min, partial coverage
            instead of total failure
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.stock import StockPrice

        sync_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
        engine = create_engine(sync_url, pool_size=10, echo=False)
        Session = sessionmaker(engine)

        # Filter symbols Yahoo Finance can't serve (warrants/units/rights, $ prefixes)
        _SKIP_SUFFIXES = frozenset({'W', 'U', 'R'})
        excluded = [s for s in symbols if s.startswith('$') or (len(s) == 5 and s[-1] in _SKIP_SUFFIXES)]
        if excluded:
            logger.info(f"Price download: excluding {len(excluded)} non-downloadable symbols (warrants/units/rights)")
        symbols = [s for s in symbols if not (s.startswith('$') or (len(s) == 5 and s[-1] in _SKIP_SUFFIXES))]

        BATCH = 100
        WORKERS = 5
        BATCH_TIMEOUT_SEC = 45

        def _process_batch(batch: list) -> int:
            """Download + persist one batch. Returns ok count."""
            try:
                data = yf.download(
                    batch, period="5d", auto_adjust=True,
                    progress=False, threads=False,
                )
                if data is None or data.empty:
                    return 0

                multi = isinstance(data.columns, pd.MultiIndex)
                ok = 0
                with Session() as session:
                    for symbol in batch:
                        try:
                            if multi:
                                if symbol not in data.columns.get_level_values(1):
                                    continue
                                hist = data.xs(symbol, axis=1, level=1)
                            else:
                                hist = data
                            hist = hist.dropna(subset=["Close"])
                            if hist.empty:
                                continue
                            for date, row in hist.iterrows():
                                date_val = date.date() if hasattr(date, 'date') else date
                                existing = session.query(StockPrice).filter_by(
                                    symbol=symbol, date=date_val
                                ).first()
                                if existing:
                                    existing.open   = float(row["Open"])   if pd.notna(row["Open"])   else existing.open
                                    existing.high   = float(row["High"])   if pd.notna(row["High"])   else existing.high
                                    existing.low    = float(row["Low"])    if pd.notna(row["Low"])    else existing.low
                                    existing.close  = float(row["Close"])  if pd.notna(row["Close"])  else existing.close
                                    existing.volume = int(row["Volume"])   if pd.notna(row["Volume"]) else existing.volume
                                else:
                                    session.add(StockPrice(
                                        symbol=symbol,
                                        date=date_val,
                                        open=float(row["Open"])   if pd.notna(row["Open"])   else None,
                                        high=float(row["High"])   if pd.notna(row["High"])   else None,
                                        low=float(row["Low"])     if pd.notna(row["Low"])    else None,
                                        close=float(row["Close"]) if pd.notna(row["Close"])  else None,
                                        volume=int(row["Volume"]) if pd.notna(row["Volume"]) else None,
                                    ))
                            ok += 1
                        except Exception:
                            continue
                    session.commit()
                return ok
            except Exception as e:
                logger.warning(f"yfinance batch failed ({len(batch)} symbols): {e}")
                return -1  # marker for retry

        batches = [symbols[i:i + BATCH] for i in range(0, len(symbols), BATCH)]
        logger.info(
            f"yfinance bulk download: {len(symbols)} symbols in {len(batches)} batches "
            f"({WORKERS} parallel workers, timeout {BATCH_TIMEOUT_SEC}s/batch)"
        )

        ok = 0
        failed_batches: list[list] = []
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {executor.submit(_process_batch, b): b for b in batches}
            for f in as_completed(futures):
                batch = futures[f]
                try:
                    result = f.result(timeout=BATCH_TIMEOUT_SEC)
                    if result < 0:
                        failed_batches.append(batch)
                    else:
                        ok += result
                except FuturesTimeout:
                    logger.warning(f"yfinance batch timed out ({len(batch)} symbols) — queued for retry")
                    failed_batches.append(batch)
                except Exception as e:
                    logger.warning(f"yfinance batch raised {type(e).__name__}: {e} — queued for retry")
                    failed_batches.append(batch)

        # Retry failed batches at half size, same parallelism
        if failed_batches:
            retry_chunks = []
            for batch in failed_batches:
                half = max(1, len(batch) // 2)
                for i in range(0, len(batch), half):
                    retry_chunks.append(batch[i:i + half])
            logger.info(f"Retrying {len(failed_batches)} failed batches as {len(retry_chunks)} half-size chunks")
            with ThreadPoolExecutor(max_workers=WORKERS) as executor:
                futures = {executor.submit(_process_batch, b): b for b in retry_chunks}
                for f in as_completed(futures):
                    batch = futures[f]
                    try:
                        result = f.result(timeout=BATCH_TIMEOUT_SEC)
                        if result > 0:
                            ok += result
                    except Exception:
                        # final failure: log and move on (partial coverage > total failure)
                        logger.warning(f"Retry batch failed permanently ({len(batch)} symbols)")

        engine.dispose()
        return ok

    @track_task_errors(task_name="run_discovery_scans")
    async def _run_discovery_scans(self):
        """Run nightly discovery scans to detect new leaders"""
        try:
            async with self._get_db() as db:
                # Fetch ticker data for scanning
                from sqlalchemy import select
                from app.models.stock import StockMetrics
                from app.models.universe import InstrumentIdentity
                
                # Get active symbols with recent metrics
                et_tz = pytz.timezone('US/Eastern')
                cutoff_date = datetime.now(et_tz) - timedelta(days=30)
                query = (
                    select(StockMetrics.symbol, StockMetrics)
                    .where(StockMetrics.date >= cutoff_date)
                    .order_by(StockMetrics.symbol.asc(), StockMetrics.date.desc())
                    .distinct(StockMetrics.symbol)
                    .limit(5000)
                )
                
                result = await db.execute(query)
                metrics_records = result.fetchall()
                
                # Build ticker data for discovery scanner
                ticker_data = []
                for symbol, metrics in metrics_records:
                    ticker_data.append({
                        "symbol": symbol,
                        "rs_spy": metrics.relative_strength_spy if hasattr(metrics, 'rs_spy') else None,
                        "rs_qqq": metrics.rs_qqq if hasattr(metrics, 'rs_qqq') else None,
                        "volume": metrics.avg_volume_10d if hasattr(metrics, 'avg_volume_10d') else None,
                        "avg_volume_20d": metrics.avg_volume_20d if hasattr(metrics, 'avg_volume_20d') else None,
                        "close": metrics.current_price if hasattr(metrics, 'current_price') else None,
                        "sector": metrics.sector if hasattr(metrics, 'sector') else None,
                        "atr": metrics.atr if hasattr(metrics, 'atr') else None,
                        "weekly_tightness": metrics.weekly_tightness if hasattr(metrics, 'weekly_tightness') else None,
                        "volume_contraction": metrics.volume_contraction if hasattr(metrics, 'volume_contraction') else None
                    })
                
                logger.info(f"Fetched ticker data for {len(ticker_data)} symbols for discovery scans")
                
                # Run discovery scans
                results = await self.universe_engine.run_nightly_scans(db)
                logger.info(f"Discovery scans complete: {len(results)} scan results")
                
                return results
        except Exception as e:
            logger.error(f"Discovery scans failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    @track_task_errors(task_name="reevaluate_tiers")
    async def _reevaluate_tiers(self):
        """Reevaluate tiers for all active symbols"""
        try:
            async with self._get_db() as db:
                from sqlalchemy import select
                from app.models.stock import StockMetrics
                from app.models.universe import InstrumentIdentity, UniverseEnrichment
                
                # Get all active symbols with current metrics
                query = (
                    select(StockMetrics)
                    .order_by(StockMetrics.symbol.asc(), StockMetrics.date.desc())
                    .distinct(StockMetrics.symbol)
                )
                
                result = await db.execute(query)
                metrics_records = result.all()
                
                logger.info(f"Reevaluating tiers for {len(metrics_records)} symbols")
                
                tier_changes = 0
                for metrics in metrics_records:
                    symbol = metrics.symbol
                    
                    # Build enriched ticker data
                    from app.universe.enrichment.enricher import EnrichedTicker
                    enriched = EnrichedTicker(
                        symbol=symbol,
                        avg_volume_20d=metrics.avg_volume_20d if hasattr(metrics, 'avg_volume_20d') else 0,
                        avg_dollar_volume_20d=metrics.avg_volume_20d * metrics.current_price if hasattr(metrics, 'avg_volume_20d') and metrics.current_price else 0,
                        rs_baseline_spy=metrics.relative_strength_spy if hasattr(metrics, 'rs_spy') else 0,
                        rs_baseline_qqq=metrics.rs_qqq if hasattr(metrics, 'rs_qqq') else 0,
                        institutional_quality_score=metrics.institutional_quality_score if hasattr(metrics, 'institutional_quality_score') else 0
                    )
                    
                    # Get market cap if available
                    market_cap = None
                    if hasattr(metrics, 'market_cap'):
                        market_cap = metrics.market_cap
                    
                    # Reevaluate tier
                    old_tier = self.universe_engine.tier_manager.get_tier(symbol)
                    new_tier = self.universe_engine.tier_manager.determine_tier(enriched, market_cap)
                    
                    if old_tier and old_tier != new_tier:
                        logger.info(f"Tier change: {symbol} {old_tier.value} → {new_tier.value}")
                        tier_changes += 1
                        
                        # Update in database
                        from app.models.universe import UniverseTier as UniverseTierModel
                        from app.models.universe import InstrumentIdentity as InstrumentIdentityModel
                        # Get internal_id from InstrumentIdentity
                        identity_query = select(InstrumentIdentityModel.internal_id).where(
                            InstrumentIdentityModel.current_symbol == symbol
                        ).limit(1)
                        identity_result = await db.execute(identity_query)
                        internal_id = identity_result.scalar_one_or_none()
                        
                        if internal_id:
                            tier_query = select(UniverseTierModel).where(UniverseTierModel.instrument_id == internal_id)
                            tier_result = await db.execute(tier_query)
                            tier_record = tier_result.scalar_one_or_none()
                        
                        if tier_record:
                            tier_record.tier = new_tier.value
                            tier_record.updated_at = datetime.utcnow()
                            await db.commit()
                
                logger.info(f"Tier re-evaluation complete: {tier_changes} tier changes")
                return tier_changes
        except Exception as e:
            logger.error(f"Tier re-evaluation failed: {e}")
            import traceback
            traceback.print_exc()
            return 0

    @track_task_errors(task_name="run_health_check")
    async def _run_health_check(self):
        """Run health monitoring and generate report"""
        try:
            async with self._get_db() as db:
                from sqlalchemy import select
                from app.models.stock import StockMetrics, Stock
                from app.models.universe import InstrumentIdentity
                
                # Get all active symbols
                query = select(InstrumentIdentity).where(InstrumentIdentity.lifecycle_state == "active")
                result = await db.execute(query)
                identities = result.scalars().all()
                
                # Get ticker data for health check
                ticker_last_updates = {}
                ticker_prices = {}
                sector_counts = {}
                current_sectors = set()
                
                for identity in identities:
                    symbol = identity.current_symbol
                    
                    # Get last update time from metrics
                    metrics_query = select(StockMetrics).where(StockMetrics.symbol == symbol).order_by(StockMetrics.date.desc()).limit(1)
                    metrics_result = await db.execute(metrics_query)
                    latest_metrics = metrics_result.scalar_one_or_none()
                    
                    if latest_metrics:
                        ticker_last_updates[symbol] = latest_metrics.date
                        ticker_prices[symbol] = latest_metrics.current_price
                        
                        if latest_metrics.sector:
                            sector_counts[latest_metrics.sector] = sector_counts.get(latest_metrics.sector, 0) + 1
                            current_sectors.add(latest_metrics.sector)
                
                # Generate health report
                report = await self.universe_engine.generate_health_report(db)
                
                logger.info(f"Health check complete: {report.universe_freshness:.2f}% freshness, {len(report.alerts)} alerts")
                
                # Take corrective actions for critical alerts
                if report.dead_listings > 0:
                    logger.warning(f"Found {report.dead_listings} dead listings - recommend review")
                
                if len(report.missing_sectors) > 0:
                    logger.warning(f"Missing sectors: {report.missing_sectors}")
                
                if len(report.coverage_gaps) > 0:
                    logger.warning(f"Coverage gaps: {report.coverage_gaps}")
                
                return report
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _fill_coverage_gaps(self, coverage_gaps: Dict[str, int]):
        """Fill coverage gaps by fetching additional tickers from Polygon"""
        try:
            logger.info(f"Filling coverage gaps for {len(coverage_gaps)} sectors")
            
            async with self._get_db() as db:
                from app.data.sources.polygon_client import PolygonClient
                from app.universe.enrichment.enricher import EnrichedTicker
                from app.models.universe import InstrumentIdentity as InstrumentIdentityModel
                from app.models.universe import UniverseEnrichment as UniverseEnrichmentModel
                from app.models.universe import UniverseTier as UniverseTierModel
                from app.models.stock import Stock
                from sqlalchemy import select
                
                polygon_client = PolygonClient()
                
                for sector, current_count in coverage_gaps.items():
                    logger.info(f"Filling coverage gap for sector: {sector} (current: {current_count})")
                    
                    # Fetch tickers from Polygon for this sector
                    # Note: Polygon doesn't have sector filtering, so we fetch general tickers
                    # In a real implementation, you would use a sector-specific data source
                    all_tickers = await polygon_client.get_all_tickers(market="stocks", limit=100)
                    
                    # Filter by sector (if available) and add to universe
                    added_count = 0
                    for ticker in all_tickers[:50]:  # Limit to 50 per sector to avoid overloading
                        symbol = ticker.get("ticker")
                        
                        if not symbol:
                            continue
                        
                        # Check if already in universe
                        existing_query = select(InstrumentIdentityModel).where(
                            InstrumentIdentityModel.current_symbol == symbol.upper()
                        ).limit(1)
                        existing_result = await db.execute(existing_query)
                        if existing_result.scalar_one_or_none():
                            continue
                        
                        # Add to universe
                        internal_id = str(uuid.uuid4())
                        db_identity = InstrumentIdentityModel(
                            internal_id=internal_id,
                            current_symbol=symbol.upper(),
                            historical_symbols=[symbol.upper()],
                            lifecycle_state="active",
                            company_name=ticker.get("name", symbol),
                            primary_exchange=ticker.get("primary_exchange", ""),
                            asset_type="common_stock",
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(db_identity)
                        
                        # Create enrichment record
                        db_enrichment = UniverseEnrichmentModel(
                            instrument_id=internal_id,
                            sector=sector,  # Assign the sector we're filling
                            industry="Unknown",
                            float_shares=None,
                            avg_volume_20d=0,
                            avg_dollar_volume_20d=0,
                            rs_baseline_spy=0,
                            rs_baseline_qqq=0,
                            institutional_quality_score=0,
                        )
                        db.add(db_enrichment)

                        # Assign tier (TIER 4 for gap fills)
                        db_tier = UniverseTierModel(
                            instrument_id=internal_id,
                            tier="tier_4",
                        )
                        db.add(db_tier)

                        # Add to Stock table
                        db_stock = Stock(
                            symbol=symbol.upper(),
                            name=ticker.get("name", symbol),
                            is_active=True,
                        )
                        db.add(db_stock)
                        
                        added_count += 1
                        
                        if added_count >= 10:  # Fill up to 10 tickers per sector
                            break
                    
                    await db.commit()
                    logger.info(f"Filled coverage gap for {sector}: added {added_count} tickers")
            
            logger.info("Coverage gap filling complete")
        except Exception as e:
            logger.error(f"Coverage gap filling failed: {e}")
            import traceback
            traceback.print_exc()

    @track_task_errors(task_name="run_realtime_discovery")
    async def _run_realtime_discovery(self):
        """Run realtime discovery to detect volume explosion and RS acceleration"""
        rd_t0 = _time.monotonic()
        rd_status = "ok"
        rd_error = None
        rd_count: Optional[int] = None
        try:
            async with self._get_db() as db:
                from sqlalchemy import select
                from app.models.stock import StockMetrics
                from app.universe.discovery.auto_discovery import DiscoveryCandidate, DiscoveryTrigger
                
                # Get recent metrics for all symbols (last 2 days)
                cutoff_date = datetime.now(pytz.UTC) - timedelta(days=2)
                query = (
                    select(StockMetrics)
                    .where(StockMetrics.date >= cutoff_date)
                    .order_by(StockMetrics.date.desc())
                    .limit(5000)
                )
                
                result = await db.execute(query)
                metrics_records = result.scalars().all()
                
                # Group by symbol
                symbol_metrics = {}
                for metrics in metrics_records:
                    if metrics.symbol not in symbol_metrics:
                        symbol_metrics[metrics.symbol] = []
                    symbol_metrics[metrics.symbol].append(metrics)
                
                realtime_candidates = []
                
                # Detect volume explosion (3x average volume)
                for symbol, metrics_list in symbol_metrics.items():
                    if len(metrics_list) < 2:
                        continue
                    
                    latest = metrics_list[0]
                    previous = metrics_list[1]
                    
                    # Volume explosion check
                    if latest.avg_volume_10d and previous.avg_volume_10d:
                        volume_ratio = latest.avg_volume_10d / previous.avg_volume_10d
                        if volume_ratio >= 3.0:
                            candidate = DiscoveryCandidate(
                                symbol=symbol,
                                trigger=DiscoveryTrigger.VOLUME_EXPLOSION,
                                timestamp=datetime.utcnow(),
                                data={
                                    "volume_ratio": volume_ratio,
                                    "current_volume": latest.avg_volume_10d,
                                    "previous_volume": previous.avg_volume_10d
                                },
                                confidence=min(100, 50 + int(volume_ratio * 10)),
                                priority=1
                            )
                            realtime_candidates.append(candidate)
                            logger.info(f"Realtime volume explosion detected: {symbol} (ratio: {volume_ratio:.2f})")
                    
                    # RS acceleration check
                    if latest.relative_strength_spy and previous.relative_strength_spy:
                        rs_change = latest.relative_strength_spy - previous.relative_strength_spy
                        if rs_change >= 0.5 and latest.relative_strength_spy > 2.0:
                            candidate = DiscoveryCandidate(
                                symbol=symbol,
                                trigger=DiscoveryTrigger.RS_ACCELERATION,
                                timestamp=datetime.utcnow(),
                                data={
                                    "rs_change": rs_change,
                                    "current_rs": latest.relative_strength_spy,
                                    "previous_rs": previous.relative_strength_spy
                                },
                                confidence=min(100, 50 + int(rs_change * 20)),
                                priority=1
                            )
                            realtime_candidates.append(candidate)
                            logger.info(f"Realtime RS acceleration detected: {symbol} (change: {rs_change:.2f})")
                
                # Process realtime candidates
                for candidate in realtime_candidates:
                    await self.universe_engine.process_discovery_candidate(candidate, db)
                
                logger.info(f"Realtime discovery complete: {len(realtime_candidates)} candidates detected")
                rd_count = len(realtime_candidates)
                return realtime_candidates
        except Exception as e:
            logger.error(f"Realtime discovery failed: {e}")
            import traceback
            traceback.print_exc()
            rd_status = "failed"
            rd_error = str(e)
            return []
        finally:
            await self._record_heartbeat(
                "realtime_discovery",
                duration_seconds=_time.monotonic() - rd_t0,
                symbols_processed=rd_count,
                status=rd_status,
                error_message=rd_error,
            )

    @track_task_errors(task_name="run_lifecycle_tracking")
    async def _run_lifecycle_tracking(self):
        """Run lifecycle tracking to detect IPOs, delistings, symbol changes, sector migrations"""
        try:
            async with self._get_db() as db:
                from sqlalchemy import select
                from app.models.universe import InstrumentIdentity as InstrumentIdentityModel
                from app.models.stock import StockMetrics
                
                logger.info("Running lifecycle tracking")
                
                # Detect delistings (symbols with no price data in last 30 days)
                cutoff_date = datetime.now(pytz.UTC) - timedelta(days=30)
                metrics_query = select(StockMetrics.symbol).where(StockMetrics.date >= cutoff_date).distinct()
                metrics_result = await db.execute(metrics_query)
                active_symbols = set([symbol for (symbol,) in metrics_result.fetchall()])
                
                # Get all active symbols from universe
                identity_query = select(InstrumentIdentityModel).where(
                    InstrumentIdentityModel.lifecycle_state == "active"
                )
                identity_result = await db.execute(identity_query)
                all_identities = identity_result.scalars().all()
                
                delisted_count = 0
                for identity in all_identities:
                    if identity.current_symbol not in active_symbols:
                        # Mark as delisted
                        identity.lifecycle_state = "delisted"
                        identity.updated_at = datetime.utcnow()
                        delisted_count += 1
                        logger.warning(f"Lifecycle change detected: {identity.current_symbol} marked as delisted (no data in 30 days)")
                
                if delisted_count > 0:
                    await db.commit()
                    logger.info(f"Lifecycle tracking complete: {delisted_count} symbols marked as delisted")
                else:
                    logger.info("Lifecycle tracking complete: no lifecycle changes detected")
                
                return delisted_count
        except Exception as e:
            logger.error(f"Lifecycle tracking failed: {e}")
            import traceback
            traceback.print_exc()
            return 0

    async def run(self):
        """Run the scheduler loop"""
        self._running = True
        try:
            await self._scheduler_loop()
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
        finally:
            self._running = False
            if self.engine:
                await self.engine.dispose()

    def stop(self):
        """Stop the scheduler"""
        self._running = False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    scheduler = DataScheduler(settings.database_url)
    try:
        asyncio.run(scheduler.run())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.stop()
