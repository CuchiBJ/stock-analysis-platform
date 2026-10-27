"""Synthetic HTTP fixtures only; no provider or production data calls."""
import asyncio
import json
from datetime import date

import httpx
import pytest

from app.services import market_volatility as volatility

CSV = "DATE,OPEN,HIGH,LOW,CLOSE\n10/19/2026,18,20,17,20\n10/20/2026,20,23,19,22\n10/21/2026,22,25,21,24\n"
CURRENT = '{"symbol":"_VIX","timestamp":"ignored","data":{"symbol":"^VIX","current_price":18.33,"prev_day_close":19.45,"last_trade_time":"2026-10-26T14:13:31"}}'


def test_parse_orders_dates_skips_bad_prices_and_handles_bom():
    rows = volatility.parse_vix_history(
        "\ufeffDATE,CLOSE\n10/20/2026,22\ninvalid,21\n10/19/2026,20\n"
        "10/21/2026,nan\n10/22/2026,inf\n10/23/2026,0\n10/24/2026,-1\n"
    )
    assert rows == [(date(2026, 10, 19), 20), (date(2026, 10, 20), 22)]


@pytest.mark.parametrize("text", ["<html>upstream error</html>", "DATE,CLOSE\ninvalid,nan\n"])
def test_parse_rejects_invalid_payloads(text):
    with pytest.raises(ValueError):
        volatility.parse_vix_history(text)


def test_historical_date_changes_cache_and_missing_previous():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=CSV)

    async def run():
        client = volatility.VixHistoryClient(transport=httpx.MockTransport(respond))
        quote = await client.quote(date(2026, 10, 20))
        assert quote["price"] == 22
        assert quote["date"] == "2026-10-20"
        assert quote["previous_date"] == "2026-10-19"
        assert quote["previous_price"] == 20
        assert quote["change_points"] == 2
        assert quote["change_pct"] == pytest.approx(10)
        assert quote["status"] == "current"
        assert quote["refresh_failed"] is False
        assert quote["source"] == "Cboe"
        first = await client.quote(date(2026, 10, 19))
        assert first["previous_date"] is None
        assert first["previous_price"] is None
        assert first["change_pct"] is None
        assert first["change_points"] is None
        assert await client.quote(date(2026, 10, 18)) is None
        older = await client.quote(date(2026, 10, 22))
        assert older["date"] == "2026-10-21"
        assert older["status"] == "stale"

    asyncio.run(run())
    assert len(requests) == 1
    assert str(requests[0].url) == volatility.VIX_HISTORY_URL


def test_failure_preserves_dated_cache_and_retries_after_cooldown():
    now = [100.0]
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 2 else httpx.Response(200, text=CSV)

    async def run():
        client = volatility.VixHistoryClient(
            transport=httpx.MockTransport(respond), clock=lambda: now[0],
        )
        assert (await client.quote(date(2026, 10, 21)))["refresh_failed"] is False
        now[0] += volatility.CACHE_SECONDS + 1
        failed_quote = await client.quote(date(2026, 10, 21))
        assert failed_quote["status"] == "stale"
        assert failed_quote["refresh_failed"] is True
        assert failed_quote["price"] == 24
        assert len(calls) == 2
        now[0] += volatility.RETRY_SECONDS + 1
        recovered_quote = await client.quote(date(2026, 10, 21))
        assert recovered_quote["status"] == "current"
        assert recovered_quote["refresh_failed"] is False
        assert len(calls) == 3

    asyncio.run(run())


def test_unavailable_is_null_and_concurrent_calls_share_failure():
    calls = []

    async def respond(request):
        calls.append(request)
        await asyncio.sleep(0)
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    async def run():
        client = volatility.VixHistoryClient(transport=httpx.MockTransport(respond))
        results = await asyncio.gather(*(client.quote(date(2026, 10, 20)) for _ in range(5)))
        assert results == [None] * 5
        assert len(calls) == 1

    asyncio.run(run())


def test_concurrent_success_downloads_once():
    calls = []

    async def respond(request):
        calls.append(request)
        await asyncio.sleep(0)
        return httpx.Response(200, text=CSV)

    async def run():
        client = volatility.VixHistoryClient(transport=httpx.MockTransport(respond))
        results = await asyncio.gather(*(client.quote(date(2026, 10, 20)) for _ in range(5)))
        assert all(result["price"] == 22 for result in results)
        assert len(calls) == 1

    asyncio.run(run())


def test_oversized_response_and_malformed_csv_fail_closed(monkeypatch):
    monkeypatch.setattr(volatility, "MAX_RESPONSE_BYTES", 20)

    async def run():
        client = volatility.VixHistoryClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text=CSV)),
        )
        assert await client.quote(date(2026, 10, 20)) is None
        invalid = volatility.VixHistoryClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html/>")),
        )
        assert await invalid.quote(date(2026, 10, 20)) is None

    asyncio.run(run())


def test_total_download_deadline_returns_unavailable(monkeypatch):
    monkeypatch.setattr(volatility, "REQUEST_TIMEOUT_SECONDS", 0.01)

    async def respond(request):
        await asyncio.sleep(0.1)
        return httpx.Response(200, text=CSV)

    async def run():
        client = volatility.VixHistoryClient(transport=httpx.MockTransport(respond))
        assert await client.quote(date(2026, 10, 20)) is None

    asyncio.run(run())


def test_current_quote_parses_new_york_trade_time_and_computes_change():
    from datetime import datetime, timezone

    quote = volatility.parse_vix_current(
        json.loads(CURRENT),
        now=datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc),
    )
    assert quote["date"] == "2026-10-26"
    assert quote["observed_at"] == "2026-10-26T18:13:31+00:00"
    assert quote["price"] == 18.33
    assert quote["previous_close"] == 19.45
    assert quote["change_points"] == pytest.approx(-1.12)
    assert quote["change_pct"] == pytest.approx((18.33 / 19.45 - 1) * 100)
    assert quote["delay_minutes"] == 20


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(symbol="VIX"),
    lambda x: x["data"].update(symbol="^SPX"),
    lambda x: x["data"].update(current_price=True),
    lambda x: x["data"].update(current_price=float("inf")),
    lambda x: x["data"].update(prev_day_close=0),
    lambda x: x["data"].update(last_trade_time="not-a-date"),
    lambda x: x["data"].update(last_trade_time="2026-10-26"),
    lambda x: x["data"].update(last_trade_time="2026-10-26 14:13:31"),
])
def test_current_quote_rejects_invalid_evidence(mutate):
    from datetime import datetime, timezone

    payload = json.loads(CURRENT)
    mutate(payload)
    with pytest.raises(ValueError):
        volatility.parse_vix_current(payload, now=datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc))


def test_current_quote_is_today_only_bounded_and_outage_marks_cached_quote_stale():
    from datetime import datetime, timezone

    now_mono = [100.0]
    now_wall = [datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc)]
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, text=CURRENT) if len(calls) == 1 else httpx.Response(503)

    async def run():
        client = volatility.VixCurrentClient(
            transport=httpx.MockTransport(respond), clock=lambda: now_mono[0],
            wall_clock=lambda: now_wall[0],
        )
        assert await client.quote(date(2026, 10, 25)) is None
        assert calls == []
        current = await client.quote(date(2026, 10, 26))
        assert current["status"] == "current"
        assert len(calls) == 1
        assert (await client.quote(date(2026, 10, 26)))["price"] == 18.33
        assert len(calls) == 1
        now_mono[0] += volatility.CURRENT_CACHE_SECONDS + 1
        failed = await client.quote(date(2026, 10, 26))
        assert failed["status"] == "stale"
        assert failed["refresh_failed"] is True
        assert failed["price"] == 18.33
        assert len(calls) == 2

    asyncio.run(run())


def test_current_quote_stale_by_age_and_future_trade_time_rejected():
    from datetime import datetime, timezone

    payload = json.loads(CURRENT)
    payload["data"]["last_trade_time"] = "2026-10-26T14:31:00"
    with pytest.raises(ValueError):
        volatility.parse_vix_current(payload, now=datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc))

    now_wall = [datetime(2026, 10, 26, 19, 30, tzinfo=timezone.utc)]
    async def run():
        client = volatility.VixCurrentClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text=CURRENT)),
            wall_clock=lambda: now_wall[0],
        )
        quote = await client.quote(date(2026, 10, 26))
        assert quote["status"] == "stale"
    asyncio.run(run())


def test_cached_prior_session_quote_is_stale_and_context_date_isolation_holds():
    from datetime import datetime, timezone

    now_wall = [datetime(2026, 10, 27, 3, 59, 30, tzinfo=timezone.utc)]
    calls = []
    async def run():
        client = volatility.VixCurrentClient(
            transport=httpx.MockTransport(lambda request: (calls.append(request), httpx.Response(200, text=CURRENT))[1]),
            wall_clock=lambda: now_wall[0],
        )
        quote = await client.quote(date(2026, 10, 26))
        assert quote["status"] == "stale"
        now_wall[0] = datetime(2026, 10, 27, 4, 0, 15, tzinfo=timezone.utc)
        # The still-cached old-session observation remains explicitly stale after midnight in New York.
        assert (await client.quote(date(2026, 10, 27)))["status"] == "stale"
        assert len(calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("response_text", [CURRENT, "not-json"])
def test_current_quote_rejects_oversized_and_malformed_json(response_text, monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(volatility, "MAX_RESPONSE_BYTES", 20 if response_text == CURRENT else 2000)
    async def run():
        client = volatility.VixCurrentClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text=response_text)),
            wall_clock=lambda: datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc),
        )
        assert await client.quote(date(2026, 10, 26)) is None
    asyncio.run(run())


def test_current_quote_total_deadline_returns_unavailable(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(volatility, "REQUEST_TIMEOUT_SECONDS", 0.01)
    async def respond(request):
        await asyncio.sleep(0.1)
        return httpx.Response(200, text=CURRENT)

    async def run():
        client = volatility.VixCurrentClient(
            transport=httpx.MockTransport(respond),
            wall_clock=lambda: datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc),
        )
        assert await client.quote(date(2026, 10, 26)) is None
    asyncio.run(run())


@pytest.mark.parametrize("fails", [False, True])
def test_concurrent_current_quote_refreshes_share_success_or_failure(fails):
    from datetime import datetime, timezone

    calls = []
    async def respond(request):
        calls.append(request)
        await asyncio.sleep(0)
        if fails:
            return httpx.Response(503)
        return httpx.Response(200, text=CURRENT)

    async def run():
        client = volatility.VixCurrentClient(
            transport=httpx.MockTransport(respond),
            wall_clock=lambda: datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc),
        )
        quotes = await asyncio.gather(*(client.quote(date(2026, 10, 26)) for _ in range(6)))
        assert len(calls) == 1
        if fails:
            assert quotes == [None] * 6
        else:
            assert all(quote["price"] == 18.33 for quote in quotes)
    asyncio.run(run())


def test_volatility_endpoint_preserves_daily_evidence_when_spot_unavailable(monkeypatch):
    daily = {"symbol": "VIX", "price": 19.45, "date": "2026-10-23"}
    async def daily_quote(as_of):
        assert as_of == date(2026, 10, 26)
        return daily
    async def spot_quote(as_of):
        assert as_of == date(2026, 10, 26)
        return None

    monkeypatch.setattr(volatility, "get_vix_quote", daily_quote)
    monkeypatch.setattr(volatility, "get_vix_current_quote", spot_quote)
    async def run():
        from app.api.v1.endpoints import market_context

        result = await market_context.get_market_volatility(date(2026, 10, 26))
        assert result == {"vix": daily, "current_quote": None}
    asyncio.run(run())
