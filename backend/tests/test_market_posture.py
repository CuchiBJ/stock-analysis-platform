"""Unit tests for the market posture verdict (pure — no DB).

Core invariant under test: health is a CEILING. It can lower today's read,
never raise it — aggression is earned back through repair, not granted by one
good breadth day.
"""
from app.services.market_posture import POSTURE_ORDER, compute_posture


def _p(participation, leadership, health, **kw):
    return compute_posture(participation, leadership, health, **kw)


class TestBaseStates:
    def test_expansion_on_robust_health_is_agresivo(self):
        assert _p("EXPANDING", "EXPANDING", "ROBUST").state == "AGRESIVO"
        assert _p("EXPANDING", "HEALTHY", "ROBUST").state == "AGRESIVO"

    def test_stable_healthy_is_normal(self):
        assert _p("STABLE", "HEALTHY", "ROBUST").state == "NORMAL"

    def test_collapsing_participation_is_defensivo(self):
        v = _p("COLLAPSING", "EXPANDING", "ROBUST")
        assert v.state == "DEFENSIVO"
        assert any("COLLAPSING" in r for r in v.reasons)

    def test_narrowing_with_adverse_leadership_is_selectivo(self):
        assert _p("NARROWING", "THINNING", "ROBUST").state == "SELECTIVO"

    def test_narrowing_with_healthy_leadership_is_normal(self):
        # Mirrors the decision filter: NARROWING alone is not suppressive.
        assert _p("NARROWING", "HEALTHY", "ROBUST").state == "NORMAL"

    def test_exhausted_leadership_caps_even_on_expansion(self):
        v = _p("EXPANDING", "EXHAUSTED", "ROBUST")
        assert v.state == "SELECTIVO"
        assert any("agotado" in r for r in v.reasons)

    def test_collapsing_leadership_alone_is_selectivo(self):
        # Extension over the filter's Phase 1 table: leaders collapsing is
        # never full-size, even with stable participation.
        assert _p("STABLE", "COLLAPSING", "ROBUST").state == "SELECTIVO"

    def test_unknown_descriptors_are_normal_never_suppressive(self):
        assert _p("UNKNOWN", "EXPANDING", "ROBUST").state == "NORMAL"
        assert _p("EXPANDING", "UNKNOWN", "ROBUST").state == "NORMAL"
        assert _p(None, None, "ROBUST").state == "NORMAL"


class TestHealthCeiling:
    def test_damaged_health_caps_a_great_day_at_defensivo(self):
        # THE audit scenario: today EXPANDING+EXPANDING but memory DAMAGED.
        v = _p("EXPANDING", "EXPANDING", "DAMAGED", damaged_days=12, window_days=20)
        assert v.state == "DEFENSIVO"
        assert any("12/20" in r for r in v.reasons)

    def test_fragile_health_caps_at_selectivo(self):
        assert _p("EXPANDING", "EXPANDING", "FRAGILE").state == "SELECTIVO"

    def test_recovering_health_caps_at_normal_never_agresivo(self):
        # Rolling repair evidence grants NORMAL back, but AGRESIVO requires ROBUST.
        assert _p("EXPANDING", "EXPANDING", "RECOVERING").state == "NORMAL"

    def test_unknown_health_caps_at_normal(self):
        assert _p("EXPANDING", "EXPANDING", "UNKNOWN").state == "NORMAL"

    def test_ceiling_never_raises(self):
        # A bad day on ROBUST health stays bad — health cannot upgrade.
        assert _p("COLLAPSING", "COLLAPSING", "ROBUST").state == "DEFENSIVO"
        assert _p("NARROWING", "THINNING", "ROBUST").state == "SELECTIVO"

    def test_fuera_requires_active_deterioration_on_damaged_memory(self):
        # DEFENSIVO today + DAMAGED memory → FUERA.
        v = _p("COLLAPSING", "THINNING", "DAMAGED", damaged_days=12, window_days=20)
        assert v.state == "FUERA"
        # DAMAGED memory alone (good day today) is DEFENSIVO, not FUERA.
        assert _p("STABLE", "HEALTHY", "DAMAGED").state == "DEFENSIVO"
        # Active collapse on healthy memory is DEFENSIVO, not FUERA.
        assert _p("COLLAPSING", "THINNING", "ROBUST").state == "DEFENSIVO"


class TestVerdictContent:
    def test_every_state_has_an_instruction(self):
        cases = {
            "AGRESIVO":  _p("EXPANDING", "EXPANDING", "ROBUST"),
            "NORMAL":    _p("STABLE", "HEALTHY", "ROBUST"),
            "SELECTIVO": _p("EXPANDING", "EXHAUSTED", "ROBUST"),
            "DEFENSIVO": _p("COLLAPSING", "HEALTHY", "ROBUST"),
            "FUERA":     _p("COLLAPSING", "COLLAPSING", "DAMAGED"),
        }
        for state, v in cases.items():
            assert v.state == state
            assert v.instruction
        assert set(cases) == set(POSTURE_ORDER)

    def test_unlock_explains_path_out_of_damage(self):
        v = _p(
            "STABLE", "HEALTHY", "DAMAGED",
            repair_streak=1,
            repair_streak_min=5,
            repair_clean_days=4,
            repair_window_days=7,
            recent_severe_days=1,
            severe_lookback_days=3,
        )
        assert "5 de las últimas 7" in v.unlock
        assert "4/7 limpias" in v.unlock
        assert "1/3 severas" in v.unlock

    def test_unlock_for_recovering_points_to_robust(self):
        v = _p("STABLE", "HEALTHY", "RECOVERING")
        assert "ROBUST" in v.unlock

    def test_no_unlock_when_robust(self):
        assert _p("EXPANDING", "HEALTHY", "ROBUST").unlock is None

    def test_capped_verdict_explains_both_layers(self):
        # Today fine + memory damaged → the reason must name the memory.
        v = _p("EXPANDING", "EXPANDING", "DAMAGED", damaged_days=10, window_days=20)
        assert any("memoria dañada" in r for r in v.reasons)
