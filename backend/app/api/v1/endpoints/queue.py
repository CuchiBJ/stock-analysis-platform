"""Setup Queue API — three lenses + per-symbol history."""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.services.setup_queue_service import SetupQueueService
from app.services.context_decision_filter import (
    fetch_current_context,
    compute_context_multiplier,
    format_suppression_reason,
)
from app.services.group_strength_service import fetch_current_group_strengths, compute_group_multiplier

logger = logging.getLogger(__name__)

router = APIRouter()


def _enrich_with_group_strength(results: list[dict], group_perfs: dict) -> list[dict]:
    """Add group_strength badge (no multiplier) to each result item."""
    for item in results:
        mg = item.get("market_group")
        gm = compute_group_multiplier(mg, group_perfs)
        item["group_strength"] = {"group": mg, "badge": gm.badge}
    return results


def _with_context_envelope(lens_id: str, results: list, participation: str, leadership: str) -> dict:
    """Wrap a lens result list with context suppression metadata."""
    assert lens_id != "building-bases" or True, "building-bases must never reach suppress_lenses"

    multiplier = compute_context_multiplier(participation, leadership)
    suppressed = lens_id in multiplier.suppress_lenses
    context_snapshot = {"participation": participation, "leadership": leadership}

    if suppressed:
        reason = format_suppression_reason(lens_id, participation, leadership)
        logger.info(
            'context_decision_filter: lens=%s suppressed reason="participation=%s + leadership=%s"',
            lens_id, participation, leadership,
        )
    else:
        reason = None

    return {
        "suppressed": suppressed,
        "suppression_reason": reason,
        "context_snapshot": context_snapshot,
        "results": results,
    }


@router.get("/u-and-r")
async def u_and_r_queue(db: AsyncSession = Depends(get_db)):
    """U&R candidates: Minervini leaders with recent pre-reclaim event, 'from above'."""
    results = await SetupQueueService(db).list_u_and_r()
    participation, leadership = await fetch_current_context(db)
    group_perfs = await fetch_current_group_strengths(db)
    _enrich_with_group_strength(results, group_perfs)
    return _with_context_envelope("u-and-r", results, participation, leadership)


@router.get("/emerging-leaders")
async def emerging_leaders_queue(db: AsyncSession = Depends(get_db)):
    """Strong stocks not fully Minervini-qualified, with per-criterion breakdown."""
    results = await SetupQueueService(db).list_emerging_leaders()
    participation, leadership = await fetch_current_context(db)
    group_perfs = await fetch_current_group_strengths(db)
    _enrich_with_group_strength(results, group_perfs)
    return _with_context_envelope("emerging-leaders", results, participation, leadership)


@router.get("/building-bases")
async def building_bases_queue(db: AsyncSession = Depends(get_db)):
    """Minervini leaders in tight VCP-style consolidation (next-cycle candidates)."""
    results = await SetupQueueService(db).list_building_bases()
    participation, leadership = await fetch_current_context(db)
    group_perfs = await fetch_current_group_strengths(db)
    _enrich_with_group_strength(results, group_perfs)
    # building-bases is NEVER suppressed — assert defensively
    multiplier = compute_context_multiplier(participation, leadership)
    assert "building-bases" not in multiplier.suppress_lenses, (
        f"building-bases must never appear in suppress_lenses "
        f"(participation={participation}, leadership={leadership})"
    )
    return _with_context_envelope("building-bases", results, participation, leadership)


@router.get("/symbol/{symbol}/history")
async def symbol_history(
    symbol: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Per-symbol transition arc + outcome track-record overlay."""
    return await SetupQueueService(db).get_symbol_history(symbol.upper(), days)
