"""APScheduler-based daily cutover job.

Runs at 20:00 Asia/Kathmandu every day to:
1. Edit the existing live-totals message into a "Day Closed" summary.
2. Send a fresh live-totals message for the new period.
"""

from __future__ import annotations

from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.error import TelegramError

from app.config import settings
from app.logging_config import get_logger
from app.repositories import BotStateRepo
from app.services import generate_day_closed_summary, update_totals_message
from app.timeutils import get_current_period_start, now_local

log = get_logger(__name__)


async def _day_close_job(bot: Bot) -> None:
    """
    Job that fires at 8 PM cutover.

    At 8 PM, the *current* period_start is already the new period (since
    ``get_current_period_start()`` now returns today-8PM).  The period
    that just ended started at *yesterday* 8 PM.

    Instead of sending a *new* "Day Closed" message, we **edit** the
    existing live-totals message in-place so there is only one message
    per period in the report channel.
    """
    current = get_current_period_start()
    ended_period = current - timedelta(days=1)

    log.info("day_close_job_started", ended_period=str(ended_period))

    try:
        # 1. Edit the existing live-totals message into "Day Closed"
        summary = await generate_day_closed_summary(ended_period)
        stored_id = await BotStateRepo.get("totals_message_id")

        if stored_id:
            try:
                await bot.edit_message_text(
                    chat_id=settings.report_chat_id,
                    message_id=int(stored_id),
                    text=summary,
                    parse_mode="HTML",
                )
            except TelegramError as exc:
                # Message may have been deleted; fall back to a new message
                log.warning("day_close_edit_failed", error=str(exc))
                await bot.send_message(
                    chat_id=settings.report_chat_id,
                    text=summary,
                    parse_mode="HTML",
                )
        else:
            # No existing message to edit – send as new
            await bot.send_message(
                chat_id=settings.report_chat_id,
                text=summary,
                parse_mode="HTML",
            )

        # 2. Clear stored totals message ID so next update creates a fresh one
        await BotStateRepo.set("totals_message_id", "")

        # 3. Send a new totals message for the new period
        await update_totals_message(bot, current)

        log.info("day_close_job_completed", new_period=str(current))

    except Exception:
        log.exception("day_close_job_error")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Create and start the APScheduler with the daily cutover cron job.

    Returns the scheduler instance so the caller can shut it down later.
    """
    scheduler = AsyncIOScheduler()

    trigger = CronTrigger(
        hour=settings.day_cutover_hour,
        minute=0,
        second=0,
        timezone=settings.timezone,
    )

    scheduler.add_job(
        _day_close_job,
        trigger=trigger,
        args=[bot],
        id="day_close",
        name="Daily cutover – close period & reset totals",
        replace_existing=True,
    )

    scheduler.start()
    log.info(
        "scheduler_started",
        cutover_hour=settings.day_cutover_hour,
        timezone=settings.timezone,
    )
    return scheduler
