from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Return current timezone-aware datetime in Indian Standard Time (IST)."""
    return datetime.now(IST)


def now_ist_str(fmt: str = "%d %b %Y, %I:%M %p IST") -> str:
    """Return formatted current IST date and time string (e.g., 12 Nov 2026, 06:48 PM IST)."""
    return now_ist().strftime(fmt)


def format_datetime_ist(dt_value: datetime | str | None, fmt: str = "%d %b %Y, %I:%M %p IST") -> str:
    """Safely format a datetime object or ISO string into readable IST date & time."""
    if not dt_value:
        return now_ist_str(fmt)
    if isinstance(dt_value, datetime):
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=timezone.utc)
        return dt_value.astimezone(IST).strftime(fmt)
    return str(dt_value)
