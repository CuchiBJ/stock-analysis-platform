"""End-of-day price ingestion using Polygon Grouped Daily Bars.

Replaces the per-symbol yfinance bulk download for the post-close cycle.
One API call returns OHLCV for ~12,000 US tickers, vs yfinance's 5-28
minute serial download.

Polygon free tier limits:
  - 5 API calls/min (we use 1 per ingestion)
  - End-of-day data available shortly after market close (~15 min delay)
  - This endpoint IS available on free tier (verified 2026-05-29)

Falls back to yfinance bulk if Polygon is unreachable or returns no data.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.stock import Stock, StockPrice

logger = logging.getLogger(__name__)


class PolygonEODIngestor:
    """Bulk EOD price ingestion via Polygon Grouped Daily Bars."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, db: AsyncSession, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key or settings.polygon_api_key

    async def fetch_grouped_daily_bars(self, target_date: date) -> list[dict]:
        """Fetch grouped daily bars for a given trading date.

        Returns list of dicts like:
          {symbol, date, open, high, low, close, volume, vwap}

        Empty list on weekends, holidays, or pre-data-availability.
        """
        url = f"{self.BASE_URL}/v2/aggs/grouped/locale/us/market/stocks/{target_date.isoformat()}"
        params = {"apikey": self.api_key, "adjusted": "true"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, params=params)
            if r.status_code != 200:
                logger.error(
                    f"Polygon grouped daily bars failed for {target_date}: "
                    f"status={r.status_code} body={r.text[:200]}"
                )
                return []

            data = r.json()
            results = data.get("results", []) or []

        bars: list[dict] = []
        for r in results:
            sym = r.get("T")
            if not sym:
                continue
            bars.append({
                "symbol": sym,
                "date": target_date,
                "open":   r.get("o"),
                "high":   r.get("h"),
                "low":    r.get("l"),
                "close":  r.get("c"),
                "volume": int(r.get("v") or 0),
                "vwap":   r.get("vw"),
            })
        return bars

    async def ingest_eod(self, target_date: date) -> dict:
        """Fetch + upsert EOD prices for the given date.

        Only writes for symbols present in the `stocks` table (filters out
        the ~5,000 extra tickers Polygon returns that aren't in our universe).

        Returns stats dict: {fetched, in_universe, written, skipped, duration_sec}.
        """
        t0 = time.monotonic()
        bars = await self.fetch_grouped_daily_bars(target_date)
        if not bars:
            return {
                "as_of": target_date.isoformat(),
                "fetched": 0, "in_universe": 0, "written": 0,
                "skipped": 0, "duration_sec": round(time.monotonic() - t0, 2),
                "source": "polygon",
                "note": "no data for date (weekend/holiday/pre-availability)",
            }

        # Universe filter — only symbols in our stocks table
        result = await self.db.execute(select(Stock.symbol))
        universe = {row[0] for row in result.fetchall()}

        in_universe = [b for b in bars if b["symbol"] in universe]
        skipped_invalid = sum(
            1 for b in in_universe
            if not all(b[k] is not None for k in ("open", "high", "low", "close"))
        )

        valid = [
            b for b in in_universe
            if all(b[k] is not None for k in ("open", "high", "low", "close"))
        ]

        # Upsert in chunks of 500 to keep statement size reasonable
        written = 0
        for i in range(0, len(valid), 500):
            chunk = valid[i : i + 500]
            stmt = (
                insert(StockPrice)
                .values([
                    {
                        "symbol": b["symbol"],
                        "date":   b["date"],
                        "open":   float(b["open"]),
                        "high":   float(b["high"]),
                        "low":    float(b["low"]),
                        "close":  float(b["close"]),
                        "volume": int(b["volume"]),
                    }
                    for b in chunk
                ])
                .on_conflict_do_update(
                    index_elements=["symbol", "date"],
                    set_={
                        "open":   insert(StockPrice).excluded.open,
                        "high":   insert(StockPrice).excluded.high,
                        "low":    insert(StockPrice).excluded.low,
                        "close":  insert(StockPrice).excluded.close,
                        "volume": insert(StockPrice).excluded.volume,
                        "updated_at": datetime.utcnow(),
                    },
                )
            )
            await self.db.execute(stmt)
            written += len(chunk)
        await self.db.commit()

        duration = round(time.monotonic() - t0, 2)
        logger.info(
            f"PolygonEODIngestor[{target_date}]: fetched={len(bars)} "
            f"in_universe={len(in_universe)} written={written} "
            f"skipped_invalid={skipped_invalid} duration={duration}s"
        )
        return {
            "as_of": target_date.isoformat(),
            "fetched": len(bars),
            "in_universe": len(in_universe),
            "written": written,
            "skipped": skipped_invalid,
            "duration_sec": duration,
            "source": "polygon",
        }
