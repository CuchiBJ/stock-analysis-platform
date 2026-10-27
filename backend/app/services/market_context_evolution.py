"""Faithful, bounded market-context evolution evidence."""
from __future__ import annotations

import math
from datetime import date
from typing import Any


def serialize_evolution(rows: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    """Serialize grouped dimension rows without turning missing coverage into zero."""
    dated_rows = [
        row for row in rows
        if isinstance(row.get("date"), date) and row["date"] <= as_of
    ]
    dated_rows.sort(key=lambda row: row["date"])
    result = []
    for row in dated_rows[-20:]:
        has_coverage = _nonnegative_integer(row.get("universe")) and row["universe"] > 0
        breadth = _breadth(row.get("breadth_ratio")) if has_coverage else None
        count = row.get("leader_count")
        leaders = count if has_coverage and _nonnegative_integer(count) else None
        result.append({
            "date": row["date"].isoformat(),
            "breadth_ratio": breadth,
            "leader_count": leaders,
        })
    return result


def _nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _breadth(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        return None
    return round(number, 4)
