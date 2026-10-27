"""Dated Cboe daily VIX closes, isolated from market decision policy.

The fixed public source is linked by Cboe's VIX historical-data page. No
credentials, database writes or background jobs are required. Calls share a
bounded in-process cache; an outage never invents a volatility observation.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import math
import re
import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Literal, TypedDict

import httpx

logger = logging.getLogger(__name__)
VIX_HISTORY_URL = "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
VIX_SOURCE_URL = "https://www.cboe.com/tradable_products/vix/vix_historical_data/"
VIX_CURRENT_SOURCE_URL = "https://www.cboe.com/tradable_products/vix/"
VIX_CURRENT_URL = "https://cdn-api.cboe.com/api/global/delayed_quotes/quotes/_VIX.json"
VIX_TRADE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
CACHE_SECONDS = 3600
RETRY_SECONDS = 60
MAX_RESPONSE_BYTES = 2_000_000
REQUEST_TIMEOUT_SECONDS = 8
CURRENT_CACHE_SECONDS = 60
CURRENT_STALE_SECONDS = 3600
NY = ZoneInfo("America/New_York")


class VixQuote(TypedDict):
    symbol: str
    price: float
    change_points: float | None
    change_pct: float | None
    date: str
    previous_date: str | None
    previous_price: float | None
    source: str
    source_url: str
    status: Literal["current", "stale"]
    refresh_failed: bool


class VixCurrentQuote(TypedDict):
    symbol: str
    price: float
    previous_close: float
    change_points: float
    change_pct: float
    date: str
    observed_at: str
    fetched_at: str
    source: str
    source_url: str
    delay_minutes: int
    status: Literal["current", "stale"]
    refresh_failed: bool


def parse_vix_current(payload: object, *, now: datetime) -> VixCurrentQuote:
    """Validate Cboe delayed quote and interpret its naive trade time as New York."""
    if not isinstance(payload, dict) or payload.get("symbol") != "_VIX":
        raise ValueError("Invalid Cboe VIX quote symbol")
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("symbol") != "^VIX":
        raise ValueError("Invalid Cboe VIX quote data")

    def price(key: str) -> float:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"Invalid Cboe {key}")
        result = float(value)
        if not math.isfinite(result) or result <= 0:
            raise ValueError(f"Invalid Cboe {key}")
        return result

    raw_time = data.get("last_trade_time")
    if not isinstance(raw_time, str) or not VIX_TRADE_TIME_RE.fullmatch(raw_time):
        raise ValueError("Missing Cboe trade time")
    try:
        observed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid Cboe trade time") from exc
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=NY)
    else:
        observed = observed.astimezone(NY)
    now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    observed_utc = observed.astimezone(timezone.utc)
    if observed_utc > now_utc:
        raise ValueError("Impossible Cboe trade time")
    current_price = price("current_price")
    previous_close = price("prev_day_close")
    return {
        "symbol": "VIX", "price": current_price, "previous_close": previous_close,
        "change_points": current_price - previous_close,
        "change_pct": (current_price / previous_close - 1) * 100,
        "date": observed.date().isoformat(), "observed_at": observed_utc.isoformat(),
        "fetched_at": now_utc.isoformat(), "source": "Cboe", "source_url": VIX_CURRENT_SOURCE_URL,
        "delay_minutes": 20, "status": "current", "refresh_failed": False,
    }


def parse_vix_history(text: str) -> list[tuple[date, float]]:
    """Validate and order daily closes; malformed observations are not prices."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if reader.fieldnames is None or not {"DATE", "CLOSE"}.issubset(reader.fieldnames):
        raise ValueError("Missing Cboe DATE/CLOSE columns")
    observations: dict[date, float] = {}
    for row in reader:
        try:
            day = datetime.strptime(row["DATE"], "%m/%d/%Y").date()
            close = float(row["CLOSE"])
        except (ValueError, TypeError, KeyError):
            continue
        if math.isfinite(close) and close > 0:
            observations[day] = close
    if not observations:
        raise ValueError("No valid Cboe daily closes")
    return sorted(observations.items())


class VixHistoryClient:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._clock = clock
        self._history: list[tuple[date, float]] = []
        self._retry_at = 0.0
        self._refresh_failed = False
        self._lock = asyncio.Lock()

    async def _download(self) -> list[tuple[date, float]]:
        async with httpx.AsyncClient(
            timeout=5.0, transport=self._transport, follow_redirects=False,
        ) as client:
            async with client.stream("GET", VIX_HISTORY_URL) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ValueError("Cboe response exceeds limit")
        return parse_vix_history(body.decode("utf-8-sig"))

    async def quote(self, as_of: date) -> VixQuote | None:
        if self._clock() >= self._retry_at:
            async with self._lock:
                # Concurrent callers reuse the winner's refresh or failure cooldown.
                if self._clock() >= self._retry_at:
                    try:
                        history = await asyncio.wait_for(
                            self._download(), timeout=REQUEST_TIMEOUT_SECONDS,
                        )
                    except (httpx.HTTPError, ValueError, UnicodeError, csv.Error, asyncio.TimeoutError) as exc:
                        self._refresh_failed = True
                        self._retry_at = self._clock() + RETRY_SECONDS
                        logger.warning("VIX daily close refresh unavailable (%s)", type(exc).__name__)
                    else:
                        self._history = history
                        self._refresh_failed = False
                        self._retry_at = self._clock() + CACHE_SECONDS

        eligible = [row for row in self._history if row[0] <= as_of]
        if not eligible:
            return None
        day, close = eligible[-1]
        previous_row = eligible[-2] if len(eligible) > 1 else None
        previous = previous_row[1] if previous_row is not None else None
        return {
            "symbol": "VIX",
            "price": close,
            "change_points": close - previous if previous is not None else None,
            "change_pct": (close / previous - 1) * 100 if previous is not None else None,
            "date": day.isoformat(),
            "previous_date": previous_row[0].isoformat() if previous_row is not None else None,
            "previous_price": previous,
            "source": "Cboe",
            "source_url": VIX_SOURCE_URL,
            "status": "stale" if day < as_of or self._refresh_failed else "current",
            "refresh_failed": self._refresh_failed,
        }


_client = VixHistoryClient()


async def get_vix_quote(as_of: date) -> VixQuote | None:
    return await _client.quote(as_of)


class VixCurrentClient:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._transport = transport
        self._clock = clock
        self._wall_clock = wall_clock
        self._quote: VixCurrentQuote | None = None
        self._retry_at = 0.0
        self._cache_until = 0.0
        self._refresh_failed = False
        self._lock = asyncio.Lock()

    async def _download(self) -> VixCurrentQuote:
        async with httpx.AsyncClient(
            timeout=5.0, transport=self._transport, follow_redirects=False,
        ) as client:
            async with client.stream("GET", VIX_CURRENT_URL) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ValueError("Cboe response exceeds limit")
        return parse_vix_current(json.loads(body), now=self._wall_clock())

    async def quote(self, as_of: date) -> VixCurrentQuote | None:
        today_ny = self._wall_clock().astimezone(NY).date()
        if as_of != today_ny:
            return None
        now_mono = self._clock()
        if now_mono >= self._retry_at and now_mono >= self._cache_until:
            async with self._lock:
                now_mono = self._clock()
                if now_mono >= self._retry_at and now_mono >= self._cache_until:
                    try:
                        quote = await asyncio.wait_for(self._download(), timeout=REQUEST_TIMEOUT_SECONDS)
                        if date.fromisoformat(quote["date"]) > as_of:
                            raise ValueError("Cboe trade date is after context date")
                    except (httpx.HTTPError, ValueError, UnicodeError, asyncio.TimeoutError) as exc:
                        self._refresh_failed = True
                        self._retry_at = self._clock() + RETRY_SECONDS
                        logger.warning("VIX spot refresh unavailable (%s)", type(exc).__name__)
                    else:
                        self._quote = quote
                        self._refresh_failed = False
                        self._cache_until = self._clock() + CURRENT_CACHE_SECONDS
                        self._retry_at = self._cache_until
        # The session can roll over while this request waits on the provider.
        if self._wall_clock().astimezone(NY).date() != as_of or self._quote is None:
            return None
        quote = dict(self._quote)
        quote_date = date.fromisoformat(quote["date"])
        if quote_date > as_of:
            return None
        observed = datetime.fromisoformat(quote["observed_at"])
        now = self._wall_clock()
        stale_by_age = (now.astimezone(timezone.utc) - observed).total_seconds() > CURRENT_STALE_SECONDS
        quote["refresh_failed"] = self._refresh_failed
        quote["status"] = "stale" if self._refresh_failed or stale_by_age or quote_date < as_of else "current"
        return quote


_current_client = VixCurrentClient()


async def get_vix_current_quote(as_of: date) -> VixCurrentQuote | None:
    return await _current_client.quote(as_of)
