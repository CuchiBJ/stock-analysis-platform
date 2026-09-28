"""Thin authenticated router for the private journal API.

Request orchestration is implemented in :mod:`app.services.journal_application`.
This module intentionally remains a small, reviewable authentication boundary.
"""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_active_user
from app.services import journal_application as _application

router = APIRouter(
    prefix="/journal",
    tags=["journal"],
    dependencies=[Depends(get_current_active_user)],
)
router.include_router(_application.router)

# Compatibility exports for existing internal callers and focused tests.
JournalTrade = _application.JournalTrade
JournalRepository = _application.JournalRepository
OpenTradeIn = _application.OpenTradeIn
CloseTradeIn = _application.CloseTradeIn
PatchTradeIn = _application.PatchTradeIn

import_journal = _application.import_journal
list_trades = _application.list_trades
journal_stats = _application.journal_stats
export_csv = _application.export_csv
backfill_regime = _application.backfill_regime
get_vocabularies = _application.get_vocabularies
get_trade_draft = _application.get_trade_draft
create_open_trade = _application.create_open_trade
close_trade = _application.close_trade
patch_trade = _application.patch_trade
get_stop_history = _application.get_stop_history
delete_trade = _application.delete_trade

_aggregate = _application._aggregate
_classify_resolved_decision = _application._classify_resolved_decision
_decision_economic_metrics = _application._decision_economic_metrics
_decision_result_detail = _application._decision_result_detail
_decision_runner_breakeven_id = _application._decision_runner_breakeven_id
_decision_weighted_r = _application._decision_weighted_r
_performance_trades = _application._performance_trades


def __getattr__(name: str):
    """Retain read-only compatibility for non-public implementation helpers."""
    return getattr(_application, name)
