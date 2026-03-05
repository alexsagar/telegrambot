"""Transaction text parser.

Matches messages like:
    "15 to jazz13gv"
    "10.5 to quanshan13gv"
    "  20   TO   some user  "

Only messages matching the ``amount TO person`` pattern are treated as
transactions.  Everything else is silently ignored.
"""

from __future__ import annotations

import re
from typing import Optional

from app.models import ParsedTransaction

# Pattern: <amount> to <person>
_TX_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s+to\s+(.+?)\s*$",
    re.IGNORECASE,
)


def parse_transaction(text: str) -> Optional[ParsedTransaction]:
    """
    Parse a transaction from raw message text.

    Returns a ``ParsedTransaction`` on match, or ``None`` if the message
    does not look like a transaction.
    """
    if not text:
        return None

    match = _TX_PATTERN.match(text)
    if not match:
        return None

    amount = float(match.group(1))
    person = match.group(2).strip()

    if amount <= 0 or not person:
        return None

    return ParsedTransaction(amount=amount, person=person)
