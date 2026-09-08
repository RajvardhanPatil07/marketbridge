"""Small standard-library domain types for the deterministic synthetic demo."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

MODEL_VERSION = "synthetic-rules-v1.0.0"
DATA_MODE = "SYNTHETIC_TEST"
SYMBOLS = {"NVDA": 182.5, "TSLA": 346.8}
START = datetime(2026, 9, 8, 13, 30, tzinfo=timezone.utc)
SOURCE_CONFIG = {
    "iex": ("IEX · simulated", "underlying-a"),
    "independent": ("Independent venue · simulated", "underlying-b"),
    "reseller": ("IEX reseller · simulated", "underlying-a"),
    "auction": ("Official opening auction · simulated", "primary-auction"),
    "qqq": ("QQQ factor · simulated", "factor-market"),
}


def timestamp(seconds: float) -> str:
    return (START + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a numeric value")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Expected a finite value")
    return value


@dataclass
class SourceState:
    source_id: str
    price: float | None = None
    event_time: float | None = None
    latest_seen_time: float | None = None
    quarantined: bool = False
    candidate_price: float | None = None
    candidate_time: float | None = None


@dataclass
class PaperAccount:
    """One fixed long unit; liquidation never opens another position."""

    entry: float
    units: float = 1.0
    liquidated: bool = False
    exited_equity: float | None = None

    @property
    def initial_equity(self) -> float:
        return 0.20 * self.entry * self.units

    def equity_at(self, price: float | None) -> float | None:
        if self.liquidated:
            return self.exited_equity
        if price is None:
            return None
        return self.initial_equity + self.units * (price - self.entry)

    def mark(self, price: float | None) -> float | None:
        equity = self.equity_at(price)
        if not self.liquidated and equity is not None and equity < 0.10 * self.entry * self.units:
            self.liquidated = True
            self.exited_equity = equity
        return equity

    def ex_post_equity(self, independent_outcome: float | None) -> float | None:
        return self.equity_at(independent_outcome)
