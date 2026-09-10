from __future__ import annotations

from datetime import datetime, timezone
import os
import re

from .alpaca_history import AlpacaHistoricalProvider
from .cache import AsyncBoundedCache
from .models import BarRequest, MarketDataError, ProviderResult, Range, Resolution, Session
from .ranges import DEFAULT_RESOLUTIONS, bounds_for_range
from .sessions import filter_session

SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,11}$")
FEEDS = {"iex", "sip", "boats"}
ADJUSTMENTS = {"raw", "all"}


class HistoricalMarketDataService:
    def __init__(self, provider: AlpacaHistoricalProvider | None = None):
        self.provider = provider
        self.cache: AsyncBoundedCache[ProviderResult] = AsyncBoundedCache(max_entries=128, ttl_seconds=30)
        self.snapshot_cache: AsyncBoundedCache[dict[str, dict]] = AsyncBoundedCache(max_entries=8, ttl_seconds=15)

    @classmethod
    def from_environment(cls) -> "HistoricalMarketDataService":
        key, secret = os.environ.get("ALPACA_API_KEY", "").strip(), os.environ.get("ALPACA_SECRET_KEY", "").strip()
        return cls(AlpacaHistoricalProvider(key, secret) if key and secret else None)

    async def bars(self, symbol: str, *, selected_range: Range, resolution: Resolution | None, feed: str, adjustment: str, session: Session, start: datetime | None = None, end: datetime | None = None) -> dict:
        symbol = symbol.upper()
        if not SYMBOL.fullmatch(symbol):
            raise MarketDataError("INVALID_SYMBOL", "Symbol format is invalid", status_code=422)
        if feed not in FEEDS:
            raise MarketDataError("INVALID_FEED", "Unsupported Alpaca feed", status_code=422)
        if adjustment not in ADJUSTMENTS:
            raise MarketDataError("INVALID_ADJUSTMENT", "Adjustment must be raw or all", status_code=422)
        if self.provider is None:
            raise MarketDataError("UNCONFIGURED", "Historical market data is unavailable because Alpaca credentials are not configured", status_code=503)
        default_start, default_end = bounds_for_range(selected_range)
        start = (start or default_start).astimezone(timezone.utc)
        end = (end or default_end).astimezone(timezone.utc)
        if start >= end:
            raise MarketDataError("INVALID_RANGE", "start must be earlier than end", status_code=422)
        resolution = resolution or DEFAULT_RESOLUTIONS[selected_range]
        request = BarRequest(symbol, start, end, resolution, feed, adjustment, session)
        result, cached = await self.cache.get_or_create(request, lambda: self.provider.fetch(request))
        bars = filter_session(result.bars, session, resolution)
        oldest = bars[0].timestamp if bars else start
        has_more = selected_range == Range.MAX and oldest.year > 1990
        return {
            "symbol": symbol, "provider": "alpaca", "feed": feed, "resolution": resolution.value,
            "adjustment": adjustment, "currency": "USD", "timezone": "America/New_York",
            "start": start.isoformat(), "end": end.isoformat(), "session": session.value,
            "status": "DELAYED" if result.is_delayed else "AVAILABLE", "is_delayed": result.is_delayed,
            "entitlement": result.entitlement, "cached": cached, "pages": result.pages,
            "bars": [bar.as_json() for bar in bars], "has_more_history": has_more,
            "next_end": oldest.isoformat() if has_more else None,
            "data_role": "DISPLAY_ONLY_NOT_ORACLE_EVIDENCE",
        }

    async def snapshots(self, symbols: tuple[str, ...], *, feed: str = "iex") -> dict[str, dict]:
        if not symbols or len(symbols) > 30 or any(not SYMBOL.fullmatch(symbol) for symbol in symbols):
            raise MarketDataError("INVALID_SYMBOLS", "One to 30 valid symbols are required", status_code=422)
        if feed not in FEEDS:
            raise MarketDataError("INVALID_FEED", "Unsupported Alpaca feed", status_code=422)
        if self.provider is None:
            raise MarketDataError("UNCONFIGURED", "Display snapshots are unavailable because Alpaca credentials are not configured", status_code=503)
        result, _cached = await self.snapshot_cache.get_or_create(
            (symbols, feed), lambda: self.provider.fetch_snapshots(symbols, feed)
        )
        return result
