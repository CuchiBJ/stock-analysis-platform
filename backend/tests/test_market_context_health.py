"""Unit tests for the health persistence engine (damage memory over 20 days).

This repo lacks an async DB fixture, so these target the pure surfaces: the
state machine (`_health_state`) and the per-day classifier
(`_classify_health_days`), which never touch the DB.
"""
from datetime import date, timedelta

from app.services.market_context_engine import (
    _HEALTH_DELTA_LOOKBACK,
    MarketContextEngine,
)
from app.services.market_health import (
    CLEAN,
    MILD,
    SEVERE,
    classify_damage_severity,
    compute_health_state,
)

# Engine instance with a sentinel DB — the pure methods never touch it.
_eng = MarketContextEngine(db=object())  # type: ignore[arg-type]

T, F = True, False


def _state(damaged):
    return MarketContextEngine._health_state(damaged)


class TestHealthState:
    def test_all_clean_is_robust(self):
        v = _state([F] * 20)
        assert v['state'] == "ROBUST"
        assert v['episodes'] == 0
        assert v['damaged_days'] == 0
        assert v['repair_streak'] == 20
        assert v['days_since_last_damage'] is None

    def test_robust_boundary_two_damaged_one_episode(self):
        # 2 damaged days in a single run, long clean tail → still ROBUST.
        v = _state([T, T] + [F] * 18)
        assert v['state'] == "ROBUST"
        assert v['episodes'] == 1

    def test_three_damaged_days_is_fragile(self):
        # Trailing clean run of 4 (< repair streak) keeps it FRAGILE.
        v = _state([F] * 13 + [T, T, T] + [F] * 4)
        assert v['state'] == "FRAGILE"

    def test_two_old_episodes_can_be_recovering(self):
        # Two episodes break ROBUST, but enough recent clean evidence now permits
        # RECOVERING once the last severe day leaves the 3-day veto window.
        v = _state([F] * 12 + [T] + [F] * 2 + [T] + [F] * 4)
        assert v['episodes'] == 2
        assert v['state'] == "RECOVERING"

    def test_old_damage_with_long_clean_tail_is_recovering(self):
        # 3 old damaged days + 17 clean: repair streak satisfied → RECOVERING
        # (returns to ROBUST only once the damage ages out of the window).
        v = _state([T, T, T] + [F] * 17)
        assert v['state'] == "RECOVERING"

    def test_heavy_total_damage_is_damaged(self):
        # 8 of 20 damaged, all old, followed by only 4 clean days (< repair streak).
        v = _state([T] * 8 + [F] * 8 + [T, F, T, F])
        assert v['damaged_days'] == 10
        assert v['state'] == "DAMAGED"

    def test_recent_cluster_is_damaged_without_heavy_total(self):
        # Only 3 damaged days total, but all within the last 5 → active deterioration.
        v = _state([F] * 15 + [T, F, T, T, F])
        assert v['damaged_days'] == 3
        assert v['state'] == "DAMAGED"

    def test_four_clean_of_latest_seven_is_not_enough(self):
        # Consecutive streak is diagnostic only; the rolling 7-day evidence is
        # what matters. Four clean sessions do not qualify.
        v = _state([F] * 13 + [T, T, T, F, F, F, F])
        assert v['repair_streak'] == 4
        assert v['state'] == "FRAGILE"

    def test_five_clean_of_seven_flips_to_recovering(self):
        v = _state([T, T, T, T] + [F] * 10 + [T, F, F, F, F, F])
        assert v['repair_streak'] == 5
        assert v['repair_clean_days'] >= 5
        assert v['state'] == "RECOVERING"

    def test_heavy_damage_with_streak_is_recovering_not_robust(self):
        # 10 damaged days + clean streak: repairing, but the damage hasn't aged out.
        v = _state([T] * 10 + [F] * 10)
        assert v['state'] == "RECOVERING"

    def test_damage_aged_out_returns_to_robust(self):
        # Only 2 damaged days left at the window start with a long clean tail —
        # the sliding window decays damage back to ROBUST automatically.
        v = _state([T, T] + [F] * 18)
        assert v['state'] == "ROBUST"

    def test_insufficient_days_is_unknown_with_counts(self):
        v = _state([T, F, T, F, T])
        assert v['state'] == "UNKNOWN"
        assert v['damaged_days'] == 3
        assert v['episodes'] == 3

    def test_empty_is_unknown(self):
        v = _state([])
        assert v['state'] == "UNKNOWN"
        assert v['damaged_days'] == 0
        assert v['repair_streak'] == 0
        assert v['days_since_last_damage'] is None

    def test_days_since_last_damage_tracks_trailing_clean_run(self):
        v = _state([T] + [F] * 19)
        assert v['days_since_last_damage'] == 19
        v = _state([F] * 19 + [T])
        assert v['days_since_last_damage'] == 0

    def test_episode_counting_run_boundaries(self):
        v = _state([T, T, F, T] + [F] * 16)
        assert v['episodes'] == 2


class TestSeverityAwareRecovery:
    def test_worst_case_severity_precedence(self):
        assert classify_damage_severity("STABLE", "HEALTHY") == CLEAN
        assert classify_damage_severity("NARROWING", "HEALTHY") == MILD
        assert classify_damage_severity("STABLE", "THINNING") == MILD
        assert classify_damage_severity("NARROWING", "COLLAPSING") == SEVERE
        assert classify_damage_severity("COLLAPSING", "HEALTHY") == SEVERE
        assert classify_damage_severity("EXPANDING", "EXHAUSTED") == SEVERE

    def test_mild_pullbacks_do_not_reset_rolling_repair(self):
        severities = [SEVERE] * 10 + [CLEAN] * 3 + [
            CLEAN, CLEAN, MILD, CLEAN, CLEAN, MILD, CLEAN,
        ]
        v = compute_health_state(severities)
        assert v['repair_clean_days'] == 5
        assert v['recent_severe_days'] == 0
        assert v['repair_streak'] == 1
        assert v['state'] == "RECOVERING"

    def test_recent_severe_day_vetoes_recovery(self):
        severities = [SEVERE] * 10 + [CLEAN] * 3 + [
            MILD, CLEAN, CLEAN, CLEAN, CLEAN, SEVERE, CLEAN,
        ]
        v = compute_health_state(severities)
        assert v['repair_clean_days'] == 5
        assert v['recent_severe_days'] == 1
        assert v['state'] == "DAMAGED"

    def test_recent_severe_day_prevents_robust(self):
        v = compute_health_state([CLEAN] * 19 + [SEVERE])
        assert v['damaged_days'] == 1
        assert v['recent_severe_days'] == 1
        assert v['state'] == "FRAGILE"
        v = _state([F, T, T, T, F] + [F] * 10 + [T] * 5)
        assert v['episodes'] == 2


def _raw_series(breadth, leaders, universe=700, extension=None):
    """Build a raw daily series like _daily_dimension_series returns."""
    n = len(breadth)
    extension = extension or [0] * n
    start = date(2026, 6, 1)
    return [
        {
            'date':            start + timedelta(days=i),
            'universe':        universe[i] if isinstance(universe, list) else universe,
            'breadth_ratio':   breadth[i],
            'leader_count':    leaders[i],
            'extension_count': extension[i],
        }
        for i in range(n)
    ]


class TestClassifyHealthDays:
    def test_flat_series_no_damage(self):
        raw = _raw_series(breadth=[0.50] * 10, leaders=[100] * 10)
        days = _eng._classify_health_days(raw)
        assert len(days) == 10 - _HEALTH_DELTA_LOOKBACK
        assert all(not d['damaged'] for d in days)
        assert all(d['participation'] == "STABLE" for d in days)
        assert all(d['leadership'] == "HEALTHY" for d in days)

    def test_breadth_drop_marks_narrowing_damage(self):
        # Last day breadth 10pp below its 5-days-ago reference → NARROWING.
        breadth = [0.50] * 9 + [0.40]
        raw = _raw_series(breadth=breadth, leaders=[100] * 10)
        days = _eng._classify_health_days(raw)
        assert days[-1]['participation'] == "NARROWING"
        assert days[-1]['damaged'] is True
        assert days[-1]['severity'] == MILD
        assert all(not d['damaged'] for d in days[:-1])

    def test_density_collapse_marks_damage(self):
        # Leaders -20% with steady universe → COLLAPSING.
        leaders = [100] * 9 + [80]
        raw = _raw_series(breadth=[0.50] * 10, leaders=leaders)
        days = _eng._classify_health_days(raw)
        assert days[-1]['leadership'] == "COLLAPSING"
        assert days[-1]['damaged'] is True
        assert days[-1]['severity'] == SEVERE

    def test_shrinking_universe_cancels_phantom_collapse(self):
        # Leader count -20% but universe also -20% → density flat → no damage.
        leaders = [100] * 9 + [80]
        universe = [700] * 9 + [560]
        raw = _raw_series(breadth=[0.50] * 10, leaders=leaders, universe=universe)
        days = _eng._classify_health_days(raw)
        assert days[-1]['leadership'] == "HEALTHY"
        assert days[-1]['damaged'] is False
        assert days[-1]['severity'] == CLEAN

    def test_extension_ratio_marks_exhausted_damage(self):
        # >40% of leaders extended → EXHAUSTED even with flat density.
        extension = [0] * 9 + [50]
        raw = _raw_series(breadth=[0.50] * 10, leaders=[100] * 10, extension=extension)
        days = _eng._classify_health_days(raw)
        assert days[-1]['leadership'] == "EXHAUSTED"
        assert days[-1]['damaged'] is True
        assert days[-1]['severity'] == SEVERE

    def test_zero_universe_day_is_skipped_not_damaged(self):
        # A data-gap day (universe=0, ratio None) is dropped from the output —
        # both as a classified day and as a delta reference.
        breadth = [0.50] * 6 + [None] + [0.50] * 3
        universe = [700] * 6 + [0] + [700] * 3
        raw = _raw_series(breadth=breadth, leaders=[100] * 10, universe=universe)
        days = _eng._classify_health_days(raw)
        # Index 6 is unclassifiable; index 11 doesn't exist; the rest classify.
        assert all(d['date'] != raw[6]['date'] for d in days)
        assert len(days) == 4
        assert all(not d['damaged'] for d in days)

    def test_series_shorter_than_lookback_is_empty(self):
        raw = _raw_series(breadth=[0.50] * 4, leaders=[100] * 4)
        assert _eng._classify_health_days(raw) == []
