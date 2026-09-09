"""Server-side Marketaux adapter for ticker-linked financial news."""

from __future__ import annotations

from datetime import datetime, timezone
from http.client import HTTPSConnection
import json
import math
import os
from threading import Lock
import time
from urllib.parse import urlencode, urlparse


MARKETAUX_HOST = "api.marketaux.com"
MARKETAUX_PATH = "/v1/news/all"
TRACKED_NEWS_SYMBOLS = ("NVDA", "TSLA", "AAPL", "MSFT", "AMD", "QQQ")
NEWS_CACHE_SECONDS = 300

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = Lock()


class MarketauxError(RuntimeError):
    """A classified upstream failure safe to expose through the read-only API."""

    def __init__(self, status: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail[:160]


def _request_marketaux(params: dict[str, str]) -> dict:
    connection = HTTPSConnection(MARKETAUX_HOST, timeout=8)
    try:
        connection.request(
            "GET",
            f"{MARKETAUX_PATH}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": "MarketBridge/0.3"},
        )
        response = connection.getresponse()
        payload = response.read().decode("utf-8")
    finally:
        connection.close()

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise MarketauxError("UPSTREAM_ERROR", "Marketaux returned an invalid response") from exc

    if response.status in {401, 403}:
        raise MarketauxError("AUTH_ERROR", "Marketaux rejected the configured API token")
    if response.status == 429:
        raise MarketauxError("RATE_LIMITED", "Marketaux request allowance is exhausted")
    if response.status >= 400:
        message = parsed.get("error", {}).get("message") if isinstance(parsed, dict) else None
        raise MarketauxError("UPSTREAM_ERROR", str(message or "Marketaux request failed"))
    if not isinstance(parsed, dict):
        raise MarketauxError("UPSTREAM_ERROR", "Marketaux returned an unexpected response")
    return parsed


def _sentiment(entities: object) -> float | None:
    if not isinstance(entities, list):
        return None
    values = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        try:
            value = float(entity.get("sentiment_score"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return sum(values) / len(values) if values else None


def _article(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    if not title or urlparse(url).scheme != "https":
        return None
    entities = item.get("entities") if isinstance(item.get("entities"), list) else []
    symbols = sorted(
        {
            str(entity.get("symbol")).upper()
            for entity in entities
            if isinstance(entity, dict) and entity.get("symbol")
        }
    )
    source = str(item.get("source") or urlparse(url).netloc).removeprefix("www.")
    return {
        "id": str(item.get("uuid") or url),
        "title": title,
        "description": str(item.get("description") or item.get("snippet") or "").strip(),
        "url": url,
        "source": source,
        "published_at": str(item.get("published_at") or ""),
        "symbols": symbols,
        "sentiment_score": _sentiment(entities),
    }


def _base_payload(symbol: str | None) -> dict:
    return {
        "provider": "marketaux",
        "configured": False,
        "status": "UNCONFIGURED",
        "symbol": symbol,
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cache_seconds": NEWS_CACHE_SECONDS,
        "cached": False,
        "articles": [],
        "message": "Set MARKETAUX_API_TOKEN on the backend to enable live financial news.",
    }


def get_market_news(symbol: str | None = None, *, force: bool = False) -> dict:
    """Fetch and normalize a small Marketaux feed without exposing its API token."""
    normalized_symbol = symbol.upper() if symbol else None
    if normalized_symbol and normalized_symbol not in TRACKED_NEWS_SYMBOLS:
        raise ValueError(f"unsupported news symbol: {normalized_symbol}")

    token = os.environ.get("MARKETAUX_API_TOKEN", "").strip()
    if not token:
        return _base_payload(normalized_symbol)

    cache_key = normalized_symbol or "__all__"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and not force and now - cached[0] < NEWS_CACHE_SECONDS:
            return {**cached[1], "cached": True}

    params = {
        "api_token": token,
        "symbols": normalized_symbol or ",".join(TRACKED_NEWS_SYMBOLS),
        "filter_entities": "true",
        "language": "en",
        "countries": "us",
        "limit": "3",
    }
    try:
        raw = _request_marketaux(params)
        articles = [article for item in raw.get("data", []) if (article := _article(item))]
        payload = {
            **_base_payload(normalized_symbol),
            "configured": True,
            "status": "AVAILABLE",
            "articles": articles,
            "message": None,
            "meta": {
                "found": int(raw.get("meta", {}).get("found", len(articles))),
                "returned": len(articles),
            },
        }
        with _cache_lock:
            _cache[cache_key] = (now, payload)
        return payload
    except MarketauxError as exc:
        if cached:
            return {**cached[1], "status": "DEGRADED", "cached": True, "message": exc.detail}
        return {
            **_base_payload(normalized_symbol),
            "configured": True,
            "status": exc.status,
            "message": exc.detail,
        }
    except (OSError, TimeoutError):
        if cached:
            return {
                **cached[1],
                "status": "DEGRADED",
                "cached": True,
                "message": "Marketaux is temporarily unreachable; showing the last cached feed.",
            }
        return {
            **_base_payload(normalized_symbol),
            "configured": True,
            "status": "UNAVAILABLE",
            "message": "Marketaux is temporarily unreachable.",
        }


def clear_news_cache() -> None:
    with _cache_lock:
        _cache.clear()
