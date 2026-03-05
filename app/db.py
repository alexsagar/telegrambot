"""MongoDB connection and index management using Motor (async)."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING

from app.config import settings
from app.logging_config import get_logger

log = get_logger(__name__)

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Return the singleton Motor client (creates on first call)."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
        log.info("mongo_client_created", uri=settings.mongo_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Return the application database handle."""
    return get_client()[settings.mongo_db_name]


async def ensure_indexes() -> None:
    """
    Create required MongoDB indexes idempotently.

    * ``transactions``: unique compound on (chat_id, message_id), plus
      indexes on period_start and direction for efficient queries.
    * ``period_totals``: _id is period_start (natural uniqueness).
    * ``bot_state``: _id is the key string (natural uniqueness).
    """
    db = get_db()

    txn_col = db["transactions"]
    await txn_col.create_indexes([
        IndexModel(
            [("chat_id", ASCENDING), ("message_id", ASCENDING)],
            unique=True,
            name="ux_chat_msg",
        ),
        IndexModel(
            [("period_start", ASCENDING), ("direction", ASCENDING)],
            name="ix_period_direction",
        ),
    ])

    log.info("indexes_ensured")


async def close_client() -> None:
    """Gracefully close the Motor client."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        log.info("mongo_client_closed")
