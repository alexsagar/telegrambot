"""Pydantic models for the ledger bot domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Direction(str, Enum):
    """Transaction direction."""
    IN = "IN"
    OUT = "OUT"


# ---------------------------------------------------------------------------
# Parser output (lightweight dataclass)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ParsedTransaction:
    """Result of parsing a transaction message."""
    amount: float
    person: str


# ---------------------------------------------------------------------------
# MongoDB document models
# ---------------------------------------------------------------------------

class TransactionRecord(BaseModel):
    """Represents a single transaction stored in MongoDB."""

    chat_id: int
    message_id: int
    direction: Direction
    amount: float
    person: str
    raw_text: str
    is_void: bool = False
    msg_time: datetime
    period_start: datetime
    updated_at: datetime

    class Config:
        use_enum_values = True


class PeriodTotals(BaseModel):
    """Aggregated totals for a single accounting period."""

    period_start: datetime = Field(alias="_id")
    total_in: float = 0.0
    total_out: float = 0.0
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class BotState(BaseModel):
    """Generic key-value state for the bot (e.g. totals_message_id)."""

    key: str = Field(alias="_id")
    value: str
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
