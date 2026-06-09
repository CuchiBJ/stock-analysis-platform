"""Journal endpoints — ingest the user's broker trade journal CSV, list parsed
trades, and surface aggregate stats (expectancy, win rate, profit factor) cut
by setup × context. The journal is the source of truth for what actually
happened with real capital and complements the synthetic transition_observations
calibration loop with verified outcomes.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.stock import JournalTrade, JournalStopEvent, TransitionObservation
from app.services.journal_importer import JournalImporter
from app.services.journal_snapshot_service import take_entry_snapshot

router = APIRouter(prefix="/journal", tags=["journal"])

# Canonical vocabularies surfaced to the form. Keep in sync with importer SETUP_MAP / CONTEXT_MAP.
SETUP_OPTIONS = [
    "u_and_r", "building_base", "emerging",
    "breakout", "episodic_pivot", "reversal",
    "vwap", "dca", "other",
]
CONTEXT_OPTIONS = [
    "favorable", "neutral", "choppy", "adverse",
    "rs_against_market", "unknown",
]
ENTRY_REASON_OPTIONS = [
    "queue_signal", "discretionary", "continuation", "news", "other",
]
EXIT_REASON_OPTIONS = [
    "stop_hit", "target", "trail", "thesis_broken",
    "discretionary", "partial_take", "unknown",
]

DEFAULT_COMMISSION = 1.0


@router.post("/import")
async def import_journal(
    file: UploadFile = File(...),
    replace: bool = Query(True, description="Clear existing trades before import"),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')

    importer = JournalImporter(db)
    cleared = 0
    if replace:
        cleared = await importer.clear_all()
    try:
        stats = await importer.import_csv(text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "cleared_prior_trades": cleared,
        **asdict(stats),
    }


@router.get("/trades")
async def list_trades(
    setup: Optional[str] = None,
    context: Optional[str] = None,
    closed_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    q = select(JournalTrade).order_by(JournalTrade.entry_date.desc(), JournalTrade.id.desc())
    if setup:
        q = q.where(JournalTrade.setup == setup)
    if context:
        q = q.where(JournalTrade.context == context)
    if closed_only:
        q = q.where(JournalTrade.exit_date.is_not(None))

    rows = (await db.execute(q)).scalars().all()
    return {
        "count": len(rows),
        "trades": [_trade_to_dict(t) for t in rows],
    }


def _derive_pnl(t: JournalTrade) -> Optional[float]:
    if t.pnl_dollars is not None:
        return t.pnl_dollars
    if t.exit_price is not None and t.entry_price is not None and t.qty is not None:
        return (t.exit_price - t.entry_price) * t.qty - 2 * DEFAULT_COMMISSION
    return None


def _derive_r(t: JournalTrade) -> Optional[float]:
    """R-multiple uses initial_stop_price (planned risk) when present, falling
    back to current stop_price for backward compatibility with historical
    CSV-imported trades. This preserves cross-trade comparability even when
    the operator has moved the stop to BE or trailed it during the trade.
    """
    if t.r_multiple is not None:
        return t.r_multiple
    if t.exit_price is None or t.entry_price is None:
        return None
    stop = t.initial_stop_price if t.initial_stop_price is not None else t.stop_price
    if stop is None or t.entry_price <= stop:
        return None
    return (t.exit_price - t.entry_price) / (t.entry_price - stop)


def _derive_duration(t: JournalTrade) -> Optional[float]:
    if t.duration_days is not None:
        return t.duration_days
    if t.exit_date is not None and t.entry_date is not None:
        return float((t.exit_date - t.entry_date).days)
    return None


def _derive_effective_risk(t: JournalTrade) -> Optional[float]:
    """Operator intent (planned_risk_dollars) takes precedence over stop-derived
    inference. Returns None when neither path produces a positive number.
    """
    if t.planned_risk_dollars is not None and t.planned_risk_dollars > 0:
        return t.planned_risk_dollars
    if (t.stop_price is not None and t.entry_price is not None
            and t.qty is not None and t.entry_price > t.stop_price):
        return (t.entry_price - t.stop_price) * t.qty
    return None


# A trade rarely lands at *exactly* $0 once commissions are netted, so a bare
# pnl == 0 test almost never fires and near-scratch results leak into wins/losses.
# We treat any result inside a tolerance band as break-even ("scratch"): a trade
# that neither meaningfully captured nor lost. The band is expressed in R (the
# system's decision unit) via effective risk, falling back to a % of position
# notional when no stop/risk is known.
_BE_R_BAND = 0.1      # within ±0.1R of entry counts as a scratch
_BE_PCT_BAND = 0.001  # fallback: within ±0.1% of position notional


def _be_band_dollars(t: JournalTrade) -> float:
    """Dollar half-width of the break-even band for one trade leg.

    Returns 0.0 when neither risk nor notional can be derived, which collapses
    back to the old exact-zero behavior for that trade rather than silently
    widening it.
    """
    risk = _derive_effective_risk(t)
    if risk is not None and risk > 0:
        return _BE_R_BAND * risk
    if t.entry_price is not None and t.qty:
        return _BE_PCT_BAND * abs(t.entry_price * t.qty)
    return 0.0


_STOP_BE_TOLERANCE = 1e-6


def _classify_stop_change(
    old: Optional[float], new: Optional[float], entry_price: float
) -> Optional[str]:
    """Auto-classify a stop change into one of 5 kinds. Returns None when
    nothing actually changed (idempotent PATCH).
    """
    if old is None and new is None:
        return None
    if old is None and new is not None:
        return 'initial'
    if old is not None and new is None:
        return 'removed'
    # Both non-null at this point.
    if abs(new - old) < _STOP_BE_TOLERANCE:
        return None
    # moved_to_be takes precedence over trailed_up: a stop reaching/passing entry
    # is the meaningful operational event.
    if new + _STOP_BE_TOLERANCE >= entry_price:
        return 'moved_to_be'
    if new > old:
        return 'trailed_up'
    return 'widened'


def _record_stop_event(
    db: AsyncSession,
    trade_id: int,
    old: Optional[float],
    new: Optional[float],
    kind: str,
) -> None:
    db.add(JournalStopEvent(
        trade_id=trade_id,
        old_stop_price=old,
        new_stop_price=new,
        kind=kind,
        auto_classified=True,
    ))


def _derive_risk_pct(t: JournalTrade) -> Optional[float]:
    risk = _derive_effective_risk(t)
    if risk is None:
        return None
    if t.account_balance_at_entry is None or t.account_balance_at_entry <= 0:
        return None
    return risk / t.account_balance_at_entry


def _aggregate(trades: list[JournalTrade]) -> dict:
    """Compute the institutional metrics: count, win rate, expectancy,
    profit factor, avg R, avg duration. Skips trades with missing pnl.
    Uses the same on-the-fly fallback as _trade_to_dict so trades whose
    CSV-imported pnl was empty still contribute to aggregates.
    """
    pnls = [(t, _derive_pnl(t)) for t in trades]
    with_pnl = [(t, p) for t, p in pnls if p is not None]
    n = len(with_pnl)
    if n == 0:
        return {
            "n": 0,
            "win_rate": None,
            "expectancy": None,
            "profit_factor": None,
            "avg_r": None,
            "total_r": None,
            "avg_duration_days": None,
            "total_pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
        }
    # Classify each resolved trade against its break-even band rather than a
    # bare sign test, so near-scratch results don't inflate wins/losses.
    wins: list[tuple[JournalTrade, float]] = []
    losses: list[tuple[JournalTrade, float]] = []
    breakeven: list[tuple[JournalTrade, float]] = []
    for t, p in with_pnl:
        if abs(p) <= _be_band_dollars(t):
            breakeven.append((t, p))
        elif p > 0:
            wins.append((t, p))
        else:
            losses.append((t, p))
    gross_win = sum(p for _, p in wins)
    gross_loss = abs(sum(p for _, p in losses))
    total = sum(p for _, p in with_pnl)
    rs = [r for r in (_derive_r(t) for t, _ in with_pnl) if r is not None]
    durs = [d for d in (_derive_duration(t) for t, _ in with_pnl) if d is not None]
    # WR excludes breakeven from denominator (institutional convention): a BE
    # trade neither captures nor loses, so it adds no information about edge.
    # Expectancy keeps the full N denominator — total return per trade taken,
    # including the BEs that consumed time/risk.
    resolved = len(wins) + len(losses)
    win_rate = (len(wins) / resolved) if resolved > 0 else None
    return {
        "n": n,
        "win_rate": win_rate,
        "expectancy": total / n,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else None,
        "avg_r": (sum(rs) / len(rs)) if rs else None,
        # Total R is the honest "edge in decision units" — invariant to operator
        # changing position size over time. When total_pnl is negative but total_r
        # is positive, the operator's recent decisions have edge that's hidden by
        # capital-management changes (e.g. shrinking R unit defensively).
        "total_r": sum(rs) if rs else None,
        "avg_duration_days": (sum(durs) / len(durs)) if durs else None,
        "total_pnl": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
    }


@router.get("/stats")
async def journal_stats(db: AsyncSession = Depends(get_db)):
    """Returns overall metrics + breakdowns by setup, context, and setup×context."""
    rows = (
        await db.execute(
            select(JournalTrade).where(JournalTrade.exit_date.is_not(None))
        )
    ).scalars().all()

    overall = _aggregate(rows)

    # By setup
    by_setup: dict[str, list[JournalTrade]] = {}
    for t in rows:
        by_setup.setdefault(t.setup, []).append(t)
    setup_breakdown = [
        {"setup": k, **_aggregate(v)}
        for k, v in sorted(by_setup.items(), key=lambda kv: -len(kv[1]))
    ]

    # By context
    by_ctx: dict[str, list[JournalTrade]] = {}
    for t in rows:
        by_ctx.setdefault(t.context, []).append(t)
    context_breakdown = [
        {"context": k, **_aggregate(v)}
        for k, v in sorted(by_ctx.items(), key=lambda kv: -len(kv[1]))
    ]

    # Setup × context matrix
    matrix: dict[tuple[str, str], list[JournalTrade]] = {}
    for t in rows:
        matrix.setdefault((t.setup, t.context), []).append(t)
    matrix_rows = [
        {"setup": s, "context": c, **_aggregate(v)}
        for (s, c), v in sorted(matrix.items(), key=lambda kv: -len(kv[1]))
    ]

    # By entry_reason — separates queue_signal from discretional decisions
    by_entry_reason_dict: dict[str, list[JournalTrade]] = {}
    for t in rows:
        by_entry_reason_dict.setdefault(t.entry_reason, []).append(t)
    entry_reason_breakdown = [
        {"entry_reason": k, **_aggregate(v)}
        for k, v in sorted(by_entry_reason_dict.items(), key=lambda kv: -len(kv[1]))
    ]

    # By regime_at_entry — objective (engine-driven) replacement for manual context
    by_regime_dict: dict[str, list[JournalTrade]] = {}
    for t in rows:
        key = t.regime_at_entry if t.regime_at_entry else "sin data"
        by_regime_dict.setdefault(key, []).append(t)
    by_regime_at_entry = [
        {"regime_at_entry": k, **_aggregate(v)}
        for k, v in sorted(by_regime_dict.items(), key=lambda kv: -len(kv[1]))
    ]

    # Setup × regime_at_entry — the honest performance matrix
    setup_regime_matrix: dict[tuple[str, str], list[JournalTrade]] = {}
    for t in rows:
        key = t.regime_at_entry if t.regime_at_entry else "sin data"
        setup_regime_matrix.setdefault((t.setup, key), []).append(t)
    by_setup_regime_matrix = [
        {"setup": s, "regime_at_entry": r, **_aggregate(v)}
        for (s, r), v in sorted(setup_regime_matrix.items(), key=lambda kv: -len(kv[1]))
    ]

    # Decision-level aggregates — institutional truth. Each "decision" is one
    # original Compra and all its partial-fill children (linked via
    # parent_trade_id). WR / Total R must be measured here, not at row level,
    # because a single decision producing 2 winning partial sells should count
    # as 1 winner, not 2.
    all_trade_rows = (
        await db.execute(select(JournalTrade))
    ).scalars().all()
    decisions: dict[int, list[JournalTrade]] = {}
    for t in all_trade_rows:
        decision_id = t.parent_trade_id if t.parent_trade_id is not None else t.id
        decisions.setdefault(decision_id, []).append(t)

    n_fully_resolved = 0
    n_partially_resolved = 0
    n_fully_open = 0
    decision_wins = 0
    decision_losses = 0
    decision_breakeven = 0
    decision_total_realized_pnl = 0.0
    decision_total_r = 0.0

    for legs in decisions.values():
        closed_legs = [l for l in legs if l.exit_date is not None]
        open_legs = [l for l in legs if l.exit_date is None]
        # State classification
        if len(closed_legs) == 0:
            n_fully_open += 1
        elif len(open_legs) == 0:
            n_fully_resolved += 1
        else:
            n_partially_resolved += 1
        # Realized PnL across all closed legs of the decision
        closed_pnls = [p for p in (_derive_pnl(l) for l in closed_legs) if p is not None]
        net_pnl = sum(closed_pnls) if closed_pnls else 0.0
        decision_total_realized_pnl += net_pnl
        # Qty-weighted R for the decision
        rs_with_qty = [
            (_derive_r(l), l.qty) for l in closed_legs
            if _derive_r(l) is not None and l.qty
        ]
        if rs_with_qty:
            tot_qty = sum(q for _, q in rs_with_qty)
            decision_total_r += sum(r * q for r, q in rs_with_qty) / tot_qty
        # WR classification only for fully_resolved. The decision's BE band is
        # the sum of its closed legs' bands, since net_pnl is summed across them.
        if len(open_legs) == 0 and len(closed_legs) > 0 and closed_pnls:
            decision_be_band = sum(_be_band_dollars(l) for l in closed_legs)
            # "Took profits previously": a decision that booked a real partial
            # gain on any leg and ended net non-negative is a WIN, even when the
            # runner was stopped at BE and net_pnl lands inside the scratch band.
            # Scaling out at a profit and giving the remainder a free shot is a
            # won trade, not a scratch — the locked-in gain stands.
            booked_partial_gain = any(
                (p := _derive_pnl(l)) is not None and p > _be_band_dollars(l)
                for l in closed_legs
            )
            if net_pnl > decision_be_band:
                decision_wins += 1
            elif net_pnl < -decision_be_band:
                decision_losses += 1
            elif booked_partial_gain and net_pnl >= 0:
                decision_wins += 1
            else:
                decision_breakeven += 1

    decision_resolved = decision_wins + decision_losses
    decision_overall = {
        "n_decisions_total": len(decisions),
        "n_fully_resolved": n_fully_resolved,
        "n_partially_resolved": n_partially_resolved,
        "n_fully_open": n_fully_open,
        "decision_wins": decision_wins,
        "decision_losses": decision_losses,
        "decision_breakeven": decision_breakeven,
        "decision_win_rate": (decision_wins / decision_resolved) if decision_resolved > 0 else None,
        "decision_total_realized_pnl": decision_total_realized_pnl,
        "decision_total_r": decision_total_r if any(
            _derive_r(l) is not None for legs in decisions.values() for l in legs
        ) else None,
    }

    # Risk evolution by month — surfaces R unit shrinkage / scaling over time.
    # Each bucket contrasts dollar P&L (affected by sizing) with total R
    # (invariant to sizing) so the operator can see when their decisions had
    # edge even if absolute P&L was masked by capital-management choices.
    by_month_dict: dict[str, list[JournalTrade]] = {}
    for t in rows:
        if t.entry_date is None:
            continue
        by_month_dict.setdefault(t.entry_date.isoformat()[:7], []).append(t)
    risk_evolution = []
    for month in sorted(by_month_dict.keys()):
        bucket = by_month_dict[month]
        eff_risks = [r for r in (_derive_effective_risk(t) for t in bucket) if r is not None]
        risk_pcts = [r for r in (_derive_risk_pct(t) for t in bucket) if r is not None]
        rs = [r for r in (_derive_r(t) for t in bucket) if r is not None]
        pnls = [p for p in (_derive_pnl(t) for t in bucket) if p is not None]
        risk_evolution.append({
            "month": month,
            "n": len(bucket),
            "avg_planned_risk_dollars": (sum(eff_risks) / len(eff_risks)) if eff_risks else None,
            "avg_risk_pct_of_account": (sum(risk_pcts) / len(risk_pcts)) if risk_pcts else None,
            "total_r": sum(rs) if rs else None,
            "total_pnl": sum(pnls) if pnls else 0.0,
        })

    # Data starvation honesty: count of (setup, context) buckets with < 5 trades
    underpowered = sum(1 for r in matrix_rows if r["n"] < 5)

    # Open positions
    open_count = (
        await db.execute(
            select(func.count(JournalTrade.id)).where(JournalTrade.exit_date.is_(None))
        )
    ).scalar() or 0

    linked_count = (
        await db.execute(
            select(func.count(JournalTrade.id)).where(JournalTrade.linked_observation_id.is_not(None))
        )
    ).scalar() or 0

    # Provenance capture rate: trades where from_queue has been marked (true OR false)
    # over total. Null means "operator never marked it" — denominator only. This
    # tells the operator whether the take-from-queue workflow is being used.
    total_count_for_provenance = (
        await db.execute(select(func.count(JournalTrade.id)))
    ).scalar() or 0
    marked_count = (
        await db.execute(
            select(func.count(JournalTrade.id)).where(JournalTrade.from_queue.is_not(None))
        )
    ).scalar() or 0
    provenance_capture_rate = (
        marked_count / total_count_for_provenance if total_count_for_provenance > 0 else 0.0
    )

    return {
        "overall": overall,
        "by_setup": setup_breakdown,
        "by_context": context_breakdown,
        "by_setup_context": matrix_rows,
        "by_entry_reason": entry_reason_breakdown,
        "by_regime_at_entry": by_regime_at_entry,
        "by_setup_regime_matrix": by_setup_regime_matrix,
        "decision_overall": decision_overall,
        "risk_evolution": risk_evolution,
        "open_positions": open_count,
        "linked_to_observations": linked_count,
        "underpowered_buckets": underpowered,
        "provenance_capture_rate": provenance_capture_rate,
    }


# --- CRUD: replace the spreadsheet ----------------------------------------------


def _trade_to_dict(t: JournalTrade) -> dict:
    # All derived fields (cost_total, pnl_dollars, pnl_pct, r_multiple,
    # duration_days) fall back to on-the-fly computation when the persisted
    # cache is NULL. This handles both new trades that skip eager persistence
    # AND historical CSV-imported rows where the Retorno/R columns were empty.
    cost_total = t.cost_total
    if cost_total is None and t.entry_price is not None and t.qty is not None:
        cost_total = t.entry_price * t.qty
    pnl_pct = t.pnl_pct
    if pnl_pct is None and t.exit_price is not None and t.entry_price not in (None, 0):
        pnl_pct = t.exit_price / t.entry_price - 1.0
    pnl_dollars = _derive_pnl(t)
    r_multiple = _derive_r(t)
    duration_days = _derive_duration(t)
    return {
        "id": t.id,
        "symbol": t.symbol,
        "setup": t.setup,
        "context": t.context,
        "entry_date": t.entry_date.isoformat() if t.entry_date else None,
        "entry_price": t.entry_price,
        "qty": t.qty,
        "stop_price": t.stop_price,
        "cost_total": cost_total,
        "exit_date": t.exit_date.isoformat() if t.exit_date else None,
        "exit_price": t.exit_price,
        "duration_days": duration_days,
        "pnl_dollars": pnl_dollars,
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,
        "error_note": t.error_note,
        "post_venta": t.post_venta,
        "linked_observation_id": t.linked_observation_id,
        "is_open": t.exit_date is None,
        "from_queue": t.from_queue,
        "entry_reason": t.entry_reason,
        "exit_reason": t.exit_reason,
        "planned_risk_dollars": t.planned_risk_dollars,
        "account_balance_at_entry": t.account_balance_at_entry,
        "effective_risk_dollars": _derive_effective_risk(t),
        "risk_pct_of_account": _derive_risk_pct(t),
        "regime_at_entry": t.regime_at_entry,
        "system_score_at_entry": t.system_score_at_entry,
        "group_strength_at_entry": t.group_strength_at_entry,
        "leader_health_at_entry": t.leader_health_at_entry,
        "initial_stop_price": t.initial_stop_price,
        "is_risk_free": (
            t.stop_price is not None and t.entry_price is not None
            and t.stop_price + _STOP_BE_TOLERANCE >= t.entry_price
        ),
        "parent_trade_id": t.parent_trade_id,
        "decision_id": t.parent_trade_id if t.parent_trade_id is not None else t.id,
    }


async def _find_linked_observation(db: AsyncSession, symbol: str, entry_date: date) -> Optional[int]:
    from datetime import timedelta
    window_start = entry_date - timedelta(days=3)
    window_end = entry_date + timedelta(days=3)
    candidates = (await db.execute(
        select(TransitionObservation.id, TransitionObservation.date_detected)
        .where(TransitionObservation.symbol == symbol)
        .where(TransitionObservation.date_detected >= window_start)
        .where(TransitionObservation.date_detected <= window_end)
    )).all()
    if not candidates:
        return None
    return min(candidates, key=lambda r: abs((r.date_detected - entry_date).days)).id


def _validate_enum(value: Optional[str], allowed: list[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    if value not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be one of {allowed}, got '{value}'",
        )
    return value


class OpenTradeIn(BaseModel):
    symbol: str
    entry_date: date
    entry_price: float = Field(gt=0)
    qty: float = Field(gt=0)
    stop_price: Optional[float] = Field(default=None, gt=0)
    setup: str = "unknown"
    context: str = "unknown"
    from_queue: Optional[bool] = None
    entry_reason: str = "other"
    planned_risk_dollars: Optional[float] = Field(default=None, gt=0)
    account_balance_at_entry: Optional[float] = Field(default=None, gt=0)
    commission: float = DEFAULT_COMMISSION


class CloseTradeIn(BaseModel):
    exit_date: date
    exit_price: float = Field(gt=0)
    qty: Optional[float] = Field(default=None, gt=0, description="If < trade.qty, performs a partial close (splits the trade).")
    exit_reason: Optional[str] = None
    error_note: Optional[str] = None
    post_venta: Optional[str] = None
    commission: float = DEFAULT_COMMISSION


class PatchTradeIn(BaseModel):
    symbol: Optional[str] = None
    setup: Optional[str] = None
    context: Optional[str] = None
    entry_date: Optional[date] = None
    entry_price: Optional[float] = Field(default=None, gt=0)
    qty: Optional[float] = Field(default=None, gt=0)
    stop_price: Optional[float] = Field(default=None, gt=0)
    exit_date: Optional[date] = None
    exit_price: Optional[float] = Field(default=None, gt=0)
    error_note: Optional[str] = None
    post_venta: Optional[str] = None
    from_queue: Optional[bool] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    planned_risk_dollars: Optional[float] = Field(default=None, gt=0)
    account_balance_at_entry: Optional[float] = Field(default=None, gt=0)


@router.get("/vocab")
async def get_vocabularies():
    """Drives the form dropdowns. Single source of truth — the frontend reads this."""
    return {
        "setup_options": SETUP_OPTIONS,
        "context_options": CONTEXT_OPTIONS,
        "entry_reason_options": ENTRY_REASON_OPTIONS,
        "exit_reason_options": EXIT_REASON_OPTIONS,
        "default_commission": DEFAULT_COMMISSION,
    }


@router.get("/trade-draft")
async def get_trade_draft(
    symbol: str,
    setup: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns prefill payload for a take-from-queue flow.

    Read-only — does NOT persist a trade. The frontend opens NewTradeModal
    with these values and the operator confirms (possibly editing qty / stop)
    before the actual POST. Persisted snapshots will be re-taken at save time
    so they reflect the system state at the moment of confirmation, not at
    the moment of click.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    if setup not in SETUP_OPTIONS:
        raise HTTPException(status_code=422, detail=f"setup must be one of {SETUP_OPTIONS}")

    # Pull most recent stock_metrics row for the symbol
    from app.models.stock import StockMetrics
    metrics = (await db.execute(
        select(StockMetrics)
        .where(StockMetrics.symbol == symbol)
        .order_by(StockMetrics.date.desc())
        .limit(1)
    )).scalar_one_or_none()
    if metrics is None:
        raise HTTPException(status_code=404, detail="no metrics for symbol")

    # Preview snapshots so operator sees what'll get saved (real snapshots taken at POST time)
    from datetime import date as _date
    snapshot = await take_entry_snapshot(db, symbol, _date.today())

    return {
        "symbol": symbol,
        "setup": setup,
        "entry_price": metrics.current_price,
        "stop_price_suggested": metrics.ema21,
        "from_queue": True,
        "entry_reason": "queue_signal",
        "regime_at_entry": snapshot["regime_at_entry"],
        "system_score_at_entry": snapshot["system_score_at_entry"],
        "group_strength_at_entry": snapshot["group_strength_at_entry"],
        "leader_health_at_entry": snapshot["leader_health_at_entry"],
    }


@router.post("/trades", status_code=201)
async def create_open_trade(payload: OpenTradeIn, db: AsyncSession = Depends(get_db)):
    """Create an open position. Server computes cost_total (entry_price·qty + commission)
    and links to the nearest transition_observation if one exists for the symbol around
    entry_date. Exit fields stay null until /close is called.
    """
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    _validate_enum(payload.entry_reason, ENTRY_REASON_OPTIONS, "entry_reason")
    obs_id = await _find_linked_observation(db, symbol, payload.entry_date)
    # Snapshot the system state at entry — non-blocking (failures yield null fields, log only).
    snapshot = await take_entry_snapshot(db, symbol, payload.entry_date)
    # cost_total left NULL; computed on response from entry_price * qty.
    trade = JournalTrade(
        symbol=symbol,
        setup=payload.setup,
        context=payload.context,
        entry_date=payload.entry_date,
        entry_price=payload.entry_price,
        qty=payload.qty,
        stop_price=payload.stop_price,
        linked_observation_id=obs_id,
        source_row=0,  # 0 = manually entered (not from CSV)
        from_queue=payload.from_queue,
        entry_reason=payload.entry_reason,
        planned_risk_dollars=payload.planned_risk_dollars,
        account_balance_at_entry=payload.account_balance_at_entry,
        regime_at_entry=snapshot["regime_at_entry"],
        system_score_at_entry=snapshot["system_score_at_entry"],
        group_strength_at_entry=snapshot["group_strength_at_entry"],
        leader_health_at_entry=snapshot["leader_health_at_entry"],
        initial_stop_price=payload.stop_price,  # immutable snapshot of planned risk
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    # Log the initial stop event after the trade has an id assigned.
    if payload.stop_price is not None:
        _record_stop_event(db, trade.id, None, payload.stop_price, 'initial')
        await db.commit()
    return _trade_to_dict(trade)


def _compute_outcomes(trade: JournalTrade, commission: float = DEFAULT_COMMISSION) -> None:
    """Fill operational outcome fields on a trade with both legs set.

    Persists only the metrics that aren't trivial UI-side derivations:
      - pnl_dollars: requires commission knowledge — non-trivial.
      - r_multiple : requires stop_price, also non-trivial.
    pnl_pct and duration_days are intentionally left to _trade_to_dict to
    compute on-demand. Assumes long-only.
    """
    if trade.exit_price is None or trade.exit_date is None or trade.entry_price is None:
        return
    qty = trade.qty
    trade.pnl_dollars = (trade.exit_price - trade.entry_price) * qty - 2 * commission
    # Honest R uses initial_stop_price (planned risk) when available, with
    # fallback to stop_price for back-compat with trades created before this
    # column existed (i.e. CSV-imported historicals).
    stop_for_r = trade.initial_stop_price if trade.initial_stop_price is not None else trade.stop_price
    if stop_for_r is not None and trade.entry_price > stop_for_r:
        risk_per_share = trade.entry_price - stop_for_r
        trade.r_multiple = (trade.exit_price - trade.entry_price) / risk_per_share


@router.post("/trades/{trade_id}/close")
async def close_trade(trade_id: int, payload: CloseTradeIn, db: AsyncSession = Depends(get_db)):
    """Close a position fully or partially.

    Partial close (when payload.qty is set and < trade.qty): the original record
    stays open with qty reduced; a new closed record is created for the chunk
    that exited. This preserves entry_price / stop_price / setup / context on
    both halves so future partials use the same basis.
    """
    trade = await db.get(JournalTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="trade not found")
    if trade.exit_date is not None:
        raise HTTPException(status_code=400, detail="trade already closed")
    _validate_enum(payload.exit_reason, EXIT_REASON_OPTIONS, "exit_reason")

    full_qty = trade.qty
    chunk = payload.qty if payload.qty is not None else full_qty
    if chunk > full_qty + 1e-9:
        raise HTTPException(status_code=400, detail=f"qty {chunk} exceeds open qty {full_qty}")

    is_partial = chunk < full_qty - 1e-9

    if is_partial:
        # Carve out a closed child trade for the chunk; original keeps the remainder open.
        # Auto-infer exit_reason='partial_take' if operator didn't specify — partials
        # are nearly always profit-taking or risk reduction; saves a forced click.
        child_exit_reason = payload.exit_reason if payload.exit_reason else 'partial_take'
        # Decision linkage: child belongs to the same decision as its source trade.
        # If trade has a parent (it's already a child), inherit that. Otherwise
        # trade IS the representative of the decision and child links to it.
        parent_id = trade.parent_trade_id if trade.parent_trade_id is not None else trade.id
        closed = JournalTrade(
            symbol=trade.symbol,
            setup=trade.setup,
            context=trade.context,
            entry_date=trade.entry_date,
            entry_price=trade.entry_price,
            qty=chunk,
            stop_price=trade.stop_price,
            cost_total=trade.entry_price * chunk,
            exit_date=payload.exit_date,
            exit_price=payload.exit_price,
            error_note=payload.error_note,
            post_venta=payload.post_venta,
            linked_observation_id=trade.linked_observation_id,
            source_row=trade.source_row,
            from_queue=trade.from_queue,
            entry_reason=trade.entry_reason,
            exit_reason=child_exit_reason,
            parent_trade_id=parent_id,
        )
        _compute_outcomes(closed, commission=payload.commission)
        db.add(closed)

        trade.qty = full_qty - chunk
        if trade.cost_total is not None:
            trade.cost_total = trade.entry_price * trade.qty

        await db.commit()
        await db.refresh(closed)
        await db.refresh(trade)
        return {"closed": _trade_to_dict(closed), "remaining_open": _trade_to_dict(trade)}

    # Full close: mutate in place. exit_reason keeps its current value
    # ('unknown' by default) unless operator provides one in the payload.
    trade.exit_date = payload.exit_date
    trade.exit_price = payload.exit_price
    trade.error_note = payload.error_note
    trade.post_venta = payload.post_venta
    if payload.exit_reason is not None:
        trade.exit_reason = payload.exit_reason
    _compute_outcomes(trade, commission=payload.commission)
    await db.commit()
    await db.refresh(trade)
    return _trade_to_dict(trade)


@router.patch("/trades/{trade_id}")
async def patch_trade(trade_id: int, payload: PatchTradeIn, db: AsyncSession = Depends(get_db)):
    """Edit any field on an existing trade. Recomputes derived metrics if any of
    (entry_price, exit_price, stop_price, qty, entry_date, exit_date) changed.
    """
    trade = await db.get(JournalTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="trade not found")

    _validate_enum(payload.entry_reason, ENTRY_REASON_OPTIONS, "entry_reason")
    _validate_enum(payload.exit_reason, EXIT_REASON_OPTIONS, "exit_reason")

    updates = payload.model_dump(exclude_unset=True)
    recompute_keys = {"entry_price", "exit_price", "stop_price", "qty", "entry_date", "exit_date"}
    needs_recompute = bool(set(updates) & recompute_keys)
    # Snapshot pre-update stop so we can detect any change after setattr loop.
    old_stop = trade.stop_price

    for k, v in updates.items():
        if k == "symbol" and v is not None:
            v = v.strip().upper()
        # initial_stop_price is immutable — silently ignore attempts to PATCH it.
        if k == "initial_stop_price":
            continue
        setattr(trade, k, v)

    # If stop_price was in the payload, classify and record any actual change.
    if "stop_price" in updates:
        # Lazily set initial_stop_price the first time the trade gets a stop.
        if trade.initial_stop_price is None and trade.stop_price is not None:
            trade.initial_stop_price = trade.stop_price
        kind = _classify_stop_change(old_stop, trade.stop_price, trade.entry_price)
        if kind is not None:
            _record_stop_event(db, trade.id, old_stop, trade.stop_price, kind)

    if needs_recompute:
        _compute_outcomes(trade)
        # cost_total / pnl_pct / duration_days are derived on response — not persisted on patch.
        if "symbol" in updates or "entry_date" in updates:
            trade.linked_observation_id = await _find_linked_observation(db, trade.symbol, trade.entry_date)

    await db.commit()
    await db.refresh(trade)
    return _trade_to_dict(trade)


@router.get("/trades/{trade_id}/stop-history")
async def get_stop_history(trade_id: int, db: AsyncSession = Depends(get_db)):
    """Chronological audit log of all stop_price changes for the trade.

    Used by the EditTradeModal to show how the operator managed risk through
    the position's lifetime. Auto-classification (initial / moved_to_be /
    trailed_up / widened / removed) lets the UI render the story without
    requiring the operator to label each event.
    """
    trade = await db.get(JournalTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="trade not found")
    rows = (
        await db.execute(
            select(JournalStopEvent)
            .where(JournalStopEvent.trade_id == trade_id)
            .order_by(JournalStopEvent.occurred_at.asc())
        )
    ).scalars().all()
    return {
        "events": [
            {
                "id": e.id,
                "old_stop_price": e.old_stop_price,
                "new_stop_price": e.new_stop_price,
                "kind": e.kind,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "auto_classified": e.auto_classified,
            }
            for e in rows
        ]
    }


@router.delete("/trades/{trade_id}", status_code=204)
async def delete_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    trade = await db.get(JournalTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="trade not found")
    await db.execute(sql_delete(JournalTrade).where(JournalTrade.id == trade_id))
    await db.commit()
    return None
