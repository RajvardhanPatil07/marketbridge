"""Canonical hashing, chain storage, verification, and replay records."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from threading import Lock
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _json_default(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"Cannot canonicalize {type(value).__name__}")


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_json_default).encode()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _presentation_claims(claims: dict) -> dict:
    """Attach immutable display context without changing USD policy semantics."""
    enriched = deepcopy(claims)
    identity = enriched.get("identity", {})
    order = enriched.get("order", {})
    timestamp = identity.get("timestamp")
    timestamp_ist = None
    if timestamp:
        try:
            timestamp_ist = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(IST).isoformat()
        except (TypeError, ValueError):
            timestamp_ist = None

    raw_fx = os.getenv("USDINR", "").strip()
    try:
        usd_inr = Decimal(raw_fx) if raw_fx else None
    except Exception:
        usd_inr = None

    def convert(value):
        if value is None or usd_inr is None:
            return None
        return float((Decimal(str(value)) * usd_inr).quantize(Decimal("0.01")))

    enriched["presentation"] = {
        "timezone": "Asia/Kolkata",
        "timestamp_ist": timestamp_ist,
        "usd_inr": float(usd_inr) if usd_inr else None,
        "fx_source": "USDINR environment configuration" if usd_inr else "UNCONFIGURED",
        "requested_notional_inr": convert(order.get("requested_notional_usd")),
        "permitted_notional_inr": convert(order.get("permitted_notional_usd")),
    }
    return enriched


@dataclass
class PassportRecord:
    passport: dict
    request: dict
    market_truth: dict
    request_hash: str


class PassportStore:
    """Process-local prototype store; persistence can implement this interface."""

    def __init__(self):
        self._lock = Lock()
        self._records: dict[str, PassportRecord] = {}
        self._requests: dict[str, str] = {}
        self._heads: dict[str, str] = {}
        self._sequences: dict[str, int] = {}

    def create(self, claims: dict, request: dict, market_truth: dict, request_hash: str) -> dict:
        claims = _presentation_claims(claims)
        symbol = claims["identity"]["symbol"]
        with self._lock:
            sequence = self._sequences.get(symbol, 0) + 1
            previous_hash = self._heads.get(symbol)
            content_hash = canonical_hash(claims)
            chain_hash = canonical_hash({
                "scope": f"symbol:{symbol}", "sequence": sequence,
                "previous_hash": previous_hash, "content_hash": content_hash,
            })
            passport_id = f"mbp_{chain_hash[:24]}"
            passport = {
                "passport_id": passport_id, "version": "marketbridge-safety-passport-v1",
                "algorithm": "sha256", "scope": f"symbol:{symbol}", "sequence": sequence,
                "previous_hash": previous_hash, "content_hash": content_hash,
                "chain_hash": chain_hash, "verification_status": "VERIFIED", "claims": deepcopy(claims),
            }
            record = PassportRecord(passport, deepcopy(request), deepcopy(market_truth), request_hash)
            self._records[passport_id] = record
            self._requests[claims["identity"]["request_id"]] = passport_id
            self._heads[symbol] = chain_hash
            self._sequences[symbol] = sequence
            return deepcopy(passport)

    def get(self, passport_id: str) -> PassportRecord | None:
        with self._lock:
            record = self._records.get(passport_id)
            return deepcopy(record) if record else None

    def by_request(self, request_id: str) -> PassportRecord | None:
        with self._lock:
            passport_id = self._requests.get(request_id)
            record = self._records.get(passport_id) if passport_id else None
            return deepcopy(record) if record else None

    @staticmethod
    def verify(passport: dict) -> bool:
        try:
            if canonical_hash(passport["claims"]) != passport["content_hash"]:
                return False
            expected = canonical_hash({
                "scope": passport["scope"], "sequence": passport["sequence"],
                "previous_hash": passport["previous_hash"], "content_hash": passport["content_hash"],
            })
            return expected == passport["chain_hash"]
        except (KeyError, TypeError, ValueError):
            return False

    def record_outcome(self, passport_id: str, outcome: str) -> dict | None:
        with self._lock:
            record = self._records.get(passport_id)
            if record is None:
                return None
            # This post-decision annotation is outside immutable decision claims.
            record.passport["outcome"] = outcome
            return deepcopy(record.passport)