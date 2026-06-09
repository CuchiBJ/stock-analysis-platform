"""Group journal legs into position episodes and assign decision linkage.

A "decision" (one operation) is a position episode: the maximal set of legs of
the same symbol whose holding intervals [entry_date, exit_date] overlap or chain
together — i.e. the symbol was held continuously without the position returning
to zero in between. Adding to a still-open position (a second fill at a different
price, possibly on a later day) stays in the same episode; re-entering the symbol
*after* fully liquidating starts a new episode.

Each episode gets a single representative (parent_trade_id IS NULL); every other
leg points to it via parent_trade_id. This is the source of truth the journal
stats and the UI both group by (decision_id = parent_trade_id or id), so it must
be computed once here and reused everywhere.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.models.stock import JournalTrade


def assign_decision_links(trades: list[JournalTrade]) -> int:
    """Group `trades` into position episodes per symbol and set parent_trade_id
    so each episode is one decision. Mutates the objects in place; the caller is
    responsible for committing. Returns the number of rows whose parent_trade_id
    changed (useful for dry-run reporting and idempotency checks).
    """
    by_symbol: dict[str, list[JournalTrade]] = defaultdict(list)
    for t in trades:
        by_symbol[t.symbol].append(t)

    changed = 0
    for legs in by_symbol.values():
        for episode in _episodes(legs):
            # Representative: prefer the open leg (the still-held runner) so the
            # decision is anchored on the live position; else the lowest id.
            open_legs = [t for t in episode if t.exit_date is None]
            rep = min(open_legs or episode, key=lambda t: t.id)
            for t in episode:
                target = None if t.id == rep.id else rep.id
                if t.parent_trade_id != target:
                    t.parent_trade_id = target
                    changed += 1
    return changed


def _episodes(legs: list[JournalTrade]) -> list[list[JournalTrade]]:
    """Partition one symbol's legs into episodes of overlapping holding periods.

    Open legs (exit_date IS NULL) are treated as held indefinitely, so any later
    entry merges into the still-open position. Touching intervals (a sell and a
    same-day re-buy) are treated as overlapping and merged.
    """
    # Sort by entry so a single forward sweep can merge overlapping intervals.
    legs_sorted = sorted(legs, key=lambda t: (t.entry_date or date.min, t.id))
    episodes: list[list[JournalTrade]] = []
    current: list[JournalTrade] = []
    current_max_exit: date | None = None

    for t in legs_sorted:
        entry = t.entry_date or date.min
        exit_ = t.exit_date or date.max  # open leg → held indefinitely
        if not current:
            current = [t]
            current_max_exit = exit_
        elif current_max_exit is not None and entry <= current_max_exit:
            current.append(t)
            if exit_ > current_max_exit:
                current_max_exit = exit_
        else:
            episodes.append(current)
            current = [t]
            current_max_exit = exit_

    if current:
        episodes.append(current)
    return episodes
