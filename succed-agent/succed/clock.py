from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (ISO strings stay sortable in SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
