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

from app.models.stock import Stock, StockMetrics, StockPrice, TransitionObservation
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


# Building Bases — ranked by a composite VCP-QUALITY score (relative to each stock),
# not absolute tightness. In an ADR≥4% universe absolute "tight bases" barely exist
# (median 20-day price range ≈ 4.4 ATR), so we score the QUALITY of contraction:
#
#   vcp_quality = (W_BAND·band_contraction + W_VOL·volume_dryup) · gap_penalty
#
#   band_contraction = 1 − recent_half_envelope / prior_half_envelope   (range coiling)
#   volume_dryup     = 1 − recent_avg_vol / prior_avg_vol               (volume drying)
#   gap_penalty      = down-weights names whose window contains a large overnight
#                      close-to-close move (event/news), since that corrupts the
#                      contraction reading and is not a real VCP.
#
# This is what earlier attempts missed: vcp_score>=70 floored long bases at 0; a raw
# envelope-contraction ratio got fooled by (a) pullbacks where EMA21 falls with price
# and (b) post-gap settling (e.g. IMVT gapped +35% then went quiet → fake "contraction").
# Volume confirmation + the gap penalty fix both. Weights are tunable.
_BB_RANGE_BARS  = 20         # OHLC window, split into prior/recent halves
_BB_MIN_BARS    = 14         # need at least this many bars to score
_BB_TOP_N       = 8          # ranked watchlist size (no threshold cutoff)
_BB_W_BAND      = 0.55       # weight: range/band contraction
_BB_W_VOLUME    = 0.45       # weight: volume dry-up
_BB_GAP_FREE_ATR = 1.5       # max close-to-close move (ATR) before the gap penalty bites
_BB_GAP_FLOOR    = 0.2       # penalty floor for event-driven names


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _vcp_quality(bars: list[tuple], atr: float) -> Optional[dict]:
    """Composite VCP-quality from a list of (high, low, close, volume) bars, oldest→newest.

    Returns dict with vcp_quality + components, or None if insufficient/degenerate data.
    """
    if len(bars) < _BB_MIN_BARS or not atr:
        return None
    half = len(bars) // 2
    prior, recent = bars[:half], bars[half:]

    env_p = max(h for h, _, _, _ in prior) - min(l for _, l, _, _ in prior)
    env_r = max(h for h, _, _, _ in recent) - min(l for _, l, _, _ in recent)
    if env_p <= 0:
        return None
    band = _clamp01(1 - env_r / env_p)

    vol_p = sum(v for *_, v in prior) / len(prior)
    vol_r = sum(v for *_, v in recent) / len(recent)
    volume_dryup = _clamp01(1 - vol_r / vol_p) if vol_p > 0 else 0.0

    closes = [c for _, _, c, _ in bars]
    max_gap_atr = max(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))) / atr
    if max_gap_atr < _BB_GAP_FREE_ATR:
        gap_penalty = 1.0
    else:
        gap_penalty = max(_BB_GAP_FLOOR, 1 - (max_gap_atr - _BB_GAP_FREE_ATR) / 2.0)

    quality = (_BB_W_BAND * band + _BB_W_VOLUME * volume_dryup) * gap_penalty
    return {
        'vcp_quality': round(quality, 3),
        'band_contraction': round(band, 2),
        'volume_dryup': round(volume_dryup, 2),
        'max_gap_atr': round(max_gap_atr, 1),
        'recent_range_atr': round(env_r / atr, 2),
    }


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

    async def _spy_perf_1w(self) -> Optional[float]:
        """SPY's trailing 1-week (~5 trading days) performance %, from price history."""
        result = await self.db.execute(
            select(StockPrice.close)
            .where(StockPrice.symbol == 'SPY')
            .order_by(StockPrice.date.desc())
            .limit(6)
        )
        closes = [row[0] for row in result.fetchall()]
        if len(closes) < 6 or not closes[5]:
            return None
        return ((closes[0] - closes[5]) / closes[5]) * 100

    async def _spy_return_between(self, start_date, end_date) -> Optional[float]:
        """SPY % return from start_date close to end_date close (None if either missing)."""
        result = await self.db.execute(
            select(StockPrice.date, StockPrice.close).where(
                StockPrice.symbol == 'SPY',
                StockPrice.date.in_([start_date, end_date]),
            )
        )
        by_date = {row[0]: row[1] for row in result.fetchall()}
        s, e = by_date.get(start_date), by_date.get(end_date)
        if not s or not e:
            return None
        return ((e - s) / s) * 100

    @staticmethod
    def _holding_status(m: StockMetrics) -> str:
        """How well a leader is holding up in the pullback — down-day context.

        Ordered strongest → weakest:
          at_highs      — within 2 ATR of the 52w high AND still holding EMA21
          above_ema21   — still above fast support (EMA21)
          testing_ema21 — just lost EMA21, still sitting near it (well above EMA50)
          testing_ema50 — pulled back further, now down near/at EMA50
          deep_pullback — below EMA50, extended retrace
        """
        d_high = m.distance_to_high_52w_atr
        d21 = m.distance_to_ema21_atr
        d50 = m.distance_to_ema50_atr
        # 'at_highs' is the strongest tier, so it must be near the high *and*
        # still above fast support — a name that already lost EMA21 has pulled
        # back and belongs in a weaker tier (testing_ema*/deep_pullback),
        # even if it's still within 2 ATR of the 52w high.
        if d_high is not None and d_high >= -2.0 and (d21 is None or d21 > 0):
            return 'at_highs'
        if d21 is not None and d21 > 0:
            return 'above_ema21'
        if d50 is not None and d50 > 0:
            # Below EMA21 but holding above EMA50: which level is it actually
            # testing? Split by proximity — a name sitting right under EMA21
            # (e.g. -0.1 ATR) is testing EMA21, not EMA50, even though it's
            # still above the slower average.
            if d21 is not None and abs(d21) < d50:
                return 'testing_ema21'
            return 'testing_ema50'
        return 'deep_pullback'

    async def list_rs_leaders(self, sort: str = 'rs', window: int = 5) -> list[dict]:
        """RS Leaders — Minervini leaders ranked by relative strength vs SPY.

        Two ranking modes over the same leader pool (gate unchanged):

        - sort='rs' (default): trailing 13-week RS (relative_strength_spy) desc.
          The "who has been strongest" watchlist for down days.

        - sort='momentum': where relative strength is flowing RIGHT NOW. Ranks by
          rs_momentum_score = rs_delta_pct + (resilience if SPY fell over the window).
          rs_delta_pct is the % slope of the RS line over the last `window` sessions
          (scale-free, so it surfaces names whose RS is *accelerating*, not just the
          ones with the highest absolute RS). resilience = stock_return − spy_return
          over the window, added only while the SPY is falling — rewarding leaders
          that hold up during the correction.

        `window` is the number of trading sessions for the momentum lookback (3/5/10).
        Momentum fields are computed in both modes so the UI can show them either way.
        """
        if window not in (3, 5, 10):
            window = 5

        latest_date = await self._latest_date()
        if not latest_date:
            return []

        q = select(StockMetrics).where(
            StockMetrics.date == latest_date,
            *QUALITY_FILTERS,
            StockMetrics.relative_strength_spy.isnot(None),
        )
        rows = (await self.db.execute(q)).scalars().all()

        leaders = [m for m in rows if is_quality_leader(m)]
        if not leaders:
            return []

        symbols = [m.symbol for m in leaders]

        # Session calendar from distinct metric dates (desc). baseline = `window` sessions back.
        dates_rows = (await self.db.execute(
            select(StockMetrics.date)
            .where(StockMetrics.date <= latest_date)
            .distinct()
            .order_by(StockMetrics.date.desc())
            .limit(window + 5)
        )).scalars().all()
        baseline_date = dates_rows[window] if len(dates_rows) > window else None

        # Bulk baseline metrics (RS + price) at baseline_date for all leaders, one query.
        baseline_by_sym: dict[str, tuple] = {}
        spy_return_n: Optional[float] = None
        if baseline_date is not None:
            base_rows = (await self.db.execute(
                select(
                    StockMetrics.symbol,
                    StockMetrics.relative_strength_spy,
                    StockMetrics.current_price,
                ).where(
                    StockMetrics.symbol.in_(symbols),
                    StockMetrics.date == baseline_date,
                )
            )).all()
            baseline_by_sym = {sym: (rs, px) for sym, rs, px in base_rows}
            spy_return_n = await self._spy_return_between(baseline_date, latest_date)

        spy_perf_1w = await self._spy_perf_1w()

        results = []
        for m in leaders:
            rel_1w = None
            if m.perf_1w is not None and spy_perf_1w is not None:
                rel_1w = round(m.perf_1w - spy_perf_1w, 1)

            # Momentum block (None when no baseline / missing data)
            rs_delta = rs_delta_pct = stock_return_n = resilience = rs_momentum_score = None
            held_up = False
            base = baseline_by_sym.get(m.symbol)
            if base is not None:
                rs_base, px_base = base
                if rs_base is not None:
                    rs_delta = m.relative_strength_spy - rs_base
                    if rs_base != 0:
                        rs_delta_pct = rs_delta / rs_base * 100
                if px_base and m.current_price is not None:
                    stock_return_n = (m.current_price - px_base) / px_base * 100
                if stock_return_n is not None and spy_return_n is not None:
                    resilience = stock_return_n - spy_return_n
                    held_up = spy_return_n < 0 and stock_return_n >= 0
                if rs_delta_pct is not None:
                    bonus = resilience if (resilience is not None and spy_return_n is not None and spy_return_n < 0) else 0.0
                    rs_momentum_score = rs_delta_pct + bonus

            results.append({
                'symbol': m.symbol,
                'rs_spy': round(m.relative_strength_spy, 1),
                'rs_qqq': round(m.relative_strength_qqq, 1) if m.relative_strength_qqq is not None else None,
                'perf_1w': round(m.perf_1w, 1) if m.perf_1w is not None else None,
                'rel_strength_1w': rel_1w,
                'perf_4w': round(m.perf_4w, 1) if m.perf_4w is not None else None,
                'perf_13w': round(m.perf_13w, 1) if m.perf_13w is not None else None,
                'distance_to_high_52w_atr': round(m.distance_to_high_52w_atr, 2) if m.distance_to_high_52w_atr is not None else None,
                'distance_to_ema21_atr': round(m.distance_to_ema21_atr, 2) if m.distance_to_ema21_atr is not None else None,
                'distance_to_ema50_atr': round(m.distance_to_ema50_atr, 2) if m.distance_to_ema50_atr is not None else None,
                'current_price': round(m.current_price, 2) if m.current_price else None,
                'holding_status': self._holding_status(m),
                # momentum block
                'window': window,
                'rs_delta': round(rs_delta, 1) if rs_delta is not None else None,
                'rs_delta_pct': round(rs_delta_pct, 1) if rs_delta_pct is not None else None,
                'stock_return_n': round(stock_return_n, 1) if stock_return_n is not None else None,
                'spy_return_n': round(spy_return_n, 1) if spy_return_n is not None else None,
                'resilience': round(resilience, 1) if resilience is not None else None,
                'held_up': held_up,
                'rs_momentum_score': round(rs_momentum_score, 1) if rs_momentum_score is not None else None,
                'tradingview_url': _tv_url(m.symbol),
            })

        if sort == 'momentum':
            # Momentum desc; rows without a score (no baseline) sink to the bottom.
            results.sort(key=lambda r: (r['rs_momentum_score'] is None, -(r['rs_momentum_score'] or 0)))
        else:
            results.sort(key=lambda r: -(r['rs_spy'] or 0))

        top = results[:40]
        market_groups = await self._fetch_market_groups([r['symbol'] for r in top])
        for r in top:
            r['market_group'] = market_groups.get(r['symbol'])
        return [_clean(r) for r in top]

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

        # Structural gate only: quality universe + Minervini leader + has been basing
        # 6+ weeks. NO absolute tightness cutoff — we RANK by range contraction below.
        q = select(StockMetrics).where(
            StockMetrics.date == latest_date,
            *QUALITY_FILTERS,
            StockMetrics.weeks_in_base >= 6,
        )
        rows = (await self.db.execute(q)).scalars().all()
        candidates = [m for m in rows if is_quality_leader(m)]
        if not candidates:
            return []

        atr_by_sym = {m.symbol: m.atr for m in candidates}
        symbols = list(atr_by_sym.keys())

        # Bulk fetch OHLCV for the contraction window. ~40 calendar days guarantees
        # _BB_RANGE_BARS (20) trading bars per symbol.
        today = date.today()
        px_rows = (await self.db.execute(
            select(StockPrice.symbol, StockPrice.high, StockPrice.low, StockPrice.close, StockPrice.volume)
            .where(
                StockPrice.symbol.in_(symbols),
                StockPrice.date >= today - timedelta(days=40),
            )
            .order_by(StockPrice.symbol, StockPrice.date)
        )).all()
        ohlc_by_sym: dict[str, list[tuple]] = defaultdict(list)
        for sym, hi, lo, cl, vol in px_rows:
            ohlc_by_sym[sym].append((hi, lo, cl, vol))

        results = []
        for m in candidates:
            bars = ohlc_by_sym.get(m.symbol, [])[-_BB_RANGE_BARS:]
            q = _vcp_quality(bars, atr_by_sym.get(m.symbol))
            if q is None:
                continue

            results.append({
                'symbol': m.symbol,
                'vcp_quality': q['vcp_quality'],
                'band_contraction': q['band_contraction'],
                'volume_dryup': q['volume_dryup'],
                'max_gap_atr': q['max_gap_atr'],
                'recent_range_atr': q['recent_range_atr'],
                'is_contracting': q['band_contraction'] > 0,
                'weeks_in_base': m.weeks_in_base,
                'current_distance_to_ema21_atr': round(m.distance_to_ema21_atr, 2) if m.distance_to_ema21_atr is not None else None,
                'vcp_score': round(m.vcp_score, 1) if m.vcp_score is not None else None,  # reference only
                'tradingview_url': _tv_url(m.symbol),
            })

        # Rank by composite VCP quality (higher = cleaner contraction + volume + no event gap).
        results.sort(key=lambda r: -r['vcp_quality'])
        top = results[:_BB_TOP_N]
        market_groups = await self._fetch_market_groups([r['symbol'] for r in top])
        for r in top:
            r['market_group'] = market_groups.get(r['symbol'])
        return [_clean(r) for r in top]

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
