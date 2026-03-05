"""Unit tests for app.services – delta logic and void processing."""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.models import Direction
from app.services import (
    _effective_amount,
    _delta_fields,
    process_transaction,
    void_transaction,
    _build_totals_text,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestEffectiveAmount:
    def test_normal(self):
        assert _effective_amount({"amount": 10.0, "is_void": False}) == 10.0

    def test_voided(self):
        assert _effective_amount({"amount": 10.0, "is_void": True}) == 0.0

    def test_missing_void_flag(self):
        assert _effective_amount({"amount": 5.0}) == 5.0


class TestDeltaFields:
    def test_in_direction(self):
        assert _delta_fields("IN", 10.0) == (10.0, 0.0)

    def test_out_direction(self):
        assert _delta_fields("OUT", 10.0) == (0.0, 10.0)


class TestBuildTotalsText:
    def test_positive_profit(self):
        text = _build_totals_text(100.0, 40.0, "2026-03-05 20:00 NPT")
        assert "60.00" in text
        assert "+" in text

    def test_negative_profit(self):
        text = _build_totals_text(30.0, 50.0, "2026-03-05 20:00 NPT")
        assert "-20.00" in text

    def test_zero_profit(self):
        text = _build_totals_text(50.0, 50.0, "2026-03-05 20:00 NPT")
        assert "+0.00" in text


# ---------------------------------------------------------------------------
# process_transaction (with mocked repos)
# ---------------------------------------------------------------------------

class TestProcessTransaction:
    """Test the delta logic in process_transaction."""

    @pytest.mark.asyncio
    async def test_new_transaction(self):
        """First-time transaction → delta equals the full amount."""
        with (
            patch("app.services.TransactionRepo") as MockTxnRepo,
            patch("app.services.PeriodTotalsRepo") as MockPeriodRepo,
        ):
            MockTxnRepo.find = AsyncMock(return_value=None)
            MockTxnRepo.upsert = AsyncMock(return_value={})

            MockPeriodRepo.inc_totals = AsyncMock()

            msg_time = datetime(2026, 3, 5, 21, 0, tzinfo=timezone.utc)

            await process_transaction(
                chat_id=-100,
                message_id=1,
                direction=Direction.IN,
                amount=15.0,
                person="alice",
                raw_text="15 to alice",
                msg_time=msg_time,
            )

            MockTxnRepo.upsert.assert_called_once()
            MockPeriodRepo.inc_totals.assert_called_once()
            call_kwargs = MockPeriodRepo.inc_totals.call_args
            assert call_kwargs.kwargs["delta_in"] == 15.0
            assert call_kwargs.kwargs["delta_out"] == 0.0

    @pytest.mark.asyncio
    async def test_edit_transaction_delta(self):
        """Editing 20→10 should produce delta = -10."""
        old_doc = {
            "amount": 20.0,
            "is_void": False,
            "period_start": datetime(2026, 3, 4, 20, 0, tzinfo=timezone.utc),
            "direction": "OUT",
        }
        with (
            patch("app.services.TransactionRepo") as MockTxnRepo,
            patch("app.services.PeriodTotalsRepo") as MockPeriodRepo,
        ):
            MockTxnRepo.find = AsyncMock(return_value=old_doc)
            MockTxnRepo.upsert = AsyncMock(return_value={})
            MockPeriodRepo.inc_totals = AsyncMock()

            msg_time = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)

            await process_transaction(
                chat_id=-100,
                message_id=1,
                direction=Direction.OUT,
                amount=10.0,
                person="bob",
                raw_text="10 to bob",
                msg_time=msg_time,
            )

            MockPeriodRepo.inc_totals.assert_called_once()
            call_kwargs = MockPeriodRepo.inc_totals.call_args
            # OUT direction, delta = 10 - 20 = -10
            assert call_kwargs.kwargs["delta_out"] == -10.0
            assert call_kwargs.kwargs["delta_in"] == 0.0


class TestVoidTransaction:
    """Test the void service."""

    @pytest.mark.asyncio
    async def test_void_existing(self):
        old_doc = {
            "amount": 25.0,
            "is_void": False,
            "direction": "IN",
            "period_start": datetime(2026, 3, 4, 20, 0, tzinfo=timezone.utc),
        }
        with (
            patch("app.services.TransactionRepo") as MockTxnRepo,
            patch("app.services.PeriodTotalsRepo") as MockPeriodRepo,
        ):
            MockTxnRepo.find = AsyncMock(return_value=old_doc)
            MockTxnRepo.set_void = AsyncMock(return_value=old_doc)
            MockPeriodRepo.inc_totals = AsyncMock()

            result = await void_transaction(-100, 1)
            assert result is True

            MockPeriodRepo.inc_totals.assert_called_once()
            call_kwargs = MockPeriodRepo.inc_totals.call_args
            assert call_kwargs.kwargs["delta_in"] == -25.0

    @pytest.mark.asyncio
    async def test_void_not_found(self):
        with patch("app.services.TransactionRepo") as MockTxnRepo:
            MockTxnRepo.find = AsyncMock(return_value=None)
            result = await void_transaction(-100, 999)
            assert result is False

    @pytest.mark.asyncio
    async def test_void_already_voided(self):
        old_doc = {"amount": 10.0, "is_void": True, "direction": "IN"}
        with patch("app.services.TransactionRepo") as MockTxnRepo:
            MockTxnRepo.find = AsyncMock(return_value=old_doc)
            result = await void_transaction(-100, 1)
            assert result is False
