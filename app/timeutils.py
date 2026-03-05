"""Time utilities for the 8 PM Asia/Kathmandu accounting period cutover."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from app.config import settings

_TZ = pytz.timezone(settings.timezone)


def now_local() -> datetime:
    """Return the current time in the configured timezone (aware)."""
    return datetime.now(tz=_TZ)


def to_local(dt: datetime) -> datetime:
    """Convert an aware datetime to the configured local timezone."""
    return dt.astimezone(_TZ)


def get_period_start(dt: datetime) -> datetime:
    """
    Compute the accounting-period start for a given timestamp.

    A "day" runs from 8:00 PM to the next day's 8:00 PM.

    * If *dt* is at or after the cutover hour today → period started today at cutover.
    * If *dt* is before the cutover hour today → period started *yesterday* at cutover.

    Returns an aware datetime in the configured timezone.
    """
    local = to_local(dt)
    cutover_today = local.replace(
        hour=settings.day_cutover_hour,
        minute=0,
        second=0,
        microsecond=0,
    )

    if local >= cutover_today:
        return cutover_today
    else:
        return cutover_today - timedelta(days=1)


def get_current_period_start() -> datetime:
    """Return the period-start for the *current* moment."""
    return get_period_start(now_local())


def format_period(period_start: datetime) -> str:
    """Human-readable label, e.g. '8:00 PM - 8:00 PM (Mar 4 - Mar 5)'."""
    local_start = to_local(period_start)
    local_end = to_local(get_period_end(period_start))
    time_fmt = "%-I:%M %p"  # 8:00 PM
    # Windows strftime uses %#I instead of %-I
    import os
    if os.name == "nt":
        time_fmt = "%#I:%M %p"
    start_time = local_start.strftime(time_fmt)
    end_time = local_end.strftime(time_fmt)
    start_date = local_start.strftime("%b %d")
    end_date = local_end.strftime("%b %d")
    return f"{start_time} - {end_time} ({start_date} - {end_date})"


def get_period_end(period_start: datetime) -> datetime:
    """Return the end (exclusive) of the given period (next day's cutover)."""
    return period_start + timedelta(days=1)
