from bookledger.db.database import Database
from bookledger.services.mobile_activity import MobileActivityStore


def test_mobile_activity_persists_only_allowlisted_events_and_retains_latest_50(tmp_path):
    path = tmp_path / "bookledger.sqlite3"
    activity = MobileActivityStore(Database(path))

    for _ in range(55):
        activity.record("capture_received")
    activity.record("transfer_completed")

    entries = MobileActivityStore(Database(path)).latest()

    assert len(entries) == 50
    assert entries[0]["event"] == "transfer_completed"
    assert entries[0]["description"] == "Book transfer completed"
    assert all(entry["event"] == "capture_received" for entry in entries[1:])


def test_mobile_activity_rejects_arbitrary_values_that_could_contain_secrets(tmp_path):
    activity = MobileActivityStore(Database(tmp_path / "bookledger.sqlite3"))

    try:
        activity.record("pairing_code-secret-token")
    except ValueError as exc:
        assert str(exc) == "Unknown mobile activity event."
    else:
        raise AssertionError("arbitrary event text must not be persisted")
