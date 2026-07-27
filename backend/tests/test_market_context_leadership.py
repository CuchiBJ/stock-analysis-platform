"""Unit tests for the leadership engine's universe-normalized density logic.

This repo lacks an async DB fixture, so these target the two pure surfaces that
carry the fix: the density-delta math (`_density_delta_pct`) and the descriptor
classification (`_leadership_descriptor`).
"""
from app.services.market_context_engine import MarketContextEngine

# Engine instance with a sentinel DB — neither pure method touches it.
_eng = MarketContextEngine(db=object())  # type: ignore[arg-type]


class TestDensityDeltaPct:
    def test_same_density_different_universe_is_flat(self):
        # 144/743 ≈ 113/583: same density, universe shrank ~20% (ingest swing).
        # Must read ~0%, not a phantom collapse.
        delta = MarketContextEngine._density_delta_pct(113, 583, 144, 743)
        assert abs(delta) < 0.5

    def test_real_case_collapse_becomes_thinning(self):
        # The 2026-06-18 → 2026-06-26 reading the fix targets.
        # Raw count delta = (111-144)/144 = -22.9% → COLLAPSING.
        # Density delta is much milder (universe also shrank 743 → 671).
        delta = MarketContextEngine._density_delta_pct(111, 671, 144, 743)
        assert -15.0 <= delta < -5.0  # THINNING band, not COLLAPSING
        # And strictly less severe than the raw-count delta it replaces.
        raw_count_delta = (111 - 144) / 144 * 100
        assert delta > raw_count_delta

    def test_empty_universe_returns_zero(self):
        assert MarketContextEngine._density_delta_pct(10, 0, 12, 100) == 0.0
        assert MarketContextEngine._density_delta_pct(10, 100, 12, 0) == 0.0

    def test_zero_leaders_then_returns_zero(self):
        assert MarketContextEngine._density_delta_pct(10, 100, 0, 100) == 0.0

    def test_genuine_expansion_positive(self):
        # Universe steady, leaders up 50% → density up ~50%.
        delta = MarketContextEngine._density_delta_pct(150, 700, 100, 700)
        assert 45.0 < delta < 55.0


class TestDensityLevel:
    def test_below_min_sample_is_unknown(self):
        assert MarketContextEngine._classify_density_level(0.9, 9) == "UNKNOWN"
        assert MarketContextEngine._classify_density_level(None, 50) == "UNKNOWN"

    def test_bands(self):
        c = MarketContextEngine._classify_density_level
        assert c(0.80, 20) == "STRONG"   # >= 0.67
        assert c(0.67, 20) == "STRONG"
        assert c(0.50, 20) == "NORMAL"   # 0.33..0.67
        assert c(0.33, 20) == "NORMAL"
        assert c(0.10, 20) == "WEAK"     # < 0.33

    def test_level_is_orthogonal_to_trend(self):
        # A flat trend (HEALTHY) can sit on a WEAK level — the whole point.
        level = MarketContextEngine._classify_density_level(0.10, 20)
        assert level == "WEAK"


class TestLeadershipDescriptor:
    def test_thresholds_on_density_delta(self):
        d = _eng._leadership_descriptor
        assert d(10.0, 0, 0, 100) == "EXPANDING"   # > +5%
        assert d(0.0, 0, 0, 100) == "HEALTHY"       # -5%..+5%
        assert d(-10.0, 0, 0, 100) == "THINNING"    # -15%..-5%
        assert d(-25.0, 0, 0, 100) == "COLLAPSING"  # < -15%

    def test_exhaustion_override_beats_direction(self):
        # >25% climactic forces EXHAUSTED even when density is expanding.
        assert _eng._leadership_descriptor(10.0, climactic_count=30, extension_count=0, leader_count=100) == "EXHAUSTED"
        # >40% extended likewise.
        assert _eng._leadership_descriptor(10.0, climactic_count=0, extension_count=50, leader_count=100) == "EXHAUSTED"
