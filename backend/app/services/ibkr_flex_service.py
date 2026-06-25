"""IBKR Flex Web Service → journal auto-sync.

Pulls executed trades from Interactive Brokers via the Flex Web Service (a
two-step token + reference-code handshake), pairs buy/sell executions into
round-trip journal trades FIFO, and upserts them idempotently so the operator
never re-types a trade.

Idempotency: every produced leg carries a stable `broker_exec_id`:
  - closed leg → "<sellExecId>:<buyExecId>"  (unique per FIFO chunk)
  - open leg   → "<buyExecId>:open"
Re-running a sync skips legs already present and preserves any manual
annotations (setup, stop, notes, risk plan) the operator added — including
across the open→closed transition, by carrying them over keyed on the buy
execution id (`broker_open_exec_id`).

Limitations (v1, documented intentionally):
  - STK only (assetCategory == "STK").
  - Each IBKR buy and its sells form one decision; scaling into a position
    across multiple buys shows as separate decisions.
  - The broker reports no stop, so R-multiple stays null until the operator
    logs a stop on the trade. P&L (incl. commissions) is captured automatically.
  - FIFO pairing matches the broker's own lot convention; it can differ from
    operator intent for overlapping same-symbol positions.
"""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import JournalTrade

logger = logging.getLogger(__name__)

_FLEX_BASE = "https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService"
_SEND_URL = f"{_FLEX_BASE}.SendRequest"
_GET_URL = f"{_FLEX_BASE}.GetStatement"
_FLEX_VERSION = "3"

# "Statement generation in progress" — GetStatement must be retried.
_IN_PROGRESS_CODE = "1019"

# SendRequest codes that mean "busy / throttled, try again shortly" rather than
# a hard failure. IBKR rate-limits how often the same query can be generated.
#   1001 = statement could not be generated at this time
#   1009 = statement could not be retrieved at this time
#   1018 = too many requests / throttled
#   1020 = invalid request (sometimes transient right after token creation)
_RETRYABLE_SEND_CODES = {"1001", "1009", "1018", "1020"}


class IbkrFlexError(Exception):
    """Raised on any Flex Web Service failure (bad token, expired query, etc.)."""


class _FlexTransient(Exception):
    """Internal: a retryable SendRequest failure (busy/throttled)."""

    def __init__(self, code: Optional[str], message: Optional[str]):
        super().__init__(message or code or "transient")
        self.code = code
        self.message = message


# ── Fetch ───────────────────────────────────────────────────────────────────


async def fetch_flex_statement(
    token: str,
    query_id: str,
    *,
    max_retries: int = 6,
    retry_delay: float = 3.0,
    timeout: float = 30.0,
) -> str:
    """Run the two-step Flex Web Service handshake and return the report XML.

    Step 1 (SendRequest) returns a reference code; step 2 (GetStatement) returns
    the statement, retrying while IBKR reports it is still being generated.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        ref_code = await _send_with_retry(client, token, query_id)
        for attempt in range(max_retries):
            resp = await client.get(
                _GET_URL, params={"q": ref_code, "t": token, "v": _FLEX_VERSION}
            )
            resp.raise_for_status()
            text = resp.text
            status, code, message = _read_flex_status(text)
            if status is None:
                # Not a status envelope → this is the actual FlexQueryResponse.
                return text
            if code == _IN_PROGRESS_CODE:
                await asyncio.sleep(retry_delay)
                continue
            raise IbkrFlexError(f"GetStatement failed ({code}): {message}")
        raise IbkrFlexError("Flex statement not ready after retries")


async def _send_with_retry(
    client: httpx.AsyncClient,
    token: str,
    query_id: str,
    *,
    retries: int = 4,
    base_delay: float = 5.0,
) -> str:
    """SendRequest with backoff on IBKR's transient throttle codes. Persistent
    throttling surfaces as a clear, operator-facing message."""
    last: Optional[_FlexTransient] = None
    for i in range(retries):
        try:
            return await _send_request(client, token, query_id)
        except _FlexTransient as exc:
            last = exc
            if i < retries - 1:
                await asyncio.sleep(base_delay * (i + 1))
    raise IbkrFlexError(
        f"IBKR está limitando la generación del reporte (código {last.code}). "
        f"Esperá unos minutos y reintentá — no sincronices repetidamente."
    )


async def _send_request(client: httpx.AsyncClient, token: str, query_id: str) -> str:
    resp = await client.get(
        _SEND_URL, params={"t": token, "q": query_id, "v": _FLEX_VERSION}
    )
    resp.raise_for_status()
    status, code, message = _read_flex_status(resp.text)
    if status != "Success":
        if code in _RETRYABLE_SEND_CODES:
            raise _FlexTransient(code, message)
        raise IbkrFlexError(f"SendRequest failed ({code}): {message}")
    root = ET.fromstring(resp.text)
    ref = root.findtext("ReferenceCode")
    if not ref:
        raise IbkrFlexError("SendRequest returned no ReferenceCode")
    return ref


def _read_flex_status(xml_text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (status, errorCode, errorMessage) if the payload is a
    FlexStatementResponse status envelope, else (None, None, None)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise IbkrFlexError(f"Malformed Flex response: {exc}") from exc
    if root.tag != "FlexStatementResponse":
        return None, None, None
    return (
        root.findtext("Status"),
        root.findtext("ErrorCode"),
        root.findtext("ErrorMessage"),
    )


# ── Parse ───────────────────────────────────────────────────────────────────


@dataclass
class Execution:
    trade_id: str
    symbol: str
    trade_date: date
    side: str          # 'BUY' | 'SELL'
    quantity: float    # absolute
    price: float
    commission: float  # absolute dollars (IBKR reports negative; we abs it)


def _parse_flex_date(raw: str) -> Optional[date]:
    s = (raw or "").strip()
    if not s:
        return None
    # IBKR may append a time as "YYYYMMDD;HHMMSS" or "YYYYMMDD HHMMSS".
    s = s.replace(";", " ").split(" ")[0]
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_executions(xml_text: str) -> list[Execution]:
    """Extract STK executions from a FlexQueryResponse. Skips non-stock rows and
    any `<Trade>` missing the fields needed to pair it."""
    root = ET.fromstring(xml_text)
    executions: list[Execution] = []
    for el in root.iter("Trade"):
        # Exclude only when the category is explicitly non-stock. When the Flex
        # query omits the assetCategory column (common), it arrives empty — we
        # include it rather than drop everything, since this is a stocks app.
        cat = (el.get("assetCategory") or "").upper()
        if cat and cat != "STK":
            continue
        trade_id = el.get("tradeID") or el.get("ibExecID") or el.get("ibOrderID") or ""
        symbol = (el.get("symbol") or "").strip().upper()
        side = (el.get("buySell") or "").strip().upper()
        trade_date = _parse_flex_date(el.get("tradeDate") or el.get("dateTime") or "")
        qty = _to_float(el.get("quantity"))
        price = _to_float(el.get("tradePrice"))
        commission = _to_float(el.get("ibCommission"))
        if not (trade_id and symbol and side in ("BUY", "SELL") and trade_date
                and qty is not None and price is not None):
            continue
        executions.append(Execution(
            trade_id=trade_id,
            symbol=symbol,
            trade_date=trade_date,
            side=side,
            quantity=abs(qty),
            price=price,
            commission=abs(commission) if commission is not None else 0.0,
        ))
    return executions


def diagnose_flex(xml_text: str) -> dict:
    """Summarize what a Flex report actually contains, to debug a 0-trades sync.

    Returns counts and a redacted sample (attribute names + symbol/side only) so
    the operator can see whether the query includes trades, the date range, and
    what asset categories came back — without dumping raw account data.
    """
    root = ET.fromstring(xml_text)
    if root.tag == "FlexStatementResponse":
        return {
            "ok": False,
            "status_envelope": True,
            "status": root.findtext("Status"),
            "error_code": root.findtext("ErrorCode"),
            "error_message": root.findtext("ErrorMessage"),
        }

    statements = root.findall(".//FlexStatement")
    stmt_info = []
    section_tags: dict[str, int] = {}
    for st in statements:
        stmt_info.append({
            "accountId": st.get("accountId"),
            "fromDate": st.get("fromDate"),
            "toDate": st.get("toDate"),
        })
        for child in st:
            section_tags[child.tag] = section_tags.get(child.tag, 0) + len(list(child))

    trades = list(root.iter("Trade"))
    by_category: dict[str, int] = {}
    by_side: dict[str, int] = {}
    for t in trades:
        cat = t.get("assetCategory") or "(none)"
        by_category[cat] = by_category.get(cat, 0) + 1
        side = t.get("buySell") or "(none)"
        by_side[side] = by_side.get(side, 0) + 1

    sample = None
    if trades:
        s = trades[0]
        sample = {
            "attribute_names": sorted(s.attrib.keys()),
            "symbol": s.get("symbol"),
            "buySell": s.get("buySell"),
            "assetCategory": s.get("assetCategory"),
            "tradeDate": s.get("tradeDate") or s.get("dateTime"),
        }

    return {
        "ok": True,
        "root_tag": root.tag,
        "flex_statements": len(statements),
        "statements": stmt_info,
        "sections_present": section_tags,
        "trade_elements_total": len(trades),
        "trade_by_asset_category": by_category,
        "trade_by_side": by_side,
        "parsed_stk_executions": len(parse_executions(xml_text)),
        "sample_trade": sample,
    }


def _to_float(raw: Optional[str]) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


# ── Pair + sync ─────────────────────────────────────────────────────────────


@dataclass
class _Lot:
    buy_exec_id: str
    entry_date: date
    entry_price: float
    qty_total: float
    qty_remaining: float
    commission_total: float  # buy-side commission for the whole lot


@dataclass
class _Leg:
    broker_exec_id: str           # idempotency key
    broker_open_exec_id: str      # buy exec id (groups a decision)
    symbol: str
    entry_date: date
    entry_price: float
    qty: float
    is_open: bool
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    pnl_dollars: Optional[float] = None


@dataclass
class SyncStats:
    fetched_executions: int = 0
    closed_inserted: int = 0
    open_upserted: int = 0
    skipped_existing: int = 0
    open_closed_out: int = 0
    errors: list[str] = field(default_factory=list)


def pair_executions(executions: list[Execution]) -> list[_Leg]:
    """FIFO-pair executions per symbol into closed legs + open remainders."""
    by_symbol: dict[str, list[Execution]] = {}
    for e in executions:
        by_symbol.setdefault(e.symbol, []).append(e)

    legs: list[_Leg] = []
    for symbol, execs in by_symbol.items():
        execs.sort(key=lambda e: (e.trade_date, e.trade_id))
        open_lots: list[_Lot] = []
        for e in execs:
            if e.side == "BUY":
                open_lots.append(_Lot(
                    buy_exec_id=e.trade_id,
                    entry_date=e.trade_date,
                    entry_price=e.price,
                    qty_total=e.quantity,
                    qty_remaining=e.quantity,
                    commission_total=e.commission,
                ))
                continue
            # SELL — consume FIFO from the oldest open lots.
            qty_to_close = e.quantity
            while qty_to_close > 1e-9 and open_lots:
                lot = open_lots[0]
                chunk = min(qty_to_close, lot.qty_remaining)
                buy_comm_share = lot.commission_total * (chunk / lot.qty_total) if lot.qty_total else 0.0
                sell_comm_share = e.commission * (chunk / e.quantity) if e.quantity else 0.0
                pnl = (e.price - lot.entry_price) * chunk - buy_comm_share - sell_comm_share
                legs.append(_Leg(
                    broker_exec_id=f"{e.trade_id}:{lot.buy_exec_id}",
                    broker_open_exec_id=lot.buy_exec_id,
                    symbol=symbol,
                    entry_date=lot.entry_date,
                    entry_price=lot.entry_price,
                    qty=chunk,
                    is_open=False,
                    exit_date=e.trade_date,
                    exit_price=e.price,
                    pnl_dollars=round(pnl, 4),
                ))
                lot.qty_remaining -= chunk
                qty_to_close -= chunk
                if lot.qty_remaining <= 1e-9:
                    open_lots.pop(0)
            # A sell with no open lot (e.g. short, or history truncated) is ignored.

        # Remaining lots are open positions.
        for lot in open_lots:
            if lot.qty_remaining <= 1e-9:
                continue
            legs.append(_Leg(
                broker_exec_id=f"{lot.buy_exec_id}:open",
                broker_open_exec_id=lot.buy_exec_id,
                symbol=symbol,
                entry_date=lot.entry_date,
                entry_price=lot.entry_price,
                qty=lot.qty_remaining,
                is_open=True,
            ))
    return legs


# Manual annotations carried across re-syncs and the open→closed transition.
_ANNOTATION_FIELDS = (
    "setup", "context", "stop_price", "initial_stop_price", "entry_reason",
    "planned_risk_dollars", "account_balance_at_entry", "from_queue",
    "regime_at_entry", "system_score_at_entry", "group_strength_at_entry",
    "leader_health_at_entry", "error_note", "post_venta",
)


async def sync_executions_to_journal(
    db: AsyncSession, executions: list[Execution]
) -> SyncStats:
    """Idempotently upsert FIFO-paired executions into journal_trades.

    Preserves manual annotations across syncs (skip existing closed legs;
    update-in-place open legs) and carries entry-level annotations from an
    open row to the closed legs that supersede it.
    """
    stats = SyncStats(fetched_executions=len(executions))
    legs = pair_executions(executions)

    # Existing broker rows, indexed by their idempotency key.
    existing_rows = (await db.execute(
        select(JournalTrade).where(JournalTrade.broker_exec_id.is_not(None))
    )).scalars().all()
    by_key = {r.broker_exec_id: r for r in existing_rows}

    # Capture entry-level annotations once per buy execution so they survive the
    # open→closed transition (the open row gets deleted, but its labels live on).
    annotations: dict[str, dict] = {}
    for r in existing_rows:
        if not r.broker_open_exec_id:
            continue
        snap = {f: getattr(r, f) for f in _ANNOTATION_FIELDS}
        # Prefer the most-informative source: keep the first non-default seen.
        cur = annotations.get(r.broker_open_exec_id)
        if cur is None or _annotation_score(snap) > _annotation_score(cur):
            annotations[r.broker_open_exec_id] = snap

    desired_keys = {leg.broker_exec_id for leg in legs}
    created: list[JournalTrade] = []

    for leg in legs:
        existing = by_key.get(leg.broker_exec_id)
        if leg.is_open:
            if existing is not None:
                # Update broker-authoritative fields; keep manual annotations.
                existing.qty = leg.qty
                existing.entry_price = leg.entry_price
                existing.entry_date = leg.entry_date
                stats.skipped_existing += 1
            else:
                row = _new_broker_row(leg, annotations.get(leg.broker_open_exec_id))
                db.add(row)
                created.append(row)
                stats.open_upserted += 1
        else:
            if existing is not None:
                stats.skipped_existing += 1
            else:
                row = _new_broker_row(leg, annotations.get(leg.broker_open_exec_id))
                db.add(row)
                created.append(row)
                stats.closed_inserted += 1

    # Delete open rows whose position is now fully closed (their key vanished
    # from the desired set). Their annotations were already captured above.
    for r in existing_rows:
        if (r.broker_exec_id and r.broker_exec_id.endswith(":open")
                and r.broker_exec_id not in desired_keys):
            await db.delete(r)
            stats.open_closed_out += 1

    await db.flush()
    _link_decisions(existing_rows + created)
    await db.commit()
    return stats


def _annotation_score(snap: dict) -> int:
    """Count of non-default annotation values — used to pick the richest source."""
    score = 0
    for f, v in snap.items():
        if v is None:
            continue
        if f in ("setup", "context") and v == "unknown":
            continue
        if f == "entry_reason" and v == "other":
            continue
        score += 1
    return score


def _new_broker_row(leg: _Leg, annotation: Optional[dict]) -> JournalTrade:
    row = JournalTrade(
        symbol=leg.symbol,
        setup="unknown",
        context="unknown",
        entry_date=leg.entry_date,
        entry_price=leg.entry_price,
        qty=leg.qty,
        exit_date=leg.exit_date,
        exit_price=leg.exit_price,
        pnl_dollars=leg.pnl_dollars,
        entry_reason="other",
        exit_reason="unknown",
        source_row=0,  # 0 = not from CSV
        broker_exec_id=leg.broker_exec_id,
        broker_open_exec_id=leg.broker_open_exec_id,
    )
    if annotation:
        for f, v in annotation.items():
            if v is not None:
                setattr(row, f, v)
    return row


def _link_decisions(rows: list[JournalTrade]) -> None:
    """Group broker rows sharing a buy execution into one decision.

    Within a group the representative (parent_trade_id = None) is the open
    remainder if present, else the latest-exiting leg; the rest point to it.
    Requires rows to already have ids (call after flush).
    """
    groups: dict[str, list[JournalTrade]] = {}
    for r in rows:
        if r.broker_open_exec_id:
            groups.setdefault(r.broker_open_exec_id, []).append(r)
    for legs in groups.values():
        rep = max(
            legs,
            key=lambda l: (l.exit_date is None, l.exit_date or date.min, l.id or 0),
        )
        for l in legs:
            l.parent_trade_id = None if l is rep else rep.id
