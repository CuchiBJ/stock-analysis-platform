"""Market Context Engine — Phase 1: participation + leadership.

Multi-dimensional behavior-based market read. Replaces single-label regime
classification with orthogonal behavior dimensions.

Change: openspec/changes/market-context-engine-phase-1/
Design: openspec/changes/market-context-engine-phase-1/design.md
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockMetrics
from app.services.quality_leader_gate import is_quality_leader
from app.services.universe_filters import QUALITY_FILTERS

# Calendar-day proxies for trading-day windows (Decision 5 in design).
# ±2 days max drift across normal holiday weeks — acceptable for descriptor reporting.
_DAYS_5T = 7    # 5 trading days ≈ 7 calendar days
_DAYS_10T = 14  # 10 trading days ≈ 14 calendar days
_DAYS_20T = 28  # 20 trading days ≈ 28 calendar days

# Participation descriptor thresholds — breadth_momentum_5d in percentage points.
# Heuristic cutoffs; recalibration milestone August 2026 when 90d of
# transition_observations are available.
_PARTICIPATION_THRESHOLDS = {
    'expanding':  +5.0,    # delta_5d > +5pp  → EXPANDING
    'stable_min': -5.0,    # -5pp ≤ x ≤ +5pp → STABLE
    'narrowing':  -15.0,   # -15pp ≤ x < -5pp → NARROWING
                            # below -15pp       → COLLAPSING
}

# Leadership descriptor thresholds — delta_5d_pct = % change in leader count.
_LEADERSHIP_THRESHOLDS = {
    'expanding':           +5.0,
    'thinning':            -5.0,
    'collapsing':         -15.0,
    'climactic_ratio_warn': 0.25,  # >25% climactic leaders → EXHAUSTED override
    'extension_ratio_warn': 0.40,  # >40% extended leaders  → EXHAUSTED override
}


@dataclass
class ParticipationAnalysis:
    descriptor: str
    delta_5d: float            # breadth_momentum_5d expressed in percentage points
    delta_sample_size_20d: int
    metrics: dict


@dataclass
class LeadershipAnalysis:
    descriptor: str
    delta_5d: float            # leader_count delta as % change
    metrics: dict


@dataclass
class MarketContext:
    as_of: date
    universe_size: int
    participation: ParticipationAnalysis
    leadership: LeadershipAnalysis
    engines_pending: list
    # Short trajectory (last N trading days, ascending) so the bar can show the
    # evolution of each engine, not just today's value + a 5d delta.
    participation_history: list = field(default_factory=list)  # [{date, value}] breadth ratio
    leadership_history: list = field(default_factory=list)      # [{date, value}] leader count


# In-memory cache keyed by as_of date (Decision 9).
# Value: (MarketContext, cached_at datetime).
_cache: dict = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


class MarketContextEngine:
    """Behavior-based market context engine — Phase 1 (participation + leadership).

    See openspec/changes/market-context-engine-phase-1/ for full design and decisions.
    The other five engines (persistence, forgiveness, rotation, volatility,
    follow_through) come in future phases.
    """

    ENGINES_PENDING = [
        "persistence", "forgiveness", "rotation", "volatility", "follow_through"
    ]

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def analyze(self) -> Optional[MarketContext]:
        """Return MarketContext for the latest as_of date, or None if DB is empty."""
        as_of = await self._latest_date()
        if as_of is None:
            return None
        return await self._analyze_for(as_of, use_cache=True)

    async def analyze_as_of(self, target: date) -> Optional[MarketContext]:
        """Reconstruct the market context as it stood on `target`.

        `target` is snapped to the most recent trading date with metrics (<=
        target), so it works for weekends/holidays and for trade entry dates.
        Returns None when no metrics exist at or before `target` — i.e. the date
        predates the StockMetrics history, so the regime can't be reconstructed.

        Caching is bypassed: historical reconstruction (e.g. journal backfill)
        sweeps many one-shot dates and must not evict the live "today" entry.
        """
        as_of = await self._resolve_trading_date(target)
        if as_of is None:
            return None
        return await self._analyze_for(as_of, use_cache=False)

    async def _analyze_for(self, as_of: date, *, use_cache: bool) -> MarketContext:
        # Cache hit within TTL
        if use_cache and as_of in _cache:
            ctx, cached_at = _cache[as_of]
            age = (datetime.utcnow() - cached_at).total_seconds()
            if age < _CACHE_TTL_SECONDS:
                return ctx

        universe_size = await self._universe_size(as_of)
        participation = await self._participation(as_of)
        leadership = await self._leadership(as_of)
        part_hist, lead_hist = await self._history(as_of)

        ctx = MarketContext(
            as_of=as_of,
            universe_size=universe_size,
            participation=participation,
            leadership=leadership,
            engines_pending=list(self.ENGINES_PENDING),
            participation_history=part_hist,
            leadership_history=lead_hist,
        )
        if use_cache:
            # Evict stale entries for older dates — only the live path caches, so
            # this keeps a single hot "today" entry without thrashing on backfill.
            for k in list(_cache.keys()):
                if k != as_of:
                    del _cache[k]
            _cache[as_of] = (ctx, datetime.utcnow())
        return ctx

    @classmethod
    def clear_cache(cls) -> None:
        """Clear in-memory cache — used in tests."""
        _cache.clear()

    # ─── Shared helpers ────────────────────────────────────────────────────────

    async def _latest_date(self) -> Optional[date]:
        result = await self._db.execute(select(func.max(StockMetrics.date)))
        return result.scalar_one_or_none()

    async def _resolve_trading_date(self, target: date) -> Optional[date]:
        """Snap a calendar-day target to the most recent date that actually has
        StockMetrics rows (<= target).

        The N-days-ago comparison dates are computed as raw calendar offsets
        (Decision 5), so they can land on a weekend or market holiday with no
        data — silently breaking the comparison (e.g. rs_persistence collapsing
        to 0.0 because the lookback date has zero leaders). Resolving to the
        nearest available trading date prevents that.
        """
        result = await self._db.execute(
            select(func.max(StockMetrics.date)).where(StockMetrics.date <= target)
        )
        return result.scalar_one_or_none()

    async def _universe_size(self, as_of: date) -> int:
        result = await self._db.execute(
            select(func.count()).select_from(StockMetrics)
            .where(StockMetrics.date == as_of, *QUALITY_FILTERS)
        )
        return result.scalar_one() or 0

    async def _count_where(self, as_of: date, *extra_filters) -> int:
        result = await self._db.execute(
            select(func.count()).select_from(StockMetrics)
            .where(StockMetrics.date == as_of, *QUALITY_FILTERS, *extra_filters)
        )
        return result.scalar_one() or 0

    async def _recent_trading_dates(self, as_of: date, n: int) -> list:
        """Last n distinct trading dates (<= as_of) with metrics, ascending."""
        result = await self._db.execute(
            select(StockMetrics.date)
            .where(StockMetrics.date <= as_of)
            .distinct()
            .order_by(StockMetrics.date.desc())
            .limit(n)
        )
        dates = [r[0] for r in result.all()]
        return list(reversed(dates))

    async def _history(self, as_of: date, n: int = 10) -> tuple:
        """Build the short trajectory for participation (breadth ratio) and
        leadership (leader count) over the last n trading days.

        Cheap and cached: runs once per as_of inside analyze() (5-min TTL),
        reusing the same breadth/leader definitions as the live values.
        """
        dates = await self._recent_trading_dates(as_of, n)
        part_hist: list = []
        lead_hist: list = []
        for d in dates:
            ratio, _ = await self._breadth_above_ema21(d)
            leaders = await self._fetch_leaders(d)
            part_hist.append({"date": d.isoformat(), "value": round(ratio, 4)})
            lead_hist.append({"date": d.isoformat(), "value": len(leaders)})
        return part_hist, lead_hist

    async def _breadth_above_ema21(self, as_of: date) -> tuple:
        """Return (ratio [0,1], universe_size) for breadth above EMA21 at as_of."""
        universe = await self._universe_size(as_of)
        if universe == 0:
            return 0.0, 0
        above = await self._count_where(
            as_of,
            StockMetrics.distance_to_ema21.isnot(None),
            StockMetrics.distance_to_ema21 >= 0,
        )
        return above / universe, universe

    # ─── Participation engine ──────────────────────────────────────────────────

    async def _participation(self, as_of: date) -> ParticipationAnalysis:
        universe = await self._universe_size(as_of)
        if universe == 0:
            empty_metrics = {
                'breadth_above_ema21':       0.0,
                'breadth_above_ema50':       0.0,
                'breadth_above_ema200':      0.0,
                'breadth_momentum_5d':       0.0,
                'breadth_momentum_20d':      0.0,
                'near_highs_count':          0,
                'near_lows_count':           0,
                'highs_lows_ratio':          0.0,
                'participation_persistence': 0.0,
            }
            return ParticipationAnalysis(
                descriptor="COLLAPSING",
                delta_5d=0.0,
                delta_sample_size_20d=0,
                metrics=empty_metrics,
            )

        # Current breadth counts
        above_ema21 = await self._count_where(
            as_of,
            StockMetrics.distance_to_ema21.isnot(None),
            StockMetrics.distance_to_ema21 >= 0,
        )
        above_ema50 = await self._count_where(
            as_of,
            StockMetrics.distance_to_ema50.isnot(None),
            StockMetrics.distance_to_ema50 >= 0,
        )
        # breadth_above_ema200 uses stocks with both price and ema200 as denominator
        total_with_ema200_result = await self._db.execute(
            select(func.count()).select_from(StockMetrics)
            .where(
                StockMetrics.date == as_of,
                *QUALITY_FILTERS,
                StockMetrics.current_price.isnot(None),
                StockMetrics.ema200.isnot(None),
            )
        )
        total_with_ema200 = total_with_ema200_result.scalar_one() or 0
        above_ema200_result = await self._db.execute(
            select(func.count()).select_from(StockMetrics)
            .where(
                StockMetrics.date == as_of,
                *QUALITY_FILTERS,
                StockMetrics.current_price.isnot(None),
                StockMetrics.ema200.isnot(None),
                StockMetrics.current_price > StockMetrics.ema200,
            )
        )
        above_ema200 = above_ema200_result.scalar_one() or 0

        near_highs = await self._count_where(
            as_of,
            StockMetrics.distance_to_high_52w_atr.isnot(None),
            StockMetrics.distance_to_high_52w_atr >= -1.0,
        )
        # Proxy for near 52w low: distance_to_high_52w_atr <= -6.0
        # (no distance_to_low_52w_atr column yet — see design Non-Goals for upgrade path)
        near_lows = await self._count_where(
            as_of,
            StockMetrics.distance_to_high_52w_atr.isnot(None),
            StockMetrics.distance_to_high_52w_atr <= -6.0,
        )

        breadth_ema21_ratio = above_ema21 / universe
        breadth_ema50_ratio = above_ema50 / universe
        breadth_ema200_ratio = (above_ema200 / total_with_ema200) if total_with_ema200 > 0 else 0.0
        highs_lows_ratio = near_highs / max(near_lows, 1)

        # Historical breadth for momentum (Decision 6: use historical date's universe).
        # Snap calendar offsets to the nearest available trading date so a weekend
        # or holiday lookback doesn't silently zero out the comparison.
        date_5d_ago = await self._resolve_trading_date(as_of - timedelta(days=_DAYS_5T))
        date_20d_ago = await self._resolve_trading_date(as_of - timedelta(days=_DAYS_20T))

        breadth_5d_ago, _ = await self._breadth_above_ema21(date_5d_ago)
        breadth_20d_ago, universe_20d = await self._breadth_above_ema21(date_20d_ago)

        momentum_5d = breadth_ema21_ratio - breadth_5d_ago
        momentum_20d = breadth_ema21_ratio - breadth_20d_ago

        persistence = await self._participation_persistence(as_of)

        return ParticipationAnalysis(
            descriptor=self._participation_descriptor(momentum_5d * 100),
            delta_5d=round(momentum_5d * 100, 2),
            delta_sample_size_20d=universe_20d,
            metrics={
                'breadth_above_ema21':       round(breadth_ema21_ratio, 4),
                'breadth_above_ema50':       round(breadth_ema50_ratio, 4),
                'breadth_above_ema200':      round(breadth_ema200_ratio, 4),
                'breadth_momentum_5d':       round(momentum_5d, 4),
                'breadth_momentum_20d':      round(momentum_20d, 4),
                'near_highs_count':          near_highs,
                'near_lows_count':           near_lows,
                'highs_lows_ratio':          round(highs_lows_ratio, 2),
                'participation_persistence': round(persistence, 4),
            },
        )

    async def _participation_persistence(self, as_of: date, days: int = 20) -> float:
        """Stddev of breadth_above_ema21 over last `days` calendar days (two grouped queries)."""
        start = as_of - timedelta(days=days)

        # Count above EMA21 per date
        above_result = await self._db.execute(
            select(StockMetrics.date, func.count().label('cnt'))
            .where(
                StockMetrics.date >= start,
                StockMetrics.date <= as_of,
                StockMetrics.distance_to_ema21.isnot(None),
                StockMetrics.distance_to_ema21 >= 0,
                *QUALITY_FILTERS,
            )
            .group_by(StockMetrics.date)
        )
        above_by_date = {row.date: row.cnt for row in above_result}

        # Total universe per date
        total_result = await self._db.execute(
            select(StockMetrics.date, func.count().label('cnt'))
            .where(
                StockMetrics.date >= start,
                StockMetrics.date <= as_of,
                *QUALITY_FILTERS,
            )
            .group_by(StockMetrics.date)
        )
        ratios = []
        for row in total_result:
            if row.cnt > 0:
                above = above_by_date.get(row.date, 0)
                ratios.append(above / row.cnt)

        if len(ratios) < 2:
            return 0.0
        return statistics.stdev(ratios)

    def _participation_descriptor(self, momentum_pp: float) -> str:
        t = _PARTICIPATION_THRESHOLDS
        if momentum_pp > t['expanding']:
            return "EXPANDING"
        if momentum_pp >= t['stable_min']:
            return "STABLE"
        if momentum_pp >= t['narrowing']:
            return "NARROWING"
        return "COLLAPSING"

    # ─── Leadership engine ─────────────────────────────────────────────────────

    async def _fetch_leaders(self, as_of: date) -> list:
        """Fetch rows at as_of passing QUALITY_FILTERS, then filter via is_quality_leader in Python."""
        result = await self._db.execute(
            select(StockMetrics)
            .where(StockMetrics.date == as_of, *QUALITY_FILTERS)
        )
        rows = result.scalars().all()
        return [m for m in rows if is_quality_leader(m)]

    async def _leadership(self, as_of: date) -> LeadershipAnalysis:
        leaders_today = await self._fetch_leaders(as_of)
        leader_count = len(leaders_today)

        # Snap calendar offsets to the nearest available trading date — otherwise a
        # holiday lookback (e.g. Memorial Day) returns zero leaders and corrupts
        # rs_persistence / turnover / deltas.
        date_5d = await self._resolve_trading_date(as_of - timedelta(days=_DAYS_5T))
        date_10d = await self._resolve_trading_date(as_of - timedelta(days=_DAYS_10T))
        date_20d = await self._resolve_trading_date(as_of - timedelta(days=_DAYS_20T))

        leaders_5d = await self._fetch_leaders(date_5d)
        leaders_10d = await self._fetch_leaders(date_10d)
        leaders_20d = await self._fetch_leaders(date_20d)

        count_5d = len(leaders_5d)
        count_20d = len(leaders_20d)

        delta_5d = leader_count - count_5d
        delta_20d = leader_count - count_20d

        def safe_avg(vals: list) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        pullback_avg = safe_avg([
            m.pullback_quality_score for m in leaders_today
            if m.pullback_quality_score is not None
        ])
        tightness_avg = safe_avg([
            m.weekly_tightness for m in leaders_today
            if m.weekly_tightness is not None
        ])
        vol_contraction_avg = safe_avg([
            m.weekly_volatility_contraction for m in leaders_today
            if m.weekly_volatility_contraction is not None
        ])

        # RS persistence: % of today's RS-strong leaders also RS-strong 10 trading days ago
        rs_persistence = self._rs_persistence(leaders_today, leaders_10d)

        # Extension: leaders with distance_to_ema21_atr > 3.0
        extension_count = sum(
            1 for m in leaders_today
            if m.distance_to_ema21_atr is not None and m.distance_to_ema21_atr > 3.0
        )

        # Climactic: current ADR > 2× their 20-day average ADR
        climactic_count = await self._climactic_count(leaders_today, as_of)

        # Turnover: symmetric difference of today vs 5d-ago leader symbol sets
        symbols_today = {m.symbol for m in leaders_today}
        symbols_5d = {m.symbol for m in leaders_5d}
        leadership_turnover_5d = len(symbols_today.symmetric_difference(symbols_5d))

        delta_5d_pct = (delta_5d / count_5d * 100) if count_5d > 0 else 0.0
        descriptor = self._leadership_descriptor(
            delta_5d_pct, climactic_count, extension_count, leader_count
        )

        return LeadershipAnalysis(
            descriptor=descriptor,
            delta_5d=round(delta_5d_pct, 2),
            metrics={
                'leader_count':                leader_count,
                'leader_count_delta_5d':       delta_5d,
                'leader_count_delta_20d':      delta_20d,
                'leader_pullback_quality_avg': round(pullback_avg, 2),
                'leader_tightness_avg':        round(tightness_avg, 4),
                'leader_vol_contraction_avg':  round(vol_contraction_avg, 4),
                'leader_rs_persistence_10d':   round(rs_persistence, 4),
                'leader_extension_count':      extension_count,
                'leader_climactic_count':      climactic_count,
                'leadership_turnover_5d':      leadership_turnover_5d,
            },
        )

    def _rs_persistence(self, today: list, past: list) -> float:
        """% of today's RS-strong leaders (RS_SPY >= 105) that were also RS-strong 10d ago."""
        rs_strong_today = {
            m.symbol for m in today
            if m.relative_strength_spy is not None and m.relative_strength_spy >= 105
        }
        if not rs_strong_today:
            return 0.0
        rs_strong_past = {
            m.symbol for m in past
            if m.relative_strength_spy is not None and m.relative_strength_spy >= 105
        }
        return len(rs_strong_today & rs_strong_past) / len(rs_strong_today)

    async def _climactic_count(self, leaders: list, as_of: date) -> int:
        """Count leaders where current ADR > 2× their 20-day average ADR."""
        if not leaders:
            return 0

        symbols = [m.symbol for m in leaders]
        start = as_of - timedelta(days=_DAYS_20T)

        result = await self._db.execute(
            select(StockMetrics.symbol, func.avg(StockMetrics.adr_percent).label('avg_adr'))
            .where(
                StockMetrics.symbol.in_(symbols),
                StockMetrics.date >= start,
                StockMetrics.date <= as_of,
                StockMetrics.adr_percent.isnot(None),
            )
            .group_by(StockMetrics.symbol)
        )
        avg_adr_by_symbol = {row.symbol: row.avg_adr for row in result}

        today_adr = {m.symbol: m.adr_percent for m in leaders if m.adr_percent is not None}
        count = 0
        for symbol, today_val in today_adr.items():
            avg = avg_adr_by_symbol.get(symbol)
            if avg and avg > 0 and today_val > 2 * avg:
                count += 1
        return count

    def _leadership_descriptor(
        self,
        delta_pct: float,
        climactic_count: int,
        extension_count: int,
        leader_count: int,
    ) -> str:
        # Exhaustion overrides direction — top-of-trend signal (Decision 8)
        if leader_count > 0:
            climactic_ratio = climactic_count / leader_count
            extension_ratio = extension_count / leader_count
            if (climactic_ratio > _LEADERSHIP_THRESHOLDS['climactic_ratio_warn'] or
                    extension_ratio > _LEADERSHIP_THRESHOLDS['extension_ratio_warn']):
                return "EXHAUSTED"

        t = _LEADERSHIP_THRESHOLDS
        if delta_pct > t['expanding']:
            return "EXPANDING"
        if delta_pct >= t['thinning']:
            return "HEALTHY"
        if delta_pct >= t['collapsing']:
            return "THINNING"
        return "COLLAPSING"
