from datetime import UTC, datetime


def ensure_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC (matches frontend parseApiDateTime)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_utc_iso(value: datetime) -> str:
    return ensure_utc(value).isoformat()
