"""MongoDB repository layer – thin, typed wrappers around Motor collections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db import get_db
from app.logging_config import get_logger
from app.models import Direction

log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Transaction repository
# ---------------------------------------------------------------------------

class TransactionRepo:
    """CRUD operations on the ``transactions`` collection."""

    @staticmethod
    def _col():
        return get_db()["transactions"]

    @classmethod
    async def find(cls, chat_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        """Find a transaction by its natural key."""
        return await cls._col().find_one(
            {"chat_id": chat_id, "message_id": message_id}
        )

    @classmethod
    async def upsert(
        cls,
        chat_id: int,
        message_id: int,
        direction: Direction,
        amount: float,
        person: str,
        raw_text: str,
        msg_time: datetime,
        period_start: datetime,
        is_void: bool = False,
    ) -> Dict[str, Any]:
        """
        Insert or update a transaction.

        Uses ``(chat_id, message_id)`` as the unique key.
        Returns the document *after* the upsert.
        """
        now = _utcnow()
        doc: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "direction": direction.value if isinstance(direction, Direction) else direction,
            "amount": amount,
            "person": person,
            "raw_text": raw_text,
            "is_void": is_void,
            "msg_time": msg_time,
            "period_start": period_start,
            "updated_at": now,
        }
        result = await cls._col().find_one_and_update(
            {"chat_id": chat_id, "message_id": message_id},
            {"$set": doc},
            upsert=True,
            return_document=True,  # return after
        )
        log.debug("transaction_upserted", chat_id=chat_id, message_id=message_id)
        return result

    @classmethod
    async def set_void(cls, chat_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        """Mark a transaction as voided. Returns the *old* document."""
        old = await cls._col().find_one_and_update(
            {"chat_id": chat_id, "message_id": message_id},
            {"$set": {"is_void": True, "updated_at": _utcnow()}},
        )
        if old:
            log.info("transaction_voided", chat_id=chat_id, message_id=message_id)
        return old


# ---------------------------------------------------------------------------
# Period totals repository
# ---------------------------------------------------------------------------

class PeriodTotalsRepo:
    """Atomic operations on the ``period_totals`` collection."""

    @staticmethod
    def _col():
        return get_db()["period_totals"]

    @classmethod
    async def inc_totals(
        cls,
        period_start: datetime,
        delta_in: float = 0.0,
        delta_out: float = 0.0,
    ) -> None:
        """
        Atomically increment totals for a period using ``$inc``.

        Creates the document on first use (upsert).
        """
        update: Dict[str, Any] = {
            "$inc": {},
            "$set": {"updated_at": _utcnow()},
        }
        if delta_in:
            update["$inc"]["total_in"] = delta_in
        if delta_out:
            update["$inc"]["total_out"] = delta_out

        if not update["$inc"]:
            return  # nothing to do

        await cls._col().update_one(
            {"_id": period_start},
            update,
            upsert=True,
        )
        log.debug(
            "period_totals_incremented",
            period_start=str(period_start),
            delta_in=delta_in,
            delta_out=delta_out,
        )

    @classmethod
    async def get(cls, period_start: datetime) -> Optional[Dict[str, Any]]:
        """Retrieve totals for a period."""
        return await cls._col().find_one({"_id": period_start})


# ---------------------------------------------------------------------------
# Bot state repository
# ---------------------------------------------------------------------------

class BotStateRepo:
    """Simple key-value store in ``bot_state`` collection."""

    @staticmethod
    def _col():
        return get_db()["bot_state"]

    @classmethod
    async def get(cls, key: str) -> Optional[str]:
        """Get a stored value by key."""
        doc = await cls._col().find_one({"_id": key})
        return doc["value"] if doc else None

    @classmethod
    async def set(cls, key: str, value: str) -> None:
        """Set a key-value pair (upsert)."""
        await cls._col().update_one(
            {"_id": key},
            {"$set": {"value": value, "updated_at": _utcnow()}},
            upsert=True,
        )
