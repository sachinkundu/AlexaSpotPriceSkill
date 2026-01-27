import requests
from datetime import datetime, timezone

def parse_iso_datetime(s):
    """Parse ISO datetimes returned by the API into a timezone-aware datetime.

    The API may return strings with a timezone offset (e.g. +02:00) or with a
    trailing Z for UTC. datetime.fromisoformat doesn't accept 'Z', so handle
    that here.
    """
    if s is None:
        return None
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def fetch_all_price_entries():
    """Fetch all available hourly entries from the API sorted by timestamp.

    Returns (entries, error_message)."""
    url = "https://api.spot-hinta.fi/TodayAndDayForward"
    params = {"priceResolution": 60, "region": "FI"}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) == 0:
            return None, "I'm sorry, I couldn't find any electricity price data right now."

        entries = []
        for item in data:
            dt = parse_iso_datetime(item.get('DateTime'))
            price = item.get('PriceWithTax')
            if dt is not None and price is not None:
                entries.append({"dt": dt, "price": price})

        if not entries:
            return None, "I'm sorry, I couldn't parse the electricity price data."

        entries.sort(key=lambda x: x['dt'])

        return entries, None

    except requests.exceptions.RequestException:
        return None, "I'm sorry, I couldn't retrieve the electricity price at this moment. Please try again later."


def get_price_entries(future_hours=4):
    """Fetch hourly entries and return a list of up to `future_hours` entries
    starting from the current hour. Returns (entries, error_message)."""
    entries, error = fetch_all_price_entries()
    if error:
        return None, error

    sample_tz = entries[0]['dt'].tzinfo or timezone.utc
    now = datetime.now(timezone.utc).astimezone(sample_tz)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    current_index = None
    for i, e in enumerate(entries):
        if e['dt'] == hour_start:
            current_index = i
            break
        if e['dt'] > hour_start:
            current_index = i - 1 if i > 0 else i
            break

    if current_index is None:
        current_index = len(entries) - 1

    desired = []
    for offset in range(0, future_hours):
        idx = current_index + offset
        if 0 <= idx < len(entries):
            desired.append(entries[idx])

    if len(desired) == 0:
        return None, "I'm sorry, I couldn't determine the spot prices for the next hours."

    return desired, None
