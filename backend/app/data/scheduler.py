from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.data.ingestors.stock_ingestor import StockIngestor
from app.data.ingestors.price_ingestor import PriceIngestor
from app.data.ingestors.metrics_calculator import MetricsCalculator
from app.core.config import settings
from app.universe.universe_engine import UniverseEngine
from app.universe.tiers.tier_manager import UniverseTier
from app.services.websocket_manager import websocket_manager
from app.services.task_error_tracker import track_task_errors
from sqlalchemy import func
from datetime import datetime, time, timedelta
import pytz
import logging
import asyncio
import uuid
import pandas as pd
import yfinance as yf
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DataScheduler:
    def __init__(self, database_url=None):
        if database_url:
            self.engine = create_async_engine(database_url, echo=False)
            self.async_session_maker = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
        else:
            self.engine = None
            self.async_session_maker = None
        self._running = False
        self._slow_running = False

        # Initialize UniverseEngine for discovery and health monitoring
        self.universe_engine = UniverseEngine(polygon_api_key=settings.polygon_api_key)

    def _get_db(self):
        """Get database session"""
        if self.async_session_maker:
            return self.async_session_maker()
        raise RuntimeError("Database not initialized")

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
        try:
            async with self._get_db() as db:
                snapshot_date = None
                if symbols is None:
                    symbols, snapshot_date = await self._get_slow_symbols_and_date(db)
                if not symbols:
                    return 0
                if limit:
                    symbols = symbols[:limit]

                logger.info(f"Calculating SLOW metrics for {len(symbols)} symbols...")
                calculator = MetricsCalculator(db)
                for sym in symbols:
                    # Write-protection: skip if FAST already wrote a row for snapshot_date
                    if snapshot_date:
                        existing = await db.execute(
                            select(StockMetricsModel.date)
                            .where(
                                StockMetricsModel.symbol == sym,
                                StockMetricsModel.date >= snapshot_date,
                            )
                            .limit(1)
                        )
                        if existing.scalar():
                            continue
                    try:
                        await calculator.calculate_metrics_for_symbol(sym)
                        count += 1
                    except Exception:
                        continue
                await db.commit()
                logger.info(f"SLOW metrics calculated for {count} symbols")
            asyncio.create_task(self._broadcast_metrics_updated(count, tier='all'))
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

    async def trigger_fast_metrics_update(self):
        """Trigger FAST metrics update for TIER 1 + institutional quality stocks."""
        try:
            async with self._get_db() as db:
                symbols = await self._get_fast_symbols(db)
                if not symbols:
                    logger.warning("FAST cycle: no symbols to update")
                    return 0

                calculator = MetricsCalculator(db)
                updated_symbols = []

                for symbol in symbols[:300]:
                    await calculator.calculate_metrics_for_symbol(symbol, days=10)
                    updated_symbols.append(symbol)

                count = len(updated_symbols)
                logger.info(f"FAST metrics updated for {count} symbols")

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

    async def _scheduler_loop(self):
        """Background scheduler loop that executes jobs based on time"""
        logger.info("Scheduler loop started")
        et_tz = pytz.timezone('US/Eastern')
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        last_price_update = None
        last_metrics_update = None
        last_fast_metrics_update = None
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
        
        while self._running:
            now = datetime.now(et_tz)
            current_time = now.time()
            
            # Check if within market hours
            if market_open <= current_time <= market_close:
                # Price update every 15 minutes — awaited so FAST always uses fresh prices
                if last_price_update is None or (now - last_price_update).total_seconds() >= 900:
                    logger.info(f"Triggering price update (current time: {current_time})")
                    try:
                        await self._update_prices()
                    except Exception as e:
                        logger.error(f"Price update failed (continuing): {e}")
                    last_price_update = now
                    # Immediately chain FAST metrics with fresh prices
                    logger.info("Chaining FAST metrics after price update")
                    await self.trigger_fast_metrics_update()
                    last_fast_metrics_update = now
                    await asyncio.sleep(30)
                    continue

                # FAST metrics every 5 minutes (between price updates)
                if last_fast_metrics_update is None or (now - last_fast_metrics_update).total_seconds() >= 300:
                    logger.info(f"Triggering FAST metrics update (current time: {current_time})")
                    await self.trigger_fast_metrics_update()
                    last_fast_metrics_update = now

                # SLOW metrics every 30 minutes — all symbols with price for today
                if last_metrics_update is None or (now - last_metrics_update).total_seconds() >= 1800:
                    logger.info(f"Triggering SLOW metrics update (current time: {current_time})")
                    await self.trigger_metrics_update()
                    last_metrics_update = now
                
                # Realtime discovery every 10 minutes (detect volume explosion, RS acceleration)
                if last_realtime_discovery is None or (now - last_realtime_discovery).total_seconds() >= 600:
                    logger.info(f"Triggering realtime discovery (current time: {current_time})")
                    asyncio.create_task(self._run_realtime_discovery())
                    last_realtime_discovery = now
            else:
                # After market close: run nightly tasks
                logger.info(f"Outside market hours (current time: {current_time})")

                # Post-close cycle: capture closing prices into a final SLOW so metrics
                # reflect the actual close, not the last 15-min snapshot before 16:00 ET.
                # Fires once per weekday, ~10 min after close (yfinance settle window).
                if (now.weekday() < 5
                        and current_time >= post_close_window_start
                        and last_post_close_cycle_date != now.date()):
                    logger.info(f"Post-close cycle: final price update + SLOW (current time: {current_time})")
                    try:
                        await self._update_prices()
                        last_price_update = now
                        await self.trigger_metrics_update()
                        last_metrics_update = now
                    except Exception as e:
                        logger.error(f"Post-close cycle failed: {e}")
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
        """Synchronous yfinance bulk download — runs in thread pool."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.stock import StockPrice

        sync_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
        engine = create_engine(sync_url, pool_size=5, echo=False)
        Session = sessionmaker(engine)

        # Filter symbols that Yahoo Finance cannot serve: warrants (*W), units (*U),
        # rights (*R) with 5-char tickers, and $ prefixes. These always fail and
        # consume rate limit quota.
        _SKIP_SUFFIXES = frozenset({'W', 'U', 'R'})
        excluded = [s for s in symbols if s.startswith('$') or (len(s) == 5 and s[-1] in _SKIP_SUFFIXES)]
        if excluded:
            logger.info(f"Price download: excluding {len(excluded)} non-downloadable symbols (warrants/units/rights)")
        symbols = [s for s in symbols if not (s.startswith('$') or (len(s) == 5 and s[-1] in _SKIP_SUFFIXES))]

        BATCH = 200
        ok = 0

        for i in range(0, len(symbols), BATCH):
            batch = symbols[i:i + BATCH]
            try:
                data = yf.download(
                    batch, period="5d", auto_adjust=True,
                    progress=False, threads=False  # threads=False prevents DNS exhaustion
                )
                if data.empty:
                    continue

                multi = isinstance(data.columns, pd.MultiIndex)

                with Session() as session:
                    for symbol in batch:
                        try:
                            if multi:
                                if symbol not in data.columns.get_level_values(1):
                                    logger.debug(f"Symbol {symbol} not in yfinance response — skipping")
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

            except Exception as e:
                logger.error(f"Batch {i//BATCH + 1} failed: {e}")

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
                        "rs_spy": metrics.rs_spy if hasattr(metrics, 'rs_spy') else None,
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
                        rs_baseline_spy=metrics.rs_spy if hasattr(metrics, 'rs_spy') else 0,
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
                        )
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
                        )
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
                            market_cap=None,
                            float_shares=None,
                            avg_volume_20d=0,
                            avg_dollar_volume_20d=0,
                            rs_baseline_spy=0,
                            rs_baseline_qqq=0,
                            institutional_quality_score=0,
                            updated_at=datetime.utcnow()
                        )
                        db.add(db_enrichment)
                        
                        # Assign tier (TIER 4 for gap fills)
                        db_tier = UniverseTierModel(
                            instrument_id=internal_id,
                            tier="tier_4",
                            assigned_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                            reason="coverage_gap_fill"
                        )
                        db.add(db_tier)
                        
                        # Add to Stock table
                        db_stock = Stock(
                            symbol=symbol.upper(),
                            company_name=ticker.get("name", symbol),
                            is_active=True,
                            added_at=datetime.utcnow()
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
                    if latest.rs_spy and previous.rs_spy:
                        rs_change = latest.rs_spy - previous.rs_spy
                        if rs_change >= 0.5 and latest.rs_spy > 2.0:
                            candidate = DiscoveryCandidate(
                                symbol=symbol,
                                trigger=DiscoveryTrigger.RS_ACCELERATION,
                                timestamp=datetime.utcnow(),
                                data={
                                    "rs_change": rs_change,
                                    "current_rs": latest.rs_spy,
                                    "previous_rs": previous.rs_spy
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
                return realtime_candidates
        except Exception as e:
            logger.error(f"Realtime discovery failed: {e}")
            import traceback
            traceback.print_exc()
            return []

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
