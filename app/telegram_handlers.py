"""Telegram message and command handlers."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from app.config import settings
from app.logging_config import get_logger
from app.models import Direction
from app.parsing import parse_transaction
from app.services import process_transaction, update_totals_message, void_transaction
from app.timeutils import get_current_period_start, get_period_start

log = get_logger(__name__)

# Chat ID → Direction mapping
_DIRECTION_MAP: dict[int, Direction] = {
    settings.in_chat_id: Direction.IN,
    settings.out_chat_id: Direction.OUT,
}


# ---------------------------------------------------------------------------
# /ping
# ---------------------------------------------------------------------------

async def handle_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with Pong! to confirm the bot is alive."""
    if update.effective_message:
        await update.effective_message.reply_text("🏓 Pong!")


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle new messages in IN / OUT groups."""
    message = update.effective_message
    if not message or not message.text:
        return

    chat_id = message.chat_id
    direction = _DIRECTION_MAP.get(chat_id)
    if direction is None:
        return  # Not a monitored group

    parsed = parse_transaction(message.text)
    if parsed is None:
        return  # Not a transaction

    try:
        await process_transaction(
            chat_id=chat_id,
            message_id=message.message_id,
            direction=direction,
            amount=parsed.amount,
            person=parsed.person,
            raw_text=message.text,
            msg_time=message.date,
        )

        period_start = get_period_start(message.date)
        await update_totals_message(context.bot, period_start)

    except Exception:
        log.exception("handle_message_error", chat_id=chat_id, message_id=message.message_id)


async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle edited messages in IN / OUT groups.

    The delta logic in ``services.process_transaction`` correctly adjusts
    totals when the amount or person changes.
    """
    message = update.edited_message
    if not message or not message.text:
        return

    chat_id = message.chat_id
    direction = _DIRECTION_MAP.get(chat_id)
    if direction is None:
        return

    parsed = parse_transaction(message.text)
    if parsed is None:
        return  # Edited to non-transaction text – we leave the old record

    try:
        await process_transaction(
            chat_id=chat_id,
            message_id=message.message_id,
            direction=direction,
            amount=parsed.amount,
            person=parsed.person,
            raw_text=message.text,
            msg_time=message.date,
        )

        period_start = get_period_start(message.date)
        await update_totals_message(context.bot, period_start)

    except Exception:
        log.exception("handle_edited_message_error", chat_id=chat_id, message_id=message.message_id)


# ---------------------------------------------------------------------------
# /void command
# ---------------------------------------------------------------------------

async def handle_void_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /void command (must be a reply to an existing transaction).

    Only admins (or the group creator) may void transactions.
    """
    message = update.effective_message
    if not message:
        return

    chat_id = message.chat_id
    if chat_id not in _DIRECTION_MAP:
        return  # Only works in IN/OUT groups

    # Must be a reply
    reply = message.reply_to_message
    if not reply:
        await message.reply_text("⚠️ Use /void as a reply to the transaction you want to void.")
        return

    # Check admin status
    try:
        member = await context.bot.get_chat_member(chat_id, message.from_user.id)
        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await message.reply_text("🚫 Only admins can void transactions.")
            return
    except Exception:
        log.exception("admin_check_failed", chat_id=chat_id, user_id=message.from_user.id)
        await message.reply_text("⚠️ Could not verify admin status. Please try again.")
        return

    # Void the transaction
    try:
        voided = await void_transaction(chat_id, reply.message_id)
        if voided:
            await message.reply_text("✅ Transaction voided successfully.")
            period_start = get_current_period_start()
            await update_totals_message(context.bot, period_start)
        else:
            await message.reply_text("ℹ️ Transaction not found or already voided.")
    except Exception:
        log.exception("void_error", chat_id=chat_id, message_id=reply.message_id)
        await message.reply_text("⚠️ An error occurred while voiding. Please try again.")
