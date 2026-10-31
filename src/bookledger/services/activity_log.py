"""Safe, compact activity events for BookLedger's optional diagnostic log."""

from __future__ import annotations

import re

_EVENT = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_IDENTIFIERS = frozenset({"copy_id", "book_id", "sale_id", "template_id", "count"})


def log_activity(logger, event: str, *, level=None, **details) -> None:
    """Log an event and numeric identifiers only; never serialize arbitrary data."""
    if not isinstance(event, str) or not _EVENT.fullmatch(event):
        raise ValueError("Activity event names must be lowercase snake case.")
    safe = []
    for key, value in details.items():
        if key not in _IDENTIFIERS or isinstance(value, bool) or not isinstance(value, int):
            continue
        safe.append(f"{key}={value}")
    logger.log(level or 20, "%s%s", event, (" " + " ".join(safe)) if safe else "")
