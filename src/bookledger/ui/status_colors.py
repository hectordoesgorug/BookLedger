"""Shared semantic colors for concise status indicators."""

SUCCESS_COLOR = "#18723a"
ERROR_COLOR = "#b42318"
NEUTRAL_COLOR = "#64748b"

INVENTORY_STATUS_COLORS = {
    "Available": SUCCESS_COLOR,
    "Sold": ERROR_COLOR,
    "Listed": NEUTRAL_COLOR,
    "Not for Sale": NEUTRAL_COLOR,
}


def status_message_color(message: str) -> str:
    """Return a semantic color for a status message, defaulting to neutral."""
    text = str(message or "").strip().casefold()
    if any(term in text for term in (
        "failed", "error", "could not", "unable to", "unavailable", "timeout", "timed out",
    )):
        return ERROR_COLOR
    if any(term in text for term in (
        "connected", " ready", "retrieved", "success", "saved", " removed", " added",
        "enabled", "photo received", "completed", "cleared", "restored", "exported",
    )):
        return SUCCESS_COLOR
    return NEUTRAL_COLOR
