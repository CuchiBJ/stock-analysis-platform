#!/usr/bin/env python3
"""Prepare a frozen QQQ price candidate, export a QQQ-only backup, or apply it."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import user as _user_model  # Register User before SQLAlchemy configures relationships.
from app.models.stock import StockMetrics, StockPrice

WINDOW = 260
MAX_VOLUME = 2_147_483_647


def validate_rows(rows: Any, expected_dates: list[str], today: date) -> None:
    if not isinstance(rows, list) or len(rows) != WINDOW or len(expected_dates) != WINDOW:
        raise ValueError("candidate must contain exactly 260 sessions")
    seen: set[str] = set()
    ordered_dates: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("candidate rows must be objects")
        if row.get("symbol", "QQQ") != "QQQ":
            raise ValueError("candidate contains a non-QQQ symbol")
        stamp = row.get("date")
        try:
            parsed = date.fromisoformat(stamp)
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate dates must be ISO dates") from exc
        if parsed.isoformat() != stamp or parsed > today:
            raise ValueError("candidate date is invalid or in the future")
        if stamp in seen:
            raise ValueError("candidate has duplicate dates")
        seen.add(stamp)
        ordered_dates.append(stamp)
        prices = []
        for key in ("open", "high", "low", "close"):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid {key} for {stamp}")
            prices.append(float(value))
        opn, high, low, close = prices
        if low > min(opn, close) or max(opn, close) > high or low > high:
            raise ValueError(f"inconsistent OHLC for {stamp}")
        volume = row.get("volume")
        if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0 or volume > MAX_VOLUME:
            raise ValueError(f"invalid volume for {stamp}")
    if sorted(seen) != expected_dates or ordered_dates != expected_dates:
        raise ValueError("candidate dates do not exactly match the reference sessions")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


async def reference_dates(db: AsyncSession) -> list[date]:
    result = await db.execute(
        select(StockPrice.date).where(StockPrice.symbol == "SPY").order_by(StockPrice.date.desc()).limit(WINDOW)
    )
    dates = sorted(result.scalars().all())
    if len(dates) != WINDOW:
        raise ValueError("SPY does not have 260 reference sessions")
    return dates


async def prepare(db: AsyncSession, path: Path) -> dict[str, Any]:
    refs = await reference_dates(db)
    import yfinance as yf

    frame = yf.download("QQQ", start=refs[0].isoformat(), end=(refs[-1] + timedelta(days=1)).isoformat(),
                        auto_adjust=True, threads=False, progress=False)
    if frame.empty:
        raise ValueError("yfinance returned no QQQ data")
    if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
        frame.columns = frame.columns.get_level_values(0)
    rows = []
    for stamp, values in frame.iterrows():
        session_date = stamp.date() if isinstance(stamp, datetime) else stamp
        rows.append({"date": session_date.isoformat(), "open": float(values["Open"]),
                     "high": float(values["High"]), "low": float(values["Low"]),
                     "close": float(values["Close"]), "volume": int(values["Volume"])})
    expected = [d.isoformat() for d in refs]
    rows = [row for row in rows if row["date"] in set(expected)]
    order = {stamp: index for index, stamp in enumerate(expected)}
    rows.sort(key=lambda row: order[row["date"]])
    validate_rows(rows, expected, date.today())
    payload = {"symbol": "QQQ", "source": "yfinance:auto_adjust=True",
               "reference_dates": expected, "rows": rows,
               "prepared_at": datetime.now(timezone.utc).isoformat()}
    write_json(path, payload)
    return payload


async def export_backup(db: AsyncSession, path: Path) -> dict[str, Any]:
    payload = await read_qqq_snapshot(db)
    write_json(path, payload)
    return payload


def _mapped_values(item: Any, model: Any) -> dict[str, Any]:
    result = {}
    for col in model.__table__.columns:
        value = getattr(item, col.name)
        result[col.name] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return result


async def read_qqq_snapshot(db: AsyncSession) -> dict[str, Any]:
    prices_result = await db.execute(select(StockPrice).where(StockPrice.symbol == "QQQ").order_by(StockPrice.date))
    metrics_result = await db.execute(select(StockMetrics).where(StockMetrics.symbol == "QQQ").order_by(StockMetrics.date))
    prices = [_mapped_values(item, StockPrice) for item in prices_result.scalars().all()]
    metrics = [_mapped_values(item, StockMetrics) for item in metrics_result.scalars().all()]
    return {"version": 1, "symbol": "QQQ", "prices": prices, "metrics": metrics}


class NoCommitSession:
    """Expose the session to MetricsCalculator while keeping its commit inside our transaction."""
    def __init__(self, db: AsyncSession):
        self._db = db

    def __getattr__(self, name: str) -> Any:
        return getattr(self._db, name)

    async def commit(self) -> None:
        await self._db.flush()


async def execute(db: AsyncSession, candidate_path: Path, backup_path: Path, expected_sha: str) -> dict[str, Any]:
    if candidate_path.resolve() == backup_path.resolve():
        raise ValueError("candidate and backup paths must differ")
    raw = candidate_path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha.casefold() != expected_sha.casefold():
        raise ValueError("candidate SHA-256 mismatch")
    candidate = json.loads(raw)
    if candidate.get("symbol") != "QQQ" or candidate.get("source") != "yfinance:auto_adjust=True":
        raise ValueError("candidate symbol/reference mismatch")
    refs = await reference_dates(db)
    ref_strings = [d.isoformat() for d in refs]
    if candidate.get("reference_dates") != ref_strings:
        raise ValueError("candidate references no longer match current SPY sessions")
    rows = candidate.get("rows")
    validate_rows(rows, ref_strings, date.today())
    if not backup_path.is_file():
        raise ValueError("QQQ backup file is missing")
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    if (not isinstance(backup, dict) or backup.get("version") != 1 or backup.get("symbol") != "QQQ"
            or not isinstance(backup.get("prices"), list) or not isinstance(backup.get("metrics"), list)):
        raise ValueError("backup is not QQQ-only")
    if any(not isinstance(row, dict) or row.get("symbol") != "QQQ" for row in backup["prices"] + backup["metrics"]):
        raise ValueError("backup contains a non-QQQ row")
    current_snapshot = await read_qqq_snapshot(db)
    if backup != current_snapshot:
        raise ValueError("backup does not match the current QQQ database snapshot")
    try:
        for row in rows:
            d = date.fromisoformat(row["date"])
            result = await db.execute(select(StockPrice).where(StockPrice.symbol == "QQQ", StockPrice.date == d))
            price = result.scalar_one_or_none()
            is_new = price is None
            if is_new:
                price = StockPrice(symbol="QQQ", date=d)
            for key in ("open", "high", "low", "close", "volume"):
                setattr(price, key, row[key])
            if is_new:
                db.add(price)
        from app.data.ingestors.metrics_calculator import MetricsCalculator
        calculator = MetricsCalculator(NoCommitSession(db))
        latest = ref_strings[-1]
        metrics = await calculator.calculate_metrics_for_symbol("QQQ", days=WINDOW, as_of_date=latest)
        if metrics is None or metrics.symbol != "QQQ" or metrics.date.isoformat() != latest:
            raise ValueError("calculator did not produce metrics for the latest QQQ session")
        closes = [float(row["close"]) for row in rows[-252:]]
        metrics.high_52w = max(closes)
        for field in ("current_price", "ema50", "ema200", "sma150", "sma200"):
            value = getattr(metrics, field)
            if value is None or not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"invalid critical metric: {field}")
        await db.flush()
        window_result = await db.execute(
            select(StockPrice.date).where(StockPrice.symbol == "QQQ", StockPrice.date <= refs[-1])
            .order_by(StockPrice.date.desc()).limit(WINDOW)
        )
        qqq_window = sorted(window_result.scalars().all())
        if qqq_window != refs:
            raise ValueError("latest 260 QQQ sessions do not exactly match SPY references")
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"prices_upserted": len(rows), "metrics_written": 1, "latest_date": latest}


async def run(args: argparse.Namespace) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            if args.execute:
                result = await execute(db, Path(args.candidate), Path(args.backup), args.sha256)
                print(json.dumps(result, sort_keys=True))
            elif args.backup:
                payload = await export_backup(db, Path(args.backup))
                print(json.dumps({"backup_written": True, "price_count": len(payload["prices"]),
                                  "metrics_count": len(payload["metrics"])}))
            else:
                payload = await prepare(db, Path(args.candidate))
                print(json.dumps({"candidate_written": True, "price_count": len(payload["rows"]),
                                  "first_date": payload["reference_dates"][0],
                                  "last_date": payload["reference_dates"][-1]}))
    except ValueError as exc:
        print(f"recovery failed: ValueError: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        print(f"recovery failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", help="candidate JSON path (prepare/execute)")
    parser.add_argument("--backup", help="QQQ backup JSON path (backup/execute)")
    parser.add_argument("--execute", action="store_true", help="apply a validated frozen candidate")
    parser.add_argument("--sha256", help="expected candidate file SHA-256 for execute")
    args = parser.parse_args()
    if args.execute:
        if not (args.candidate and args.backup and args.sha256):
            parser.error("--execute requires --candidate, --backup, and --sha256")
    elif bool(args.backup) == bool(args.candidate):
        parser.error("choose exactly one of --candidate (prepare) or --backup")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
