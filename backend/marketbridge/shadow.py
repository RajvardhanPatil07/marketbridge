"""Low-latency shadow-oracle pipeline with explicit source lineage.

MarketBridge treats the trading venue's mark as an observation to compare against,
not as independent evidence used to validate itself.  Direct market evidence has
priority.  A conservative factor estimate can be emitted when direct evidence is
insufficient, but it is clearly labelled ESTIMATED and carries tighter risk limits.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from queue import SimpleQueue
from statistics import median
from threading import Condition, Event, Lock, Thread
from time import perf_counter_ns
from typing import Callable

from .live import get_live_snapshot


TRACKED_SYMBOLS = ("NVDA", "TSLA", "AAPL", "MSFT", "AMD", "QQQ")
FRESH_SECONDS = 10
AGREEMENT_BPS = 75
LARGE_MOVE_BPS = 500

# Lightweight, explainable prototype fallback.  These are intentionally static
# demonstration coefficients, not fitted production parameters.
QQQ_BETA = {
    "NVDA": 1.45,
    "TSLA": 1.30,
    "AAPL": 1.05,
    "MSFT": 1.00,
    "AMD": 1.35,
}


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class NormalizedObservation:
    symbol: str
    price: float
    event_time: datetime
    received_at: datetime
    source_id: str
    source_family: str
    venue: str
    eligible: bool
    # Two independent axes.  Several venues delivered through one vendor still
    # share provider failure risk.
    provider_family: str | None = None
    venue_family: str | None = None

    @property
    def provider(self) -> str:
        if self.provider_family:
            return self.provider_family
        if self.source_id.startswith("alpaca"):
            return "alpaca"
        if self.source_id.startswith("hyperliquid"):
            return "hyperliquid"
        if self.source_id.startswith("yfinance") or "yahoo" in self.source_family:
            return "yahoo"
        return self.source_id.split(":", 1)[0]

    @property
    def venue_key(self) -> str:
        return self.venue_family or self.venue or self.source_family


class ShadowOracle:
    """Normalize evidence in and produce a deterministic advisory decision out."""

    def __init__(self, audit_sink: Callable[[dict], None] | None = None):
        self._latest: dict[str, dict[str, NormalizedObservation]] = {}
        self._marks: dict[str, dict] = {}
        self._last_reference: dict[str, float] = {}
        self._factor_anchor: dict[str, float] = {}
        self._qqq_anchor: float | None = None
        self._decisions: dict[str, dict] = {}
        self._history: deque[dict] = deque(maxlen=500)
        self._latencies: deque[float] = deque(maxlen=1000)
        self._source_age_ms: deque[float] = deque(maxlen=1000)
        self._generation = 0
        self._lock = Lock()
        self._changed = Condition(self._lock)
        self._audit_sink = audit_sink

    def ingest(self, observation: NormalizedObservation) -> dict:
        if not math.isfinite(observation.price) or observation.price <= 0:
            raise ValueError("observation price must be positive and finite")
        started = perf_counter_ns()
        source_age_ms = max(0.0, (observation.received_at - observation.event_time).total_seconds() * 1000)
        key = f"{observation.provider}|{observation.venue_key}|{observation.source_id}"
        with self._changed:
            self._latest.setdefault(observation.symbol, {})[key] = observation
            decision = self._decide(observation.symbol, observation.received_at)
            decision["decision_latency_ms"] = (perf_counter_ns() - started) / 1_000_000
            # Keep legacy field for compatibility; the clearer name is emitted too.
            decision["provider_to_decision_ms"] = source_age_ms
            decision["source_event_age_ms"] = source_age_ms
            self._latencies.append(decision["decision_latency_ms"])
            self._source_age_ms.append(source_age_ms)
            self._decisions[observation.symbol] = decision
            self._history.appendleft(decision)
            self._generation += 1
            self._changed.notify_all()
        if self._audit_sink:
            self._audit_sink(decision)
        return decision

    def update_venue_mark(self, symbol: str, price: float, event_time: datetime) -> dict:
        if not math.isfinite(price) or price <= 0:
            raise ValueError("mark price must be positive and finite")
        started = perf_counter_ns()
        audited_decision = None
        with self._changed:
            mark = {
                "price": price,
                "event_time": event_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            self._marks[symbol] = mark
            current = self._decisions.get(symbol)
            if current:
                reasons = [reason for reason in current["reasons"] if reason != "VENUE_MARK_OBSERVED"]
                reference = current["reference"]
                divergence = abs(price / reference - 1) * 10_000 if reference else None
                risk = self._risk_policy(current.get("confidence", 0), divergence, current["status"])
                audited_decision = {
                    **current,
                    "decision_id": f"{symbol}-{self._generation + 1}",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "reasons": [*reasons, "VENUE_MARK_OBSERVED"],
                    "venue_mark": mark,
                    "mark_divergence_bps": divergence,
                    "decision_latency_ms": (perf_counter_ns() - started) / 1_000_000,
                    **risk,
                }
                self._latencies.append(audited_decision["decision_latency_ms"])
                self._decisions[symbol] = audited_decision
                self._history.appendleft(audited_decision)
            self._generation += 1
            self._changed.notify_all()
        if self._audit_sink and audited_decision:
            self._audit_sink(audited_decision)
        return mark

    def _eligible_evidence(self, symbol: str, now: datetime) -> tuple[list[dict], list[NormalizedObservation]]:
        evidence: list[dict] = []
        eligible: list[NormalizedObservation] = []
        for source in self._latest.get(symbol, {}).values():
            age = max(0.0, (now - source.event_time).total_seconds())
            row = {
                "source_id": source.source_id,
                "family": source.source_family,
                "provider_family": source.provider,
                "venue_family": source.venue_key,
                "venue": source.venue,
                "price": source.price,
                "event_time": source.event_time.isoformat().replace("+00:00", "Z"),
                "age_seconds": age,
                "eligible": source.eligible,
                "fresh": age <= FRESH_SECONDS,
            }
            evidence.append(row)
            if row["eligible"] and row["fresh"]:
                eligible.append(source)
        return evidence, eligible

    @staticmethod
    def _independence(eligible: list[NormalizedObservation]) -> tuple[int, int]:
        providers = {item.provider for item in eligible}
        venues = {item.venue_key for item in eligible}
        return len(providers), len(venues)

    def _factor_estimate(self, symbol: str, now: datetime) -> tuple[float | None, float, list[str]]:
        if symbol not in QQQ_BETA:
            return None, 0.0, []
        qqq_rows = [
            source for source in self._latest.get("QQQ", {}).values()
            if source.eligible and max(0.0, (now - source.event_time).total_seconds()) <= FRESH_SECONDS
        ]
        if not qqq_rows:
            return None, 0.0, []
        qqq_price = median([row.price for row in qqq_rows])
        if self._qqq_anchor is None:
            self._qqq_anchor = qqq_price
        stock_anchor = self._factor_anchor.get(symbol) or self._last_reference.get(symbol)
        if stock_anchor is None:
            return None, 0.0, ["FACTOR_WAITING_FOR_STOCK_ANCHOR"]
        qqq_return = qqq_price / self._qqq_anchor - 1
        estimate = stock_anchor * math.exp(QQQ_BETA[symbol] * math.log1p(qqq_return))
        providers, venues = self._independence(qqq_rows)
        confidence = min(72.0, 48.0 + providers * 7.0 + venues * 4.0)
        return estimate, confidence, ["QQQ_FACTOR_FALLBACK", "ESTIMATE_NOT_DIRECT_MARKET_EVIDENCE"]

    @staticmethod
    def _risk_policy(confidence: float, divergence_bps: float | None, status: str) -> dict:
        divergence = divergence_bps or 0.0
        if divergence >= 500 or confidence < 35:
            state, lev, notional = "HALTED", 0, 0.0
        elif divergence >= 150 or confidence < 60:
            state, lev, notional = "RESTRICTED", 3, 0.25
        elif divergence >= 75 or confidence < 80 or status == "ESTIMATED":
            state, lev, notional = "GUARDED", 5 if status == "ESTIMATED" else 10, 0.5
        else:
            state, lev, notional = "NORMAL", 20, 1.0
        return {
            "risk_state": state,
            "recommended_max_leverage": lev,
            "max_notional_multiplier": notional,
            "new_exposure_allowed": state not in {"HALTED"},
            "advisory_exposure_multiplier": notional,
        }

    def _decide(self, symbol: str, now: datetime) -> dict:
        evidence, eligible = self._eligible_evidence(symbol, now)
        reference = None
        reasons: list[str] = []
        status = "INSUFFICIENT_EVIDENCE"
        confidence = 20.0
        band_bps = 250.0
        provider_count, venue_count = self._independence(eligible)

        prices = [source.price for source in eligible]
        if venue_count >= 2 and len(prices) >= 2:
            candidate = median(prices)
            dispersion_bps = (max(prices) / min(prices) - 1) * 10_000
            previous = self._last_reference.get(symbol)
            move_bps = 0.0 if previous is None else abs(candidate / previous - 1) * 10_000
            if dispersion_bps > AGREEMENT_BPS:
                reasons.append("CROSS_VENUE_DISAGREEMENT")
            elif previous is not None and move_bps > LARGE_MOVE_BPS and venue_count < 3:
                reasons.append("LARGE_MOVE_NEEDS_THREE_VENUE_FAMILIES")
            else:
                reference = candidate
                self._last_reference[symbol] = candidate
                self._factor_anchor[symbol] = candidate
                if symbol == "QQQ":
                    self._qqq_anchor = candidate
                status = "QUALIFIED"
                confidence = max(80.0, min(99.0, 97.0 - dispersion_bps / 10 - max(0, 2 - provider_count) * 6))
                band_bps = max(12.0, min(75.0, 12.0 + dispersion_bps * 0.6))
                reasons.append("INDEPENDENT_VENUES_AGREE")
                if provider_count < 2:
                    reasons.append("SINGLE_PROVIDER_CONCENTRATION")
        else:
            reasons.append("NEEDS_TWO_FRESH_ORIGINAL_VENUE_FAMILIES")

        if reference is None:
            estimate, factor_confidence, factor_reasons = self._factor_estimate(symbol, now)
            if estimate is not None:
                reference = estimate
                status = "ESTIMATED"
                confidence = factor_confidence
                band_bps = 150.0
                reasons.extend(factor_reasons)

        if any(not row["eligible"] for row in evidence):
            reasons.append("RESEARCH_FEED_VISIBLE_NOT_COUNTED")
        mark = self._marks.get(symbol)
        divergence_bps = abs(mark["price"] / reference - 1) * 10_000 if mark and reference else None
        risk = self._risk_policy(confidence, divergence_bps, status)

        return {
            "decision_id": f"{symbol}-{self._generation + 1}",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "symbol": symbol,
            "status": status,
            "reference": reference,
            "last_valid": self._last_reference.get(symbol),
            "confidence": round(confidence, 1),
            "band_bps": round(band_bps, 1),
            "band_lower": reference * (1 - band_bps / 10_000) if reference else None,
            "band_upper": reference * (1 + band_bps / 10_000) if reference else None,
            "independent_source_families": venue_count,
            "independent_provider_families": provider_count,
            "reasons": list(dict.fromkeys(reasons)),
            "evidence": sorted(evidence, key=lambda row: (row["provider_family"], row["venue_family"])),
            "venue_mark": mark,
            "mark_divergence_bps": divergence_bps,
            "model_version": "marketbridge-shadow-v0.2",
            **risk,
        }

    def snapshot(self) -> dict:
        with self._lock:
            ordered = sorted(self._latencies)
            source_ages = sorted(self._source_age_ms)
            p50 = median(ordered) if ordered else None
            p95 = ordered[round((len(ordered) - 1) * 0.95)] if ordered else None
            p99 = ordered[round((len(ordered) - 1) * 0.99)] if ordered else None
            age_p95 = source_ages[round((len(source_ages) - 1) * 0.95)] if source_ages else None
            return {
                "generation": self._generation,
                "decisions": [self._decisions[symbol] for symbol in TRACKED_SYMBOLS if symbol in self._decisions],
                "decision_log": list(self._history)[:60],
                "latency": {
                    "samples": len(ordered),
                    "p50_ms": p50,
                    "p95_ms": p95,
                    "p99_ms": p99,
                    "last_ms": self._history[0]["decision_latency_ms"] if self._history else None,
                    "source_event_age_p95_ms": age_p95,
                    "ui_delivery_target_ms": 250,
                },
            }

    def wait_for_generation(self, generation: int, timeout: float = 10.0) -> dict:
        """Block without polling until a newer decision exists or timeout expires."""
        with self._changed:
            if self._generation == generation:
                self._changed.wait(timeout=timeout)
        return self.snapshot()


class LivePipeline:
    """Own provider adapters, audit persistence and the shadow-oracle lifecycle."""

    def __init__(self, audit_path: Path):
        self._stop = Event()
        self._threads: list[Thread] = []
        self._audit_queue: SimpleQueue[dict | None] = SimpleQueue()
        self._audit_path = audit_path
        self.oracle = ShadowOracle(self._audit_queue.put)
        self._provider_status = {
            "yahoo": {"status": "STARTING", "kind": "RESEARCH", "detail": "Background bootstrap"},
            "alpaca": {"status": "DISABLED", "kind": "DIRECT_MARKET", "detail": "Set ALPACA_API_KEY and ALPACA_SECRET_KEY"},
            "hyperliquid": {"status": "DISABLED", "kind": "VENUE_MARK", "detail": "Set HYPERLIQUID_COIN_MAP to observe venue marks"},
            "mochatrade": {"status": "WAITING", "kind": "VENUE_MARK", "detail": "No mark received"},
        }
        self._yahoo: dict | None = None
        self._last_yahoo_event: dict[str, str] = {}
        self._started = False
        self._state_lock = Lock()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._stop.clear()
        self._threads = [
            Thread(target=self._audit_loop, name="marketbridge-audit", daemon=True),
            Thread(target=self._yahoo_loop, name="marketbridge-yahoo", daemon=True),
        ]
        if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
            self._provider_status["alpaca"] = {"status": "CONNECTING", "kind": "DIRECT_MARKET", "detail": "Alpaca WebSocket"}
            self._threads.append(Thread(target=self._alpaca_loop, name="marketbridge-alpaca", daemon=True))
        if os.environ.get("HYPERLIQUID_COIN_MAP"):
            self._provider_status["hyperliquid"] = {"status": "CONNECTING", "kind": "VENUE_MARK", "detail": "Hyperliquid WebSocket"}
            self._threads.append(Thread(target=self._hyperliquid_loop, name="marketbridge-hyperliquid", daemon=True))
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._audit_queue.put(None)
        for thread in self._threads:
            thread.join(timeout=2)
        self._started = False

    def _audit_loop(self) -> None:
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as output:
            while True:
                item = self._audit_queue.get()
                if item is None:
                    return
                output.write(json.dumps(item, allow_nan=False, separators=(",", ":")) + "\n")
                output.flush()

    def _yahoo_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh_yahoo()
            except Exception as exc:
                with self._state_lock:
                    self._provider_status["yahoo"] = {"status": "UNAVAILABLE", "kind": "RESEARCH", "detail": str(exc)[:160]}
            self._stop.wait(15)

    def refresh_yahoo(self) -> dict:
        snapshot = get_live_snapshot(force=True)
        with self._state_lock:
            self._yahoo = snapshot
            self._provider_status["yahoo"] = {
                "status": snapshot["provider_status"], "kind": "RESEARCH", "detail": snapshot["fetched_at"]
            }
        received_at = datetime.now(timezone.utc)
        for row in snapshot["observations"]:
            if self._last_yahoo_event.get(row["symbol"]) == row["event_time"]:
                continue
            self._last_yahoo_event[row["symbol"]] = row["event_time"]
            self.oracle.ingest(NormalizedObservation(
                symbol=row["symbol"], price=row["observed_price"], event_time=_utc(row["event_time"]),
                received_at=received_at, source_id="yfinance", source_family="yahoo-research-feed",
                venue=row["exchange"], eligible=False, provider_family="yahoo", venue_family=row["exchange"],
            ))
        return self.snapshot()

    def _alpaca_loop(self) -> None:
        from websockets.sync.client import connect

        feed = os.environ.get("ALPACA_FEED", "iex")
        url = f"wss://stream.data.alpaca.markets/v2/{feed}"
        backoff = 1
        while not self._stop.is_set():
            try:
                with connect(url, open_timeout=8, close_timeout=2) as socket:
                    socket.send(json.dumps({"action": "auth", "key": os.environ["ALPACA_API_KEY"], "secret": os.environ["ALPACA_SECRET_KEY"]}))
                    socket.send(json.dumps({"action": "subscribe", "trades": list(TRACKED_SYMBOLS)}))
                    with self._state_lock:
                        self._provider_status["alpaca"] = {"status": "AVAILABLE", "kind": "DIRECT_MARKET", "detail": f"{feed} WebSocket"}
                    backoff = 1
                    for message in socket:
                        if self._stop.is_set():
                            return
                        received_at = datetime.now(timezone.utc)
                        for event in json.loads(message):
                            if event.get("T") != "t" or event.get("S") not in TRACKED_SYMBOLS:
                                continue
                            venue = str(event.get("x") or "UNKNOWN")
                            self.oracle.ingest(NormalizedObservation(
                                symbol=event["S"], price=float(event["p"]), event_time=_utc(event["t"]),
                                received_at=received_at, source_id=f"alpaca-{feed}", source_family=f"equity-venue:{venue}",
                                venue=venue, eligible=venue != "UNKNOWN", provider_family="alpaca", venue_family=venue,
                            ))
            except Exception as exc:
                with self._state_lock:
                    self._provider_status["alpaca"] = {"status": "RECONNECTING", "kind": "DIRECT_MARKET", "detail": str(exc)[:160]}
                self._stop.wait(backoff)
                backoff = min(15, backoff * 2)

    def _hyperliquid_loop(self) -> None:
        """Observe configured Hyperliquid asset contexts as venue marks.

        HYPERLIQUID_COIN_MAP is a JSON object such as {"NVDA":"xyz:NVDA"}.  We
        deliberately do not hard-code coin names because deployed HIP-3 market
        identifiers are venue configuration, not stable API constants.
        """
        from websockets.sync.client import connect

        coin_map = json.loads(os.environ["HYPERLIQUID_COIN_MAP"])
        reverse = {coin: symbol for symbol, coin in coin_map.items() if symbol in TRACKED_SYMBOLS}
        backoff = 1
        while not self._stop.is_set():
            try:
                with connect("wss://api.hyperliquid.xyz/ws", open_timeout=8, close_timeout=2) as socket:
                    for coin in reverse:
                        socket.send(json.dumps({"method": "subscribe", "subscription": {"type": "activeAssetCtx", "coin": coin}}))
                    with self._state_lock:
                        self._provider_status["hyperliquid"] = {"status": "AVAILABLE", "kind": "VENUE_MARK", "detail": f"{len(reverse)} configured assets"}
                    backoff = 1
                    for message in socket:
                        if self._stop.is_set():
                            return
                        payload = json.loads(message)
                        if payload.get("channel") != "activeAssetCtx":
                            continue
                        data = payload.get("data") or {}
                        coin = data.get("coin")
                        ctx = data.get("ctx") or {}
                        symbol = reverse.get(coin)
                        mark = ctx.get("markPx")
                        if symbol and mark:
                            self.ingest_mochatrade(symbol, float(mark), datetime.now(timezone.utc), source="hyperliquid")
            except Exception as exc:
                with self._state_lock:
                    self._provider_status["hyperliquid"] = {"status": "RECONNECTING", "kind": "VENUE_MARK", "detail": str(exc)[:160]}
                self._stop.wait(backoff)
                backoff = min(15, backoff * 2)

    def ingest_mochatrade(self, symbol: str, mark_price: float, event_time: datetime, source: str = "mochatrade") -> dict:
        mark = self.oracle.update_venue_mark(symbol, mark_price, event_time)
        with self._state_lock:
            self._provider_status[source] = {"status": "AVAILABLE", "kind": "VENUE_MARK", "detail": mark["event_time"]}
        return mark

    def wait_for_generation(self, generation: int, timeout: float = 10.0) -> dict:
        return {"data_mode": "SHADOW_ORACLE", "advisory_only": True, "started": self._started, **self.oracle.wait_for_generation(generation, timeout), **self._provider_payload()}

    def _provider_payload(self) -> dict:
        with self._state_lock:
            providers = [{"id": key, **value} for key, value in self._provider_status.items()]
            yahoo = self._yahoo
        return {"providers": providers, "yahoo": yahoo}

    def snapshot(self) -> dict:
        return {
            "data_mode": "SHADOW_ORACLE",
            "advisory_only": True,
            "started": self._started,
            **self._provider_payload(),
            **self.oracle.snapshot(),
        }


def test_observation(symbol: str, price: float, family: str, venue: str, now: datetime) -> NormalizedObservation:
    """Small public constructor used by tests and local integration probes."""
    return NormalizedObservation(symbol, price, now, now, family, family, venue, True)
