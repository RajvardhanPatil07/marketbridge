from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from marketbridge.market_data.alpaca_history import AlpacaHistoricalProvider
from marketbridge.market_data.models import BarRequest, MarketDataError, Range, Resolution, Session
from marketbridge.market_data.ranges import DEFAULT_RESOLUTIONS, bounds_for_range
from marketbridge.market_data.service import HistoricalMarketDataService


BAR = {"t": "2026-09-08T14:00:00Z", "o": 100, "h": 102, "l": 99, "c": 101, "v": 500, "vw": 100.5, "n": 17}


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls: list[str] = []

    async def get_json(self, url, headers, timeout):
        self.urls.append(url)
        assert headers["APCA-API-KEY-ID"] == "key"
        assert headers["APCA-API-SECRET-KEY"] == "secret"
        return self.responses.pop(0)


def request() -> BarRequest:
    return BarRequest("NVDA", datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 9, tzinfo=timezone.utc), Resolution.MIN_5, "iex", "raw", Session.ALL)


def test_default_range_and_resolution_mapping():
    assert DEFAULT_RESOLUTIONS[Range.DAY_5] == Resolution.MIN_5
    assert DEFAULT_RESOLUTIONS[Range.MONTH_1] == Resolution.MIN_30
    assert DEFAULT_RESOLUTIONS[Range.MAX] == Resolution.MONTH_1
    now = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    assert (bounds_for_range(Range.MONTH_1, now)[0].month, bounds_for_range(Range.MONTH_1, now)[0].day) == (8, 9)
    assert bounds_for_range(Range.YTD, now)[0] == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_alpaca_paginates_and_normalizes_without_exposing_credentials():
    later = {**BAR, "t": "2026-09-08T14:05:00Z", "c": 103}
    transport = Transport([(200, {"bars": [BAR], "next_page_token": "next"}, {}), (200, {"bars": [later], "next_page_token": None}, {})])
    result = asyncio.run(AlpacaHistoricalProvider("key", "secret", transport=transport).fetch(request()))
    assert result.pages == 2
    assert [bar.close for bar in result.bars] == [101.0, 103.0]
    assert parse_qs(urlparse(transport.urls[1]).query)["page_token"] == ["next"]
    assert "secret" not in transport.urls[0]


def test_entitlement_and_rate_limit_are_normalized(monkeypatch):
    provider = AlpacaHistoricalProvider("key", "secret", transport=Transport([(403, {"message": "forbidden"}, {})]))
    with pytest.raises(MarketDataError, match="entitlement") as error:
        asyncio.run(provider.fetch(request()))
    assert error.value.code == "ENTITLEMENT"

    async def no_sleep(_):
        return None

    monkeypatch.setattr("marketbridge.market_data.alpaca_history.asyncio.sleep", no_sleep)
    provider = AlpacaHistoricalProvider("key", "secret", transport=Transport([(429, {}, {})] * 4))
    with pytest.raises(MarketDataError) as error:
        asyncio.run(provider.fetch(request()))
    assert error.value.code == "RATE_LIMITED"


def test_service_deduplicates_identical_requests_and_filters_regular_session():
    transport = Transport([(200, {"bars": [BAR], "next_page_token": None}, {})])
    service = HistoricalMarketDataService(AlpacaHistoricalProvider("key", "secret", transport=transport))
    args = dict(selected_range=Range.DAY_5, resolution=Resolution.MIN_5, feed="iex", adjustment="raw", session=Session.REGULAR, start=datetime(2026, 9, 1, tzinfo=timezone.utc), end=datetime(2026, 9, 9, tzinfo=timezone.utc))
    async def load():
        return await service.bars("NVDA", **args), await service.bars("NVDA", **args)

    first, second = asyncio.run(load())
    assert first["bars"][0]["trade_count"] == 17
    assert first["data_role"] == "DISPLAY_ONLY_NOT_ORACLE_EVIDENCE"
    assert second["cached"] is True
    assert len(transport.urls) == 1


def test_service_keeps_daily_bars_for_regular_session():
    daily_bar = {**BAR, "t": "2026-09-08T04:00:00Z"}
    transport = Transport([(200, {"bars": [daily_bar], "next_page_token": None}, {})])
    service = HistoricalMarketDataService(AlpacaHistoricalProvider("key", "secret", transport=transport))

    result = asyncio.run(service.bars(
        "NVDA",
        selected_range=Range.MONTH_6,
        resolution=Resolution.DAY_1,
        feed="iex",
        adjustment="raw",
        session=Session.REGULAR,
        start=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 9, tzinfo=timezone.utc),
    ))

    assert len(result["bars"]) == 1
    assert result["bars"][0]["timestamp"] == "2026-09-08T04:00:00Z"


def test_service_rejects_invalid_inputs_and_unconfigured_provider():
    service = HistoricalMarketDataService()
    with pytest.raises(MarketDataError) as error:
        asyncio.run(service.bars("bad symbol", selected_range=Range.DAY_1, resolution=None, feed="iex", adjustment="raw", session=Session.ALL))
    assert error.value.code == "INVALID_SYMBOL"


def test_batch_snapshots_supply_quote_and_daily_context():
    payload = {
        "snapshots": {
            "AMZN": {
                "latestTrade": {"p": 252.84, "t": "2026-09-10T15:00:00Z"},
                "latestQuote": {"bp": 252.80, "ap": 252.86},
                "dailyBar": {"c": 252.84, "v": 1_250_000, "t": "2026-09-10T04:00:00Z"},
                "prevDailyBar": {"c": 250.00, "t": "2026-09-09T04:00:00Z"},
            }
        }
    }
    transport = Transport([(200, payload, {})])
    service = HistoricalMarketDataService(AlpacaHistoricalProvider("key", "secret", transport=transport))

    result = asyncio.run(service.snapshots(("AMZN",), feed="iex"))

    assert result["AMZN"] == {
        "status": "AVAILABLE", "price": 252.84, "previous_close": 250.0,
        "change_pct": pytest.approx(1.136), "event_time": "2026-09-10T15:00:00Z",
        "bid": 252.8, "ask": 252.86, "day_volume": 1_250_000.0,
        "feed": "iex", "is_delayed": True,
    }
    assert parse_qs(urlparse(transport.urls[0]).query)["symbols"] == ["AMZN"]
