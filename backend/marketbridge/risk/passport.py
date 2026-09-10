"""Canonical hashing, chain storage, verification, and replay records."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from threading import Lock


def _json_default(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"Cannot canonicalize {type(value).__name__}")


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_json_default).encode()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


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
