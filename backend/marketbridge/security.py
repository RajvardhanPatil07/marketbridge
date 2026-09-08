"""Small, dependency-free security primitives for MarketBridge integrations.

The demo remains advisory-only, but remote integration endpoints still need strong
request authentication and replay protection.  These helpers intentionally keep
state in-process so they do not add a database round-trip to the hot path.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
import time
from threading import Lock


@dataclass(frozen=True)
class SignatureHeaders:
    timestamp: str
    nonce: str
    signature: str


def sign_request(secret: str, timestamp: str, nonce: str, body: bytes) -> str:
    """Return the lowercase SHA-256 HMAC for a canonical request payload."""
    payload = timestamp.encode() + b"." + nonce.encode() + b"." + body
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_signature(secret: str, headers: SignatureHeaders, body: bytes) -> bool:
    expected = sign_request(secret, headers.timestamp, headers.nonce, body)
    return hmac.compare_digest(expected, headers.signature.lower())


class NonceStore:
    """Bounded replay cache with TTL eviction."""

    def __init__(self, ttl_seconds: int = 30, max_entries: int = 10_000):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, float] = {}
        self._order: deque[tuple[str, float]] = deque()
        self._lock = Lock()

    def use_once(self, nonce: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        cutoff = now - self.ttl_seconds
        with self._lock:
            while self._order and self._order[0][1] < cutoff:
                old_nonce, old_ts = self._order.popleft()
                if self._entries.get(old_nonce) == old_ts:
                    self._entries.pop(old_nonce, None)
            if nonce in self._entries:
                return False
            self._entries[nonce] = now
            self._order.append((nonce, now))
            while len(self._entries) > self.max_entries and self._order:
                old_nonce, old_ts = self._order.popleft()
                if self._entries.get(old_nonce) == old_ts:
                    self._entries.pop(old_nonce, None)
            return True


class SlidingWindowLimiter:
    """Simple per-key request limiter suitable for a single hackathon instance."""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True
