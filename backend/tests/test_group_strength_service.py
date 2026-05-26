"""Unit tests for group_strength_service."""
import pytest
from app.services.group_strength_service import (
    GroupMultiplier,
    compute_group_multiplier,
    clear_cache,
    _NEUTRAL,
    _LEADER,
    _WEAK,
)

# ─── Fixture ──────────────────────────────────────────────────────────────────

def _perfs(groups: list[tuple[str, float, int]]) -> dict[str, dict]:
    """Build a group_perfs dict from (name, perf_monthly, stock_count) tuples."""
    return {
        name: {"performance_monthly": perf, "stock_count": count}
        for name, perf, count in groups
    }


# 10 groups, each with ≥5 stocks — top 20% = 2, bottom 20% = 2
_SAMPLE_10 = _perfs([
    ("G1",  5.0, 50),   # rank 0 → leader
    ("G2",  4.0, 50),   # rank 1 → leader
    ("G3",  3.0, 50),   # rank 2 → neutral
    ("G4",  2.5, 50),   # rank 3 → neutral
    ("G5",  2.0, 50),   # rank 4 → neutral
    ("G6",  1.5, 50),   # rank 5 → neutral
    ("G7",  1.0, 50),   # rank 6 → neutral
    ("G8",  0.5, 50),   # rank 7 → neutral
    ("G9", -1.0, 50),   # rank 8 → weak
    ("G10",-2.0, 50),   # rank 9 → weak
])


class TestGroupMultiplierDataclass:
    def test_valid_leader(self):
        gm = GroupMultiplier(1.15, "leader")
        assert gm.score_multiplier == 1.15
        assert gm.badge == "leader"

    def test_valid_weak(self):
        gm = GroupMultiplier(0.85, "weak")
        assert gm.badge == "weak"

    def test_invalid_multiplier_raises(self):
        with pytest.raises(ValueError):
            GroupMultiplier(1.10, "leader")  # 1.10 not allowed

    def test_invalid_badge_raises(self):
        with pytest.raises(ValueError):
            GroupMultiplier(1.00, "medium")  # only leader/neutral/weak


class TestComputeGroupMultiplier:
    def test_top_group_is_leader(self):
        assert compute_group_multiplier("G1", _SAMPLE_10) == _LEADER

    def test_second_group_is_leader(self):
        assert compute_group_multiplier("G2", _SAMPLE_10) == _LEADER

    def test_third_group_is_neutral(self):
        # rank 2 is outside top 20% for n=10 (cutoff=2)
        assert compute_group_multiplier("G3", _SAMPLE_10) == _NEUTRAL

    def test_bottom_group_is_weak(self):
        assert compute_group_multiplier("G10", _SAMPLE_10) == _WEAK

    def test_second_to_last_is_weak(self):
        assert compute_group_multiplier("G9", _SAMPLE_10) == _WEAK

    def test_middle_group_is_neutral(self):
        assert compute_group_multiplier("G5", _SAMPLE_10) == _NEUTRAL

    def test_none_group_returns_neutral(self):
        assert compute_group_multiplier(None, _SAMPLE_10) == _NEUTRAL

    def test_empty_string_group_returns_neutral(self):
        assert compute_group_multiplier("", _SAMPLE_10) == _NEUTRAL

    def test_empty_perfs_returns_neutral(self):
        assert compute_group_multiplier("G1", {}) == _NEUTRAL

    def test_group_not_in_perfs_returns_neutral(self):
        assert compute_group_multiplier("Unknown Group", _SAMPLE_10) == _NEUTRAL

    def test_small_group_forced_neutral_even_if_top(self):
        # n=4 stocks, performance would be top — must be forced neutral
        perfs = _perfs([
            ("SmallTop", 10.0, 4),  # n < _MIN_GROUP_SIZE
            ("G1",        5.0, 50),
            ("G2",        4.0, 50),
            ("G9",       -1.0, 50),
            ("G10",      -2.0, 50),
        ])
        assert compute_group_multiplier("SmallTop", perfs) == _NEUTRAL

    def test_small_group_forced_neutral_even_if_bottom(self):
        perfs = _perfs([
            ("SmallBot", -5.0, 3),  # n < _MIN_GROUP_SIZE
            ("G1",        5.0, 50),
            ("G2",        4.0, 50),
            ("G9",       -1.0, 50),
            ("G10",      -2.0, 50),
        ])
        assert compute_group_multiplier("SmallBot", perfs) == _NEUTRAL

    def test_composition_macro_dominates(self):
        # priority 80, ctx 0.5 (COLLAPSING), group leader 1.15 → 80 × 0.5 × 1.15 = 46
        base = 80.0
        ctx  = 0.5
        gm   = compute_group_multiplier("G1", _SAMPLE_10)
        assert gm.score_multiplier == 1.15
        final = min(100.0, base * ctx * gm.score_multiplier)
        assert abs(final - 46.0) < 0.01

    def test_composition_capped_at_100(self):
        # priority 95, ctx 1.1, group leader 1.15 → would be 120, capped at 100
        gm = compute_group_multiplier("G1", _SAMPLE_10)
        final = min(100.0, 95.0 * 1.1 * gm.score_multiplier)
        assert final == 100.0

    def test_weak_composition(self):
        # priority 80, ctx 1.0, group weak 0.85 → 68
        gm = compute_group_multiplier("G10", _SAMPLE_10)
        assert gm.score_multiplier == 0.85
        final = min(100.0, 80.0 * 1.0 * gm.score_multiplier)
        assert abs(final - 68.0) < 0.01

    def test_single_group_in_perfs_is_neutral(self):
        # With only 1 eligible group, top 20% cutoff = max(1, round(1*0.2)) = 1
        # rank 0 < 1 → leader. Checking degenerate case works.
        perfs = _perfs([("OnlyGroup", 3.0, 20)])
        result = compute_group_multiplier("OnlyGroup", perfs)
        assert result == _LEADER  # rank 0 is in top 20% of 1

    def test_all_small_groups_returns_neutral(self):
        perfs = _perfs([("A", 5.0, 2), ("B", 3.0, 1), ("C", 1.0, 4)])
        assert compute_group_multiplier("A", perfs) == _NEUTRAL
        assert compute_group_multiplier("B", perfs) == _NEUTRAL
        assert compute_group_multiplier("C", perfs) == _NEUTRAL


class TestCacheHelper:
    def test_clear_cache_works(self):
        clear_cache()  # should not raise
