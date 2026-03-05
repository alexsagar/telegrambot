"""Application entry-point – wires everything together and starts polling."""

from __future__ import annotations

import asyncio

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import settings
from app.db import close_client, ensure_indexes
from app.logging_config import get_logger, setup_logging
from app.scheduler import setup_scheduler
from app.services import update_totals_message
from app.telegram_handlers import (
    handle_edited_message,
    handle_message,
    handle_ping,
    handle_void_command,
)
from app.timeutils import get_current_period_start

log = get_logger(__name__)


async def post_init(application: Application) -> None:
    """Called after the Application is fully initialized (bot ready)."""
    log.info("post_init_start")

    # Ensure MongoDB indexes
    await ensure_indexes()

    # Start the day-close scheduler
    scheduler = setup_scheduler(application.bot)
    application.bot_data["scheduler"] = scheduler

    # Refresh the totals message on startup
    period_start = get_current_period_start()
    await update_totals_message(application.bot, period_start)

    log.info("post_init_complete")


async def post_shutdown(application: Application) -> None:
    """Graceful shutdown hook."""
    scheduler = application.bot_data.get("scheduler")
    if scheduler:
        scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
    await close_client()
    log.info("shutdown_complete")


def main() -> None:
    """Build and run the Telegram bot application."""
    setup_logging()
    log.info("starting_bot", timezone=settings.timezone)

    # Build the application
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register handler for /void command
    app.add_handler(CommandHandler("void", handle_void_command))

    # Register handler for /ping command
    app.add_handler(CommandHandler("ping", handle_ping))

    # Register handler for new messages (IN/OUT groups)
    chat_filter = filters.Chat(chat_id=[settings.in_chat_id, settings.out_chat_id])
    app.add_handler(
        MessageHandler(
            chat_filter & filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    # Register handler for edited messages (IN/OUT groups)
    app.add_handler(
        MessageHandler(
            chat_filter & filters.TEXT & filters.UpdateType.EDITED_MESSAGE,
            handle_edited_message,
        )
    )

    # Start polling
    log.info("polling_started")
    app.run_polling(
        allowed_updates=["message", "edited_message"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
