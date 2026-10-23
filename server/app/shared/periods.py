from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

LAGOS = ZoneInfo("Africa/Lagos")

Period = Literal["today", "7d", "30d"]

_PERIOD_DAYS: dict[str, int] = {"today": 1, "7d": 7, "30d": 30}


def period_start(period: Period, now: datetime | None = None) -> datetime:
    """Start of the period at Lagos midnight; '7d' means today plus the 6 days before it."""
    current = (now or datetime.now(LAGOS)).astimezone(LAGOS)
    first_day = current.date() - timedelta(days=_PERIOD_DAYS[period] - 1)
    return datetime.combine(first_day, time.min, LAGOS)
