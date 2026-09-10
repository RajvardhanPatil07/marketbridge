"""Public, advisory-only Kalshi event-market signal adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from http.client import HTTPSConnection
import json
import math
import re
from threading import Lock
import time
from urllib.parse import urlencode


KALSHI_HOST = "external-api.kalshi.com"
KALSHI_BASE_PATH = "/trade-api/v2"
KALSHI_CACHE_SECONDS = 120
TRACKED_KALSHI_SYMBOLS = ("NVDA", "TSLA", "AAPL", "MSFT", "AMD", "QQQ")

SYMBOL_CONTEXT = {
    "NVDA": (("NVDA", 5), ("NVIDIA", 5), ("AI CHIP", 2), ("SEMICONDUCTOR", 2)),
    "TSLA": (("TSLA", 5), ("TESLA", 5), ("ELON MUSK", 2)),
    "AAPL": (("AAPL", 5), ("APPLE", 5), ("IPHONE", 2)),
    "MSFT": (("MSFT", 5), ("MICROSOFT", 5), ("OPENAI", 2)),
    "AMD": (("AMD", 5), ("ADVANCED MICRO DEVICES", 5), ("SEMICONDUCTOR", 2)),
    "QQQ": (("QQQ", 5), ("NASDAQ-100", 4), ("NASDAQ 100", 4)),
}

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = Lock()


class KalshiError(RuntimeError):
    """A classified upstream failure safe to expose through the API."""

    def __init__(self, status: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail[:160]


def _request_kalshi(path: str, params: dict[str, str]) -> dict:
    connection = HTTPSConnection(KALSHI_HOST, timeout=10)
    try:
        connection.request(
            "GET",
            f"{KALSHI_BASE_PATH}{path}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": "MarketBridge/0.3"},
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8")
    finally:
        connection.close()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise KalshiError("UPSTREAM_ERROR", "Kalshi returned an invalid response") from exc
    if response.status == 429:
        raise KalshiError("RATE_LIMITED", "Kalshi's public market-data rate limit was reached")
    if response.status >= 400:
        raise KalshiError("UPSTREAM_ERROR", "Kalshi public market data is temporarily unavailable")
    if not isinstance(payload, dict):
        raise KalshiError("UPSTREAM_ERROR", "Kalshi returned an unexpected response")
    return payload


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _contains(text: str, term: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(term)}(?![A-Z0-9])", text) is not None


def _relevance(symbol: str, item: dict) -> tuple[int, list[str]]:
    text = " ".join(
        str(item.get(key) or "")
        for key in (
            "ticker", "event_ticker", "series_ticker", "title", "subtitle",
            "yes_sub_title", "no_sub_title", "tags", "product_metadata",
        )
    ).upper()
    matched = [(term, weight) for term, weight in SYMBOL_CONTEXT[symbol] if _contains(text, term)]
    return (max((weight for _, weight in matched), default=0), [term for term, _ in matched])


def _midpoint(bid: float | None, ask: float | None, last: float | None) -> tuple[float | None, str]:
    if bid is not None and ask is not None and 0 <= bid <= ask <= 1:
        return (bid + ask) / 2, "BID_ASK_MIDPOINT"
    if last is not None and 0 <= last <= 1:
        return last, "LAST_TRADE"
    return None, "UNPRICED"


def _normalize_market(symbol: str, market: object, series_title: str = "") -> dict | None:
    if not isinstance(market, dict):
        return None
    relevance, terms = _relevance(symbol, {**market, "series_title": series_title})
    if not relevance:
        # Series discovery already established relevance, even when an individual
        # strike title does not repeat the company name.
        relevance, terms = _relevance(symbol, {"title": series_title})
    if not relevance:
        return None

    bid = _number(market.get("yes_bid_dollars"))
    ask = _number(market.get("yes_ask_dollars"))
    last = _number(market.get("last_price_dollars"))
    probability, price_source = _midpoint(bid, ask, last)
    previous_bid = _number(market.get("previous_yes_bid_dollars"))
    previous_ask = _number(market.get("previous_yes_ask_dollars"))
    previous_last = _number(market.get("previous_price_dollars"))
    previous_probability, _ = _midpoint(previous_bid, previous_ask, previous_last)
    change_pp = (
        round((probability - previous_probability) * 100, 4)
        if probability is not None and previous_probability is not None
        else None
    )
    spread_pp = round((ask - bid) * 100, 4) if bid is not None and ask is not None and ask >= bid else None
    volume_24h = _number(market.get("volume_24h_fp")) or 0.0
    if price_source == "BID_ASK_MIDPOINT" and spread_pp is not None and spread_pp <= 5 and volume_24h >= 100:
        quality = "HIGH"
    elif price_source == "BID_ASK_MIDPOINT" and spread_pp is not None and spread_pp <= 15:
        quality = "MEDIUM"
    else:
        quality = "LOW"

    title = str(market.get("title") or market.get("subtitle") or series_title).strip()
    if not title:
        title = str(market.get("yes_sub_title") or market.get("ticker") or "Kalshi event")
    return {
        "ticker": str(market.get("ticker") or ""),
        "event_ticker": str(market.get("event_ticker") or ""),
        "series_ticker": str(market.get("series_ticker") or ""),
        "title": title,
        "yes_label": str(market.get("yes_sub_title") or "Yes"),
        "probability": probability,
        "probability_change_pp": change_pp,
        "yes_bid": bid,
        "yes_ask": ask,
        "spread_pp": spread_pp,
        "volume_24h": volume_24h,
        "open_interest": _number(market.get("open_interest_fp")) or 0.0,
        "liquidity_dollars": _number(market.get("liquidity_dollars")) or 0.0,
        "close_time": str(market.get("close_time") or market.get("expected_expiration_time") or ""),
        "updated_time": str(market.get("updated_time") or ""),
        "quality": quality,
        "price_source": price_source,
        "relevance": "DIRECT" if relevance >= 4 else "RELATED",
        "matched_terms": terms,
        "advisory_only": True,
        "_rank": relevance * 100 + min(30.0, math.log10(volume_24h + 1) * 10),
    }


def _base_payload(symbol: str) -> dict:
    return {
        "provider": "kalshi",
        "symbol": symbol,
        "status": "UNAVAILABLE",
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cache_seconds": KALSHI_CACHE_SECONDS,
        "cached": False,
        "api_key_required": False,
        "cost": "FREE_PUBLIC_REST",
        "execution_authority": "ADVISORY_ONLY",
        "markets": [],
        "summary": {"matched": 0, "high_quality": 0, "largest_move_pp": None},
        "message": None,
        "limitations": [
            "Kalshi probabilities are event signals, not direct equity-price evidence.",
            "A displayed dislocation is not executable arbitrage after fees, spread, size, and settlement risk.",
        ],
    }


def _fetch_relevant_markets(symbol: str) -> tuple[list[dict], int, bool]:
    series_payload = _request_kalshi(
        "/series", {"include_product_metadata": "true", "include_volume": "true"}
    )
    relevant_series = []
    for item in series_payload.get("series", []):
        if not isinstance(item, dict):
            continue
        relevance, _ = _relevance(symbol, item)
        if relevance:
            relevant_series.append((relevance, _number(item.get("volume_fp")) or 0.0, item))
    relevant_series.sort(key=lambda row: (row[0], row[1]), reverse=True)

    normalized: list[dict] = []
    scanned = 0
    partial = len(relevant_series) > 8
    for _, _, series in relevant_series[:8]:
        cursor = ""
        for page in range(2):
            params = {
                "series_ticker": str(series.get("ticker") or ""),
                "status": "open",
                "limit": "1000",
                "mve_filter": "exclude",
            }
            if cursor:
                params["cursor"] = cursor
            payload = _request_kalshi("/markets", params)
            markets = payload.get("markets", [])
            scanned += len(markets) if isinstance(markets, list) else 0
            for market in markets if isinstance(markets, list) else []:
                if item := _normalize_market(symbol, market, str(series.get("title") or "")):
                    normalized.append(item)
            cursor = str(payload.get("cursor") or "")
            if not cursor:
                break
            if page == 1:
                partial = True

    # If series discovery finds nothing, scan one broad public page. This keeps the
    # endpoint useful when Kalshi changes series metadata without creating an
    # unbounded crawl of the exchange catalog.
    if not relevant_series:
        payload = _request_kalshi(
            "/markets", {"status": "open", "limit": "1000", "mve_filter": "exclude"}
        )
        markets = payload.get("markets", [])
        scanned += len(markets) if isinstance(markets, list) else 0
        partial = bool(payload.get("cursor"))
        for market in markets if isinstance(markets, list) else []:
            if item := _normalize_market(symbol, market):
                normalized.append(item)
    return normalized, scanned, partial


def get_kalshi_pulse(symbol: str, *, force: bool = False) -> dict:
    """Return ticker-relevant public Kalshi markets as an advisory signal."""
    normalized_symbol = symbol.upper()
    if normalized_symbol not in TRACKED_KALSHI_SYMBOLS:
        raise ValueError(f"unsupported Kalshi symbol: {normalized_symbol}")

    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(normalized_symbol)
        if cached and not force and now - cached[0] < KALSHI_CACHE_SECONDS:
            return {**cached[1], "cached": True}

    try:
        markets, scanned, partial = _fetch_relevant_markets(normalized_symbol)
        unique = {market["ticker"]: market for market in markets if market["ticker"]}
        ranked = sorted(unique.values(), key=lambda item: item["_rank"], reverse=True)[:8]
        for market in ranked:
            market.pop("_rank", None)
        changes = [abs(item["probability_change_pp"]) for item in ranked if item["probability_change_pp"] is not None]
        payload = {
            **_base_payload(normalized_symbol),
            "status": "AVAILABLE" if ranked else "NO_RELEVANT_MARKETS",
            "markets": ranked,
            "summary": {
                "matched": len(ranked),
                "high_quality": sum(item["quality"] == "HIGH" for item in ranked),
                "largest_move_pp": max(changes) if changes else None,
            },
            "catalog": {"scanned_markets": scanned, "partial": partial},
            "message": None if ranked else "No currently open Kalshi contract matched this asset.",
        }
        with _cache_lock:
            _cache[normalized_symbol] = (now, payload)
        return payload
    except KalshiError as exc:
        if cached:
            return {**cached[1], "status": "DEGRADED", "cached": True, "message": exc.detail}
        return {**_base_payload(normalized_symbol), "status": exc.status, "message": exc.detail}
    except (OSError, TimeoutError):
        if cached:
            return {
                **cached[1], "status": "DEGRADED", "cached": True,
                "message": "Kalshi is temporarily unreachable; showing cached event data.",
            }
        return {
            **_base_payload(normalized_symbol),
            "status": "UNAVAILABLE",
            "message": "Kalshi public market data is temporarily unreachable.",
        }


def clear_kalshi_cache() -> None:
    with _cache_lock:
        _cache.clear()
