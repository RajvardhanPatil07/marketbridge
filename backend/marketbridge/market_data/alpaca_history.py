from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import random
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Bar, BarRequest, MarketDataError, ProviderResult


class JsonTransport(Protocol):
    async def get_json(self, url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict, dict]: ...


class UrllibTransport:
    async def get_json(self, url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict, dict]:
        def request() -> tuple[int, dict, dict]:
            try:
                with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                    return response.status, json.load(response), dict(response.headers.items())
            except HTTPError as exc:
                try:
                    payload = json.loads(exc.read().decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    payload = {}
                return exc.code, payload, dict(exc.headers.items())
            except (TimeoutError, URLError) as exc:
                raise MarketDataError("PROVIDER_UNAVAILABLE", "Alpaca historical data is temporarily unavailable") from exc

        return await asyncio.to_thread(request)


class AlpacaHistoricalProvider:
    endpoint = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    snapshots_endpoint = "https://data.alpaca.markets/v2/stocks/snapshots"

    def __init__(self, api_key: str, secret_key: str, *, transport: JsonTransport | None = None, timeout: float = 8.0, max_pages: int = 100):
        self.api_key = api_key
        self.secret_key = secret_key
        self.transport = transport or UrllibTransport()
        self.timeout = timeout
        self.max_pages = max_pages

    async def fetch(self, request: BarRequest) -> ProviderResult:
        token: str | None = None
        bars: dict[datetime, Bar] = {}
        pages = 0
        while True:
            params = {
                "timeframe": request.resolution.value,
                "start": request.start.isoformat(),
                "end": request.end.isoformat(),
                "adjustment": request.adjustment,
                "feed": request.feed,
                "sort": "asc",
                "limit": "10000",
            }
            if token:
                params["page_token"] = token
            payload = await self._request_page(self.endpoint.format(symbol=request.symbol) + "?" + urlencode(params))
            pages += 1
            for raw in payload.get("bars") or []:
                bar = self._normalize(raw)
                bars[bar.timestamp] = bar
            token = payload.get("next_page_token")
            if not token:
                break
            if pages >= self.max_pages:
                raise MarketDataError("PAGE_LIMIT", "Historical request exceeded its safe pagination limit", status_code=422)
            await asyncio.sleep(0)
        return ProviderResult(tuple(bars[key] for key in sorted(bars)), pages, self._entitlement(request.feed), request.feed == "iex")

    async def fetch_snapshots(self, symbols: tuple[str, ...], feed: str) -> dict[str, dict]:
        url = self.snapshots_endpoint + "?" + urlencode({"symbols": ",".join(symbols), "feed": feed})
        payload = await self._request_page(url)
        raw_snapshots = payload.get("snapshots", payload)
        if not isinstance(raw_snapshots, dict):
            raise MarketDataError("INVALID_PROVIDER_RESPONSE", "Alpaca returned invalid stock snapshots")
        return {
            symbol: self._normalize_snapshot(raw_snapshots.get(symbol), feed)
            for symbol in symbols
        }

    async def _request_page(self, url: str) -> dict:
        headers = {"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key, "Accept": "application/json"}
        for attempt in range(4):
            status, payload, response_headers = await self.transport.get_json(url, headers, self.timeout)
            if status == 200:
                return payload
            if status in {401, 403}:
                raise MarketDataError("ENTITLEMENT", "Alpaca credentials or feed entitlement were rejected", status_code=403)
            if status == 404:
                raise MarketDataError("SYMBOL_NOT_FOUND", "No historical data is available for this symbol", status_code=404)
            if status == 429 or status >= 500:
                if attempt == 3:
                    code = "RATE_LIMITED" if status == 429 else "PROVIDER_UNAVAILABLE"
                    raise MarketDataError(code, "Alpaca historical data is temporarily unavailable", status_code=429 if status == 429 else 503)
                retry_after = response_headers.get("Retry-After")
                delay = min(float(retry_after), 4.0) if retry_after and retry_after.replace(".", "", 1).isdigit() else min(0.25 * 2**attempt + random.random() * 0.1, 4.0)
                await asyncio.sleep(delay)
                continue
            raise MarketDataError("PROVIDER_ERROR", str(payload.get("message") or "Alpaca historical request failed"))
        raise AssertionError("unreachable")

    @staticmethod
    def _normalize(raw: dict) -> Bar:
        try:
            timestamp = datetime.fromisoformat(str(raw["t"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            return Bar(timestamp, float(raw["o"]), float(raw["h"]), float(raw["l"]), float(raw["c"]), float(raw["v"]), float(raw["vw"]) if raw.get("vw") is not None else None, int(raw["n"]) if raw.get("n") is not None else None)
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError("INVALID_PROVIDER_RESPONSE", "Alpaca returned an invalid historical bar") from exc

    @staticmethod
    def _normalize_snapshot(raw: object, feed: str) -> dict:
        if not isinstance(raw, dict):
            return {"status": "UNAVAILABLE", "price": None, "previous_close": None, "change_pct": None, "event_time": None, "bid": None, "ask": None, "day_volume": None, "feed": feed, "is_delayed": feed in {"iex", "delayed_sip"}}
        trade = raw.get("latestTrade") if isinstance(raw.get("latestTrade"), dict) else {}
        quote = raw.get("latestQuote") if isinstance(raw.get("latestQuote"), dict) else {}
        minute = raw.get("minuteBar") if isinstance(raw.get("minuteBar"), dict) else {}
        daily = raw.get("dailyBar") if isinstance(raw.get("dailyBar"), dict) else {}
        previous = raw.get("prevDailyBar") if isinstance(raw.get("prevDailyBar"), dict) else {}
        price = trade.get("p") or minute.get("c") or daily.get("c")
        previous_close = previous.get("c")
        try:
            price = float(price) if price is not None else None
            previous_close = float(previous_close) if previous_close is not None else None
            change_pct = (price / previous_close - 1) * 100 if price is not None and previous_close else None
            bid = float(quote["bp"]) if quote.get("bp") is not None else None
            ask = float(quote["ap"]) if quote.get("ap") is not None else None
            volume = float(daily["v"]) if daily.get("v") is not None else None
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            raise MarketDataError("INVALID_PROVIDER_RESPONSE", "Alpaca returned an invalid stock snapshot") from exc
        event_time = trade.get("t") or minute.get("t") or daily.get("t")
        return {
            "status": "AVAILABLE" if price is not None else "UNAVAILABLE", "price": price,
            "previous_close": previous_close, "change_pct": change_pct,
            "event_time": str(event_time) if event_time else None, "bid": bid, "ask": ask,
            "day_volume": volume, "feed": feed, "is_delayed": feed in {"iex", "delayed_sip"},
        }

    @staticmethod
    def _entitlement(feed: str) -> str:
        return "LIMITED_SINGLE_EXCHANGE" if feed == "iex" else "CONSOLIDATED" if feed == "sip" else "OVERNIGHT"
