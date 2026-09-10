"""US equity session classification with explicit prototype calendar boundaries."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .models import Session

NEW_YORK = ZoneInfo("America/New_York")

# NYSE full-day holidays for the checked-in demo year. Production should replace
# this adapter with a maintained exchange-calendar service and verified updates.
FULL_HOLIDAYS_2026 = {
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
}
EARLY_CLOSES_2026 = {date(2026, 11, 27), date(2026, 12, 24)}


def equity_session(at: datetime) -> Session:
    """Classify an aware timestamp; ZoneInfo handles US DST transitions."""
    if at.tzinfo is None:
        raise ValueError("session timestamp must include a timezone")
    local = at.astimezone(NEW_YORK)
    if local.weekday() >= 5 or local.date() in FULL_HOLIDAYS_2026:
        return Session.CLOSED
    wall = local.time().replace(tzinfo=None)
    close = time(13) if local.date() in EARLY_CLOSES_2026 else time(16)
    if time(4) <= wall < time(9, 30):
        return Session.PRE
    if time(9, 30) <= wall < close:
        return Session.REGULAR
    if close <= wall < time(20):
        return Session.POST
    return Session.OVERNIGHT
