from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum


class MarketDataError(Exception):
    """A safe, normalized provider error."""

    def __init__(self, code: str, message: str, *, status_code: int = 502, retry_after: float | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


class Range(StrEnum):
    DAY_1 = "1D"
    DAY_5 = "5D"
    MONTH_1 = "1M"
    MONTH_3 = "3M"
    MONTH_6 = "6M"
    YTD = "YTD"
    YEAR_1 = "1Y"
    YEAR_5 = "5Y"
    MAX = "MAX"


class Resolution(StrEnum):
    MIN_1 = "1Min"
    MIN_2 = "2Min"
    MIN_5 = "5Min"
    MIN_10 = "10Min"
    MIN_15 = "15Min"
    MIN_30 = "30Min"
    HOUR_1 = "1Hour"
    HOUR_2 = "2Hour"
    HOUR_4 = "4Hour"
    DAY_1 = "1Day"
    WEEK_1 = "1Week"
    MONTH_1 = "1Month"


class Session(StrEnum):
    REGULAR = "regular"
    EXTENDED = "extended"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None
    trade_count: int | None

    def as_json(self) -> dict:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat().replace("+00:00", "Z")
        return result


@dataclass(frozen=True, slots=True)
class BarRequest:
    symbol: str
    start: datetime
    end: datetime
    resolution: Resolution
    feed: str
    adjustment: str
    session: Session


@dataclass(frozen=True, slots=True)
class ProviderResult:
    bars: tuple[Bar, ...]
    pages: int
    entitlement: str
    is_delayed: bool
