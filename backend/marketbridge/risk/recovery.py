"""Small per-symbol hysteresis state machine for restored evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock


@dataclass
class RecoveryState:
    state: str = "NORMAL"
    stable_count: int = 0
    recovery_started: datetime | None = None


class RecoveryTracker:
    def __init__(self, stable_observations: int = 3, minimum_duration_seconds: float = 2.0):
        self.stable_observations = stable_observations
        self.minimum_duration = timedelta(seconds=minimum_duration_seconds)
        self._states: dict[str, RecoveryState] = {}
        self._lock = Lock()

    def update(self, symbol: str, raw_state: str, stable: bool, now: datetime) -> dict:
        with self._lock:
            state = self._states.setdefault(symbol, RecoveryState())
            if raw_state in {"HALTED", "RESTRICTED"}:
                state.state = raw_state
                state.stable_count = 0
                state.recovery_started = None
            elif state.state in {"HALTED", "RESTRICTED", "RECOVERY_PENDING"}:
                if not stable:
                    state.state = "HALTED"
                    state.stable_count = 0
                    state.recovery_started = None
                else:
                    state.state = "RECOVERY_PENDING"
                    state.recovery_started = state.recovery_started or now
                    state.stable_count += 1
                    if state.stable_count >= self.stable_observations and now - state.recovery_started >= self.minimum_duration:
                        state.state = "NORMAL"
                        state.stable_count = 0
                        state.recovery_started = None
            else:
                state.state = raw_state
            elapsed = (now - state.recovery_started).total_seconds() if state.recovery_started else 0.0
            return {
                "state": state.state,
                "stable_observations": state.stable_count,
                "required_observations": self.stable_observations,
                "elapsed_seconds": round(elapsed, 3),
                "minimum_duration_seconds": self.minimum_duration.total_seconds(),
            }
