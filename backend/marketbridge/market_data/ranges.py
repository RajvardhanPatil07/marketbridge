from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone

from .models import Range, Resolution

DEFAULT_RESOLUTIONS = {
    Range.DAY_1: Resolution.MIN_1,
    Range.DAY_5: Resolution.MIN_5,
    Range.MONTH_1: Resolution.MIN_30,
    Range.MONTH_3: Resolution.HOUR_1,
    Range.MONTH_6: Resolution.DAY_1,
    Range.YTD: Resolution.DAY_1,
    Range.YEAR_1: Resolution.DAY_1,
    Range.YEAR_5: Resolution.WEEK_1,
    Range.MAX: Resolution.MONTH_1,
}


def _subtract_months(value: datetime, months: int) -> datetime:
    index = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def bounds_for_range(selected: Range, now: datetime | None = None) -> tuple[datetime, datetime]:
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if selected == Range.DAY_1:
        start = end - timedelta(days=1)
    elif selected == Range.DAY_5:
        # Seven calendar days normally contains five US trading days. The service
        # never fills weekends or market holidays with synthetic candles.
        start = end - timedelta(days=7)
    elif selected == Range.MONTH_1:
        start = _subtract_months(end, 1)
    elif selected == Range.MONTH_3:
        start = _subtract_months(end, 3)
    elif selected == Range.MONTH_6:
        start = _subtract_months(end, 6)
    elif selected == Range.YTD:
        start = end.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif selected == Range.YEAR_1:
        start = _subtract_months(end, 12)
    elif selected == Range.YEAR_5:
        start = _subtract_months(end, 60)
    else:
        # Alpaca coverage varies by subscription and symbol. Start with a bounded
        # window; clients can progressively request older windows.
        start = _subtract_months(end, 120)
    return start, end
