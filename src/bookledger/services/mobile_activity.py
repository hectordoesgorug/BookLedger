from __future__ import annotations


MOBILE_ACTIVITY = {
    "pairing_established": ("Device paired", "success"),
    "device_unpaired": ("Device unpaired", "neutral"),
    "batch_started": ("Book transfer started", "neutral"),
    "capture_received": ("Book and photo received", "success"),
    "transfer_completed": ("Book transfer completed", "success"),
    "reception_started": ("Receiving from mobile companion", "warning"),
    "reception_failed": ("Mobile reception failed", "error"),
}


class MobileActivityStore:
    def __init__(self, db):
        self.db = db

    def record(self, event: str) -> None:
        if not isinstance(event, str) or event not in MOBILE_ACTIVITY:
            raise ValueError("Unknown mobile activity event.")
        with self.db.connect() as conn:
            conn.execute("INSERT INTO mobile_activity_events(event) VALUES(?)", (event,))
            conn.execute(
                "DELETE FROM mobile_activity_events WHERE id NOT IN "
                "(SELECT id FROM mobile_activity_events ORDER BY id DESC LIMIT 50)"
            )

    def latest(self) -> list[dict]:
        events = tuple(MOBILE_ACTIVITY)
        with self.db.connect() as conn:
            return [
                {**dict(row), **dict(zip(("description", "level"), MOBILE_ACTIVITY[row["event"]]))}
                for row in conn.execute(
                    f"SELECT event,created_at FROM mobile_activity_events WHERE event IN ({','.join('?' for _ in events)}) ORDER BY id DESC LIMIT 50",
                    events,
                )
            ]
