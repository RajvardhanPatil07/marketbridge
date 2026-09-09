"""Low-latency shadow-oracle pipeline with deterministic safety + learned estimates.

Direct independent market evidence always has priority. A learned fair-value model
may provide a lower-trust ESTIMATED reference when direct evidence is insufficient.
Anomaly probability is advisory and can only tighten risk when the loaded model is
explicitly configured as non-synthetic. The venue mark never validates itself.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
from queue import SimpleQueue
from statistics import median
from threading import Condition, Event, Lock, Thread
from time import perf_counter_ns
from typing import Callable

from .evidence_store import EvidenceStore
from .live import get_live_snapshot
from .ml import MarketBridgeAI
from .metrics import observe_decision


EQUITY_SYMBOLS = ("NVDA", "TSLA", "AAPL", "MSFT", "AMD")
FACTOR_SYMBOLS = ("QQQ", "SPY", "SOXX")
TRACKED_SYMBOLS = (*EQUITY_SYMBOLS, *FACTOR_SYMBOLS)
FRESH_SECONDS = 10
VENUE_MARK_FRESH_SECONDS = 30
AGREEMENT_BPS = 75
LARGE_MOVE_BPS = 500
ALPACA_SUPPORTED_FEEDS = frozenset({"iex", "sip", "delayed_sip", "boats", "overnight", "otc"})
ALPACA_MULTI_VENUE_FEEDS = frozenset({"sip"})
ALPACA_DEFAULT_REJECT_CONDITIONS = frozenset({"I"})
logger = logging.getLogger(__name__)


class AlpacaStreamError(RuntimeError):
    """Safe, classified stream failure that never contains credentials."""

    def __init__(self, status: str, detail: str, *, code: object = "unknown", permanent: bool = False):
        super().__init__(detail[:160])
        self.status = status
        self.detail = detail[:160]
        self.code = str(code)
        self.permanent = permanent


def _classify_alpaca_error(event: dict, *, authenticated: bool) -> AlpacaStreamError:
    detail = str(event.get("msg") or "Alpaca stream error")[:160]
    normalized = detail.lower()
    code = event.get("code", "unknown")
    if "insufficient subscription" in normalized or "not subscribed" in normalized:
        return AlpacaStreamError("ENTITLEMENT_ERROR", detail, code=code, permanent=True)
    if not authenticated or str(code) in {"401", "402", "403"}:
        return AlpacaStreamError("AUTH_ERROR", detail, code=code, permanent=True)
    return AlpacaStreamError("STREAM_ERROR", detail, code=code)


def probe_alpaca_subscription(connect_fn=None) -> dict:
    """Perform an auth + subscription handshake and return only safe diagnostics."""
    feed = os.environ.get("ALPACA_FEED", "iex").strip().lower()
    api_key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    base = {"feed": feed, "authenticated": False, "subscribed": False, "runtime_eligible": False}
    if not api_key or not secret:
        return {
            "status": "CONFIG_ERROR", **base, "permanent_error": True,
            "error_code": "MISSING_CREDENTIALS", "detail": "Alpaca credential pair is not configured",
        }
    if feed not in ALPACA_SUPPORTED_FEEDS:
        return {
            "status": "CONFIG_ERROR", **base, "permanent_error": True,
            "error_code": "UNSUPPORTED_FEED", "detail": "ALPACA_FEED is unsupported",
        }
    if connect_fn is None:
        from websockets.sync.client import connect as connect_fn
    authenticated = False
    try:
        url = f"wss://stream.data.alpaca.markets/v2/{feed}"
        with connect_fn(url, open_timeout=8, close_timeout=2) as socket:
            socket.send(json.dumps({"action": "auth", "key": api_key, "secret": secret}))
            for message in socket:
                events = json.loads(message)
                if not isinstance(events, list):
                    raise AlpacaStreamError("STREAM_ERROR", "Alpaca returned a non-list WebSocket payload")
                for event in events:
                    event_type = event.get("T")
                    if event_type == "error":
                        raise _classify_alpaca_error(event, authenticated=authenticated)
                    if event_type == "success" and event.get("msg") == "authenticated":
                        authenticated = True
                        socket.send(json.dumps({
                            "action": "subscribe", "trades": list(TRACKED_SYMBOLS),
                            "quotes": list(TRACKED_SYMBOLS),
                        }))
                    if event_type == "subscription":
                        subscribed = set(event.get("trades") or [])
                        if not authenticated or not set(TRACKED_SYMBOLS).issubset(subscribed):
                            raise AlpacaStreamError(
                                "SUBSCRIPTION_ERROR", "Alpaca subscription acknowledgment is incomplete",
                                code="INCOMPLETE_ACK", permanent=True,
                            )
                        capable = feed in ALPACA_MULTI_VENUE_FEEDS
                        return {
                            "status": "AVAILABLE" if capable else "LIMITED", "feed": feed,
                            "authenticated": True, "subscribed": True, "runtime_eligible": capable,
                            "permanent_error": False, "error_code": None,
                            "detail": (
                                f"{feed} authenticated multi-venue stream" if capable
                                else f"{feed} authenticated; single/non-qualifying venue feed"
                            ),
                        }
        raise AlpacaStreamError("STREAM_ERROR", "Alpaca WebSocket closed before subscription")
    except AlpacaStreamError as exc:
        return {
            "status": exc.status, "feed": feed, "authenticated": authenticated,
            "subscribed": False, "runtime_eligible": False, "permanent_error": exc.permanent,
            "error_code": exc.code, "detail": exc.detail,
        }
    except Exception as exc:
        return {
            "status": "CONNECTION_ERROR", "feed": feed, "authenticated": authenticated,
            "subscribed": False, "runtime_eligible": False, "permanent_error": False,
            "error_code": type(exc).__name__, "detail": "Unable to complete Alpaca runtime handshake",
        }

# Safety fallback if no learned model bundle is available. These are explicitly
# static prototype coefficients and remain lower trust than direct consensus.
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


def _bps(price: float, anchor: float) -> float:
    if anchor <= 0:
        return 0.0
    return math.log(price / anchor) * 10_000


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _positive_float_or_default(name: str, default: float) -> float:
    try:
        return _positive_float_env(name, default)
    except ValueError:
        return default


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    """Normalize evidence and produce an advisory reference/risk decision."""

    def __init__(
        self,
        audit_sink: Callable[[dict], None] | None = None,
        ai: MarketBridgeAI | None = None,
    ):
        self._latest: dict[str, dict[str, NormalizedObservation]] = {}
        self._marks: dict[str, dict] = {}
        self._last_reference: dict[str, float] = {}
        self._anchor_time: dict[str, datetime] = {}
        self._factor_reference: dict[str, float] = {}
        self._stock_factor_anchor: dict[str, dict[str, float]] = {}
        self._decisions: dict[str, dict] = {}
        self._history: deque[dict] = deque(maxlen=500)
        self._latencies: deque[float] = deque(maxlen=1000)
        self._source_age_ms: deque[float] = deque(maxlen=1000)
        self._passport_heads: dict[str, str] = {}
        self._passport_sequences: dict[str, int] = {}
        self._generation = 0
        self._lock = Lock()
        self._changed = Condition(self._lock)
        self._audit_sink = audit_sink
        self.ai = ai or MarketBridgeAI.from_environment()

    def ai_status(self) -> dict:
        status = self.ai.status()
        status["risk_signal_enforced"] = bool(
            status.get("enabled") and not str(status.get("data_mode") or "").startswith("SYNTHETIC")
        )
        return status

    def ingest(self, observation: NormalizedObservation) -> dict:
        if observation.symbol not in TRACKED_SYMBOLS:
            raise ValueError(f"unsupported symbol: {observation.symbol}")
        if not math.isfinite(observation.price) or observation.price <= 0:
            raise ValueError("observation price must be positive and finite")
        started = perf_counter_ns()
        source_age_ms = max(0.0, (observation.received_at - observation.event_time).total_seconds() * 1000)
        key = f"{observation.provider}|{observation.venue_key}|{observation.source_id}"
        with self._changed:
            self._latest.setdefault(observation.symbol, {})[key] = observation
            decision = self._decide(observation.symbol, observation.received_at)
            decision["decision_latency_ms"] = (perf_counter_ns() - started) / 1_000_000
            decision["provider_to_decision_ms"] = source_age_ms
            decision["source_event_age_ms"] = source_age_ms
            decision = self._seal_decision(decision)
            self._latencies.append(decision["decision_latency_ms"])
            self._source_age_ms.append(source_age_ms)
            self._decisions[observation.symbol] = decision
            if observation.symbol in EQUITY_SYMBOLS:
                self._history.appendleft(decision)
            self._generation += 1
            self._changed.notify_all()
        if self._audit_sink and observation.symbol in EQUITY_SYMBOLS:
            self._audit_sink(decision)
        return decision

    def update_venue_mark(self, symbol: str, price: float, event_time: datetime) -> dict:
        if symbol not in EQUITY_SYMBOLS:
            raise ValueError(f"unsupported venue-mark symbol: {symbol}")
        if not math.isfinite(price) or price <= 0:
            raise ValueError("mark price must be positive and finite")
        started = perf_counter_ns()
        audited_decision = None
        with self._changed:
            mark = {
                "price": price,
                "event_time": _iso(event_time),
            }
            self._marks[symbol] = mark
            public_mark = self._mark_view(mark, event_time)
            current = self._decisions.get(symbol)
            if current:
                reasons = [reason for reason in current["reasons"] if reason != "VENUE_MARK_OBSERVED"]
                reference = current["reference"]
                divergence = abs(price / reference - 1) * 10_000 if reference else None
                anomaly_probability, anomaly_factors = self._anomaly_score(
                    current.get("evidence", []), current["status"], divergence
                )
                ai_payload = dict(current.get("ai") or self._empty_ai_payload())
                ai_payload["anomaly_probability"] = anomaly_probability
                ai_payload["anomaly_factors"] = anomaly_factors
                enforce_ai = self._ai_risk_enforced(ai_payload)
                risk = self._risk_policy(
                    current.get("confidence", 0),
                    divergence,
                    current["status"],
                    anomaly_probability,
                    enforce_ai,
                )
                if anomaly_probability is not None and anomaly_probability >= 0.90:
                    reasons.append("AI_ANOMALY_SIGNAL_HIGH")
                audited_decision = {
                    **current,
                    "decision_id": f"{symbol}-{self._generation + 1}",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "reasons": list(dict.fromkeys([*reasons, "VENUE_MARK_OBSERVED"])),
                    "venue_mark": public_mark,
                    "mark_divergence_bps": divergence,
                    "decision_latency_ms": (perf_counter_ns() - started) / 1_000_000,
                    "ai": ai_payload,
                    **risk,
                }
                audited_decision = self._seal_decision(audited_decision)
                self._latencies.append(audited_decision["decision_latency_ms"])
                self._decisions[symbol] = audited_decision
                self._history.appendleft(audited_decision)
            self._generation += 1
            self._changed.notify_all()
        if self._audit_sink and audited_decision:
            self._audit_sink(audited_decision)
        return public_mark

    @staticmethod
    def _mark_view(mark: dict | None, now: datetime) -> dict | None:
        if mark is None:
            return None
        age_seconds = max(0.0, (now - _utc(mark["event_time"])).total_seconds())
        return {
            **mark,
            "age_seconds": round(age_seconds, 3),
            "fresh": age_seconds
            <= _positive_float_or_default("MARKETBRIDGE_VENUE_MARK_TTL_SECONDS", VENUE_MARK_FRESH_SECONDS),
        }

    def _decision_view(self, decision: dict, now: datetime) -> dict:
        output = dict(decision)
        evidence = []
        for item in decision.get("evidence", []):
            age_seconds = max(0.0, (now - _utc(item["event_time"])).total_seconds())
            evidence.append({**item, "age_seconds": age_seconds, "fresh": age_seconds <= FRESH_SECONDS})
        output["evidence"] = evidence
        fresh_eligible = [item for item in evidence if item["eligible"] and item["fresh"]]
        provider_count = len({item["provider_family"] for item in fresh_eligible})
        venue_count = len({item["venue_family"] for item in fresh_eligible})
        output["independent_provider_families"] = provider_count
        output["independent_source_families"] = venue_count

        status = decision["status"]
        reference = decision["reference"]
        confidence = decision.get("confidence", 0)
        band_bps = decision.get("band_bps", 250.0)
        mark = self._mark_view(self._marks.get(decision["symbol"]), now)
        output["venue_mark"] = mark
        reasons = [
            reason
            for reason in decision["reasons"]
            if reason not in {"VENUE_MARK_OBSERVED", "VENUE_MARK_STALE", "AI_ANOMALY_SIGNAL_HIGH"}
        ]
        if status == "QUALIFIED" and venue_count < 2:
            status = "INSUFFICIENT_EVIDENCE"
            reference = None
            confidence = 20.0
            band_bps = 250.0
            reasons = [
                reason
                for reason in reasons
                if reason not in {"INDEPENDENT_VENUES_AGREE", "SINGLE_PROVIDER_CONCENTRATION"}
            ]
            reasons.extend(["DIRECT_EVIDENCE_EXPIRED", "NEEDS_TWO_FRESH_ORIGINAL_VENUE_FAMILIES"])
        divergence = None
        if mark and mark["fresh"]:
            reasons.append("VENUE_MARK_OBSERVED")
            if reference:
                divergence = abs(mark["price"] / reference - 1) * 10_000
        elif mark:
            reasons.append("VENUE_MARK_STALE")
        ai_payload = dict(decision.get("ai") or self._empty_ai_payload())
        anomaly_probability, anomaly_factors = self._anomaly_score(evidence, status, divergence)
        ai_payload["anomaly_probability"] = anomaly_probability
        ai_payload["anomaly_factors"] = anomaly_factors
        if anomaly_probability is not None and anomaly_probability >= 0.90:
            reasons.append("AI_ANOMALY_SIGNAL_HIGH")
        output.update(
            {
                "status": status,
                "reference": reference,
                "confidence": confidence,
                "band_bps": band_bps,
                "band_lower": reference * (1 - band_bps / 10_000) if reference else None,
                "band_upper": reference * (1 + band_bps / 10_000) if reference else None,
                "reasons": list(dict.fromkeys(reasons)),
                "mark_divergence_bps": divergence,
                "ai": ai_payload,
                **self._risk_policy(
                    confidence,
                    divergence,
                    status,
                    anomaly_probability,
                    self._ai_risk_enforced(ai_payload),
                ),
            }
        )
        return output

    @staticmethod
    def _passport_claims(decision: dict) -> dict:
        evidence = []
        for item in decision.get("evidence", []):
            normalized = {
                "source_id": item["source_id"],
                "provider_family": item["provider_family"],
                "venue_family": item["venue_family"],
                "venue": item["venue"],
                "price": item["price"],
                "event_time": item["event_time"],
                "eligible": item["eligible"],
                "fresh_at_decision": item["fresh"],
            }
            evidence.append({**normalized, "evidence_hash": _canonical_hash(normalized)})
        ai = decision.get("ai") or {}
        mark = decision.get("venue_mark")
        return {
            "decision_id": decision["decision_id"],
            "issued_at": decision["timestamp"],
            "symbol": decision["symbol"],
            "status": decision["status"],
            "reference": decision["reference"],
            "confidence": decision["confidence"],
            "band_bps": decision["band_bps"],
            "independent_provider_families": decision["independent_provider_families"],
            "independent_source_families": decision["independent_source_families"],
            "risk_state": decision["risk_state"],
            "recommended_max_leverage": decision["recommended_max_leverage"],
            "max_notional_multiplier": decision["max_notional_multiplier"],
            "new_exposure_allowed": decision["new_exposure_allowed"],
            "mark_divergence_bps": decision.get("mark_divergence_bps"),
            "venue_mark": (
                {"price": mark["price"], "event_time": mark["event_time"]}
                if mark
                else None
            ),
            "reasons": decision["reasons"],
            "evidence": evidence,
            "policy_version": decision["model_version"],
            "ai_model_version": ai.get("model_version"),
            "ai_data_mode": ai.get("data_mode"),
            "ai_risk_signal_enforced": bool(ai.get("risk_signal_enforced")),
        }

    def _seal_decision(self, decision: dict) -> dict:
        symbol = decision["symbol"]
        sequence = self._passport_sequences.get(symbol, 0) + 1
        previous_hash = self._passport_heads.get(symbol)
        claims = self._passport_claims(decision)
        content_hash = _canonical_hash(claims)
        chain_hash = _canonical_hash({
            "scope": f"symbol:{symbol}",
            "sequence": sequence,
            "previous_hash": previous_hash,
            "content_hash": content_hash,
        })
        passport = {
            "version": "marketbridge-passport-v1",
            "algorithm": "sha256",
            "scope": f"symbol:{symbol}",
            "sequence": sequence,
            "previous_hash": previous_hash,
            "content_hash": content_hash,
            "chain_hash": chain_hash,
            "claims": claims,
        }
        self._passport_sequences[symbol] = sequence
        self._passport_heads[symbol] = chain_hash
        return {**decision, "passport": passport}

    @staticmethod
    def verify_passport(passport: dict) -> bool:
        try:
            content_hash = _canonical_hash(passport["claims"])
            chain_hash = _canonical_hash({
                "scope": passport["scope"],
                "sequence": passport["sequence"],
                "previous_hash": passport["previous_hash"],
                "content_hash": content_hash,
            })
        except (KeyError, TypeError, ValueError):
            return False
        return content_hash == passport.get("content_hash") and chain_hash == passport.get("chain_hash")

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

    @staticmethod
    def _dispersion_bps(eligible: list[NormalizedObservation]) -> float:
        prices = [source.price for source in eligible]
        if len(prices) < 2:
            return 0.0
        return (max(prices) / min(prices) - 1) * 10_000

    def _fresh_factor_price(self, factor: str, now: datetime) -> float | None:
        rows = [
            source
            for source in self._latest.get(factor, {}).values()
            if source.eligible and max(0.0, (now - source.event_time).total_seconds()) <= FRESH_SECONDS
        ]
        return median([row.price for row in rows]) if rows else None

    def _factor_features(
        self,
        symbol: str,
        now: datetime,
        stock_eligible: list[NormalizedObservation],
    ) -> dict[str, float] | None:
        stock_anchor = self._last_reference.get(symbol)
        if stock_anchor is None:
            return None
        anchors = self._stock_factor_anchor.setdefault(symbol, {})
        factor_returns: dict[str, float] = {}
        at_least_one_factor = False
        for factor in FACTOR_SYMBOLS:
            current = self._fresh_factor_price(factor, now)
            if current is None:
                factor_returns[factor] = 0.0
                continue
            at_least_one_factor = True
            if factor not in anchors:
                anchors[factor] = current
            factor_returns[factor] = _bps(current, anchors[factor])
        if not at_least_one_factor:
            return None

        stock_prices = [row.price for row in stock_eligible]
        single_source_return = _bps(median(stock_prices), stock_anchor) if stock_prices else 0.0
        ages = [max(0.0, (now - row.event_time).total_seconds()) * 1000 for row in stock_eligible]
        source_age_ms = median(ages) if ages else float(FRESH_SECONDS * 1000)
        providers, venues = self._independence(stock_eligible)
        anchor_time = self._anchor_time.get(symbol, now)
        minutes_since_anchor = max(0.0, (now - anchor_time).total_seconds() / 60.0)
        return {
            "qqq_return_bps": factor_returns.get("QQQ", 0.0),
            "spy_return_bps": factor_returns.get("SPY", 0.0),
            "soxx_return_bps": factor_returns.get("SOXX", 0.0),
            "single_source_return_bps": single_source_return,
            "minutes_since_anchor": minutes_since_anchor,
            "source_age_ms": source_age_ms,
            "provider_count": float(providers),
            "venue_count": float(venues),
        }

    def _learned_estimate(
        self,
        symbol: str,
        now: datetime,
        stock_eligible: list[NormalizedObservation],
    ) -> tuple[object | None, dict[str, float] | None]:
        if symbol not in EQUITY_SYMBOLS:
            return None, None
        features = self._factor_features(symbol, now, stock_eligible)
        stock_anchor = self._last_reference.get(symbol)
        if features is None or stock_anchor is None:
            return None, features
        return self.ai.predict_fair_value(symbol, stock_anchor, features), features

    def _static_factor_estimate(self, symbol: str, now: datetime) -> tuple[float | None, float, list[str]]:
        if symbol not in QQQ_BETA:
            return None, 0.0, []
        qqq_price = self._fresh_factor_price("QQQ", now)
        stock_anchor = self._last_reference.get(symbol)
        if qqq_price is None or stock_anchor is None:
            return None, 0.0, []
        anchors = self._stock_factor_anchor.setdefault(symbol, {})
        qqq_anchor = anchors.setdefault("QQQ", qqq_price)
        qqq_return = qqq_price / qqq_anchor - 1
        estimate = stock_anchor * math.exp(QQQ_BETA[symbol] * math.log1p(qqq_return))
        qqq_rows = [
            source
            for source in self._latest.get("QQQ", {}).values()
            if source.eligible and max(0.0, (now - source.event_time).total_seconds()) <= FRESH_SECONDS
        ]
        providers, venues = self._independence(qqq_rows)
        confidence = min(62.0, 42.0 + providers * 6.0 + venues * 3.0)
        return estimate, confidence, ["QQQ_STATIC_FACTOR_FALLBACK", "ESTIMATE_NOT_DIRECT_MARKET_EVIDENCE"]

    def _empty_ai_payload(self) -> dict:
        status = self.ai_status()
        return {
            "enabled": status["enabled"],
            "model_version": status["model_version"],
            "data_mode": status["data_mode"],
            "fair_value_used": False,
            "fair_value_model_type": None,
            "predicted_reference": None,
            "predicted_return_bps": None,
            "top_factors": [],
            "anomaly_probability": None,
            "anomaly_factors": [],
            "risk_signal_enforced": status["risk_signal_enforced"],
        }

    @staticmethod
    def _ai_risk_enforced(ai_payload: dict) -> bool:
        return bool(ai_payload.get("risk_signal_enforced"))

    def _anomaly_score(
        self,
        evidence: list[dict],
        status: str,
        divergence_bps: float | None,
    ) -> tuple[float | None, list[dict]]:
        fresh_eligible = [row for row in evidence if row.get("fresh") and row.get("eligible")]
        prices = [float(row["price"]) for row in fresh_eligible]
        dispersion = (max(prices) / min(prices) - 1) * 10_000 if len(prices) >= 2 else 0.0
        ages = [float(row.get("age_seconds") or 0.0) * 1000 for row in fresh_eligible]
        providers = len({row.get("provider_family") for row in fresh_eligible})
        venues = len({row.get("venue_family") for row in fresh_eligible})
        features = {
            "mark_divergence_bps": float(divergence_bps or 0.0),
            "dispersion_bps": dispersion,
            "source_age_ms": median(ages) if ages else float(FRESH_SECONDS * 1000),
            "provider_count": float(providers),
            "venue_count": float(venues),
            "status_estimated": 1.0 if status == "ESTIMATED" else 0.0,
        }
        return self.ai.anomaly_probability(features)

    @staticmethod
    def _risk_policy(
        confidence: float,
        divergence_bps: float | None,
        status: str,
        anomaly_probability: float | None = None,
        enforce_ai: bool = False,
    ) -> dict:
        divergence = divergence_bps or 0.0
        if divergence >= 500 or confidence < 35:
            state, lev, notional = "HALTED", 0, 0.0
        elif divergence >= 150 or confidence < 60:
            state, lev, notional = "RESTRICTED", 3, 0.25
        elif divergence >= 75 or confidence < 80 or status == "ESTIMATED":
            state, lev, notional = "GUARDED", 5 if status == "ESTIMATED" else 10, 0.5
        else:
            state, lev, notional = "NORMAL", 20, 1.0

        # Learned signals are permitted to tighten, never loosen, deterministic risk.
        if enforce_ai and anomaly_probability is not None:
            if anomaly_probability >= 0.95 and state == "NORMAL":
                state, lev, notional = "RESTRICTED", 3, 0.25
            elif anomaly_probability >= 0.95 and state == "GUARDED":
                state, lev, notional = "RESTRICTED", min(lev, 3), min(notional, 0.25)
            elif anomaly_probability >= 0.80 and state == "NORMAL":
                state, lev, notional = "GUARDED", 10, 0.5
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
        dispersion_bps = self._dispersion_bps(eligible)

        prices = [source.price for source in eligible]
        qualified_candidate = None
        if venue_count >= 2 and len(prices) >= 2:
            candidate = median(prices)
            previous = self._last_reference.get(symbol)
            move_bps = 0.0 if previous is None else abs(candidate / previous - 1) * 10_000
            if dispersion_bps > AGREEMENT_BPS:
                reasons.append("CROSS_VENUE_DISAGREEMENT")
            elif previous is not None and move_bps > LARGE_MOVE_BPS and venue_count < 3:
                reasons.append("LARGE_MOVE_NEEDS_THREE_VENUE_FAMILIES")
            else:
                reference = candidate
                qualified_candidate = candidate
                status = "QUALIFIED"
                confidence = max(80.0, min(99.0, 97.0 - dispersion_bps / 10 - max(0, 2 - provider_count) * 6))
                band_bps = max(12.0, min(75.0, 12.0 + dispersion_bps * 0.6))
                reasons.append("INDEPENDENT_VENUES_AGREE")
                if provider_count < 2:
                    reasons.append("SINGLE_PROVIDER_CONCENTRATION")
        else:
            reasons.append("NEEDS_TWO_FRESH_ORIGINAL_VENUE_FAMILIES")

        ai_payload = self._empty_ai_payload()
        learned, _features = self._learned_estimate(symbol, now, eligible)
        if learned is not None:
            ai_payload.update({
                "fair_value_model_type": learned.model_type,
                "predicted_reference": learned.predicted_reference,
                "predicted_return_bps": learned.predicted_return_bps,
                "top_factors": learned.top_factors,
            })
            if reference is None:
                reference = learned.predicted_reference
                status = "ESTIMATED"
                confidence = learned.confidence
                band_bps = learned.band_bps
                ai_payload["fair_value_used"] = True
                reasons.extend(["ML_FAIR_VALUE_FALLBACK", "ESTIMATE_NOT_DIRECT_MARKET_EVIDENCE"])
                if str(learned.data_mode).startswith("SYNTHETIC"):
                    reasons.append("AI_MODEL_SYNTHETIC_CALIBRATION")

        if reference is None and symbol in EQUITY_SYMBOLS:
            estimate, factor_confidence, factor_reasons = self._static_factor_estimate(symbol, now)
            if estimate is not None:
                reference = estimate
                status = "ESTIMATED"
                confidence = factor_confidence
                band_bps = 180.0
                reasons.extend(factor_reasons)

        # Anchor only after direct evidence has qualified. Learned estimates never
        # become trusted anchors on their own.
        if qualified_candidate is not None:
            self._last_reference[symbol] = qualified_candidate
            self._anchor_time[symbol] = now
            if symbol in FACTOR_SYMBOLS:
                self._factor_reference[symbol] = qualified_candidate
            elif symbol in EQUITY_SYMBOLS:
                self._stock_factor_anchor[symbol] = dict(self._factor_reference)

        if any(not row["eligible"] for row in evidence):
            reasons.append("RESEARCH_FEED_VISIBLE_NOT_COUNTED")
        mark = self._mark_view(self._marks.get(symbol), now)
        divergence_bps = abs(mark["price"] / reference - 1) * 10_000 if mark and mark["fresh"] and reference else None
        if mark and mark["fresh"]:
            reasons.append("VENUE_MARK_OBSERVED")
        elif mark:
            reasons.append("VENUE_MARK_STALE")
        anomaly_probability, anomaly_factors = self._anomaly_score(evidence, status, divergence_bps)
        ai_payload["anomaly_probability"] = anomaly_probability
        ai_payload["anomaly_factors"] = anomaly_factors
        if anomaly_probability is not None and anomaly_probability >= 0.90:
            reasons.append("AI_ANOMALY_SIGNAL_HIGH")
        risk = self._risk_policy(
            confidence,
            divergence_bps,
            status,
            anomaly_probability,
            self._ai_risk_enforced(ai_payload),
        )

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
            "model_version": "marketbridge-shadow-v0.3",
            "ai": ai_payload,
            **risk,
        }

    def snapshot(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            ordered = sorted(self._latencies)
            source_ages = sorted(self._source_age_ms)
            p50 = median(ordered) if ordered else None
            p95 = ordered[round((len(ordered) - 1) * 0.95)] if ordered else None
            p99 = ordered[round((len(ordered) - 1) * 0.99)] if ordered else None
            age_p95 = source_ages[round((len(source_ages) - 1) * 0.95)] if source_ages else None
            return {
                "generation": self._generation,
                "decisions": [
                    self._decision_view(self._decisions[symbol], now)
                    for symbol in EQUITY_SYMBOLS
                    if symbol in self._decisions
                ],
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
                "ai": self.ai_status(),
            }

    def wait_for_generation(self, generation: int, timeout: float = 10.0) -> dict:
        with self._changed:
            if self._generation == generation:
                self._changed.wait(timeout=timeout)
        return self.snapshot()


class LivePipeline:
    """Own provider adapters, audit persistence and the shadow-oracle lifecycle."""

    def __init__(self, audit_path: Path):
        self.tracked_symbols = TRACKED_SYMBOLS
        self._stop = Event()
        self._threads: list[Thread] = []
        self._audit_queue: SimpleQueue[dict | None] = SimpleQueue()
        self._audit_path = audit_path
        self.oracle = ShadowOracle(self._audit_queue.put)
        self._provider_status = {
            "yahoo": {"status": "STARTING", "kind": "RESEARCH", "detail": "Background bootstrap"},
            "alpaca": {
                "status": "DISABLED",
                "kind": "DIRECT_MARKET",
                "detail": "Set ALPACA_API_KEY and ALPACA_SECRET_KEY",
                "qualification_capable": False,
                "retry_count": 0,
                "consecutive_failures": 0,
            },
            "databento": {
                "status": "DISABLED",
                "kind": "DIRECT_MARKET",
                "detail": "Set DATABENTO_API_KEY for EQUS.MINI MBP-1",
                "qualification_capable": False,
            },
            "hyperliquid": {
                "status": "DISABLED",
                "kind": "VENUE_MARK",
                "detail": "Set HYPERLIQUID_COIN_MAP to observe venue marks",
            },
            "mochatrade": {"status": "WAITING", "kind": "VENUE_MARK", "detail": "No mark received"},
        }
        self._yahoo: dict | None = None
        self._last_yahoo_event: dict[str, str] = {}
        self._alpaca_quotes: dict[str, dict] = {}
        self._last_alpaca_event: dict[tuple[str, str], datetime] = {}
        self._seen_alpaca_trade_ids: set[tuple[str, str]] = set()
        self._alpaca_trade_order: deque[tuple[str, str]] = deque(maxlen=10_000)
        self._started = False
        self._state_lock = Lock()
        self._databento_symbols: dict[int, str] = {}

    def configuration(self) -> dict:
        api_key = bool(os.environ.get("ALPACA_API_KEY", "").strip())
        secret_key = bool(os.environ.get("ALPACA_SECRET_KEY", "").strip())
        feed = os.environ.get("ALPACA_FEED", "iex").strip().lower()
        alpaca_errors: list[str] = []
        hyperliquid_errors: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        if api_key != secret_key:
            alpaca_errors.append("ALPACA_CREDENTIAL_PAIR_INCOMPLETE")
        if feed not in ALPACA_SUPPORTED_FEEDS:
            alpaca_errors.append("ALPACA_FEED_UNSUPPORTED")
        credentials_configured = api_key and secret_key
        databento_configured = bool(os.environ.get("DATABENTO_API_KEY", "").strip())
        qualification_capable = credentials_configured and feed in ALPACA_MULTI_VENUE_FEEDS
        if credentials_configured and feed == "iex":
            warnings.append("ALPACA_IEX_SINGLE_VENUE")
        elif credentials_configured and feed not in ALPACA_MULTI_VENUE_FEEDS:
            warnings.append("ALPACA_FEED_NOT_MULTI_VENUE")

        coin_map = os.environ.get("HYPERLIQUID_COIN_MAP")
        if coin_map:
            try:
                parsed_coin_map = json.loads(coin_map)
                if (
                    not isinstance(parsed_coin_map, dict)
                    or not parsed_coin_map
                    or any(
                        symbol not in EQUITY_SYMBOLS or not isinstance(coin, str) or not coin.strip()
                        for symbol, coin in parsed_coin_map.items()
                    )
                ):
                    hyperliquid_errors.append("HYPERLIQUID_COIN_MAP_INVALID")
            except json.JSONDecodeError:
                hyperliquid_errors.append("HYPERLIQUID_COIN_MAP_INVALID")

        thresholds = {}
        for env_name, default, key in (
            ("ALPACA_MAX_NBBO_DEVIATION_BPS", 150.0, "max_nbbo_deviation_bps"),
            ("MARKETBRIDGE_VENUE_MARK_TTL_SECONDS", VENUE_MARK_FRESH_SECONDS, "venue_mark_ttl_seconds"),
        ):
            try:
                thresholds[key] = _positive_float_env(env_name, default)
            except ValueError:
                if env_name.startswith("ALPACA"):
                    alpaca_errors.append(f"{env_name}_INVALID")
                else:
                    errors.append(f"{env_name}_INVALID")

        errors = [*errors, *alpaca_errors, *hyperliquid_errors]

        return {
            "strict_live_data": _env_enabled("MARKETBRIDGE_REQUIRE_LIVE_DATA"),
            "alpaca": {
                "credentials_configured": credentials_configured,
                "feed": feed,
                "qualification_capable": qualification_capable,
                "configured_multi_venue": qualification_capable,
                "errors": alpaca_errors,
            },
            "databento": {
                "credentials_configured": databento_configured,
                "dataset": "EQUS.MINI",
                "schema": "mbp-1",
                "qualification_capable": databento_configured,
                "errors": [],
            },
            "hyperliquid_configured": bool(coin_map),
            "hyperliquid_errors": hyperliquid_errors,
            "thresholds": thresholds,
            "errors": errors,
            "warnings": warnings,
            "valid": not errors,
        }

    def start(self) -> None:
        if self._started:
            return
        configuration = self.configuration()
        if configuration["strict_live_data"] and not configuration["alpaca"]["qualification_capable"]:
            raise RuntimeError("strict live-data mode requires authenticated multi-venue Alpaca feed configuration")
        if configuration["strict_live_data"] and configuration["errors"]:
            raise RuntimeError("strict live-data configuration is invalid: " + ",".join(configuration["errors"]))
        self._started = True
        self._stop.clear()
        self._threads = [Thread(target=self._audit_loop, name="marketbridge-audit", daemon=True)]
        if not _env_enabled("MARKETBRIDGE_DISABLE_RESEARCH_FEED"):
            self._threads.append(Thread(target=self._yahoo_loop, name="marketbridge-yahoo", daemon=True))
        else:
            self._provider_status["yahoo"] = {
                "status": "DISABLED", "kind": "RESEARCH", "detail": "Disabled by configuration"
            }
        if configuration["alpaca"]["errors"]:
            self._provider_status["alpaca"] = {
                "status": "CONFIG_ERROR",
                "kind": "DIRECT_MARKET",
                "detail": ",".join(configuration["alpaca"]["errors"]),
                "qualification_capable": False,
                "retry_count": 0,
                "consecutive_failures": 0,
            }
        elif configuration["alpaca"]["credentials_configured"]:
            self._provider_status["alpaca"] = {
                "status": "CONNECTING",
                "kind": "DIRECT_MARKET",
                "detail": f"{configuration['alpaca']['feed']} WebSocket",
                "qualification_capable": configuration["alpaca"]["qualification_capable"],
                "retry_count": 0,
                "consecutive_failures": 0,
            }
            self._threads.append(Thread(target=self._alpaca_loop, name="marketbridge-alpaca", daemon=True))
        if configuration["databento"]["credentials_configured"]:
            self._provider_status["databento"] = {
                "status": "CONNECTING",
                "kind": "DIRECT_MARKET",
                "detail": "EQUS.MINI MBP-1",
                "qualification_capable": True,
            }
            self._threads.append(Thread(target=self._databento_loop, name="marketbridge-databento", daemon=True))
        if configuration["hyperliquid_configured"] and not configuration["hyperliquid_errors"]:
            self._provider_status["hyperliquid"] = {
                "status": "CONNECTING",
                "kind": "VENUE_MARK",
                "detail": "Hyperliquid WebSocket",
            }
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
        database_path = Path(
            os.environ.get(
                "MARKETBRIDGE_DUCKDB_PATH",
                str(self._audit_path.with_name("marketbridge.duckdb")),
            )
        )
        with self._audit_path.open("a", encoding="utf-8") as output, EvidenceStore(database_path) as store:
            while True:
                item = self._audit_queue.get()
                if item is None:
                    return
                output.write(json.dumps(item, allow_nan=False, separators=(",", ":")) + "\n")
                output.flush()
                store.append(item)
                observe_decision(item)

    def _yahoo_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh_yahoo()
            except Exception as exc:
                with self._state_lock:
                    self._provider_status["yahoo"] = {
                        "status": "UNAVAILABLE",
                        "kind": "RESEARCH",
                        "detail": str(exc)[:160],
                    }
            self._stop.wait(15)

    def refresh_yahoo(self) -> dict:
        snapshot = get_live_snapshot(force=True)
        with self._state_lock:
            self._yahoo = snapshot
            latest_event = max(
                (row["event_time"] for row in snapshot["observations"]),
                default=None,
            )
            self._provider_status["yahoo"] = {
                "status": snapshot["provider_status"],
                "kind": "RESEARCH",
                "detail": snapshot["fetched_at"],
                "last_event_time": latest_event,
            }
        received_at = datetime.now(timezone.utc)
        for row in snapshot["observations"]:
            if row["symbol"] not in TRACKED_SYMBOLS:
                continue
            if self._last_yahoo_event.get(row["symbol"]) == row["event_time"]:
                continue
            self._last_yahoo_event[row["symbol"]] = row["event_time"]
            self.oracle.ingest(
                NormalizedObservation(
                    symbol=row["symbol"],
                    price=row["observed_price"],
                    event_time=_utc(row["event_time"]),
                    received_at=received_at,
                    source_id="yfinance",
                    source_family="yahoo-research-feed",
                    venue=row["exchange"],
                    eligible=False,
                    provider_family="yahoo",
                    venue_family=row["exchange"],
                )
            )
        return self.snapshot()

    def _alpaca_loop(self) -> None:
        from websockets.sync.client import connect

        feed = os.environ.get("ALPACA_FEED", "iex").strip().lower()
        url = f"wss://stream.data.alpaca.markets/v2/{feed}"
        backoff = 1
        while not self._stop.is_set():
            try:
                self._set_provider(
                    "alpaca",
                    status="CONNECTING",
                    connection_time=_iso(datetime.now(timezone.utc)),
                    permanent_error=False,
                )
                with connect(url, open_timeout=8, close_timeout=2) as socket:
                    socket.send(
                        json.dumps(
                            {
                                "action": "auth",
                                "key": os.environ["ALPACA_API_KEY"],
                                "secret": os.environ["ALPACA_SECRET_KEY"],
                            }
                        )
                    )
                    session = {"authenticated": False, "subscription_sent": False, "subscribed": False}
                    for message in socket:
                        if self._stop.is_set():
                            return
                        received_at = datetime.now(timezone.utc)
                        self._set_provider("alpaca", last_message_time=_iso(received_at))
                        events = json.loads(message)
                        if not isinstance(events, list):
                            raise RuntimeError("Alpaca returned a non-list WebSocket payload")
                        self._handle_alpaca_events(events, socket, feed, session, received_at)
                        if session["subscribed"]:
                            backoff = 1
                    raise RuntimeError("Alpaca WebSocket closed")
            except AlpacaStreamError as exc:
                current = self._provider_status.get("alpaca", {})
                retries = int(current.get("retry_count", 0))
                self._set_provider(
                    "alpaca",
                    status=exc.status,
                    detail=exc.detail,
                    last_error_time=_iso(datetime.now(timezone.utc)),
                    last_error_code=exc.code,
                    permanent_error=exc.permanent,
                    consecutive_failures=int(current.get("consecutive_failures", 0)) + 1,
                    retry_count=retries,
                )
                logger.warning(
                    "market_data_provider_event provider=alpaca status=%s retry_count=%d error_code=%s",
                    exc.status,
                    retries,
                    exc.code,
                )
                if exc.permanent:
                    return
                self._set_provider("alpaca", status="RECONNECTING", retry_count=retries + 1)
                self._stop.wait(backoff)
                backoff = min(15, backoff * 2)
            except Exception as exc:
                current = self._provider_status.get("alpaca", {})
                retries = int(current.get("retry_count", 0)) + 1
                self._set_provider(
                    "alpaca",
                    status="RECONNECTING",
                    detail=str(exc)[:160],
                    last_error_time=_iso(datetime.now(timezone.utc)),
                    last_error_code=type(exc).__name__,
                    permanent_error=False,
                    retry_count=retries,
                    consecutive_failures=int(current.get("consecutive_failures", 0)) + 1,
                )
                logger.warning(
                    "market_data_provider_event provider=alpaca status=RECONNECTING retry_count=%d error_code=%s",
                    retries,
                    type(exc).__name__,
                )
                self._stop.wait(backoff)
                backoff = min(15, backoff * 2)

    def _databento_loop(self) -> None:
        """Consume Databento's aggregated EQUS.MINI BBO as one independent witness."""
        import databento as db

        client = db.Live(key=os.environ["DATABENTO_API_KEY"], reconnect_policy="reconnect")

        def on_exception(exc: Exception) -> None:
            self._set_provider(
                "databento",
                status="RECONNECTING",
                detail=str(exc)[:160],
                last_error_time=_iso(datetime.now(timezone.utc)),
            )

        def on_record(record) -> None:
            if isinstance(record, db.SymbolMappingMsg):
                candidates = (record.stype_in_symbol, record.stype_out_symbol)
                symbol = next(
                    (
                        value.decode() if isinstance(value, bytes) else str(value)
                        for value in candidates
                        if (value.decode() if isinstance(value, bytes) else str(value)) in TRACKED_SYMBOLS
                    ),
                    None,
                )
                if symbol:
                    self._databento_symbols[int(record.instrument_id)] = symbol
                return
            if not isinstance(record, db.MBP1Msg):
                return
            symbol = self._databento_symbols.get(int(record.instrument_id))
            if symbol is None:
                return
            received_at = datetime.now(timezone.utc)
            event_time = datetime.fromtimestamp(int(record.ts_event) / 1_000_000_000, timezone.utc)
            observation = self._normalized_databento_bbo(
                symbol,
                float(record.pretty_bid_px_00),
                float(record.pretty_ask_px_00),
                event_time,
                received_at,
            )
            if observation is None:
                return
            decision = self.oracle.ingest(observation)
            values = {
                "status": "AVAILABLE",
                "detail": "EQUS.MINI aggregated MBP-1",
                "last_event_time": _iso(event_time),
                "last_message_time": _iso(received_at),
            }
            if decision["status"] == "QUALIFIED":
                values["last_qualified_evidence_time"] = _iso(received_at)
            self._set_provider("databento", **values)

        try:
            client.add_callback(on_record, on_exception)
            client.subscribe(
                dataset="EQUS.MINI",
                schema="mbp-1",
                symbols=list(TRACKED_SYMBOLS),
                stype_in="raw_symbol",
            )
            client.start()
            self._stop.wait()
        except Exception as exc:
            on_exception(exc)
        finally:
            client.stop()

    @staticmethod
    def _normalized_databento_bbo(
        symbol: str,
        bid: float,
        ask: float,
        event_time: datetime,
        received_at: datetime,
    ) -> NormalizedObservation | None:
        if symbol not in TRACKED_SYMBOLS:
            return None
        if not all(math.isfinite(value) and value > 0 for value in (bid, ask)) or ask < bid:
            return None
        if event_time > received_at + timedelta(seconds=5) or received_at - event_time > timedelta(seconds=30):
            return None
        return NormalizedObservation(
            symbol=symbol,
            price=(bid + ask) / 2,
            event_time=event_time,
            received_at=received_at,
            source_id="databento-equs-mini-mbp1",
            source_family="databento-equs-mini",
            venue="EQUS.MINI",
            eligible=True,
            provider_family="databento",
            venue_family="databento-equs-mini",
        )

    def _set_provider(self, provider: str, **values) -> None:
        with self._state_lock:
            current = self._provider_status.get(provider, {})
            self._provider_status[provider] = {**current, **values}

    def _remember_trade(self, key: tuple[str, str]) -> bool:
        if key in self._seen_alpaca_trade_ids:
            return False
        if len(self._alpaca_trade_order) == self._alpaca_trade_order.maxlen:
            expired = self._alpaca_trade_order.popleft()
            self._seen_alpaca_trade_ids.discard(expired)
        self._alpaca_trade_order.append(key)
        self._seen_alpaca_trade_ids.add(key)
        return True

    def _record_alpaca_quote(self, event: dict, received_at: datetime) -> None:
        symbol = event.get("S")
        if symbol not in TRACKED_SYMBOLS:
            return
        try:
            bid = float(event["bp"])
            ask = float(event["ap"])
            bid_size = float(event["bs"])
            ask_size = float(event["as"])
            event_time = _utc(event["t"])
        except (KeyError, TypeError, ValueError):
            return
        if not all(math.isfinite(value) and value > 0 for value in (bid, ask, bid_size, ask_size)) or ask < bid:
            return
        if event_time > received_at + timedelta(seconds=5) or received_at - event_time > timedelta(seconds=30):
            return
        self._alpaca_quotes[symbol] = {"bid": bid, "ask": ask, "event_time": event_time}
        self._set_provider("alpaca", last_quote_time=_iso(received_at))

    def _normalized_alpaca_trade(
        self, event: dict, feed: str, received_at: datetime
    ) -> NormalizedObservation | None:
        symbol = event.get("S")
        venue = str(event.get("x") or "UNKNOWN")
        if symbol not in TRACKED_SYMBOLS or venue == "UNKNOWN":
            return None
        try:
            price = float(event["p"])
            size = float(event["s"])
            event_time = _utc(event["t"])
        except (KeyError, TypeError, ValueError):
            return None
        if not math.isfinite(price) or price <= 0 or not math.isfinite(size) or size <= 0:
            return None
        tape = str(event.get("z") or "")
        if tape not in {"A", "B", "C", "O"}:
            return None
        rejected = {
            item.strip()
            for item in os.environ.get("ALPACA_REJECT_CONDITIONS", ",".join(ALPACA_DEFAULT_REJECT_CONDITIONS)).split(",")
            if item.strip()
        }
        conditions = {str(item) for item in (event.get("c") or [])}
        if conditions & rejected:
            return None
        if event_time > received_at + timedelta(seconds=5) or received_at - event_time > timedelta(seconds=30):
            return None
        last_event = self._last_alpaca_event.get((symbol, venue))
        if last_event is not None and event_time < last_event:
            return None
        trade_id = str(event.get("i") or "")
        if not trade_id or not self._remember_trade((symbol, trade_id)):
            return None
        quote = self._alpaca_quotes.get(symbol)
        if quote and abs((event_time - quote["event_time"]).total_seconds()) <= 5:
            midpoint = (quote["bid"] + quote["ask"]) / 2
            deviation_bps = abs(price / midpoint - 1) * 10_000
            max_deviation = _positive_float_or_default("ALPACA_MAX_NBBO_DEVIATION_BPS", 150.0)
            if deviation_bps > max_deviation:
                return None
        self._last_alpaca_event[(symbol, venue)] = event_time
        return NormalizedObservation(
            symbol=symbol,
            price=price,
            event_time=event_time,
            received_at=received_at,
            source_id=f"alpaca-{feed}",
            source_family=f"equity-venue:{venue}",
            venue=venue,
            eligible=True,
            provider_family="alpaca",
            venue_family=venue,
        )

    def _handle_alpaca_events(
        self,
        events: list[dict],
        socket,
        feed: str,
        session: dict[str, bool],
        received_at: datetime,
    ) -> int:
        ingested = 0
        for event in events:
            event_type = event.get("T")
            if event_type == "error":
                error = _classify_alpaca_error(event, authenticated=session["authenticated"])
                self._set_provider(
                    "alpaca",
                    status=error.status,
                    detail=error.detail,
                    last_error_time=_iso(received_at),
                    last_error_code=error.code,
                    permanent_error=error.permanent,
                )
                raise error
            if event_type == "success" and event.get("msg") == "authenticated":
                session["authenticated"] = True
                self._set_provider(
                    "alpaca",
                    status="AUTHENTICATED",
                    detail=f"{feed} authenticated",
                    auth_time=_iso(received_at),
                    last_message_time=_iso(received_at),
                )
                if not session["subscription_sent"]:
                    socket.send(
                        json.dumps(
                            {
                                "action": "subscribe",
                                "trades": list(TRACKED_SYMBOLS),
                                "quotes": list(TRACKED_SYMBOLS),
                            }
                        )
                    )
                    session["subscription_sent"] = True
                continue
            if event_type == "subscription":
                subscribed = set(event.get("trades") or [])
                if not session["authenticated"] or not set(TRACKED_SYMBOLS).issubset(subscribed):
                    raise AlpacaStreamError(
                        "SUBSCRIPTION_ERROR",
                        "Alpaca subscription acknowledgment is incomplete",
                        code="INCOMPLETE_ACK",
                        permanent=True,
                    )
                session["subscribed"] = True
                capable = feed in ALPACA_MULTI_VENUE_FEEDS
                self._set_provider(
                    "alpaca",
                    status="AVAILABLE" if capable else "LIMITED",
                    detail=(
                        f"{feed} authenticated multi-venue stream"
                        if capable
                        else f"{feed} authenticated; single/non-qualifying venue feed"
                    ),
                    qualification_capable=capable,
                    subscription_time=_iso(received_at),
                    last_message_time=_iso(received_at),
                    retry_count=0,
                    consecutive_failures=0,
                    permanent_error=False,
                )
                continue
            if event_type == "q" and session["subscribed"]:
                self._record_alpaca_quote(event, received_at)
                continue
            if event_type != "t" or not session["subscribed"]:
                continue
            observation = self._normalized_alpaca_trade(event, feed, received_at)
            if observation is None:
                continue
            decision = self.oracle.ingest(observation)
            ingested += 1
            values = {
                "last_event_time": _iso(observation.event_time),
                "last_trade_time": _iso(received_at),
                "last_message_time": _iso(received_at),
            }
            if decision["status"] == "QUALIFIED":
                values["last_qualified_evidence_time"] = _iso(received_at)
            self._set_provider("alpaca", **values)
        return ingested

    def _hyperliquid_loop(self) -> None:
        """Observe configured Hyperliquid asset contexts as venue marks."""
        from websockets.sync.client import connect

        coin_map = json.loads(os.environ["HYPERLIQUID_COIN_MAP"])
        reverse = {coin: symbol for symbol, coin in coin_map.items() if symbol in EQUITY_SYMBOLS}
        backoff = 1
        while not self._stop.is_set():
            try:
                with connect("wss://api.hyperliquid.xyz/ws", open_timeout=8, close_timeout=2) as socket:
                    for coin in reverse:
                        socket.send(
                            json.dumps(
                                {"method": "subscribe", "subscription": {"type": "activeAssetCtx", "coin": coin}}
                            )
                        )
                    with self._state_lock:
                        self._provider_status["hyperliquid"] = {
                            "status": "AVAILABLE",
                            "kind": "VENUE_MARK",
                            "detail": f"{len(reverse)} configured assets",
                        }
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
                            self.ingest_mochatrade(
                                symbol,
                                float(mark),
                                datetime.now(timezone.utc),
                                source="hyperliquid",
                            )
            except Exception as exc:
                with self._state_lock:
                    self._provider_status["hyperliquid"] = {
                        "status": "RECONNECTING",
                        "kind": "VENUE_MARK",
                        "detail": str(exc)[:160],
                    }
                self._stop.wait(backoff)
                backoff = min(15, backoff * 2)

    def ingest_direct_observation(
        self,
        symbol: str,
        price: float,
        event_time: datetime,
        *,
        provider: str,
        venue: str,
        received_at: datetime | None = None,
    ) -> dict:
        """Adapter boundary for trusted direct feeds that preserve venue identity."""
        if not provider.strip() or not venue.strip():
            raise ValueError("provider and venue are required")
        received_at = received_at or event_time
        decision = self.oracle.ingest(
            NormalizedObservation(
                symbol=symbol,
                price=price,
                event_time=event_time,
                received_at=received_at,
                source_id=f"{provider}:{venue}",
                source_family=f"equity-venue:{venue}",
                venue=venue,
                eligible=True,
                provider_family=provider,
                venue_family=venue,
            )
        )
        values = {
            "status": "AVAILABLE",
            "kind": "DIRECT_MARKET",
            "detail": "direct venue-labelled adapter",
            "qualification_capable": True,
            "last_event_time": _iso(event_time),
            "last_trade_time": _iso(received_at),
            "last_message_time": _iso(received_at),
            "retry_count": 0,
            "consecutive_failures": 0,
            "permanent_error": False,
        }
        if decision["status"] == "QUALIFIED":
            values["last_qualified_evidence_time"] = _iso(received_at)
        self._set_provider(provider, **values)
        return decision

    def ingest_mochatrade(
        self,
        symbol: str,
        mark_price: float,
        event_time: datetime,
        source: str = "mochatrade",
    ) -> dict:
        mark = self.oracle.update_venue_mark(symbol, mark_price, event_time)
        with self._state_lock:
            self._provider_status[source] = {
                "status": "AVAILABLE",
                "kind": "VENUE_MARK",
                "detail": mark["event_time"],
                "last_event_time": mark["event_time"],
            }
        return mark

    def wait_for_generation(self, generation: int, timeout: float = 10.0) -> dict:
        self.oracle.wait_for_generation(generation, timeout)
        return self.snapshot()

    def _provider_payload(self, now: datetime) -> dict:
        with self._state_lock:
            providers = []
            for key, value in self._provider_status.items():
                provider = {"id": key, **value}
                for time_key in (
                    "connection_time",
                    "auth_time",
                    "subscription_time",
                    "last_message_time",
                    "last_quote_time",
                    "last_trade_time",
                    "last_qualified_evidence_time",
                    "last_error_time",
                ):
                    timestamp = value.get(time_key)
                    age_key = time_key.removesuffix("_time") + "_age_seconds"
                    provider[age_key] = (
                        round(max(0.0, (now - _utc(timestamp)).total_seconds()), 3)
                        if timestamp
                        else None
                    )
                last_event_time = value.get("last_event_time")
                if last_event_time:
                    age_seconds = max(0.0, (now - _utc(last_event_time)).total_seconds())
                    provider["event_age_seconds"] = round(age_seconds, 3)
                    freshness_limit = (
                        120
                        if value.get("kind") == "RESEARCH"
                        else FRESH_SECONDS
                        if value.get("kind") == "DIRECT_MARKET"
                        else VENUE_MARK_FRESH_SECONDS
                    )
                    if value.get("kind") == "VENUE_MARK":
                        freshness_limit = _positive_float_or_default(
                            "MARKETBRIDGE_VENUE_MARK_TTL_SECONDS", VENUE_MARK_FRESH_SECONDS
                        )
                    provider["fresh"] = age_seconds <= freshness_limit
                    if not provider["fresh"] and value.get("status") in {"AVAILABLE", "LIMITED"}:
                        provider["status"] = "STALE"
                else:
                    provider["event_age_seconds"] = None
                    provider["fresh"] = False
                providers.append(provider)
            yahoo = self._yahoo
        return {"providers": providers, "yahoo": yahoo}

    @staticmethod
    def _market_health(started: bool, oracle_snapshot: dict, providers: list[dict]) -> dict:
        qualified_symbols = sorted(
            decision["symbol"] for decision in oracle_snapshot["decisions"] if decision["status"] == "QUALIFIED"
        )
        comparable_symbols = sorted(
            decision["symbol"]
            for decision in oracle_snapshot["decisions"]
            if decision["status"] == "QUALIFIED"
            and decision.get("venue_mark")
            and decision["venue_mark"].get("fresh")
        )
        multi_venue_feeds = [
            provider["id"]
            for provider in providers
            if provider.get("kind") == "DIRECT_MARKET"
            and provider.get("status") in {"AVAILABLE", "STALE"}
            and provider.get("qualification_capable")
        ]
        fresh_multi_venue_feeds = [
            provider["id"]
            for provider in providers
            if provider.get("kind") == "DIRECT_MARKET"
            and provider.get("status") == "AVAILABLE"
            and provider.get("qualification_capable")
            and provider.get("fresh")
        ]
        reasons: list[str] = []
        if not qualified_symbols:
            reasons.append("NO_QUALIFIED_REFERENCES")
        if not any(provider.get("kind") == "VENUE_MARK" and provider.get("fresh") for provider in providers):
            reasons.append("NO_FRESH_VENUE_MARKS")
        if not multi_venue_feeds and not qualified_symbols:
            reasons.append("NO_AUTHENTICATED_MULTI_VENUE_FEED")
        elif not fresh_multi_venue_feeds and not qualified_symbols:
            reasons.append("NO_FRESH_MULTI_VENUE_FEED")
        if not started:
            status = "OFFLINE"
        elif comparable_symbols:
            status = "HEALTHY"
        elif any(
            provider.get("kind") in {"DIRECT_MARKET", "VENUE_MARK"}
            and provider["status"] in {"STARTING", "CONNECTING", "AUTHENTICATED"}
            for provider in providers
        ):
            status = "STARTING"
        else:
            status = "DEGRADED"
        return {
            "status": status,
            "execution_ready": bool(comparable_symbols),
            "qualified_symbols": qualified_symbols,
            "comparable_symbols": comparable_symbols,
            "authenticated_multi_venue_feeds": multi_venue_feeds,
            "fresh_multi_venue_feeds": fresh_multi_venue_feeds,
            "reasons": reasons,
        }

    def readiness(self, now: datetime | None = None) -> dict:
        snapshot = self.snapshot(now=now)
        strict = snapshot["configuration"]["strict_live_data"]
        ready = self._started and (not strict or snapshot["market_health"]["execution_ready"])
        return {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "pipeline_started": self._started,
            "strict_live_data": strict,
            "market_health": snapshot["market_health"],
            "configuration": snapshot["configuration"],
        }

    def snapshot(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        provider_payload = self._provider_payload(now)
        oracle_snapshot = self.oracle.snapshot(now=now)
        configuration = self.configuration()
        return {
            "data_mode": "SHADOW_ORACLE",
            "advisory_only": True,
            "started": self._started,
            **provider_payload,
            **oracle_snapshot,
            "configuration": configuration,
            "market_health": self._market_health(self._started, oracle_snapshot, provider_payload["providers"]),
        }


def test_observation(symbol: str, price: float, family: str, venue: str, now: datetime) -> NormalizedObservation:
    """Small public constructor used by tests and local integration probes."""
    return NormalizedObservation(symbol, price, now, now, family, family, venue, True)
