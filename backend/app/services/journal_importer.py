"""Parse the user's broker journal CSV (Google Sheets export, IBKR Operaciones tab)
and persist round-trip trades into journal_trades.

The journal records one row per leg (Compra/Venta). We pair them per-symbol in FIFO
order — each Venta closes the oldest open Compra of the same symbol with remaining
qty, supporting partial fills. After pairing, we attempt to link each closed trade
to the nearest transition_observation (same symbol, entry_date ± 3d) so the journal
can feed the empirical calibration loop with real outcomes.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import JournalTrade, TransitionObservation
from app.services.journal_decisions import assign_decision_links


# --- Normalization vocabularies ---------------------------------------------

SETUP_MAP = {
    'u&r': 'u_and_r',
    'u y r': 'u_and_r',
    'ur': 'u_and_r',
    'breakout': 'breakout',
    'episodic pivot': 'episodic_pivot',
    'reversal': 'reversal',
    'vwap': 'vwap',
    'long time/dca': 'dca',
    'dca': 'dca',
    'building base': 'building_base',
    'building bases': 'building_base',
}

CONTEXT_MAP = {
    'favorable': 'favorable',
    'choppy': 'choppy',
    'malo': 'adverse',
    'adversa': 'adverse',
    'adverse': 'adverse',
    'neutral': 'neutral',
    'rs agains market': 'rs_against_market',
    'rs against market': 'rs_against_market',
}


def _normalize_setup(raw: str) -> str:
    s = (raw or '').strip().lower()
    return SETUP_MAP.get(s, 'unknown' if not s else s)


def _normalize_context(raw: str) -> str:
    c = (raw or '').strip().lower()
    return CONTEXT_MAP.get(c, 'unknown' if not c else c)


# --- Number parsing ---------------------------------------------------------

_MONEY_RX = re.compile(r"[^\d,.\-]")


def _parse_number(raw: str) -> Optional[float]:
    """Parse Spanish-locale numbers from the sheet: '$429,50' → 429.50,
    '2,' → 2.0, '"1.166,40"' → 1166.40, '' → None.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = _MONEY_RX.sub('', s)
    if not s or s in ('-', '.', ','):
        return None
    # If both . and , present: . is thousands, , is decimal (es-AR style)
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    # Strip trailing dot ("2," → "2." → "2")
    if s.endswith('.'):
        s = s[:-1]
    if not s or s == '-':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[date]:
    s = (raw or '').strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


# --- Header detection -------------------------------------------------------

EXPECTED_HEADERS = {'fecha', 'ticker', 'tipo', 'cantidad', 'precio unitario'}


def _find_header_row(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        lower = {(c or '').strip().lower() for c in row}
        if EXPECTED_HEADERS.issubset(lower):
            return i
    raise ValueError(
        f"Could not find header row containing {sorted(EXPECTED_HEADERS)} in CSV"
    )


# --- Pairing ----------------------------------------------------------------

@dataclass
class _OpenLeg:
    source_row: int
    entry_date: date
    entry_price: float
    qty_remaining: float
    stop_price: Optional[float]
    cost_total: Optional[float]
    setup_at_entry: str
    context_at_entry: str


@dataclass
class ParsedTrade:
    symbol: str
    setup: str
    context: str
    entry_date: date
    entry_price: float
    qty: float
    stop_price: Optional[float]
    cost_total: Optional[float]
    exit_date: Optional[date]
    exit_price: Optional[float]
    duration_days: Optional[float]
    pnl_dollars: Optional[float]
    pnl_pct: Optional[float]
    r_multiple: Optional[float]
    error_note: Optional[str]
    post_venta: Optional[str]
    source_row: int


@dataclass
class ImportStats:
    rows_seen: int = 0
    trades_closed: int = 0
    positions_open: int = 0
    skipped_rows: int = 0
    linked_observations: int = 0
    parse_errors: list[str] = field(default_factory=list)


class JournalImporter:
    """Parses a CSV blob and inserts journal_trades. Idempotent at the call
    site: callers may want to clear the table before re-importing (see endpoint).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def import_csv(self, csv_text: str) -> ImportStats:
        reader = csv.reader(io.StringIO(csv_text))
        rows = [r for r in reader]
        header_idx = _find_header_row(rows)
        header = [(c or '').strip().lower() for c in rows[header_idx]]

        def col(name: str) -> int:
            try:
                return header.index(name)
            except ValueError:
                return -1

        idx_fecha = col('fecha')
        idx_ticker = col('ticker')
        idx_tipo = col('tipo')
        idx_qty = col('cantidad')
        idx_price = col('precio unitario')
        idx_cost = col('costo total')
        idx_stop = col('stop')
        idx_pnl = col('retorno')
        idx_r = col('r')
        idx_dur = col('duracion (d)')
        idx_pct = col('retorno %')
        idx_setup = col('setup')
        idx_ctx = col('contexto')
        idx_err = col('error/nota')
        idx_post = col('post venta')

        opens: dict[str, list[_OpenLeg]] = {}
        parsed: list[ParsedTrade] = []
        stats = ImportStats()

        for n, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
            if not any((c or '').strip() for c in row):
                continue
            stats.rows_seen += 1

            symbol = (row[idx_ticker] if idx_ticker >= 0 else '').strip().upper()
            tipo = (row[idx_tipo] if idx_tipo >= 0 else '').strip().lower()
            fecha = _parse_date(row[idx_fecha] if idx_fecha >= 0 else '')
            price = _parse_number(row[idx_price] if idx_price >= 0 else '')
            qty = _parse_number(row[idx_qty] if idx_qty >= 0 else '')

            if not symbol or not fecha or price is None or qty is None:
                stats.skipped_rows += 1
                stats.parse_errors.append(f"row {n}: missing symbol/date/price/qty")
                continue

            setup = _normalize_setup(row[idx_setup] if idx_setup >= 0 else '')
            context = _normalize_context(row[idx_ctx] if idx_ctx >= 0 else '')

            if tipo == 'compra':
                leg = _OpenLeg(
                    source_row=n,
                    entry_date=fecha,
                    entry_price=price,
                    qty_remaining=qty,
                    stop_price=_parse_number(row[idx_stop] if idx_stop >= 0 else ''),
                    cost_total=_parse_number(row[idx_cost] if idx_cost >= 0 else ''),
                    setup_at_entry=setup,
                    context_at_entry=context,
                )
                opens.setdefault(symbol, []).append(leg)
                continue

            if tipo != 'venta':
                stats.skipped_rows += 1
                continue

            queue = opens.get(symbol, [])
            if not queue:
                stats.skipped_rows += 1
                stats.parse_errors.append(
                    f"row {n}: Venta of {symbol} with no open Compra"
                )
                continue

            qty_to_close = qty
            error = (row[idx_err] if idx_err >= 0 else '').strip() or None
            post = (row[idx_post] if idx_post >= 0 else '').strip() or None
            pnl_dollars = _parse_number(row[idx_pnl] if idx_pnl >= 0 else '')
            r_mult = _parse_number(row[idx_r] if idx_r >= 0 else '')
            duration = _parse_number(row[idx_dur] if idx_dur >= 0 else '')
            pnl_pct_raw = _parse_number(row[idx_pct] if idx_pct >= 0 else '')

            while qty_to_close > 1e-9 and queue:
                leg = queue[0]
                chunk = min(qty_to_close, leg.qty_remaining)
                # Use sell-row setup/context if non-unknown; else inherit from entry
                final_setup = setup if setup != 'unknown' else leg.setup_at_entry
                final_ctx = context if context != 'unknown' else leg.context_at_entry

                # For partial fills, prorate PnL/cost by chunk share of original Venta qty
                share = chunk / qty if qty > 0 else 1.0
                parsed.append(ParsedTrade(
                    symbol=symbol,
                    setup=final_setup,
                    context=final_ctx,
                    entry_date=leg.entry_date,
                    entry_price=leg.entry_price,
                    qty=chunk,
                    stop_price=leg.stop_price,
                    cost_total=leg.entry_price * chunk,
                    exit_date=fecha,
                    exit_price=price,
                    duration_days=duration,
                    pnl_dollars=(pnl_dollars * share) if pnl_dollars is not None else None,
                    pnl_pct=pnl_pct_raw,  # percentage independent of size
                    r_multiple=r_mult,
                    error_note=error,
                    post_venta=post,
                    source_row=n,
                ))
                leg.qty_remaining -= chunk
                qty_to_close -= chunk
                if leg.qty_remaining <= 1e-9:
                    queue.pop(0)

            stats.trades_closed += 1

        created: list[JournalTrade] = []

        # Persist remaining open legs as open trades (exit fields null) so the
        # user can close them later from the UI instead of re-entering them.
        for sym, queue in opens.items():
            for leg in queue:
                stats.positions_open += 1
                obs_id = await self._find_linked_observation(sym, leg.entry_date)
                if obs_id is not None:
                    stats.linked_observations += 1
                row = JournalTrade(
                    symbol=sym,
                    setup=leg.setup_at_entry,
                    context=leg.context_at_entry,
                    entry_date=leg.entry_date,
                    entry_price=leg.entry_price,
                    qty=leg.qty_remaining,
                    stop_price=leg.stop_price,
                    cost_total=leg.entry_price * leg.qty_remaining,
                    linked_observation_id=obs_id,
                    source_row=leg.source_row,
                )
                self.db.add(row)
                created.append(row)

        # Persist + link closed trades
        for t in parsed:
            obs_id = await self._find_linked_observation(t.symbol, t.entry_date)
            if obs_id is not None:
                stats.linked_observations += 1
            row = JournalTrade(
                symbol=t.symbol,
                setup=t.setup,
                context=t.context,
                entry_date=t.entry_date,
                entry_price=t.entry_price,
                qty=t.qty,
                stop_price=t.stop_price,
                cost_total=t.cost_total,
                exit_date=t.exit_date,
                exit_price=t.exit_price,
                duration_days=t.duration_days,
                pnl_dollars=t.pnl_dollars,
                pnl_pct=t.pnl_pct,
                r_multiple=t.r_multiple,
                error_note=t.error_note,
                post_venta=t.post_venta,
                linked_observation_id=obs_id,
                source_row=t.source_row,
            )
            self.db.add(row)
            created.append(row)

        # Flush to assign ids, then group legs into position-episode decisions
        # (one Compra and everything held alongside it, plus its partial sells)
        # so the journal's decision-level stats and the UI agree on what counts
        # as a single operation. See assign_decision_links for the episode rule.
        await self.db.flush()
        assign_decision_links(created)

        await self.db.commit()
        return stats

    async def _find_linked_observation(self, symbol: str, entry_date: date) -> Optional[int]:
        """Pick the nearest transition_observation for (symbol, entry_date ± 3d)."""
        window_start = entry_date - timedelta(days=3)
        window_end = entry_date + timedelta(days=3)
        stmt = (
            select(TransitionObservation.id, TransitionObservation.date_detected)
            .where(TransitionObservation.symbol == symbol)
            .where(TransitionObservation.date_detected >= window_start)
            .where(TransitionObservation.date_detected <= window_end)
        )
        candidates = (await self.db.execute(stmt)).all()
        if not candidates:
            return None
        # Pick the one closest in time to entry_date
        best = min(candidates, key=lambda r: abs((r.date_detected - entry_date).days))
        return best.id

    async def clear_all(self) -> int:
        """Wipe journal_trades. Used before re-import. Returns rows deleted."""
        result = await self.db.execute(delete(JournalTrade))
        await self.db.commit()
        return result.rowcount or 0
