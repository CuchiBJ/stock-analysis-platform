from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.data.ingestors.stock_ingestor import StockIngestor
from app.data.ingestors.price_ingestor import PriceIngestor
from app.data.ingestors.metrics_calculator import MetricsCalculator
from app.core.config import settings
from app.universe.universe_engine import UniverseEngine
from app.universe.tiers.tier_manager import UniverseTier
from datetime import datetime, time, timedelta
import pytz
import logging
import asyncio
import uuid
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
        
        # Initialize UniverseEngine for discovery and health monitoring
        self.universe_engine = UniverseEngine(polygon_api_key=settings.polygon_api_key)

    def _get_db(self):
        """Get database session"""
        if self.async_session_maker:
            return self.async_session_maker()
        raise RuntimeError("Database not initialized")

    async def trigger_metrics_update(self, limit=100):
        """Manually trigger SLOW metrics calculation (comprehensive metrics for all tiers)"""
        async with self._get_db() as db:
            ingestor = StockIngestor(db)
            symbols = await ingestor.get_active_symbols(limit=limit)
            logger.info(f"Calculating SLOW metrics for {len(symbols)} symbols...")
            
            calculator = MetricsCalculator(db)
            count = await calculator.calculate_metrics_batch(symbols)
            logger.info(f"SLOW metrics calculated for {count} symbols")
            return count

    async def trigger_fast_metrics_update(self):
        """Trigger FAST metrics update for TIER 1 only (operational metrics)"""
        try:
            async with self._get_db() as db:
                from sqlalchemy import select
                from app.models.universe import UniverseTier as UniverseTierModel
                from app.models.stock import StockMetrics
                
                # Get TIER 1 symbols
                tier_query = select(UniverseTierModel).where(UniverseTierModel.tier == "tier_1")
                tier_result = await db.execute(tier_query)
                tier_records = tier_result.scalars().all()
                
                tier1_symbols = [record.instrument_id for record in tier_records]
                logger.info(f"Updating FAST metrics for {len(tier1_symbols)} TIER 1 symbols")
                
                # Update only operational metrics for TIER 1
                calculator = MetricsCalculator(db)
                count = 0
                
                for symbol in tier1_symbols[:200]:  # Limit to 200 TIER 1 symbols for performance
                    # Calculate only FAST metrics (distance_to_ema21, reclaim status, deterioration)
                    # This is a simplified version - in production, you'd have a dedicated fast_metrics method
                    await calculator.calculate_metrics_for_symbol(symbol, days=10)  # Only need recent data
                    count += 1
                
                logger.info(f"FAST metrics updated for {count} TIER 1 symbols")
                return count
        except Exception as e:
            logger.error(f"FAST metrics update failed: {e}")
            import traceback
            traceback.print_exc()
            return 0

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
        
        # Trigger initial metrics update immediately
        logger.info("Triggering initial metrics update")
        await self.trigger_metrics_update(limit=3125)
        last_metrics_update = datetime.now(et_tz)
        
        # Load tiers from database
        async with self._get_db() as db:
            await self.universe_engine.tier_manager.load_tiers_from_database(db)
            logger.info("Loaded tier assignments from database")
        
        while self._running:
            now = datetime.now(et_tz)
            current_time = now.time()
            
            # Check if within market hours
            if market_open <= current_time <= market_close:
                # Price update every 15 minutes
                if last_price_update is None or (now - last_price_update).total_seconds() >= 900:
                    logger.info(f"Triggering price update (current time: {current_time})")
                    # Run price update in background to not block metrics
                    asyncio.create_task(self._update_prices())
                    last_price_update = now
                
                # FAST metrics every 5 minutes (TIER 1 only - operational metrics)
                if last_fast_metrics_update is None or (now - last_fast_metrics_update).total_seconds() >= 300:
                    logger.info(f"Triggering FAST metrics update for TIER 1 (current time: {current_time})")
                    await self.trigger_fast_metrics_update()
                    last_fast_metrics_update = now
                
                # SLOW metrics every 30 minutes (all tiers - comprehensive metrics)
                if last_metrics_update is None or (now - last_metrics_update).total_seconds() >= 1800:
                    logger.info(f"Triggering SLOW metrics update for all tiers (current time: {current_time})")
                    await self.trigger_metrics_update(limit=3125)
                    last_metrics_update = now
                
                # Realtime discovery every 10 minutes (detect volume explosion, RS acceleration)
                if last_realtime_discovery is None or (now - last_realtime_discovery).total_seconds() >= 600:
                    logger.info(f"Triggering realtime discovery (current time: {current_time})")
                    asyncio.create_task(self._run_realtime_discovery())
                    last_realtime_discovery = now
            else:
                # After market close: run nightly tasks
                logger.info(f"Outside market hours (current time: {current_time})")
                
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
        """Update prices"""
        async with self._get_db() as db:
            ingestor = PriceIngestor(db)
            try:
                count = await ingestor.ingest_intraday_prices()
                logger.info(f"Price update complete: {count} symbols")
            except Exception as e:
                logger.error(f"Price update failed: {e}")

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
                    .order_by(StockMetrics.date.desc())
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
