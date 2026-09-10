from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import time
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class _Entry(Generic[T]):
    expires_at: float
    value: T


class AsyncBoundedCache(Generic[T]):
    """Small TTL LRU with single-flight request deduplication."""

    def __init__(self, max_entries: int = 128, ttl_seconds: float = 30.0):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._values: OrderedDict[object, _Entry[T]] = OrderedDict()
        self._pending: dict[object, asyncio.Task[T]] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, key: object, factory: Callable[[], Awaitable[T]]) -> tuple[T, bool]:
        async with self._lock:
            entry = self._values.get(key)
            if entry and entry.expires_at > time.monotonic():
                self._values.move_to_end(key)
                return entry.value, True
            if entry:
                del self._values[key]
            task = self._pending.get(key)
            owner = task is None
            if task is None:
                task = asyncio.create_task(factory())
                self._pending[key] = task
        try:
            value = await asyncio.shield(task)
        finally:
            if owner:
                async with self._lock:
                    self._pending.pop(key, None)
        if owner:
            async with self._lock:
                self._values[key] = _Entry(time.monotonic() + self.ttl_seconds, value)
                self._values.move_to_end(key)
                while len(self._values) > self.max_entries:
                    self._values.popitem(last=False)
        return value, False
