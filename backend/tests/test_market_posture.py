"""Unit tests for the market posture verdict (pure — no DB).

Core invariant under test: health is a CEILING. It can lower today's read,
never raise it — aggression is earned back through repair, not granted by one
good breadth day.
"""
from app.services.market_posture import POSTURE_ORDER, compute_posture


def _p(participation, leadership, health, **kw):
    kw.setdefault('index_bullish', True)
    kw.setdefault('index_above_ema200', True)
    kw.setdefault('breadth_ratio', 0.65)
    kw.setdefault('leader_density', 0.12)
    kw.setdefault('policy_evidence', {
        'normal_active': True,
        'aggressive_active': False,
        'normal_confirmation_streak': 3,
        'normal_confirmation_required_days': 3,
    })
    return compute_posture(participation, leadership, health, **kw)


class TestBaseStates:
    def test_agresivo_requires_active_strong_hysteresis_state(self):
        v = _p(
            "EXPANDING", "EXPANDING", "ROBUST",
            breadth_ratio=0.75,
            leader_density=0.18,
            index_new_high=True,
            policy_evidence={'normal_active': True, 'aggressive_active': True},
        )
        assert v.state == "AGRESIVO"

    def test_stable_healthy_is_normal(self):
        assert _p("STABLE", "HEALTHY", "ROBUST").state == "NORMAL"

    def test_collapsing_participation_is_defensivo(self):
        v = _p("COLLAPSING", "EXPANDING", "ROBUST")
        assert v.state == "DEFENSIVO"
        assert any("COLLAPSING" in r for r in v.reasons)

    def test_narrowing_with_adverse_leadership_is_selectivo(self):
        assert _p(
            "NARROWING", "THINNING", "ROBUST",
            policy_evidence={'normal_active': False, 'aggressive_active': False},
        ).state == "SELECTIVO"

    def test_narrowing_with_healthy_leadership_is_normal(self):
        # An already-active NORMAL state survives a mild pullback inside exits.
        assert _p("NARROWING", "HEALTHY", "ROBUST").state == "NORMAL"

    def test_exhausted_leadership_caps_even_on_expansion(self):
        v = _p("EXPANDING", "EXHAUSTED", "ROBUST")
        assert v.state == "DEFENSIVO"
        assert any("severa" in r for r in v.reasons)

    def test_collapsing_leadership_alone_is_selectivo(self):
        assert _p("STABLE", "COLLAPSING", "ROBUST").state == "DEFENSIVO"

    def test_unknown_descriptors_are_selectivo_incomplete(self):
        assert _p("UNKNOWN", "EXPANDING", "ROBUST").state == "SELECTIVO"
        assert _p("EXPANDING", "UNKNOWN", "ROBUST").state == "SELECTIVO"
        assert _p(None, None, "ROBUST").state == "SELECTIVO"

    def test_explicit_low_levels_are_defensivo_even_with_stable_descriptors(self):
        assert _p("STABLE", "HEALTHY", "ROBUST", breadth_ratio=0.39).state == "DEFENSIVO"
        assert _p("STABLE", "HEALTHY", "ROBUST", leader_density=0.049).state == "DEFENSIVO"


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
        assert _p(
            "NARROWING", "THINNING", "ROBUST",
            policy_evidence={'normal_active': False, 'aggressive_active': False},
        ).state == "SELECTIVO"

    def test_fuera_requires_active_deterioration_on_damaged_memory(self):
        # DEFENSIVO today + DAMAGED memory → FUERA.
        v = _p("COLLAPSING", "THINNING", "DAMAGED", damaged_days=12, window_days=20)
        assert v.state == "FUERA"
        # DAMAGED memory alone (good day today) is DEFENSIVO, not FUERA.
        assert _p("STABLE", "HEALTHY", "DAMAGED").state == "DEFENSIVO"
        # Active collapse on healthy memory is DEFENSIVO, not FUERA.
        assert _p("COLLAPSING", "THINNING", "ROBUST").state == "DEFENSIVO"


class TestAcceleratedRecoveryCeiling:
    def test_exceptional_session_immediately_relaxes_to_selectivo(self):
        v = _p(
            "EXPANDING", "EXPANDING", "DAMAGED",
            damaged_days=16,
            window_days=20,
            recent_severe_days=0,
            recovery_confirmation_streak=1,
            exceptional_recovery_session=True,
        )
        assert v.state == "SELECTIVO"
        assert any("momentum excepcional" in reason for reason in v.reasons)

    def test_near_miss_exceptional_session_stays_defensivo(self):
        v = _p(
            "EXPANDING", "EXPANDING", "DAMAGED",
            recent_severe_days=0,
            recovery_confirmation_streak=1,
            exceptional_recovery_session=False,
        )
        assert v.state == "DEFENSIVO"

    def test_recent_severe_blocks_exceptional_session(self):
        v = _p(
            "EXPANDING", "EXPANDING", "DAMAGED",
            recent_severe_days=1,
            exceptional_recovery_session=True,
        )
        assert v.state == "DEFENSIVO"

    def test_exceptional_override_retains_selectivo_on_following_normal_session(self):
        v = _p(
            "STABLE", "HEALTHY", "DAMAGED",
            recent_severe_days=0,
            exceptional_recovery_session=False,
            policy_evidence={
                'normal_active': False,
                'aggressive_active': False,
                'exceptional_retained': True,
                'exceptional_retention_age': 1,
                'exceptional_retention_sessions': 2,
            },
        )
        assert v.state == "SELECTIVO"
        assert any("retención excepcional" in reason for reason in v.reasons)

    def test_expired_exceptional_retention_returns_to_damaged_ceiling(self):
        v = _p(
            "STABLE", "HEALTHY", "DAMAGED",
            recent_severe_days=0,
            exceptional_recovery_session=False,
            policy_evidence={
                'normal_active': False,
                'aggressive_active': False,
                'exceptional_retained': False,
            },
        )
        assert v.state == "DEFENSIVO"

    def test_three_confirmed_sessions_relax_damaged_to_selectivo(self):
        # Mirrors the live recovery shape: today's anatomy is excellent, but
        # the 20-session damage memory remains heavy.
        v = _p(
            "EXPANDING", "EXPANDING", "DAMAGED",
            damaged_days=16,
            window_days=20,
            recent_severe_days=0,
            recovery_confirmation_streak=3,
        )
        assert v.state == "SELECTIVO"
        assert any("recuperación confirmada" in reason for reason in v.reasons)

    def test_insufficient_confirmation_stays_defensivo(self):
        v = _p(
            "EXPANDING", "EXPANDING", "DAMAGED",
            recent_severe_days=0,
            recovery_confirmation_streak=2,
        )
        assert v.state == "DEFENSIVO"

    def test_recent_severe_deterioration_blocks_acceleration(self):
        v = _p(
            "EXPANDING", "EXPANDING", "DAMAGED",
            recent_severe_days=1,
            recovery_confirmation_streak=3,
        )
        assert v.state == "DEFENSIVO"

    def test_active_collapse_remains_fuera_even_with_stale_confirmation(self):
        v = _p(
            "COLLAPSING", "EXPANDING", "DAMAGED",
            recent_severe_days=0,
            recovery_confirmation_streak=3,
        )
        assert v.state == "FUERA"

    def test_existing_five_of_seven_path_can_reach_normal(self):
        # Accelerated recovery itself caps at SELECTIVO. Once the independent
        # health reducer reaches RECOVERING, the existing NORMAL ceiling applies.
        v = _p(
            "EXPANDING", "EXPANDING", "RECOVERING",
            recovery_confirmation_streak=5,
        )
        assert v.state == "NORMAL"


class TestVerdictContent:
    def test_every_state_has_an_instruction(self):
        cases = {
            "AGRESIVO":  _p(
                "EXPANDING", "EXPANDING", "ROBUST",
                breadth_ratio=0.75,
                leader_density=0.18,
                index_new_high=True,
                policy_evidence={'normal_active': True, 'aggressive_active': True},
            ),
            "NORMAL":    _p("STABLE", "HEALTHY", "ROBUST"),
            "SELECTIVO": _p(
                "EXPANDING", "HEALTHY", "ROBUST",
                breadth_ratio=0.50,
                leader_density=0.08,
                policy_evidence={'normal_active': False, 'aggressive_active': False},
            ),
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
