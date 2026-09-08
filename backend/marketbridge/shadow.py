"""Low-latency shadow-oracle module with swappable market-data adapters."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from queue import SimpleQueue
from statistics import median
from threading import Event, Lock, Thread
from time import perf_counter_ns
from typing import Callable

from .live import get_live_snapshot


TRACKED_SYMBOLS = ("NVDA", "TSLA", "QQQ")
FRESH_SECONDS = 10
AGREEMENT_BPS = 75
LARGE_MOVE_BPS = 500


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
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


class ShadowOracle:
    """Deep module: normalize evidence in, deterministic advisory decision out."""

    def __init__(self, audit_sink: Callable[[dict], None] | None = None):
        self._latest: dict[str, dict[str, NormalizedObservation]] = {}
        self._marks: dict[str, dict] = {}
        self._last_reference: dict[str, float] = {}
        self._decisions: dict[str, dict] = {}
        self._history: deque[dict] = deque(maxlen=250)
        self._latencies: deque[float] = deque(maxlen=500)
        self._generation = 0
        self._lock = Lock()
        self._audit_sink = audit_sink

    def ingest(self, observation: NormalizedObservation) -> dict:
        started = perf_counter_ns()
        with self._lock:
            self._latest.setdefault(observation.symbol, {})[observation.source_family] = observation
            decision = self._decide(observation.symbol, observation.received_at)
            decision["decision_latency_ms"] = (perf_counter_ns() - started) / 1_000_000
            decision["provider_to_decision_ms"] = max(
                0.0, (observation.received_at - observation.event_time).total_seconds() * 1000
            )
            self._latencies.append(decision["decision_latency_ms"])
            self._decisions[observation.symbol] = decision
            self._history.appendleft(decision)
            self._generation += 1
        if self._audit_sink:
            self._audit_sink(decision)
        return decision

    def update_venue_mark(self, symbol: str, price: float, event_time: datetime) -> dict:
        started = perf_counter_ns()
        audited_decision = None
        with self._lock:
            mark = {
                "price": price,
                "event_time": event_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            self._marks[symbol] = mark
            current = self._decisions.get(symbol)
            if current:
                reasons = [reason for reason in current["reasons"] if reason != "VENUE_MARK_OBSERVED"]
                reference = current["reference"]
                audited_decision = {
                    **current,
                    "decision_id": f"{symbol}-{self._generation + 1}",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "reasons": [*reasons, "VENUE_MARK_OBSERVED"],
                    "venue_mark": mark,
                    "mark_divergence_bps": (
                        abs(price / reference - 1) * 10_000 if reference is not None else None
                    ),
                    "decision_latency_ms": (perf_counter_ns() - started) / 1_000_000,
                }
                self._latencies.append(audited_decision["decision_latency_ms"])
                self._decisions[symbol] = audited_decision
                self._history.appendleft(audited_decision)
            self._generation += 1
        if self._audit_sink and audited_decision:
            self._audit_sink(audited_decision)
        return mark

    def _decide(self, symbol: str, now: datetime) -> dict:
        sources = list(self._latest.get(symbol, {}).values())
        evidence = []
        eligible = []
        for source in sources:
            age = max(0.0, (now - source.event_time).total_seconds())
            row = {
                "source_id": source.source_id,
                "family": source.source_family,
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
        prices = [source.price for source in eligible]
        reference = None
        reasons = []
        quality = "INSUFFICIENT_EVIDENCE"
        if len(prices) < 2:
            reasons.append("NEEDS_TWO_FRESH_ORIGINAL_VENUE_FAMILIES")
        else:
            candidate = median(prices)
            dispersion_bps = (max(prices) / min(prices) - 1) * 10_000
            previous = self._last_reference.get(symbol)
            move_bps = 0.0 if previous is None else abs(candidate / previous - 1) * 10_000
            if dispersion_bps > AGREEMENT_BPS:
                reasons.append("CROSS_VENUE_DISAGREEMENT")
            elif previous is not None and move_bps > LARGE_MOVE_BPS and len(prices) < 3:
                reasons.append("LARGE_MOVE_NEEDS_THREE_VENUE_FAMILIES")
            else:
                reference = candidate
                self._last_reference[symbol] = candidate
                quality = "QUALIFIED"
                reasons.append("INDEPENDENT_VENUES_AGREE")
        if any(not row["eligible"] for row in evidence):
            reasons.append("RESEARCH_FEED_VISIBLE_NOT_COUNTED")
        mark = self._marks.get(symbol)
        divergence_bps = None
        if mark and reference:
            divergence_bps = abs(mark["price"] / reference - 1) * 10_000
        return {
            "decision_id": f"{symbol}-{self._generation + 1}",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "symbol": symbol,
            "status": quality,
            "reference": reference,
            "last_valid": self._last_reference.get(symbol),
            "independent_source_families": len(eligible),
            "new_exposure_allowed": quality == "QUALIFIED",
            "advisory_exposure_multiplier": 1.0 if quality == "QUALIFIED" else 0.0,
            "reasons": reasons,
            "evidence": sorted(evidence, key=lambda row: row["family"]),
            "venue_mark": mark,
            "mark_divergence_bps": divergence_bps,
        }

    def snapshot(self) -> dict:
        with self._lock:
            ordered = sorted(self._latencies)
            p50 = median(ordered) if ordered else None
            p95 = ordered[round((len(ordered) - 1) * 0.95)] if ordered else None
            return {
                "generation": self._generation,
                "decisions": [self._decisions[symbol] for symbol in TRACKED_SYMBOLS if symbol in self._decisions],
                "decision_log": list(self._history)[:40],
                "latency": {
                    "samples": len(ordered),
                    "p50_ms": p50,
                    "p95_ms": p95,
                    "last_ms": self._history[0]["decision_latency_ms"] if self._history else None,
                    "ui_delivery_target_ms": 250,
                },
            }


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
            "alpaca": {"status": "DISABLED", "kind": "VENUE_LABELED", "detail": "Set ALPACA_API_KEY and ALPACA_SECRET_KEY"},
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
            self._provider_status["alpaca"] = {"status": "CONNECTING", "kind": "VENUE_LABELED", "detail": "Alpaca WebSocket"}
            self._threads.append(Thread(target=self._alpaca_loop, name="marketbridge-alpaca", daemon=True))
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
                venue=row["exchange"], eligible=False,
            ))
        return self.snapshot()

    def _alpaca_loop(self) -> None:
        from websockets.sync.client import connect

        feed = os.environ.get("ALPACA_FEED", "iex")
        url = f"wss://stream.data.alpaca.markets/v2/{feed}"
        while not self._stop.is_set():
            try:
                with connect(url, open_timeout=8, close_timeout=2) as socket:
                    socket.send(json.dumps({"action": "auth", "key": os.environ["ALPACA_API_KEY"], "secret": os.environ["ALPACA_SECRET_KEY"]}))
                    socket.send(json.dumps({"action": "subscribe", "trades": list(TRACKED_SYMBOLS)}))
                    with self._state_lock:
                        self._provider_status["alpaca"] = {"status": "AVAILABLE", "kind": "VENUE_LABELED", "detail": f"{feed} WebSocket"}
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
                                venue=venue, eligible=venue != "UNKNOWN",
                            ))
            except Exception as exc:
                with self._state_lock:
                    self._provider_status["alpaca"] = {"status": "RECONNECTING", "kind": "VENUE_LABELED", "detail": str(exc)[:160]}
                self._stop.wait(2)

    def ingest_mochatrade(self, symbol: str, mark_price: float, event_time: datetime) -> dict:
        mark = self.oracle.update_venue_mark(symbol, mark_price, event_time)
        with self._state_lock:
            self._provider_status["mochatrade"] = {"status": "AVAILABLE", "kind": "VENUE_MARK", "detail": mark["event_time"]}
        return mark

    def snapshot(self) -> dict:
        with self._state_lock:
            providers = [{"id": key, **value} for key, value in self._provider_status.items()]
            yahoo = self._yahoo
        return {
            "data_mode": "SHADOW_ORACLE",
            "advisory_only": True,
            "started": self._started,
            "providers": providers,
            "yahoo": yahoo,
            **self.oracle.snapshot(),
        }


def test_observation(symbol: str, price: float, family: str, venue: str, now: datetime) -> NormalizedObservation:
    """Small public constructor used by tests and local integration probes."""
    return NormalizedObservation(symbol, price, now, now, family, family, venue, True)
