"""Context Decision Filter — translates market context descriptor pairs to filtering decisions.

Change: openspec/changes/market-context-decision-wiring/
Spec:   openspec/changes/market-context-decision-wiring/specs/context-decision-filter/spec.md
Prior:  openspec/changes/market-context-engine-phase-1/
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300

# ─── Value object ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ContextMultiplier:
    score_multiplier: float
    suppress_lenses: list[str]
    surface_warnings: list[str]

    def __post_init__(self):
        # frozen dataclass: use object.__setattr__ trick not needed here — just validate
        if not (0.0 <= self.score_multiplier <= 2.0):
            raise ValueError(f"score_multiplier {self.score_multiplier} out of range [0.0, 2.0]")


_NEUTRAL = ContextMultiplier(1.0, [], [])

# ─── Valid descriptor sets ────────────────────────────────────────────────────

_VALID_PARTICIPATION = {"EXPANDING", "STABLE", "NARROWING", "COLLAPSING", "UNKNOWN"}
_VALID_LEADERSHIP    = {"EXPANDING", "HEALTHY", "THINNING", "COLLAPSING", "EXHAUSTED", "UNKNOWN"}

# ─── Phase 1 rules table ──────────────────────────────────────────────────────
# Each entry covers an exact (participation, leadership) pair.
# Cells not listed fall back to _NEUTRAL.
# Precedence (handled in compute_context_multiplier):
#   1. COLLAPSING participation — strongest rule
#   2. NARROWING + adverse leadership
#   3. EXHAUSTED leadership override (when not already covered by 1 or 2)
#   4. EXPANDING + supportive leadership

_ADVERSE_LEADERSHIP = {"THINNING", "COLLAPSING", "EXHAUSTED"}
_SUPPORTIVE_LEADERSHIP = {"EXPANDING", "HEALTHY"}

_RULES: dict[tuple[str, str], ContextMultiplier] = {
    # ── COLLAPSING participation (rule 1) ────────────────────────────────────
    **{
        ("COLLAPSING", ldr): ContextMultiplier(0.5, ["u-and-r", "emerging-leaders"], [])
        for ldr in _VALID_LEADERSHIP
    },
    # ── NARROWING + adverse leadership (rule 2) ──────────────────────────────
    **{
        ("NARROWING", ldr): ContextMultiplier(0.7, ["emerging-leaders"], [])
        for ldr in _ADVERSE_LEADERSHIP
    },
    # ── EXHAUSTED leadership override (rule 3) ───────────────────────────────
    # Only applies to participation values NOT already handled by rules 1 or 2.
    # COLLAPSING handled above; NARROWING+EXHAUSTED handled above.
    # So EXHAUSTED applies to: EXPANDING, STABLE, NARROWING (non-adverse), UNKNOWN
    # Note: NARROWING + EXHAUSTED is already in rule 2 above (0.7, suppress emerging)
    # For EXPANDING + EXHAUSTED, rule 3 (0.6 + warning) takes precedence over rule 4 boost.
    ("EXPANDING", "EXHAUSTED"): ContextMultiplier(0.6, [], ["leadership_exhausted"]),
    ("STABLE",    "EXHAUSTED"): ContextMultiplier(0.6, [], ["leadership_exhausted"]),
    ("UNKNOWN",   "EXHAUSTED"): _NEUTRAL,  # UNKNOWN is always neutral per Decision 2
    # NARROWING + EXHAUSTED already in rule 2 → suppress emerging-leaders, multiplier 0.7
    # Add warning on top for NARROWING + EXHAUSTED (override rule 2 with warning added)
    ("NARROWING", "EXHAUSTED"): ContextMultiplier(0.7, ["emerging-leaders"], ["leadership_exhausted"]),
    # ── EXPANDING + supportive leadership (rule 4) ───────────────────────────
    ("EXPANDING", "EXPANDING"): ContextMultiplier(1.1, [], []),
    ("EXPANDING", "HEALTHY"):   ContextMultiplier(1.1, [], []),
}

# ─── Spanish suppression reasons ─────────────────────────────────────────────

_REASONS: dict[tuple[str, str], str] = {
    ("COLLAPSING", "EXPANDING"):  "Participación COLLAPSING — sin amplitud de mercado, los setups de corto horizonte fallan históricamente",
    ("COLLAPSING", "HEALTHY"):    "Participación COLLAPSING — sin amplitud de mercado, los setups de corto horizonte fallan históricamente",
    ("COLLAPSING", "THINNING"):   "Participación COLLAPSING + liderazgo debilitándose — condición de mercado hostil",
    ("COLLAPSING", "COLLAPSING"): "Participación y liderazgo COLLAPSING — mercado en deterioro severo",
    ("COLLAPSING", "EXHAUSTED"):  "Participación COLLAPSING con liderazgo EXHAUSTED — mercado en deterioro severo",
    ("COLLAPSING", "UNKNOWN"):    "Participación COLLAPSING — sin amplitud de mercado, los setups de corto horizonte fallan históricamente",
    ("NARROWING",  "THINNING"):   "Participación NARROWING + liderazgo THINNING — líderes emergentes sin soporte de amplitud",
    ("NARROWING",  "COLLAPSING"): "Participación NARROWING + liderazgo COLLAPSING — líderes emergentes no tienen base para continuar",
    ("NARROWING",  "EXHAUSTED"):  "Participación NARROWING + liderazgo EXHAUSTED — líderes emergentes en contexto de agotamiento",
}

# ─── Module-level cache ───────────────────────────────────────────────────────

_cache: dict[tuple[str, str], tuple[ContextMultiplier, datetime]] = {}


def clear_cache() -> None:
    """Clear the in-process decision cache (for testing and invalidation hooks)."""
    _cache.clear()


# ─── Core function ────────────────────────────────────────────────────────────

def compute_context_multiplier(participation: str, leadership: str) -> ContextMultiplier:
    """Return the ContextMultiplier for the given descriptor pair.

    Pure and idempotent. Invalid values coerced to UNKNOWN.
    UNKNOWN in either dimension → _NEUTRAL (never suppressive on missing data).
    """
    p = participation.upper() if participation else "UNKNOWN"
    l = leadership.upper() if leadership else "UNKNOWN"

    if p not in _VALID_PARTICIPATION:
        p = "UNKNOWN"
    if l not in _VALID_LEADERSHIP:
        l = "UNKNOWN"

    # UNKNOWN in either dimension is always neutral (Decision 2)
    if p == "UNKNOWN" or l == "UNKNOWN":
        return _NEUTRAL

    key = (p, l)

    # Cache check
    if key in _cache:
        cached, cached_at = _cache[key]
        if (datetime.utcnow() - cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return cached

    result = _RULES.get(key, _NEUTRAL)
    _cache[key] = (result, datetime.utcnow())
    return result


def format_suppression_reason(lens: str, participation: str, leadership: str) -> str:
    """Return human-readable Spanish reason for suppression of the given lens."""
    p = (participation or "UNKNOWN").upper()
    l = (leadership or "UNKNOWN").upper()
    reason = _REASONS.get((p, l))
    if reason:
        return reason
    return f"Contexto de mercado ({p} × {l}) suprime esta lens en régimen actual"


# ─── Endpoint integration helper ─────────────────────────────────────────────

async def fetch_current_context(db) -> tuple[str, str]:
    """Fetch (participation_descriptor, leadership_descriptor) from MarketContextEngine.

    Returns ("UNKNOWN", "UNKNOWN") on any exception — cold-start safety.
    """
    try:
        from app.services.market_context_engine import MarketContextEngine
        ctx = await MarketContextEngine(db).analyze()
        if ctx is None:
            return ("UNKNOWN", "UNKNOWN")
        participation = (ctx.participation.descriptor or "UNKNOWN").upper()
        leadership = (ctx.leadership.descriptor or "UNKNOWN").upper()
        logger.info(
            "context_decision_filter: fetched context participation=%s leadership=%s",
            participation, leadership,
        )
        return (participation, leadership)
    except Exception as exc:
        logger.info("context_decision_filter: fetch_current_context fallback to UNKNOWN — %s", exc)
        return ("UNKNOWN", "UNKNOWN")
