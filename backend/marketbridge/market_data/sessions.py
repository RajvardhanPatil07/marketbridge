from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

from .models import Bar, Resolution, Session

NEW_YORK = ZoneInfo("America/New_York")


def filter_session(bars: tuple[Bar, ...], session: Session, resolution: Resolution) -> tuple[Bar, ...]:
    # Daily and coarser Alpaca bars are stamped at the session date boundary,
    # not at an intraday market time. Time-of-day filtering would remove every
    # bar from 6M, YTD, 1Y, 5Y, and MAX responses.
    if session == Session.ALL or resolution in {Resolution.DAY_1, Resolution.WEEK_1, Resolution.MONTH_1}:
        return bars
    start, end = (time(9, 30), time(16, 0)) if session == Session.REGULAR else (time(4, 0), time(20, 0))
    return tuple(bar for bar in bars if bar.timestamp.astimezone(NEW_YORK).weekday() < 5 and start <= bar.timestamp.astimezone(NEW_YORK).time() < end)
