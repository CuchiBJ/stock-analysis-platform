"""Invalidation-first selection and ranking for Setups Forming."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import SetupStateLog, Stock, StockMetrics
from app.services.context_decision_filter import compute_context_multiplier
from app.services.group_strength_service import GroupMultiplier, compute_group_multiplier, fetch_current_group_strengths
from app.services.live_transition_service import LiveTransitionSelector, day_change_pct
from app.services.market_context_engine import MarketContextEngine
from app.services.setup_invalidation_engine import InvalidationReason, SetupInvalidationEngine
from app.services.setup_lifecycle_engine import SetupLifecycleEngine, SetupState


MIN_FORMATION_SCORE = 55.0
MAX_FORMATION_RESULTS = 6
FORMATION_WEIGHTS = {
    "trigger_readiness": 0.35,
    "structural_integrity": 0.25,
    "orderliness_contraction": 0.20,
    "relative_strength_trajectory": 0.10,
    "regime_group_alignment": 0.10,
}


@dataclass(frozen=True)
class FormationCriterion:
    key: str
    name: str
    actual: Any
    threshold: Any
    passes: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CandidateEvaluation:
    symbol: str
    eligible: bool
    criteria: list[FormationCriterion]
    rejection_reasons: list[str]
    state: SetupState
    score: float | None = None
    score_breakdown: dict[str, Any] | None = None
    trigger_distance: float = float("inf")
    structural_score: float = 0.0
    response: dict[str, Any] | None = None
    promoted_to_feed: bool = False
    rank: int | None = None


def evaluate_formation_eligibility(
    metrics: StockMetrics,
    *,
    market_cap: float | None,
    state: SetupState,
    invalidation_reasons: list[InvalidationReason],
) -> tuple[list[FormationCriterion], list[str]]:
    """Apply institutional gates without a near-high or EMA membership cliff."""
    price = metrics.current_price
    hard_invalidations = [reason for reason in invalidation_reasons if reason != InvalidationReason.RS_DETERIORATION]
    raw = [
        ("market_cap", "Market cap at least $600M", market_cap, 600_000_000, market_cap is not None and market_cap >= 600_000_000),
        ("min_volume", "10-day average volume at least 800k", metrics.avg_volume_10d, 800_000, metrics.avg_volume_10d is not None and metrics.avg_volume_10d >= 800_000),
        ("min_adr", "ADR at least 4%", metrics.adr_percent, 4.0, metrics.adr_percent is not None and metrics.adr_percent >= 4.0),
        ("min_price", "Price at least $5", price, 5.0, price is not None and price >= 5.0),
        ("perf_1y", "One-year performance above 30%", metrics.perf_1y, "> 30", metrics.perf_1y is not None and metrics.perf_1y > 30.0),
        ("price_above_ema50", "Price above EMA50", price, metrics.ema50, price is not None and metrics.ema50 is not None and price > metrics.ema50),
        ("price_above_sma150", "Price above SMA150", price, metrics.sma150, price is not None and metrics.sma150 is not None and price > metrics.sma150),
        ("sma150_above_sma200", "SMA150 above SMA200", metrics.sma150, metrics.sma200, metrics.sma150 is not None and metrics.sma200 is not None and metrics.sma150 > metrics.sma200),
        ("above_52w_low", "Price at least 1.5 times the 52-week low", price, metrics.low_52w * 1.5 if metrics.low_52w is not None else None, price is not None and metrics.low_52w is not None and price >= metrics.low_52w * 1.5),
        ("lifecycle_intact", "Lifecycle is intact", state.value, "not broken/distribution", state not in (SetupState.BROKEN, SetupState.DISTRIBUTION)),
        ("invalidation_clear", "No hard setup invalidation", [reason.value for reason in hard_invalidations], [], not hard_invalidations),
    ]
    criteria = [FormationCriterion(*item) for item in raw]
    reasons = [criterion.key for criterion in criteria if not criterion.passes]
    reasons.extend(reason.value for reason in hard_invalidations)
    return criteria, list(dict.fromkeys(reasons))


def _trigger_gap(value: float | None) -> float | None:
    if value is None:
        return None
    if -1.0 <= value <= 0.5:
        return 0.0
    return min(abs(value + 1.0), abs(value - 0.5))


def _nearest_trigger(metrics: StockMetrics) -> tuple[str, float | None, float | None]:
    options = [
        ("EMA9", metrics.distance_to_ema9_atr, metrics.distance_to_ema9),
        ("EMA21", metrics.distance_to_ema21_atr, metrics.distance_to_ema21),
    ]
    available = [option for option in options if option[1] is not None]
    return min(available, key=lambda option: _trigger_gap(option[1]) or 0.0) if available else ("EMA", None, None)


def _bucket(value: float | None, boundaries: list[tuple[float, float]], default: float = 50.0) -> float:
    if value is None:
        return default
    return next(score for maximum, score in boundaries if value <= maximum)


def calculate_rs_trajectory_score(current: float | None, baseline: float | None) -> tuple[float, dict[str, Any]]:
    if current is None or baseline in (None, 0):
        return 50.0, {"current_rs": current, "baseline_rs": baseline, "rs_delta_pct": None, "status": "missing_history_neutral"}
    delta = (current - baseline) / baseline * 100.0
    if delta >= 2:
        score, status = 100.0, "improving"
    elif delta >= 0.5:
        score, status = 80.0, "improving"
    elif delta > -0.5:
        score, status = 60.0, "stable"
    elif delta > -2:
        score, status = 30.0, "deteriorating"
    else:
        score, status = 0.0, "deteriorating"
    return score, {"current_rs": round(current, 2), "baseline_rs": round(baseline, 2), "rs_delta_pct": round(delta, 2), "status": status}


def calculate_formation_score(
    metrics: StockMetrics,
    *,
    previous: StockMetrics | None,
    rs_baseline: float | None,
    regime: str,
    group: GroupMultiplier,
) -> dict[str, Any]:
    """Return the deterministic 35/25/20/10/10 score and raw evidence."""
    trigger, current_distance, _ = _nearest_trigger(metrics)
    current_gap = _trigger_gap(current_distance)
    previous_distance = None if previous is None else (previous.distance_to_ema9_atr if trigger == "EMA9" else previous.distance_to_ema21_atr)
    previous_gap = _trigger_gap(previous_distance)
    proximity = _bucket(current_gap, [(0, 100), (0.25, 90), (0.75, 80), (1.5, 65), (2.5, 45), (4, 25), (float("inf"), 10)])
    convergence = None if current_gap is None or previous_gap is None else previous_gap - current_gap
    if convergence is None:
        direction_score, direction = 50.0, "missing_history_neutral"
    elif convergence >= 0.25:
        direction_score, direction = 100.0, "converging"
    elif convergence >= 0.05:
        direction_score, direction = 75.0, "converging"
    elif convergence > -0.05:
        direction_score, direction = 50.0, "stable"
    elif convergence > -0.5:
        direction_score, direction = 30.0, "diverging"
    else:
        direction_score, direction = 10.0, "diverging"
    trigger_score = 0.7 * proximity + 0.3 * direction_score

    weekly = 50.0 if metrics.weekly_trend_quality is None else max(0.0, min(100.0, metrics.weekly_trend_quality * 100))
    ema50 = _bucket(None if metrics.distance_to_ema50_atr is None else -metrics.distance_to_ema50_atr, [(-1.5, 100), (-0.5, 85), (0, 70), (1, 50), (float("inf"), 25)])
    structural = 0.65 * weekly + 0.25 * ema50 + 10.0

    tightness = 50.0 if metrics.weekly_tightness is None else max(0.0, min(100.0, metrics.weekly_tightness * 100))
    volatility = 50.0 if metrics.weekly_volatility_contraction is None else max(0.0, min(100.0, metrics.weekly_volatility_contraction * 100))
    volume = 50.0 if metrics.volume_contraction is None else max(0.0, min(100.0, metrics.volume_contraction * 100 if metrics.volume_contraction <= 1 else metrics.volume_contraction))
    rv = metrics.relative_volume
    dryup = 50.0 if rv is None else 100.0 if rv <= 0.6 else 85.0 if rv <= 0.8 else 65.0 if rv <= 1 else 40.0 if rv <= 1.2 else 15.0
    orderliness = (tightness + volatility + volume + dryup) / 4

    rs_score, rs_inputs = calculate_rs_trajectory_score(metrics.relative_strength_spy, rs_baseline)
    regime_score = {"risk_on": 100.0, "choppy": 65.0, "transition": 50.0, "risk_off": 25.0}.get(regime, 50.0)
    group_score = {"leader": 90.0, "neutral": 60.0, "weak": 30.0}[group.badge]
    alignment = (regime_score + group_score) / 2
    raw = {
        "trigger_readiness": (trigger_score, {"next_trigger": trigger, "current_distance_atr": current_distance, "previous_distance_atr": previous_distance, "trigger_gap_atr": current_gap, "convergence_atr": convergence, "direction": direction, "proximity_score": proximity, "direction_score": direction_score}),
        "structural_integrity": (structural, {"weekly_trend_quality": metrics.weekly_trend_quality, "distance_to_ema50_atr": metrics.distance_to_ema50_atr, "weekly_score": weekly, "ema50_buffer_score": ema50, "long_term_stack_intact": True}),
        "orderliness_contraction": (orderliness, {"weekly_tightness": metrics.weekly_tightness, "weekly_volatility_contraction": metrics.weekly_volatility_contraction, "volume_contraction": metrics.volume_contraction, "relative_volume": rv, "dryup_score": dryup}),
        "relative_strength_trajectory": (rs_score, rs_inputs),
        "regime_group_alignment": (alignment, {"regime": regime, "regime_score": regime_score, "group_badge": group.badge, "group_score": group_score}),
    }
    components: dict[str, Any] = {}
    total = 0.0
    for name, (score, inputs) in raw.items():
        contribution = score * FORMATION_WEIGHTS[name]
        total += contribution
        components[name] = {"score": round(score, 2), "weight": FORMATION_WEIGHTS[name], "contribution": round(contribution, 2), "inputs": inputs}
    return {"raw_score": round(total, 2), "final_score": round(max(0.0, min(100.0, total)), 2), "components": components}


async def get_five_session_rs_baselines(db: AsyncSession, metrics_rows: list[StockMetrics]) -> dict[str, float]:
    if not metrics_rows:
        return {}
    latest_date = max(row.date for row in metrics_rows)
    dates = (await db.execute(select(StockMetrics.date).where(StockMetrics.date <= latest_date).distinct().order_by(StockMetrics.date.desc()).limit(6))).scalars().all()
    if len(dates) < 6:
        return {}
    rows = (await db.execute(select(StockMetrics.symbol, StockMetrics.relative_strength_spy).where(StockMetrics.symbol.in_([row.symbol for row in metrics_rows]), StockMetrics.date == dates[5], StockMetrics.relative_strength_spy.isnot(None)))).all()
    return dict(rows)


class FormationSetupService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_forming_setups(self, limit: int | None = MAX_FORMATION_RESULTS) -> dict[str, Any]:
        if limit is not None:
            limit = min(MAX_FORMATION_RESULTS, max(1, limit))
        evaluations, context = await self._analyze()
        ranked = self._rank(evaluations)
        response_limit = len(ranked) if limit is None else limit
        cutoff = ranked[response_limit - 1].score if response_limit and len(ranked) >= response_limit else None
        for index, item in enumerate(ranked, 1):
            item.rank = index
            if item.response is not None:
                item.response.update(rank=index, eligible_count=len(ranked))
        returned = ranked if limit is None else ranked[:limit]
        return {"setups": [item.response for item in returned if item.response], "context_snapshot": context, "total_eligible": len(ranked), "returned_count": len(returned), "minimum_score": MIN_FORMATION_SCORE, "cutoff_score": cutoff, "limit": response_limit}

    async def diagnose_symbol(self, symbol: str) -> dict[str, Any] | None:
        evaluations, context = await self._analyze()
        ranked = self._rank(evaluations)
        cutoff = ranked[MAX_FORMATION_RESULTS - 1].score if len(ranked) >= MAX_FORMATION_RESULTS else None
        for index, item in enumerate(ranked, 1):
            item.rank = index
        item = next((candidate for candidate in evaluations if candidate.symbol == symbol.upper()), None)
        if item is None:
            return None
        if item.promoted_to_feed:
            status = "promoted_to_feed"
        elif not item.eligible or item.score is None or item.score < MIN_FORMATION_SCORE:
            status = "ineligible"
        elif item.rank is not None and item.rank <= MAX_FORMATION_RESULTS:
            status = "eligible_ranked"
        else:
            status = "eligible_below_cutoff"
        diagnostic_breakdown = None
        if item.score_breakdown is not None:
            kind_by_name = {
                "trigger_readiness": "symbol_controllable",
                "structural_integrity": "symbol_controllable",
                "orderliness_contraction": "symbol_controllable",
                "relative_strength_trajectory": "symbol_controllable",
                "regime_group_alignment": "market_wide",
            }
            components = []
            for name, component in item.score_breakdown["components"].items():
                weight = component["weight"]
                components.append({
                    "name": name,
                    "value": component["score"],
                    "max_value": 100.0,
                    "contribution": component["contribution"] / 100.0,
                    "max_contribution": weight,
                    "to_improve": max(0.0, weight - component["contribution"] / 100.0),
                    "kind": kind_by_name[name],
                    "note": "Deterministic formation component",
                    "inputs": component["inputs"],
                })
            final_fraction = item.score_breakdown["final_score"] / 100.0
            diagnostic_breakdown = {
                "components": components,
                "base_score": item.score_breakdown["raw_score"] / 100.0,
                "after_regime_adjust": final_fraction,
                "ctx_multiplier": {"value": 1.0, "max_value": 1.0, "kind": "market_wide"},
                "group_multiplier": {"value": 1.0, "max_value": 1.0, "kind": "group_rotation"},
                "final_priority_unclamped": final_fraction,
                "final_priority": final_fraction,
                "clamped": False,
                "raw": item.score_breakdown,
            }
        return {
            "key": "forming", "name": "Setups Forming", "passes": item.eligible,
            "status": status, "criteria": [criterion.to_dict() for criterion in item.criteria],
            "rejection_reasons": item.rejection_reasons, "rank": item.rank,
            "eligible_count": len(ranked), "cutoff_score": cutoff,
            "cutoff_gap": round(cutoff - item.score, 2) if cutoff is not None and item.score is not None and item.rank and item.rank > MAX_FORMATION_RESULTS else None,
            "formation_score": item.score, "score_breakdown": diagnostic_breakdown,
            "structural_age_days": item.response.get("structural_age_days") if item.response else None,
            "context_snapshot": context,
        }

    async def _analyze(self) -> tuple[list[CandidateEvaluation], dict[str, Any] | None]:
        market = await MarketContextEngine(self.db).analyze()
        if market is None or market.regime is None:
            return [], None
        participation, leadership = market.participation.descriptor, market.leadership.descriptor
        multiplier = compute_context_multiplier(participation, leadership)
        regime = market.regime.regime.value
        context = {"as_of": market.as_of.isoformat(), "participation": participation, "leadership": leadership, "regime": regime, "follow_through": market.follow_through.descriptor if market.follow_through else "UNKNOWN", "warnings": multiplier.surface_warnings}

        latest = select(StockMetrics.symbol, func.max(StockMetrics.date).label("max_date")).group_by(StockMetrics.symbol).subquery()
        rows = (await self.db.execute(select(StockMetrics, Stock.market_cap, Stock.market_group).join(latest, and_(StockMetrics.symbol == latest.c.symbol, StockMetrics.date == latest.c.max_date)).join(Stock, Stock.symbol == StockMetrics.symbol))).all()
        if not rows:
            return [], context
        metrics_rows = [row[0] for row in rows]
        symbols = [row.symbol for row in metrics_rows]
        latest_date = max(row.date for row in metrics_rows)
        history = (await self.db.execute(select(StockMetrics).where(StockMetrics.symbol.in_(symbols), StockMetrics.date < latest_date).order_by(StockMetrics.date.desc()))).scalars().all()
        previous: dict[str, StockMetrics] = {}
        for row in history:
            previous.setdefault(row.symbol, row)
        rs_baselines = await get_five_session_rs_baselines(self.db, metrics_rows)
        feed_symbols = await LiveTransitionSelector(self.db).current_symbols()
        group_performances = await fetch_current_group_strengths(self.db)
        ages = await self._structural_ages(symbols)
        lifecycle, invalidation = SetupLifecycleEngine(self.db), SetupInvalidationEngine(self.db)
        evaluations: list[CandidateEvaluation] = []
        for metrics, market_cap, market_group in rows:
            state = lifecycle.detect_current_state(metrics)
            invalidation_result = invalidation.check_setup_validity(metrics)
            criteria, reasons = evaluate_formation_eligibility(metrics, market_cap=market_cap, state=state, invalidation_reasons=invalidation_result.invalidation_reasons)
            eligible = not reasons
            promoted = metrics.symbol in feed_symbols
            group = compute_group_multiplier(market_group, group_performances)
            score = breakdown = response = None
            trigger, trigger_atr, trigger_pct = _nearest_trigger(metrics)
            structural_score = 0.0
            if eligible:
                breakdown = calculate_formation_score(metrics, previous=previous.get(metrics.symbol), rs_baseline=rs_baselines.get(metrics.symbol), regime=regime, group=group)
                score = breakdown["final_score"]
                structural_score = breakdown["components"]["structural_integrity"]["score"]
                rs_status = breakdown["components"]["relative_strength_trajectory"]["inputs"]["status"]
                direction = breakdown["components"]["trigger_readiness"]["inputs"]["direction"]
                structure = f"Weekly structure {(metrics.weekly_trend_quality or 0.5) * 100:.0f}/100; long-term averages intact"
                contraction = f"Tightness {(metrics.weekly_tightness or 0.5) * 100:.0f}/100; relative volume {metrics.relative_volume:.2f}x" if metrics.relative_volume is not None else "Contraction history incomplete"
                risk = (
                    "Relative strength is deteriorating"
                    if rs_status == "deteriorating"
                    else "Relative strength is below the leadership threshold"
                    if metrics.relative_strength_spy is not None and metrics.relative_strength_spy < 90
                    else "Price is moving away from the nearest trigger"
                    if direction == "diverging"
                    else "Market group is weak"
                    if group.badge == "weak"
                    else "Await a qualifying Setup Feed transition"
                )
                response = {"symbol": metrics.symbol, "current_price": round(metrics.current_price, 2) if metrics.current_price is not None else None, "change_pct": day_change_pct(metrics, previous.get(metrics.symbol)), "formation_state": state.value, "formation_score": score, "rank": 0, "eligible_count": 0, "formation_narrative": f"{state.value.replace('_', ' ').capitalize()} structure; {direction.replace('_', ' ')} toward {trigger}.", "primary_risk": risk, "next_trigger": trigger, "distance_to_trigger_atr": trigger_atr, "distance_to_trigger_pct": trigger_pct, "distance_to_high_52w_atr": metrics.distance_to_high_52w_atr, "structural_age_days": ages.get(metrics.symbol), "structure_evidence": structure, "contraction_evidence": contraction, "rs_direction": rs_status, "group_strength": {"group": market_group, "badge": group.badge}, "context_warnings": multiplier.surface_warnings, "score_breakdown": breakdown}
            evaluations.append(CandidateEvaluation(metrics.symbol, eligible, criteria, reasons, state, score, breakdown, abs(_trigger_gap(trigger_atr)) if _trigger_gap(trigger_atr) is not None else float("inf"), structural_score, response, promoted))
        return evaluations, context

    @staticmethod
    def _rank(evaluations: list[CandidateEvaluation]) -> list[CandidateEvaluation]:
        ranked = [item for item in evaluations if item.eligible and not item.promoted_to_feed and item.score is not None and item.score >= MIN_FORMATION_SCORE]
        ranked.sort(key=lambda item: (-(item.score or 0.0), item.trigger_distance, -item.structural_score, item.symbol))
        return ranked

    async def _structural_ages(self, symbols: list[str]) -> dict[str, int]:
        rows = (await self.db.execute(select(SetupStateLog.symbol, SetupStateLog.entered_at).where(SetupStateLog.symbol.in_(symbols), SetupStateLog.exited_at.is_(None)))).all()
        now = datetime.now(timezone.utc)
        result: dict[str, int] = {}
        for symbol, entered_at in rows:
            if entered_at is not None:
                if entered_at.tzinfo is None:
                    entered_at = entered_at.replace(tzinfo=timezone.utc)
                result[symbol] = max(0, (now - entered_at).days)
        return result
