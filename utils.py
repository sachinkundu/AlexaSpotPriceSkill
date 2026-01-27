from datetime import datetime

def format_hour(dt, tz):
    """Format a datetime into a human-readable local hour string."""
    localized = dt.astimezone(tz)
    return localized.strftime("%H:%M")


def parse_hour_from_time_value(time_value):
    if not time_value:
        return None
    parts = time_value.split(":")
    if not parts:
        return None
    try:
        hour = int(parts[0])
    except ValueError:
        return None
    if 0 <= hour <= 23:
        return hour
    return None


def parse_date_value(date_value, now_local):
    if not date_value or date_value == "today":
        return now_local.date()
    if date_value == "tomorrow":
        from datetime import timedelta

        return (now_local + timedelta(days=1)).date()
    try:
        parsed = datetime.fromisoformat(date_value)
    except ValueError:
        return None
    return parsed.date()
