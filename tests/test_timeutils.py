"""Unit tests for app.timeutils – period boundary computation."""

import pytest
from datetime import datetime
import pytz

from app.timeutils import get_period_start, get_period_end, format_period

_TZ = pytz.timezone("Asia/Kathmandu")


def _make_dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Helper to create an aware datetime in Asia/Kathmandu."""
    return _TZ.localize(datetime(year, month, day, hour, minute))


class TestGetPeriodStart:
    """Test the 8 PM cutover logic."""

    def test_before_cutover(self):
        """10 AM on Mar 5 → period started Mar 4 at 8 PM."""
        dt = _make_dt(2026, 3, 5, 10, 0)
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 4, 20, 0)
        assert result == expected

    def test_at_cutover_exactly(self):
        """Exactly 8 PM on Mar 5 → period started Mar 5 at 8 PM."""
        dt = _make_dt(2026, 3, 5, 20, 0)
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 5, 20, 0)
        assert result == expected

    def test_after_cutover(self):
        """11 PM on Mar 5 → period started Mar 5 at 8 PM."""
        dt = _make_dt(2026, 3, 5, 23, 0)
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 5, 20, 0)
        assert result == expected

    def test_midnight(self):
        """Midnight Mar 6 → period started Mar 5 at 8 PM."""
        dt = _make_dt(2026, 3, 6, 0, 0)
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 5, 20, 0)
        assert result == expected

    def test_just_before_cutover(self):
        """7:59 PM on Mar 5 → period started Mar 4 at 8 PM."""
        dt = _make_dt(2026, 3, 5, 19, 59)
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 4, 20, 0)
        assert result == expected

    def test_early_morning(self):
        """3 AM on Mar 5 → period started Mar 4 at 8 PM."""
        dt = _make_dt(2026, 3, 5, 3, 0)
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 4, 20, 0)
        assert result == expected

    def test_utc_input_converted(self):
        """Test with a UTC datetime – should convert to NPT first."""
        utc = pytz.utc
        # 2 PM UTC = 7:45 PM NPT (before cutover)
        dt = utc.localize(datetime(2026, 3, 5, 14, 0))
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 4, 20, 0)
        assert result == expected

    def test_utc_after_cutover(self):
        """15:00 UTC = 20:45 NPT → period started today at 8 PM NPT."""
        utc = pytz.utc
        dt = utc.localize(datetime(2026, 3, 5, 15, 0))
        result = get_period_start(dt)
        expected = _make_dt(2026, 3, 5, 20, 0)
        assert result == expected


class TestGetPeriodEnd:
    """Test period_end = period_start + 1 day."""

    def test_period_end(self):
        start = _make_dt(2026, 3, 5, 20, 0)
        end = get_period_end(start)
        expected = _make_dt(2026, 3, 6, 20, 0)
        assert end == expected


class TestFormatPeriod:
    """Test human-readable formatting."""

    def test_format(self):
        dt = _make_dt(2026, 3, 5, 20, 0)
        label = format_period(dt)
        assert "2026-03-05" in label
        assert "20:00" in label
