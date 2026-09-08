"""Read-only Yahoo Finance research feed for the live shadow-mode demo."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timezone
import math
from threading import Lock
from time import monotonic
import warnings
from zoneinfo import ZoneInfo

import yfinance as yf


SYMBOLS = {"NVDA": "NVIDIA", "TSLA": "Tesla", "QQQ": "Invesco QQQ"}
REFRESH_SECONDS = 15
_cache: dict | None = None
_cached_at = 0.0
_lock = Lock()


def _market_phase(now: datetime) -> str:
    """Best-effort US session label; freshness remains the authoritative signal."""
    eastern = now.astimezone(ZoneInfo("America/New_York"))
    if eastern.weekday() >= 5:
        return "CLOSED"
    clock = eastern.time()
    if time(4) <= clock < time(9, 30):
        return "PRE_MARKET"
    if time(9, 30) <= clock < time(16):
        return "REGULAR"
    if time(16) <= clock < time(20):
        return "POST_MARKET"
    return "CLOSED"


def _finite(value: object) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _fetch_symbol(symbol: str, now: datetime) -> dict:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Timestamp.utcnow is deprecated.*")
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1d", interval="1m", prepost=True, auto_adjust=False)
        fast = ticker.fast_info
    if history.empty:
        raise RuntimeError("Yahoo returned no one-minute observations")
    points = []
    for timestamp, row in history.tail(180).iterrows():
        price = _finite(row.get("Close"))
        if price is not None:
            points.append({"timestamp": timestamp.to_pydatetime().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "price": price})
    if not points:
        raise RuntimeError("Yahoo returned no finite closing observations")
    last = points[-1]
    event_time = datetime.fromisoformat(last["timestamp"].replace("Z", "+00:00"))
    age_seconds = max(0, int((now - event_time).total_seconds()))
    previous_close = _finite(fast.get("regularMarketPreviousClose"))
    change_pct = None if not previous_close else (last["price"] / previous_close - 1) * 100
    fresh = age_seconds <= 120
    return {
        "symbol": symbol,
        "name": SYMBOLS[symbol],
        "observed_price": last["price"],
        "previous_close": previous_close,
        "change_pct": change_pct,
        "currency": str(fast.get("currency") or "USD"),
        "exchange": str(fast.get("exchange") or "UNKNOWN"),
        "event_time": last["timestamp"],
        "age_seconds": age_seconds,
        "points": points,
        "source": {
            "id": "yahoo-finance",
            "name": "Yahoo Finance via yfinance",
            "family": "yahoo-research-feed",
            "status": "FRESH" if fresh else "STALE",
        },
        "decision": {
            "status": "CAUTION" if fresh else "INSUFFICIENT_EVIDENCE",
            "reference": None,
            "independent_source_families": 1,
            "new_exposure_allowed": False,
            "advisory_exposure_multiplier": 0,
            "reasons": [
                "SINGLE_RESEARCH_FEED_NOT_LIQUIDATION_ELIGIBLE",
                "FRESH_YAHOO_OBSERVATION" if fresh else "STALE_YAHOO_OBSERVATION",
            ],
        },
    }


def get_live_snapshot(force: bool = False) -> dict:
    """Fetch and cache current Yahoo observations without converting them into an oracle price."""
    global _cache, _cached_at
    with _lock:
        if not force and _cache is not None and monotonic() - _cached_at < REFRESH_SECONDS:
            return _cache
        now = datetime.now(timezone.utc)
        observations = []
        errors = []
        with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
            futures = {symbol: executor.submit(_fetch_symbol, symbol, now) for symbol in SYMBOLS}
            for symbol, future in futures.items():
                try:
                    observations.append(future.result())
                except Exception as exc:  # provider/network failures are returned as data
                    errors.append({"symbol": symbol, "message": str(exc)[:180]})
        _cache = {
            "data_mode": "LIVE_RESEARCH",
            "provider": "Yahoo Finance via yfinance",
            "provider_status": "AVAILABLE" if observations and not errors else "DEGRADED" if observations else "UNAVAILABLE",
            "market_phase": _market_phase(now),
            "fetched_at": now.isoformat().replace("+00:00", "Z"),
            "refresh_seconds": REFRESH_SECONDS,
            "advisory_only": True,
            "api_key_required": False,
            "observations": observations,
            "errors": errors,
            "limitations": [
                "Yahoo Finance is a single research feed and is not eligible as a liquidation reference.",
                "Market phase is a schedule heuristic; event age determines whether an observation is fresh.",
                "Yahoo data may be delayed or unavailable and must not be redistributed or used for execution.",
            ],
        }
        _cached_at = monotonic()
        return _cache


def clear_live_cache() -> None:
    global _cache, _cached_at
    with _lock:
        _cache = None
        _cached_at = 0.0
