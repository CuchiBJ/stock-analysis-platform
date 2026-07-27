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

# Ordered from most to least restrictive — capping = taking the minimum.
POSTURE_ORDER = ["FUERA", "DEFENSIVO", "SELECTIVO", "NORMAL", "AGRESIVO"]
_RANK = {s: i for i, s in enumerate(POSTURE_ORDER)}

_ADVERSE_LEADERSHIP = {"THINNING", "COLLAPSING", "EXHAUSTED"}
_SUPPORTIVE_LEADERSHIP = {"EXPANDING", "HEALTHY"}

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


def _base_state(p: str, l: str) -> tuple[str, Optional[str]]:
    """Today's read from the descriptor pair → (state, reason).

    Mirrors the severity ladder of context_decision_filter's rules table, with
    one extension: leadership COLLAPSING alone is SELECTIVO (the filter's Phase
    1 table left that cell neutral, but no committee member buys full size
    while leaders collapse).
    """
    if p == "UNKNOWN" or l == "UNKNOWN":
        return "NORMAL", "contexto incompleto — sin datos suficientes hoy"
    if p == "COLLAPSING":
        return "DEFENSIVO", "participación COLLAPSING — la amplitud se está yendo del mercado"
    if p == "NARROWING" and l in _ADVERSE_LEADERSHIP:
        return "SELECTIVO", "amplitud contrayéndose con liderazgo adverso"
    if l == "EXHAUSTED":
        return "SELECTIVO", "liderazgo agotado — extensión/clímax en los líderes"
    if l == "COLLAPSING":
        return "SELECTIVO", "liderazgo COLLAPSING — los líderes están fallando"
    if p == "EXPANDING" and l in _SUPPORTIVE_LEADERSHIP:
        return "AGRESIVO", None
    return "NORMAL", None


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

    base, base_reason = _base_state(p, l)
    reasons = [base_reason] if base_reason else []

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

    # Follow-through ceiling: the market not paying recent signals caps
    # aggression at SELECTIVO regardless of how the anatomy looks. UNKNOWN is
    # never suppressive (same rule as everywhere else).
    if ft == "NOT_PAYING" and _RANK[state] > _RANK["SELECTIVO"]:
        state = "SELECTIVO"
        detail = ""
        if ft_delivery is not None:
            detail = f" ({ft_delivery * 100:.0f}% pagando"
            detail += f" vs {ft_baseline * 100:.0f}% base)" if ft_baseline is not None else ")"
        reasons.append(f"el mercado no está pagando las señales recientes{detail}")

    unlock = None
    if h in ("DAMAGED", "FRAGILE"):
        unlock = (
            f"RECOVERING requiere {repair_streak_min} ruedas limpias consecutivas "
            f"(racha actual: {repair_streak})"
        )
    elif h == "RECOVERING":
        unlock = "ROBUST cuando el daño envejezca fuera de la ventana de 20 ruedas"

    return Posture(
        state=state,
        instruction=_instruction(state),
        reasons=reasons,
        unlock=unlock,
    )
