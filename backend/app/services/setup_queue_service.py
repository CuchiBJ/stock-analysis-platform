"""Setup Queue Service — three lenses for institutional momentum workflow.

Lens 1: U&R Queue — Minervini leaders with recent pre-reclaim event + "from above" rule
Lens 2: Emerging Leaders — strong stocks not fully Minervini-qualified, with breakdown
Lens 3: Building Bases — Minervini leaders in tight VCP-style consolidation

Plus per-symbol history endpoint for drill-down.
"""
import math
from datetime import date, datetime, timedelta
from typing import Optional
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.stock import Stock, StockMetrics, TransitionObservation
from app.services.quality_leader_gate import is_quality_leader, evaluate_minervini_criteria
from app.services.universe_filters import QUALITY_FILTERS


def _clean(v):
    """Replace non-finite floats with None so FastAPI can serialize them."""
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {k: _clean(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


def _tv_url(symbol: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol={symbol}"


class SetupQueueService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _fetch_market_groups(self, symbols: list[str]) -> dict[str, Optional[str]]:
        """Return {symbol: market_group} for a list of symbols in one query."""
        if not symbols:
            return {}
        result = await self.db.execute(
            select(Stock.symbol, Stock.market_group).where(Stock.symbol.in_(symbols))
        )
        return {row.symbol: row.market_group for row in result.fetchall()}

    async def _latest_date(self) -> Optional[str]:
        result = await self.db.execute(select(func.max(StockMetrics.date)))
        return result.scalar()

    async def list_u_and_r(self) -> list[dict]:
        today = date.today()
        cutoff_2d = today - timedelta(days=2)

        # 1. Candidates: symbols with non-stable observation in last 2 days
        obs_q = select(
            TransitionObservation.symbol,
            TransitionObservation.transition_type,
            TransitionObservation.date_detected,
        ).where(
            TransitionObservation.date_detected >= cutoff_2d,
            TransitionObservation.transition_type != 'stable',
        ).order_by(TransitionObservation.date_detected.desc())
        obs_rows = (await self.db.execute(obs_q)).all()

        if not obs_rows:
            return []

        # Pick most recent observation per symbol
        latest_obs: dict[str, dict] = {}
        for sym, ttype, ddet in obs_rows:
            if sym not in latest_obs:
                latest_obs[sym] = {
                    'symbol': sym,
                    'transition_type': ttype,
                    'date_detected': ddet,
                    'event_age_days': (today - ddet).days,
                }

        symbols = list(latest_obs.keys())

        # 2. Latest metrics per symbol (filter by is_quality_leader + d21_atr range)
        latest_date = await self._latest_date()
        if not latest_date:
            return []
        metrics_q = select(StockMetrics).where(
            StockMetrics.date == latest_date,
            StockMetrics.symbol.in_(symbols),
            *QUALITY_FILTERS,
        )
        metrics_rows = (await self.db.execute(metrics_q)).scalars().all()
        metrics_by_sym = {m.symbol: m for m in metrics_rows}

        # 3. Historical bulk fetch: d21_atr last 20 days (covers "from above" + "no broke EMA50")
        hist_start = today - timedelta(days=25)
        hist_q = select(
            StockMetrics.symbol,
            StockMetrics.date,
            StockMetrics.distance_to_ema21_atr,
            StockMetrics.distance_to_ema50_atr,
        ).where(
            StockMetrics.symbol.in_(symbols),
            StockMetrics.date >= hist_start,
        ).order_by(StockMetrics.symbol, StockMetrics.date)
        hist_rows = (await self.db.execute(hist_q)).all()

        hist_by_sym: dict[str, list] = defaultdict(list)
        for sym, d, d21, d50 in hist_rows:
            hist_by_sym[sym].append({'date': d, 'd21': d21, 'd50': d50})

        # 4. Touch count last 30 days
        touch_cutoff = today - timedelta(days=30)
        touch_q = select(
            TransitionObservation.symbol,
            func.count(TransitionObservation.id),
        ).where(
            TransitionObservation.symbol.in_(symbols),
            TransitionObservation.date_detected >= touch_cutoff,
            TransitionObservation.transition_type != 'stable',
        ).group_by(TransitionObservation.symbol)
        touch_rows = (await self.db.execute(touch_q)).all()
        touches_by_sym = {sym: count for sym, count in touch_rows}

        # Apply filters per candidate
        results = []
        day10 = today - timedelta(days=10)
        day5 = today - timedelta(days=5)

        for sym, obs in latest_obs.items():
            m = metrics_by_sym.get(sym)
            if not m:
                continue
            if not is_quality_leader(m):
                continue
            d21_atr = m.distance_to_ema21_atr
            if d21_atr is None or not (-0.5 <= d21_atr <= 1.5):
                continue

            history = hist_by_sym.get(sym, [])
            # "From above" rule: any d21_atr > 0.5 between day-10 and day-5
            was_above = any(
                h['d21'] is not None and h['d21'] > 0.5
                and day10 <= h['date'] <= day5
                for h in history
            )
            if not was_above:
                continue

            # "No broke EMA50": d50_atr never negative in last 20 days
            broke_ema50 = any(
                h['d50'] is not None and h['d50'] < 0
                for h in history
            )
            if broke_ema50:
                continue

            results.append({
                'symbol': sym,
                'transition_type': obs['transition_type'],
                'event_age_days': obs['event_age_days'],
                'distance_to_ema21_atr': round(d21_atr, 2),
                'rs_spy': round(m.relative_strength_spy, 1) if m.relative_strength_spy else None,
                'volume_contraction': round(m.volume_contraction, 1) if m.volume_contraction else None,
                'touches_last_30d': touches_by_sym.get(sym, 1),
                'tradingview_url': _tv_url(sym),
            })

        # Sort: event_age asc, |d21_atr| asc, rs_spy desc
        results.sort(key=lambda r: (
            r['event_age_days'],
            abs(r['distance_to_ema21_atr']),
            -(r['rs_spy'] or 0),
        ))
        market_groups = await self._fetch_market_groups([r['symbol'] for r in results])
        for r in results:
            r['market_group'] = market_groups.get(r['symbol'])
        return [_clean(r) for r in results]

    async def list_emerging_leaders(self) -> list[dict]:
        latest_date = await self._latest_date()
        if not latest_date:
            return []

        q = select(StockMetrics).where(
            StockMetrics.date == latest_date,
            *QUALITY_FILTERS,
            StockMetrics.perf_4w.isnot(None),
            StockMetrics.perf_13w.isnot(None),
            StockMetrics.relative_strength_spy > 105,
            StockMetrics.current_price > StockMetrics.ema50,
            StockMetrics.current_price > StockMetrics.ema200,
        )
        rows = (await self.db.execute(q)).scalars().all()

        results = []
        for m in rows:
            # Approximate perf_6m using perf_13w (closest available metric)
            # perf_6m > 20% threshold
            perf_proxy = m.perf_13w
            if perf_proxy is None or perf_proxy <= 20.0:
                continue

            # Must NOT pass full Minervini
            if is_quality_leader(m):
                continue

            criteria = evaluate_minervini_criteria(m)
            # Build the "qualifies as emerging because" string from first failed criterion
            failed = [k for k, v in criteria.items() if not v.get('passes')]
            reason_parts = []
            if 'perf_1y_gt_30' in failed:
                reason_parts.append(
                    f"Strong 13w perf ({perf_proxy:.0f}%) + RS ({m.relative_strength_spy:.0f}) "
                    f"but lacks 12m history for Stage 2"
                )
            if 'sma50_gt_sma150' in failed or 'sma150_gt_sma200_x_105' in failed:
                reason_parts.append("SMA chain not yet established")
            if 'range_52w_gte_60pct' in failed:
                reason_parts.append("52W range still tight")
            if not reason_parts:
                reason_parts.append("Strong momentum but missing structural criteria")

            results.append({
                'symbol': m.symbol,
                'perf_13w': round(m.perf_13w, 1) if m.perf_13w else None,
                'perf_4w': round(m.perf_4w, 1) if m.perf_4w else None,
                'rs_spy': round(m.relative_strength_spy, 1),
                'current_price': round(m.current_price, 2) if m.current_price else None,
                'minervini_status': criteria,
                'qualifies_as_emerging_because': '. '.join(reason_parts),
                'tradingview_url': _tv_url(m.symbol),
            })

        # Sort by perf_13w descending, top 30 (browsing list, not exhaustive)
        results.sort(key=lambda r: -(r['perf_13w'] or 0))
        top30 = results[:30]
        market_groups = await self._fetch_market_groups([r['symbol'] for r in top30])
        for r in top30:
            r['market_group'] = market_groups.get(r['symbol'])
        return [_clean(r) for r in top30]

    async def list_building_bases(self) -> list[dict]:
        latest_date = await self._latest_date()
        if not latest_date:
            return []

        # Initial filter on current metrics
        q = select(StockMetrics).where(
            StockMetrics.date == latest_date,
            *QUALITY_FILTERS,
            StockMetrics.vcp_score >= 70,
            StockMetrics.weeks_in_base >= 6,
        )
        rows = (await self.db.execute(q)).scalars().all()

        if not rows:
            return []

        # Filter by is_quality_leader (pure function, no extra query)
        candidates = [m for m in rows if is_quality_leader(m)]
        if not candidates:
            return []

        symbols = [m.symbol for m in candidates]

        # Bulk fetch last 20 trading days of d21_atr for oscillation check
        today = date.today()
        hist_start = today - timedelta(days=30)
        hist_q = select(
            StockMetrics.symbol,
            StockMetrics.distance_to_ema21_atr,
        ).where(
            StockMetrics.symbol.in_(symbols),
            StockMetrics.date >= hist_start,
            StockMetrics.distance_to_ema21_atr.isnot(None),
        )
        hist_rows = (await self.db.execute(hist_q)).all()

        d21_by_sym: dict[str, list[float]] = defaultdict(list)
        for sym, d21 in hist_rows:
            d21_by_sym[sym].append(d21)

        results = []
        for m in candidates:
            values = d21_by_sym.get(m.symbol, [])
            # Need at least 10 data points to be meaningful
            if len(values) < 10:
                continue
            atr_range = max(values) - min(values)
            if atr_range > 2.0:
                continue

            # Volume contraction trend (simple: current value)
            vc = m.volume_contraction
            if vc is None:
                trend = 'unknown'
            elif vc > 25:
                trend = 'declining'
            elif vc > 10:
                trend = 'mild'
            else:
                trend = 'flat'

            results.append({
                'symbol': m.symbol,
                'vcp_score': round(m.vcp_score, 1),
                'weeks_in_base': m.weeks_in_base,
                'atr_range_last_20d': round(atr_range, 2),
                'current_distance_to_ema21_atr': round(m.distance_to_ema21_atr, 2) if m.distance_to_ema21_atr is not None else None,
                'volume_contraction_trend': trend,
                'tradingview_url': _tv_url(m.symbol),
            })

        # Sort by tightest range first, then highest vcp_score
        results.sort(key=lambda r: (r['atr_range_last_20d'], -r['vcp_score']))
        market_groups = await self._fetch_market_groups([r['symbol'] for r in results])
        for r in results:
            r['market_group'] = market_groups.get(r['symbol'])
        return [_clean(r) for r in results]

    async def get_symbol_history(self, symbol: str, days: int = 30) -> dict:
        symbol = symbol.upper()
        cutoff = date.today() - timedelta(days=days)

        # Detect current regime
        try:
            from app.services.market_regime_engine import MarketRegimeEngine
            analysis = await MarketRegimeEngine(self.db).detect_regime()
            current_regime = analysis.regime.value if hasattr(analysis.regime, 'value') else str(analysis.regime)
        except Exception:
            current_regime = 'unknown'

        # Fetch observations
        obs_q = select(TransitionObservation).where(
            TransitionObservation.symbol == symbol,
            TransitionObservation.date_detected >= cutoff,
        ).order_by(TransitionObservation.date_detected)
        obs_rows = (await self.db.execute(obs_q)).scalars().all()

        observations = [
            {
                'date_detected': o.date_detected.isoformat(),
                'transition_type': o.transition_type,
                'outcome_status': o.outcome_status,
                'distance_to_ema21_atr_at_detection': (
                    round((o.price_at_detection - o.ema21_at_detection) / o.atr_at_detection, 2)
                    if (o.price_at_detection and o.ema21_at_detection and o.atr_at_detection)
                    else None
                ),
                'pct_5d': o.pct_5d,
                'pct_20d': o.pct_20d,
                'regime_at_detection': o.regime_at_detection,
            }
            for o in obs_rows
        ]

        # Track record: per transition_type observed in this symbol, success_rate in current regime
        track_record: dict[str, dict] = {}
        transition_types_seen = set(o.transition_type for o in obs_rows)
        for ttype in transition_types_seen:
            tr_q = select(TransitionObservation).where(
                TransitionObservation.transition_type == ttype,
                TransitionObservation.regime_at_detection == current_regime,
                TransitionObservation.outcome_status.in_(['SUCCESS', 'FAILURE', 'NEUTRAL']),
            )
            tr_rows = (await self.db.execute(tr_q)).scalars().all()
            n = len(tr_rows)
            if n == 0:
                track_record[f'{ttype}_in_{current_regime}'] = {
                    'success_rate': None,
                    'sample_size': 0,
                }
            else:
                succ = sum(1 for r in tr_rows if r.outcome_status == 'SUCCESS')
                track_record[f'{ttype}_in_{current_regime}'] = {
                    'success_rate': round(succ / n, 3),
                    'sample_size': n,
                }

        return _clean({
            'symbol': symbol,
            'current_regime': current_regime,
            'observations': observations,
            'track_record': track_record,
        })
