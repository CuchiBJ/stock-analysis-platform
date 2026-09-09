"""Market Posture — the one-sentence operational verdict.

Answers the only question Market Context exists to answer: "¿qué tan agresivo
debería ser hoy?". Maps (participation, leadership, health) to a single
operational state plus an explicit exposure instruction.

Design principles (from the trading-committee audit):
- Context can BRAKE you, never accelerate you: health acts as a ceiling on
  today's read. Aggression is earned back through repair streaks, not granted
  by one good breadth day.
- UNKNOWN data is never suppressive (mirrors context_decision_filter
  Decision 2) but is never permissive either — without memory the ceiling
  is NORMAL.
- Informational phase: this does not touch scoring; it surfaces the verdict
  the ContextMultiplier already implies but never states.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.services.market_posture_policy import POSTURE_THRESHOLDS, thresholds_contract

# Ordered from most to least restrictive — capping = taking the minimum.
POSTURE_ORDER = ["FUERA", "DEFENSIVO", "SELECTIVO", "NORMAL", "AGRESIVO"]
_RANK = {s: i for i, s in enumerate(POSTURE_ORDER)}

# Health state → ceiling on the posture. ROBUST imposes none; UNKNOWN caps at
# NORMAL (no aggression without memory); the rest implement asymmetric repair.
_HEALTH_CEILING = {
    "ROBUST":     "AGRESIVO",
    "UNKNOWN":    "NORMAL",
    "RECOVERING": "NORMAL",
    "FRAGILE":    "SELECTIVO",
    "DAMAGED":    "DEFENSIVO",
}


@dataclass(frozen=True)
class Posture:
    state: str                # FUERA | DEFENSIVO | SELECTIVO | NORMAL | AGRESIVO
    instruction: str          # the one-sentence exposure instruction
    reasons: list = field(default_factory=list)   # which rules fired, human-readable
    unlock: Optional[str] = None                  # what upgrades the state
    policy: dict = field(default_factory=dict)    # auditable levels, bands and active hysteresis


def _base_state(
    p: str,
    l: str,
    *,
    index_bullish: bool,
    breadth_ratio: Optional[float],
    leader_density: Optional[float],
    policy_evidence: dict,
) -> tuple[str, str]:
    """Explicit level + trend posture before health/follow-through ceilings."""
    t = POSTURE_THRESHOLDS
    if p == "COLLAPSING" or l in {"COLLAPSING", "EXHAUSTED"}:
        return "DEFENSIVO", f"anatomía severa activa — participación {p} / liderazgo {l}"
    if breadth_ratio is None or leader_density is None or p == "UNKNOWN" or l == "UNKNOWN":
        return "SELECTIVO", "contexto incompleto — faltan niveles o descriptores confirmados"
    if (
        breadth_ratio < t.defensive_breadth_entry
        or leader_density < t.defensive_leader_density_entry
    ):
        return (
            "DEFENSIVO",
            f"nivel defensivo — amplitud {breadth_ratio:.0%} (piso {t.defensive_breadth_entry:.0%}) "
            f"y líderes {leader_density:.1%} (piso {t.defensive_leader_density_entry:.0%})",
        )
    if policy_evidence.get("defensive_active", False):
        return (
            "DEFENSIVO",
            f"histeresis defensiva activa — salida exige amplitud ≥{t.defensive_breadth_exit:.0%} "
            f"y líderes ≥{t.defensive_leader_density_exit:.0%}",
        )
    if policy_evidence.get("aggressive_active", False):
        return "AGRESIVO", "condiciones AGRESIVO confirmadas y dentro de bandas de salida"
    if policy_evidence.get("normal_active", False):
        return "NORMAL", "condiciones NORMAL confirmadas y dentro de bandas de salida"
    if not index_bullish:
        return "SELECTIVO", "índice sin tendencia alcista confirmada"
    if (
        breadth_ratio <= t.normal_breadth_entry
        or leader_density <= t.normal_leader_density_entry
    ):
        return (
            "SELECTIVO",
            f"niveles de recuperación — amplitud {breadth_ratio:.0%} / líderes {leader_density:.1%}",
        )
    streak = policy_evidence.get("normal_confirmation_streak", 0)
    required = policy_evidence.get(
        "normal_confirmation_required_days", t.normal_confirmation_days
    )
    return "SELECTIVO", f"confirmación NORMAL en curso: {streak}/{required} ruedas"


def _instruction(state: str) -> str:
    return {
        "AGRESIVO":  "Tamaño completo — expansión con salud de mercado intacta.",
        "NORMAL":    "Tamaño normal — sin daño relevante en la ventana.",
        "SELECTIVO": "Media posición y solo setups A+.",
        "DEFENSIVO": "Tamaño mínimo — priorizar gestión de posiciones sobre compras nuevas.",
        "FUERA":     "Sin compras nuevas — deterioro pesado y activo.",
    }[state]


def compute_posture(
    participation: str,
    leadership: str,
    health_state: str,
    *,
    damaged_days: int = 0,
    window_days: int = 0,
    repair_streak: int = 0,
    repair_streak_min: int = 5,
    repair_clean_days: Optional[int] = None,
    repair_window_days: int = 7,
    recent_severe_days: int = 0,
    severe_lookback_days: int = 3,
    recovery_confirmation_streak: int = 0,
    recovery_confirmation_required_days: int = 3,
    exceptional_recovery_session: bool = False,
    index_bullish: bool = False,
    index_above_ema200: bool = False,
    index_new_high: bool = False,
    breadth_ratio: Optional[float] = None,
    leader_density: Optional[float] = None,
    policy_evidence: Optional[dict] = None,
    follow_through: str = "UNKNOWN",
    ft_delivery: Optional[float] = None,
    ft_baseline: Optional[float] = None,
) -> Posture:
    """Pure verdict: today's read capped by the damage memory and by whether
    the market is paying recent signals.

    Ceilings only lower, never raise: a great breadth day on DAMAGED health
    stays DAMAGED-bound, and no amount of breadth buys size while breakouts
    are dying (NOT_PAYING caps at SELECTIVO). FUERA is reserved for active
    severe deterioration — today already DEFENSIVO *and* memory DAMAGED.
    """
    p = (participation or "UNKNOWN").upper()
    l = (leadership or "UNKNOWN").upper()
    h = (health_state or "UNKNOWN").upper()
    ft = (follow_through or "UNKNOWN").upper()
    if h not in _HEALTH_CEILING:
        h = "UNKNOWN"

    evidence = policy_evidence or {}
    base, base_reason = _base_state(
        p,
        l,
        index_bullish=index_bullish,
        breadth_ratio=breadth_ratio,
        leader_density=leader_density,
        policy_evidence=evidence,
    )
    reasons = [base_reason]

    ceiling = _HEALTH_CEILING[h]
    if h == "DAMAGED" and base == "DEFENSIVO":
        state = "FUERA"
        reasons.append(
            f"memoria dañada ({damaged_days}/{window_days} ruedas) con deterioro activo hoy"
        )
    else:
        state = base if _RANK[base] <= _RANK[ceiling] else ceiling
        if state != base:
            reasons.append({
                "DAMAGED":    f"memoria dañada: {damaged_days}/{window_days} ruedas con deterioro",
                "FRAGILE":    "salud frágil: hubo deterioro reciente sin reparación sostenida",
                "RECOVERING": "reparación en curso — la agresividad se recupera al volver a ROBUST",
                "UNKNOWN":    "sin historia suficiente para validar la salud del mercado",
            }[h])

    # Evidence-based early recovery: three consecutive sessions with bullish
    # index structure, breadth >60% and expanding, and leader density >10% and
    # expanding may relax DAMAGED from DEFENSIVO to SELECTIVO.  It cannot
    # override active defensive deterioration or a recent severe session, and
    # it never grants NORMAL/AGRESIVO; those remain owned by health repair.
    protective_recovery_conditions = (
        h == "DAMAGED"
        and state == "DEFENSIVO"
        and base not in {"DEFENSIVO", "FUERA"}
        and recent_severe_days == 0
    )
    exceptional_retained = evidence.get("exceptional_retained", False)
    exceptional_recovery = protective_recovery_conditions and (
        exceptional_recovery_session or exceptional_retained
    )
    accelerated_recovery = (
        protective_recovery_conditions
        and recovery_confirmation_streak >= recovery_confirmation_required_days
    )
    if exceptional_recovery:
        state = "SELECTIVO"
        if exceptional_recovery_session:
            reasons.append(
                "momentum excepcional: índice en nuevo máximo, amplitud >65% "
                "(+20pp) y densidad de líderes >12% (+50%)"
            )
        else:
            age = evidence.get("exceptional_retention_age", 0)
            limit = evidence.get("exceptional_retention_sessions", 2)
            reasons.append(
                f"retención excepcional {age}/{limit}: niveles de salida siguen intactos"
            )
    elif accelerated_recovery:
        state = "SELECTIVO"
        reasons.append(
            "recuperación confirmada: "
            f"{recovery_confirmation_streak} ruedas con índice alcista, "
            "amplitud >60% en expansión y densidad de líderes >10% en expansión"
        )

    # Follow-through ceiling: the market not paying recent signals caps
    # aggression at SELECTIVO regardless of how the anatomy looks. UNKNOWN is
    # never suppressive (same rule as everywhere else).
    if ft == "NOT_PAYING":
        if _RANK[state] > _RANK["SELECTIVO"]:
            state = "SELECTIVO"
        detail = ""
        if ft_delivery is not None:
            detail = f" ({ft_delivery * 100:.0f}% pagando"
            detail += f" vs {ft_baseline * 100:.0f}% base)" if ft_baseline is not None else ")"
        reasons.append(f"el mercado no está pagando las señales recientes{detail}")

    unlock = None
    if h in ("DAMAGED", "FRAGILE"):
        clean_days = repair_streak if repair_clean_days is None else repair_clean_days
        normal_unlock = (
            f"RECOVERING requiere {repair_streak_min} de las últimas "
            f"{repair_window_days} ruedas limpias y 0 deterioros severos en las últimas "
            f"{severe_lookback_days} (actual: {clean_days}/{repair_window_days} limpias, "
            f"{recent_severe_days}/{severe_lookback_days} severas)"
        )
        if h == "DAMAGED" and not (accelerated_recovery or exceptional_recovery):
            unlock = (
                "SELECTIVO anticipado requiere una rueda excepcional o "
                f"{recovery_confirmation_required_days} ruedas confirmadas de nivel + expansión "
                f"(actual: {recovery_confirmation_streak}/"
                f"{recovery_confirmation_required_days}); {normal_unlock}"
            )
        else:
            unlock = normal_unlock
    elif h == "RECOVERING":
        unlock = "ROBUST cuando el daño envejezca fuera de la ventana de 20 ruedas"

    return Posture(
        state=state,
        instruction=_instruction(state),
        reasons=reasons,
        unlock=unlock,
        policy={
            "thresholds": evidence.get("thresholds", thresholds_contract()),
            "inputs": {
                "index_bullish": index_bullish,
                "index_above_ema200": index_above_ema200,
                "index_new_high": index_new_high,
                "breadth_ratio": breadth_ratio,
                "leader_density": leader_density,
                "participation": p,
                "leadership": l,
            },
            "normal_confirmation_streak": evidence.get("normal_confirmation_streak", 0),
            "normal_confirmation_required_days": evidence.get(
                "normal_confirmation_required_days", POSTURE_THRESHOLDS.normal_confirmation_days
            ),
            "normal_active": evidence.get("normal_active", False),
            "defensive_active": evidence.get("defensive_active", False),
            "aggressive_active": evidence.get("aggressive_active", False),
            "exceptional_retained": exceptional_retained,
            "exceptional_retention_age": evidence.get("exceptional_retention_age"),
            "today": evidence.get("today", {}),
            "base_state": base,
            "health_ceiling": ceiling,
            "final_state": state,
        },
    )
