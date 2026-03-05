"""Business-logic service layer.

Orchestrates transaction processing, delta computation, void handling,
and totals-message management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from telegram import Bot
from telegram.error import TelegramError

from app.config import settings
from app.logging_config import get_logger
from app.models import Direction
from app.repositories import BotStateRepo, PeriodTotalsRepo, TransactionRepo
from app.timeutils import format_period, get_period_start

log = get_logger(__name__)

_STATE_KEY_TOTALS_MSG = "totals_message_id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _effective_amount(txn: Dict[str, Any]) -> float:
    """Return the amount that should count toward totals (0 if voided)."""
    if txn.get("is_void"):
        return 0.0
    return float(txn["amount"])


def _delta_fields(direction: str, delta: float) -> tuple[float, float]:
    """Split a delta value into (delta_in, delta_out)."""
    if direction == Direction.IN.value:
        return delta, 0.0
    return 0.0, delta


# ---------------------------------------------------------------------------
# Transaction processing
# ---------------------------------------------------------------------------

async def process_transaction(
    chat_id: int,
    message_id: int,
    direction: Direction,
    amount: float,
    person: str,
    raw_text: str,
    msg_time: datetime,
) -> None:
    """
    Process a new or edited transaction.

    1. Look up the old record (if any) to get the old effective amount.
    2. Upsert the new record.
    3. Compute delta = new_effective - old_effective.
    4. Apply delta atomically to ``period_totals``.

    The period_start is always derived from ``msg_time`` (the original
    message timestamp), **not** from the edit timestamp.
    """
    old_doc = await TransactionRepo.find(chat_id, message_id)
    old_effective = _effective_amount(old_doc) if old_doc else 0.0

    # Period is always based on the *original* message time
    if old_doc and "period_start" in old_doc:
        period_start = old_doc["period_start"]
    else:
        period_start = get_period_start(msg_time)

    # Preserve void status if already voided – an edit should not un-void
    is_void = old_doc.get("is_void", False) if old_doc else False

    await TransactionRepo.upsert(
        chat_id=chat_id,
        message_id=message_id,
        direction=direction,
        amount=amount,
        person=person,
        raw_text=raw_text,
        msg_time=msg_time,
        period_start=period_start,
        is_void=is_void,
    )

    new_effective = 0.0 if is_void else amount
    delta = new_effective - old_effective

    if delta != 0.0:
        d_in, d_out = _delta_fields(direction.value, delta)
        await PeriodTotalsRepo.inc_totals(period_start, delta_in=d_in, delta_out=d_out)
        log.info(
            "transaction_processed",
            chat_id=chat_id,
            message_id=message_id,
            direction=direction.value,
            amount=amount,
            delta=delta,
        )


# ---------------------------------------------------------------------------
# Void
# ---------------------------------------------------------------------------

async def void_transaction(chat_id: int, message_id: int) -> bool:
    """
    Void a transaction so it no longer contributes to totals.

    Returns ``True`` if a transaction was actually voided, ``False`` if
    the transaction was not found or already voided.
    """
    old_doc = await TransactionRepo.find(chat_id, message_id)
    if not old_doc:
        log.warning("void_no_transaction", chat_id=chat_id, message_id=message_id)
        return False

    if old_doc.get("is_void"):
        log.info("void_already_voided", chat_id=chat_id, message_id=message_id)
        return False

    old_effective = _effective_amount(old_doc)
    await TransactionRepo.set_void(chat_id, message_id)

    if old_effective != 0.0:
        direction = old_doc["direction"]
        d_in, d_out = _delta_fields(direction, -old_effective)
        period_start = old_doc["period_start"]
        await PeriodTotalsRepo.inc_totals(period_start, delta_in=d_in, delta_out=d_out)

    log.info("transaction_voided_service", chat_id=chat_id, message_id=message_id)
    return True


# ---------------------------------------------------------------------------
# Totals message
# ---------------------------------------------------------------------------

def _build_totals_text(
    total_in: float,
    total_out: float,
    period_label: str,
) -> str:
    """Format the totals message text."""
    profit = total_in - total_out
    sign = "+" if profit >= 0 else ""
    return (
        f"📊 <b>Live Totals</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Period: <code>{period_label}</code>\n\n"
        f"💰 Total IN:  <code>{total_in:,.2f}</code>\n"
        f"💸 Total OUT: <code>{total_out:,.2f}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 Profit/Loss: <code>{sign}{profit:,.2f}</code>"
    )


async def get_totals_text(period_start: datetime) -> str:
    """Build the totals string for a given period."""
    doc = await PeriodTotalsRepo.get(period_start)
    total_in = doc["total_in"] if doc else 0.0
    total_out = doc["total_out"] if doc else 0.0
    period_label = format_period(period_start)
    return _build_totals_text(total_in, total_out, period_label)


async def update_totals_message(bot: Bot, period_start: datetime) -> None:
    """
    Edit (or create) the single totals message in the DAILY REPORT group.

    Stores the ``message_id`` in ``bot_state`` so we can keep editing it.
    """
    text = await get_totals_text(period_start)

    stored_id = await BotStateRepo.get(_STATE_KEY_TOTALS_MSG)

    if stored_id:
        try:
            await bot.edit_message_text(
                chat_id=settings.report_chat_id,
                message_id=int(stored_id),
                text=text,
                parse_mode="HTML",
            )
            return
        except TelegramError as exc:
            # Message may have been deleted or is too old to edit
            log.warning("totals_edit_failed", error=str(exc))

    # Send a new message and store its ID
    msg = await bot.send_message(
        chat_id=settings.report_chat_id,
        text=text,
        parse_mode="HTML",
    )
    await BotStateRepo.set(_STATE_KEY_TOTALS_MSG, str(msg.message_id))
    log.info("totals_message_created", message_id=msg.message_id)


# ---------------------------------------------------------------------------
# Day-close summary
# ---------------------------------------------------------------------------

async def generate_day_closed_summary(period_start: datetime) -> str:
    """Generate the 'Day Closed' summary for a completed period."""
    doc = await PeriodTotalsRepo.get(period_start)
    total_in = doc["total_in"] if doc else 0.0
    total_out = doc["total_out"] if doc else 0.0
    profit = total_in - total_out
    sign = "+" if profit >= 0 else ""
    period_label = format_period(period_start)

    return (
        f"🔒 <b>Day Closed</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Period: <code>{period_label}</code>\n\n"
        f"💰 Total IN:  <code>{total_in:,.2f}</code>\n"
        f"💸 Total OUT: <code>{total_out:,.2f}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 Profit/Loss: <code>{sign}{profit:,.2f}</code>\n\n"
        f"✅ A new period has started."
    )
