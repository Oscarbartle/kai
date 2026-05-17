from datetime import datetime


def format_date(date: datetime | str | None) -> str:
    """Return a human-readable date string (e.g. 'Jan 05, 2025').

    Accepts a datetime object, an ISO-format string, or None.
    Returns 'Unknown date' if the input is missing or unparseable.
    """
    if date is None:
        return "Unknown date"
    try:
        if isinstance(date, str):
            date = datetime.fromisoformat(date)
        return date.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return "Unknown date"
