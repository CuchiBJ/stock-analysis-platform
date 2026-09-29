import asyncio
from types import SimpleNamespace
from inspect import signature

import pytest

from app.services.forming_setup_service import (
    CandidateEvaluation,
    FORMATION_WEIGHTS,
    FormationSetupService,
    calculate_formation_score,
    calculate_rs_trajectory_score,
    evaluate_formation_eligibility,
)
from app.services.group_strength_service import GroupMultiplier
from app.services.setup_invalidation_engine import InvalidationReason
from app.services.setup_lifecycle_engine import SetupState


def metrics(**overrides):
    values = {
        "symbol": "BEFX", "current_price": 100.0, "avg_volume_10d": 1_500_000,
        "adr_percent": 5.0, "perf_1y": 55.0, "ema50": 90.0,
        "sma150": 84.0, "sma200": 75.0, "low_52w": 55.0,
        "distance_to_ema9": -0.2, "distance_to_ema21": -1.0,
        "distance_to_ema9_atr": -0.09, "distance_to_ema21_atr": -1.35,
        "distance_to_ema50_atr": 2.4, "distance_to_high_52w_atr": -4.35,
        "weekly_trend_quality": 0.82, "weekly_tightness": 0.68,
        "weekly_volatility_contraction": 0.62, "volume_contraction": 0.55,
        "relative_volume": 0.72, "relative_strength_spy": 106.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_far_from_high_is_not_an_eligibility_gate():
    candidate = metrics(distance_to_high_52w_atr=-8.0)
    criteria, reasons = evaluate_formation_eligibility(
        candidate,
        market_cap=2_000_000_000,
        state=SetupState.CONTROLLED_PULLBACK,
        invalidation_reasons=[],
    )
    assert reasons == []
    assert all(item.key != "near_52w_high" for item in criteria)


def test_invalidation_and_broken_lifecycle_precede_scoring():
    _, reasons = evaluate_formation_eligibility(
        metrics(),
        market_cap=2_000_000_000,
        state=SetupState.BROKEN,
        invalidation_reasons=[InvalidationReason.HEAVY_SELLING],
    )
    assert "lifecycle_intact" in reasons
    assert "heavy_selling" in reasons


def test_weak_rs_is_context_not_a_hard_gate():
    _, reasons = evaluate_formation_eligibility(
        metrics(relative_strength_spy=85.0),
        market_cap=2_000_000_000,
        state=SetupState.CONTROLLED_PULLBACK,
        invalidation_reasons=[InvalidationReason.RS_DETERIORATION],
    )
    assert reasons == []


def test_score_uses_declared_weights_and_missing_rs_history_is_neutral():
    current = metrics()
    previous = metrics(distance_to_ema9_atr=-0.8, relative_strength_spy=104.0)
    breakdown = calculate_formation_score(
        current,
        previous=previous,
        rs_baseline=None,
        regime="risk_on",
        group=GroupMultiplier(1.0, "neutral"),
    )
    assert set(breakdown["components"]) == set(FORMATION_WEIGHTS)
    assert breakdown["components"]["relative_strength_trajectory"]["score"] == 50.0
    assert sum(component["contribution"] for component in breakdown["components"].values()) == pytest.approx(breakdown["raw_score"], abs=0.03)
    assert breakdown["final_score"] == pytest.approx(breakdown["raw_score"])


@pytest.mark.parametrize(
    ("current", "previous"),
    [
        (
            metrics(symbol="BEFX", distance_to_ema9_atr=-0.09, distance_to_high_52w_atr=-4.35),
            metrics(symbol="BEFX", distance_to_ema9_atr=-0.75, relative_strength_spy=104.0),
        ),
        (
            metrics(symbol="DOCNFX", distance_to_ema9_atr=-1.65, distance_to_ema21_atr=-2.45, distance_to_high_52w_atr=-5.2, weekly_tightness=0.78, weekly_volatility_contraction=0.74, relative_volume=0.58),
            metrics(symbol="DOCNFX", distance_to_ema9_atr=-2.25, distance_to_ema21_atr=-2.9, relative_strength_spy=105.0),
        ),
    ],
)
def test_be_and_docn_shaped_formations_clear_initial_score_floor(current, previous):
    result = calculate_formation_score(
        current,
        previous=previous,
        rs_baseline=previous.relative_strength_spy,
        regime="transition",
        group=GroupMultiplier(1.0, "neutral"),
    )
    assert result["final_score"] >= 55.0


def test_structural_age_cannot_change_formation_score():
    assert "structural_age_days" not in signature(calculate_formation_score).parameters


def test_rank_excludes_current_feed_symbols_and_preserves_scarcity_order():
    def item(symbol, score, promoted=False):
        return CandidateEvaluation(
            symbol=symbol,
            eligible=True,
            criteria=[],
            rejection_reasons=[],
            state=SetupState.CONTROLLED_PULLBACK,
            score=score,
            score_breakdown={},
            trigger_distance=0.2,
            structural_score=80.0,
            response={"symbol": symbol},
            promoted_to_feed=promoted,
        )

    ranked = FormationSetupService._rank([
        item("FEED", 95.0, promoted=True),
        item("BE", 72.0),
        item("LOW", 54.9),
        item("DOCN", 68.0),
    ])
    assert [candidate.symbol for candidate in ranked] == ["BE", "DOCN"]


def test_full_catalog_preserves_all_eligible_candidates_in_rank_order(monkeypatch):
    def item(symbol, score):
        return CandidateEvaluation(
            symbol=symbol,
            eligible=True,
            criteria=[],
            rejection_reasons=[],
            state=SetupState.CONTROLLED_PULLBACK,
            score=score,
            score_breakdown={},
            trigger_distance=0.2,
            structural_score=80.0,
            response={"symbol": symbol},
        )

    candidates = [item(f"S{index}", 80.0 - index) for index in range(8)]
    service = FormationSetupService(None)

    async def analyze():
        return candidates, None

    monkeypatch.setattr(service, "_analyze", analyze)

    async def load_both():
        return (
            await service.get_forming_setups(limit=6),
            await service.get_forming_setups(limit=None),
        )

    dashboard, catalog = asyncio.run(load_both())

    assert dashboard["returned_count"] == 6
    assert catalog["returned_count"] == 8
    assert catalog["total_eligible"] == 8
    assert [setup["symbol"] for setup in catalog["setups"]] == [f"S{index}" for index in range(8)]
    assert [setup["rank"] for setup in catalog["setups"]] == list(range(1, 9))


@pytest.mark.parametrize(
    ("current", "baseline", "expected"),
    [(106.0, 100.0, "improving"), (100.0, 100.0, "stable"), (96.0, 100.0, "deteriorating")],
)
def test_rs_trajectory_buckets(current, baseline, expected):
    _, detail = calculate_rs_trajectory_score(current, baseline)
    assert detail["status"] == expected
