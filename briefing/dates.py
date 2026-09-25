"""Local-time helpers: the edition date is the calendar day in the reader's timezone."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def local_now(now_utc: datetime, tz: str) -> datetime:
    return now_utc.astimezone(ZoneInfo(tz))


def edition_date(now_utc: datetime, tz: str) -> str:
    return local_now(now_utc, tz).date().isoformat()
