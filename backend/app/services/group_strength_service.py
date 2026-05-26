"""Group Strength Service — translates market_group performance rank to scoring multipliers.

Architectural mirror of context_decision_filter.py (macro context → multiplier),
but operating at the group level. See: openspec/changes/wire-group-strength-to-scoring/

Each stock's market_group is ranked by performance_monthly among the ~24 active
groups. Top 20% → leader/1.15 boost; bottom 20% → weak/0.85 penalty; rest → neutral.
Multiplier is applied compositionally in the /actionable endpoint, after ctx_multiplier.
Queue endpoints surface only the badge — no sort modification.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300
_MIN_GROUP_SIZE = 5  # groups with fewer stocks post-quality-filter → forced neutral

# ─── Value object ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GroupMultiplier:
    score_multiplier: float
    badge: str  # "leader" | "neutral" | "weak"

    def __post_init__(self):
        if self.score_multiplier not in (0.85, 1.00, 1.15):
            raise ValueError(f"score_multiplier must be 0.85, 1.00, or 1.15 — got {self.score_multiplier}")
        if self.badge not in ("leader", "neutral", "weak"):
            raise ValueError(f"badge must be leader/neutral/weak — got {self.badge!r}")


_NEUTRAL = GroupMultiplier(1.00, "neutral")
_LEADER  = GroupMultiplier(1.15, "leader")
_WEAK    = GroupMultiplier(0.85, "weak")

# ─── Module-level cache ───────────────────────────────────────────────────────

_cache: dict[str, tuple[dict, datetime]] = {}


def clear_cache() -> None:
    """Clear the in-process cache (for tests and manual invalidation)."""
    _cache.clear()


# ─── Core function ────────────────────────────────────────────────────────────

def compute_group_multiplier(
    market_group: Optional[str],
    group_perfs: dict[str, dict],
) -> GroupMultiplier:
    """Return GroupMultiplier for a given market_group using the current performance snapshot.

    Args:
        market_group: value of stocks.market_group for the stock, or None.
        group_perfs: dict keyed by group name with at least
                     {"performance_monthly": float, "stock_count": int}.
                     Produced by fetch_current_group_strengths().

    Returns:
        GroupMultiplier — always _NEUTRAL on any missing/unknown input.
    """
    if not market_group:
        return _NEUTRAL
    if not group_perfs:
        return _NEUTRAL

    entry = group_perfs.get(market_group)
    if entry is None:
        return _NEUTRAL

    # Small-group guard: n<5 post-quality-filter → noise too high to trust
    if (entry.get("stock_count") or 0) < _MIN_GROUP_SIZE:
        return _NEUTRAL

    # Rank all groups with sufficient size by performance_monthly
    eligible = {
        g: d["performance_monthly"]
        for g, d in group_perfs.items()
        if (d.get("stock_count") or 0) >= _MIN_GROUP_SIZE
        and d.get("performance_monthly") is not None
    }

    if not eligible:
        return _NEUTRAL

    sorted_groups = sorted(eligible, key=lambda g: eligible[g], reverse=True)
    n = len(sorted_groups)
    top_cutoff    = max(1, round(n * 0.20))
    bottom_cutoff = n - max(1, round(n * 0.20))

    try:
        rank = sorted_groups.index(market_group)  # 0-based, lower = stronger
    except ValueError:
        return _NEUTRAL

    if rank < top_cutoff:
        return _LEADER
    if rank >= bottom_cutoff:
        return _WEAK
    return _NEUTRAL


# ─── DB fetch helper ──────────────────────────────────────────────────────────

async def fetch_current_group_strengths(db) -> dict[str, dict]:
    """Fetch {group_name: {performance_monthly, stock_count}} from SectorService.

    Cached for _CACHE_TTL_SECONDS. Returns {} on any exception (cold-start safety).
    """
    cache_key = "current_group_strengths"
    now = datetime.utcnow()

    if cache_key in _cache:
        cached_data, cached_at = _cache[cache_key]
        if (now - cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return cached_data

    try:
        from app.services.sector_service import SectorService
        raw: list[dict] = await SectorService(db).calculate_sector_performance()
        result = {
            entry["name"]: {
                "performance_monthly": entry.get("performance_monthly"),
                "stock_count": entry.get("stock_count", 0),
            }
            for entry in raw
            if entry.get("name")
        }
    except Exception as exc:
        logger.info("group_strength_service: fetch fallback to {} — %s", exc)
        result = {}

    _cache[cache_key] = (result, now)
    return result
