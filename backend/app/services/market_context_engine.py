"""Market Context Engine — participation + leadership + health persistence.

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

from app.models.stock import StockMetrics, TransitionObservation
from app.services.follow_through import (
    BULLISH_TRANSITIONS,
    FT_BASELINE_CAL_DAYS,
    FT_FAMILIES,
    FT_WINDOW_CAL_DAYS,
    FollowThroughAnalysis,
    classify_follow_through,
    classify_provisional,
)
from app.services.market_posture import Posture, compute_posture
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

# Leadership descriptor thresholds — delta_5d_pct = % change in leader DENSITY
# (leaders/universe), universe-normalized so ingest-completeness swings in the
# universe size don't masquerade as leadership expansion/collapse. Same relative
# % scale as the prior raw-count delta, so thresholds carry over unchanged.
_LEADERSHIP_THRESHOLDS = {
    'expanding':           +5.0,
    'thinning':            -5.0,
    'collapsing':         -15.0,
    'climactic_ratio_warn': 0.25,  # >25% climactic leaders → EXHAUSTED override
    'extension_ratio_warn': 0.40,  # >40% extended leaders  → EXHAUSTED override
}

# Minimum density samples before a leadership LEVEL (vs recent norm) is trusted.
_DENSITY_LEVEL_MIN_SAMPLE = 10

# ─── Market health persistence (IBD distribution-day inspired) ────────────────
# Health has MEMORY: repeated deterioration episodes over the recent window keep
# the market unhealthy even when today's descriptors look fine. Damage
# accumulates fast; repair is asymmetric — it requires a sustained clean streak
# (follow-through), never a single good day.
_HEALTH_WINDOW = 20               # trading days of memory
_HEALTH_DELTA_LOOKBACK = 5        # trading-day index offset for per-day deltas
_HEALTH_MIN_CLASSIFIED_DAYS = 10  # fewer classified days → state UNKNOWN

_DAMAGE_PARTICIPATION = frozenset({"NARROWING", "COLLAPSING"})
_DAMAGE_LEADERSHIP = frozenset({"THINNING", "COLLAPSING", "EXHAUSTED"})

_HEALTH_THRESHOLDS = {
    'robust_max_damaged_days': 2,   # ≤2 damaged days AND ≤1 episode → ROBUST
    'robust_max_episodes':     1,
    'damaged_min_days':        8,   # ≥8 of 20 damaged → DAMAGED (heavy total)
    'damaged_recent_window':   5,   # ...or an active cluster right now:
    'damaged_min_recent':      3,   #    ≥3 damaged of the last 5 days → DAMAGED
    'repair_streak_min':       5,   # ≥5 trailing clean days → RECOVERING overlay
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
    delta_5d: float            # leader DENSITY (leaders/universe) delta as % change vs 5d ago
    metrics: dict


@dataclass
class HealthAnalysis:
    state: str                 # ROBUST | FRAGILE | DAMAGED | RECOVERING | UNKNOWN
    episodes: int              # maximal runs of damaged days within the window
    damaged_days: int
    window_days: int           # days actually classified (≤ _HEALTH_WINDOW)
    days_since_last_damage: Optional[int]  # None when no damage in window
    repair_streak: int         # trailing consecutive clean days
    series: list = field(default_factory=list)  # [{date, participation, leadership, damaged}] ascending


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
    health: Optional[HealthAnalysis] = None
    follow_through: Optional[FollowThroughAnalysis] = None
    posture: Optional[Posture] = None  # the one-sentence operational verdict


# In-memory cache keyed by as_of date (Decision 9).
# Value: (MarketContext, cached_at datetime).
_cache: dict = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


class MarketContextEngine:
    """Behavior-based market context engine — participation + leadership + health.

    See openspec/changes/market-context-engine-phase-1/ for full design and decisions.
    The remaining engines (forgiveness, rotation, volatility, follow_through)
    come in future phases.
    """

    ENGINES_PENDING = [
        "forgiveness", "rotation", "volatility"
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
        health = await self._health(as_of)
        follow_through = await self._follow_through(as_of)
        posture = compute_posture(
            participation.descriptor,
            leadership.descriptor,
            health.state,
            damaged_days=health.damaged_days,
            window_days=health.window_days,
            repair_streak=health.repair_streak,
            repair_streak_min=_HEALTH_THRESHOLDS['repair_streak_min'],
            follow_through=follow_through.descriptor,
            ft_delivery=follow_through.delivery_rate,
            ft_baseline=follow_through.baseline_rate,
        )

        ctx = MarketContext(
            as_of=as_of,
            universe_size=universe_size,
            participation=participation,
            leadership=leadership,
            engines_pending=list(self.ENGINES_PENDING),
            participation_history=part_hist,
            leadership_history=lead_hist,
            health=health,
            follow_through=follow_through,
            posture=posture,
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
        universe_today = await self._universe_size(as_of)

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

        # Leader DENSITY (leaders / universe) instead of raw counts: the
        # QUALITY_FILTERS universe swings ±~20% day to day with ingest
        # completeness, so a raw count delta conflates market leadership with
        # how many rows landed in stock_metrics that day. Dividing each count by
        # its own universe cancels that, mirroring the participation engine
        # (which already classifies on breadth ratios, not counts).
        universe_5d = await self._universe_size(date_5d)
        universe_20d = await self._universe_size(date_20d)
        density_today = leader_count / universe_today if universe_today else 0.0
        density_delta_5d_pct = self._density_delta_pct(
            leader_count, universe_today, count_5d, universe_5d
        )
        density_delta_20d_pct = self._density_delta_pct(
            leader_count, universe_today, count_20d, universe_20d
        )

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

        descriptor = self._leadership_descriptor(
            density_delta_5d_pct, climactic_count, extension_count, leader_count
        )
        # Level (density vs recent norm) — orthogonal to the trend descriptor, so
        # a flat "HEALTHY" delta can't be misread as "good" when the level is weak.
        density_level, density_percentile, density_sample = await self._leadership_level(as_of)

        return LeadershipAnalysis(
            descriptor=descriptor,
            delta_5d=round(density_delta_5d_pct, 2),
            metrics={
                'leader_count':                leader_count,
                'leader_count_delta_5d':       delta_5d,
                'leader_count_delta_20d':      delta_20d,
                'leader_density':              round(density_today, 4),
                'leader_density_delta_5d':     round(density_delta_5d_pct, 2),
                'leader_density_delta_20d':    round(density_delta_20d_pct, 2),
                'leader_density_level':        density_level,
                'leader_density_percentile':   round(density_percentile, 2) if density_percentile is not None else None,
                'leader_density_sample_size':  density_sample,
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

    @staticmethod
    def _density_delta_pct(
        count_now: int, universe_now: int, count_then: int, universe_then: int
    ) -> float:
        """% change in leader density (count/universe) between two dates.

        Normalizing each count by its own universe before differencing cancels
        the ±~20% day-to-day swing in universe size driven by ingest
        completeness, so equal leadership across two differently-sized universes
        reads as ~0% — not a phantom expansion/collapse. Returns 0.0 when either
        universe is empty (can't form a ratio).
        """
        if not universe_now or not universe_then:
            return 0.0
        density_now = count_now / universe_now
        density_then = count_then / universe_then
        if density_then <= 0:
            return 0.0
        return (density_now - density_then) / density_then * 100

    @staticmethod
    def _classify_density_level(percentile: Optional[float], sample_size: int) -> str:
        """Map today's leader-density percentile (vs recent history) to a LEVEL.

        Orthogonal to the trend descriptor: the descriptor (EXPANDING/HEALTHY/
        THINNING/COLLAPSING) is a 5-day DELTA, so HEALTHY only means "density
        barely moved" — it can't tell whether the level is good or stuck-at-bad.
        This answers the level question directly: is today's leader density high
        or low vs its own recent norm. Returns UNKNOWN below the min sample.
        """
        if percentile is None or sample_size < _DENSITY_LEVEL_MIN_SAMPLE:
            return "UNKNOWN"
        if percentile >= 0.67:
            return "STRONG"
        if percentile >= 0.33:
            return "NORMAL"
        return "WEAK"

    async def _leadership_level(self, as_of: date, n: int = 20) -> tuple:
        """Return (level, percentile, sample_size) for leader density at as_of.

        Builds the leader-density series over the last `n` trading days (reusing
        the same is_quality_leader definition via _fetch_leaders, the single
        source of truth) and ranks today's density within it. Cached upstream
        per as_of (5-min TTL), so the per-date fetch cost is paid once.
        """
        dates = await self._recent_trading_dates(as_of, n)
        densities: list[float] = []
        today_density: Optional[float] = None
        for d in dates:
            universe = await self._universe_size(d)
            if not universe:
                continue
            density = len(await self._fetch_leaders(d)) / universe
            densities.append(density)
            if d == as_of:
                today_density = density
        if today_density is None or not densities:
            return "UNKNOWN", None, len(densities)
        # Empirical percentile: share of the window at or below today's density.
        percentile = sum(1 for x in densities if x <= today_density) / len(densities)
        return self._classify_density_level(percentile, len(densities)), percentile, len(densities)

    def _leadership_descriptor(
        self,
        delta_pct: float,  # leader-density % change vs 5d ago (universe-normalized)
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

    # ─── Health persistence engine ─────────────────────────────────────────────

    async def _health(self, as_of: date) -> HealthAnalysis:
        """Damage memory over the last _HEALTH_WINDOW trading days.

        Classifies each day with the same participation/leadership thresholds
        as the headline descriptors and runs the damaged flags through the
        health state machine. Rides the same 5-min cache as the other engines.
        """
        raw = await self._daily_dimension_series(
            as_of, _HEALTH_WINDOW + _HEALTH_DELTA_LOOKBACK
        )
        days = self._classify_health_days(raw)[-_HEALTH_WINDOW:]
        verdict = self._health_state([d['damaged'] for d in days])
        return HealthAnalysis(
            state=verdict['state'],
            episodes=verdict['episodes'],
            damaged_days=verdict['damaged_days'],
            window_days=len(days),
            days_since_last_damage=verdict['days_since_last_damage'],
            repair_streak=verdict['repair_streak'],
            series=[
                {
                    'date':          d['date'].isoformat(),
                    'participation': d['participation'],
                    'leadership':    d['leadership'],
                    'damaged':       d['damaged'],
                }
                for d in days
            ],
        )

    async def _daily_dimension_series(self, as_of: date, n: int) -> list:
        """Per-day raw inputs for the health engine over the last n trading days.

        Returns ascending [{date, universe, breadth_ratio, leader_count,
        extension_count}] in 3 grouped/bulk queries total (independent of n) —
        cheaper per day than the per-date fetches in _history/_leadership_level.
        A date with no universe rows yields breadth_ratio=None so the classifier
        can skip it (a data gap must never count as damage).
        """
        dates = await self._recent_trading_dates(as_of, n)
        if not dates:
            return []
        start = dates[0]

        universe_result = await self._db.execute(
            select(StockMetrics.date, func.count().label('cnt'))
            .where(
                StockMetrics.date >= start,
                StockMetrics.date <= as_of,
                *QUALITY_FILTERS,
            )
            .group_by(StockMetrics.date)
        )
        universe_by_date = {row.date: row.cnt for row in universe_result}

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

        # Column projection keeps the bulk fetch narrow; is_quality_leader only
        # does attribute access, so it works on Row objects as well as ORM rows.
        leader_result = await self._db.execute(
            select(
                StockMetrics.date,
                StockMetrics.perf_1y,
                StockMetrics.ema200,
                StockMetrics.current_price,
                StockMetrics.sma50,
                StockMetrics.sma150,
                StockMetrics.sma200,
                StockMetrics.low_52w,
                StockMetrics.high_52w,
                StockMetrics.adr_percent,
                StockMetrics.distance_to_ema50_atr,
                StockMetrics.distance_to_ema21_atr,
            )
            .where(
                StockMetrics.date >= start,
                StockMetrics.date <= as_of,
                *QUALITY_FILTERS,
            )
        )
        leaders_by_date: dict = {}
        extension_by_date: dict = {}
        for row in leader_result:
            if is_quality_leader(row):
                leaders_by_date[row.date] = leaders_by_date.get(row.date, 0) + 1
                if row.distance_to_ema21_atr is not None and row.distance_to_ema21_atr > 3.0:
                    extension_by_date[row.date] = extension_by_date.get(row.date, 0) + 1

        series = []
        for d in dates:
            universe = universe_by_date.get(d, 0)
            series.append({
                'date':            d,
                'universe':        universe,
                'breadth_ratio':   (above_by_date.get(d, 0) / universe) if universe else None,
                'leader_count':    leaders_by_date.get(d, 0),
                'extension_count': extension_by_date.get(d, 0),
            })
        return series

    def _classify_health_days(self, raw: list) -> list:
        """Classify each day of the raw series → [{date, participation,
        leadership, damaged}] for indexes _HEALTH_DELTA_LOOKBACK..N-1, ascending.

        Day i's deltas compare against day i-_HEALTH_DELTA_LOOKBACK — a strict
        trading-day offset, whereas the headline descriptors use a calendar
        proxy (_DAYS_5T + snap). Around holidays the series' last-day descriptor
        may drift ±1-2 days from the headline; acceptable for damage counting.

        The historical EXHAUSTED override uses extension ratio only
        (climactic_count=0): per-day climactic counts would need a ~45-day ADR
        matrix. Known simplification that only under-counts damage on days that
        were exhausted purely climactically.
        """
        days = []
        for i in range(_HEALTH_DELTA_LOOKBACK, len(raw)):
            cur = raw[i]
            prev = raw[i - _HEALTH_DELTA_LOOKBACK]
            if (
                not cur['universe'] or not prev['universe']
                or cur['breadth_ratio'] is None or prev['breadth_ratio'] is None
            ):
                continue
            breadth_pp = (cur['breadth_ratio'] - prev['breadth_ratio']) * 100
            participation = self._participation_descriptor(breadth_pp)
            density_delta = self._density_delta_pct(
                cur['leader_count'], cur['universe'],
                prev['leader_count'], prev['universe'],
            )
            leadership = self._leadership_descriptor(
                density_delta,
                climactic_count=0,
                extension_count=cur['extension_count'],
                leader_count=cur['leader_count'],
            )
            days.append({
                'date':          cur['date'],
                'participation': participation,
                'leadership':    leadership,
                'damaged': (
                    participation in _DAMAGE_PARTICIPATION
                    or leadership in _DAMAGE_LEADERSHIP
                ),
            })
        return days

    @staticmethod
    def _health_state(damaged: list) -> dict:
        """State machine over ascending damaged flags (today last).

        Asymmetric by construction: DAMAGED/FRAGILE can only upgrade to
        RECOVERING via a clean streak of repair_streak_min days, and ROBUST only
        returns once damage ages out of the sliding window — one good day never
        changes the state.
        """
        n = len(damaged)
        damaged_days = sum(1 for f in damaged if f)
        episodes = sum(
            1 for i, f in enumerate(damaged) if f and (i == 0 or not damaged[i - 1])
        )
        repair_streak = 0
        for f in reversed(damaged):
            if f:
                break
            repair_streak += 1
        days_since_last_damage = repair_streak if damaged_days else None

        t = _HEALTH_THRESHOLDS
        if n < _HEALTH_MIN_CLASSIFIED_DAYS:
            state = "UNKNOWN"
        elif (
            damaged_days <= t['robust_max_damaged_days']
            and episodes <= t['robust_max_episodes']
        ):
            state = "ROBUST"
        else:
            recent = damaged[-t['damaged_recent_window']:]
            if (
                damaged_days >= t['damaged_min_days']
                or sum(1 for f in recent if f) >= t['damaged_min_recent']
            ):
                state = "DAMAGED"
            else:
                state = "FRAGILE"
            if repair_streak >= t['repair_streak_min']:
                state = "RECOVERING"

        return {
            'state':                  state,
            'episodes':               episodes,
            'damaged_days':           damaged_days,
            'repair_streak':          repair_streak,
            'days_since_last_damage': days_since_last_damage,
        }

    # ─── Follow-through engine ─────────────────────────────────────────────────

    async def _follow_through(self, as_of: date) -> FollowThroughAnalysis:
        """Is the market paying recent bullish signals? 3 grouped/bulk queries.

        Note on historical reconstruction (analyze_as_of): outcome_status for
        signals near a past as_of resolved AFTER that date, so a reconstructed
        follow-through has mild lookahead. Acceptable for journal backfill
        (it shows what actually happened); the live path has no such issue.
        """
        window_start = as_of - timedelta(days=FT_WINDOW_CAL_DAYS)
        baseline_start = window_start - timedelta(days=FT_BASELINE_CAL_DAYS)

        # Window: signal counts per transition_type × outcome_status.
        window_result = await self._db.execute(
            select(
                TransitionObservation.transition_type,
                TransitionObservation.outcome_status,
                func.count().label('cnt'),
            )
            .where(
                TransitionObservation.date_detected > window_start,
                TransitionObservation.date_detected <= as_of,
                TransitionObservation.transition_type.in_(BULLISH_TRANSITIONS),
            )
            .group_by(
                TransitionObservation.transition_type,
                TransitionObservation.outcome_status,
            )
        )
        by_type_status: dict = {}
        for row in window_result:
            by_type_status[(row.transition_type, row.outcome_status)] = row.cnt

        def _sum(statuses, types=BULLISH_TRANSITIONS) -> int:
            return sum(
                cnt for (t, s), cnt in by_type_status.items()
                if s in statuses and t in types
            )

        success = _sum({'SUCCESS'})
        failure = _sum({'FAILURE'})
        neutral = _sum({'NEUTRAL'})
        pending = _sum({'PENDING'})
        resolved = success + failure + neutral
        signals = resolved + pending + _sum({'INSUFFICIENT_DATA'})

        # Provisional layer: early proxies on the window's PENDING signals.
        prov_result = await self._db.execute(
            select(
                TransitionObservation.pct_5d,
                TransitionObservation.price_at_detection,
                TransitionObservation.atr_at_detection,
            )
            .where(
                TransitionObservation.date_detected > window_start,
                TransitionObservation.date_detected <= as_of,
                TransitionObservation.transition_type.in_(BULLISH_TRANSITIONS),
                TransitionObservation.outcome_status == 'PENDING',
            )
        )
        prov_on_track = prov_failing = prov_unclear = 0
        for row in prov_result:
            verdict = classify_provisional(
                row.pct_5d, row.price_at_detection, row.atr_at_detection
            )
            if verdict == 'on_track':
                prov_on_track += 1
            elif verdict == 'failing':
                prov_failing += 1
            else:
                prov_unclear += 1

        # Baseline: resolved outcomes detected before the window.
        baseline_result = await self._db.execute(
            select(TransitionObservation.outcome_status, func.count().label('cnt'))
            .where(
                TransitionObservation.date_detected > baseline_start,
                TransitionObservation.date_detected <= window_start,
                TransitionObservation.transition_type.in_(BULLISH_TRANSITIONS),
                TransitionObservation.outcome_status.in_(('SUCCESS', 'FAILURE', 'NEUTRAL')),
            )
            .group_by(TransitionObservation.outcome_status)
        )
        baseline_counts = {row.outcome_status: row.cnt for row in baseline_result}

        verdict = classify_follow_through(
            success=success,
            failure=failure,
            neutral=neutral,
            baseline_success=baseline_counts.get('SUCCESS', 0),
            baseline_failure=baseline_counts.get('FAILURE', 0),
            baseline_neutral=baseline_counts.get('NEUTRAL', 0),
            prov_on_track=prov_on_track,
            prov_failing=prov_failing,
        )

        per_family = {}
        for family, types in FT_FAMILIES.items():
            f_success = _sum({'SUCCESS'}, types)
            f_resolved = f_success + _sum({'FAILURE', 'NEUTRAL'}, types)
            per_family[family] = {
                'signals':  f_resolved + _sum({'PENDING', 'INSUFFICIENT_DATA'}, types),
                'success':  f_success,
                'resolved': f_resolved,
                'delivery': round(f_success / f_resolved, 4) if f_resolved else None,
            }

        return FollowThroughAnalysis(
            descriptor=verdict['descriptor'],
            basis=verdict['basis'],
            window_days=FT_WINDOW_CAL_DAYS,
            signals=signals,
            resolved=resolved,
            success=success,
            failure=failure,
            neutral=neutral,
            pending=pending,
            delivery_rate=round(verdict['delivery_rate'], 4) if verdict['delivery_rate'] is not None else None,
            baseline_rate=round(verdict['baseline_rate'], 4) if verdict['baseline_rate'] is not None else None,
            baseline_n=sum(baseline_counts.values()),
            delta_pp=round(verdict['delta_pp'], 2) if verdict['delta_pp'] is not None else None,
            provisional_on_track=prov_on_track,
            provisional_failing=prov_failing,
            provisional_unclear=prov_unclear,
            per_family=per_family,
        )
