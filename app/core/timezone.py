"""Clinic-local clock. All "now"/"today" decisions for scheduling must go through
here so they are correct regardless of which timezone the server runs in.

Uses the configured clinic TIMEZONE (default Asia/Karachi). Falls back to the
machine's own local timezone if the configured zone is unavailable.
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo

from app.core.config import TIMEZONE

try:
    _tz = ZoneInfo(TIMEZONE)
except Exception:
    _tz = None


def now() -> datetime:
    """Current time in the clinic timezone, naive (slot times are stored naive)."""
    if _tz:
        return datetime.now(_tz).replace(tzinfo=None)
    return datetime.now().astimezone().replace(tzinfo=None)


def today() -> date:
    return now().date()
