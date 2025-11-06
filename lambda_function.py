import json
import requests
from datetime import datetime, timezone


def _parse_iso_datetime(s):
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


def get_spot_price():
    # Keep previous behavior by delegating to a helper that returns a plain text
    entries, error = _get_price_entries(4)
    if error:
        return error

    def fmt_cents(price_eur):
        return f"{price_eur * 100:.1f}"

    curr_price = fmt_cents(entries[0]['price'])
    next1 = fmt_cents(entries[1]['price']) if len(entries) > 1 else None
    next2 = fmt_cents(entries[2]['price']) if len(entries) > 2 else None
    next3 = fmt_cents(entries[3]['price']) if len(entries) > 3 else None

    message = f"The current electricity spot price in Finland is {curr_price} cents per kilowatt-hour."

    parts = []
    if next1 is not None:
        parts.append(f"Next hour {next1} cents")
    if next2 is not None:
        parts.append(f"in two hours {next2} cents")
    if next3 is not None:
        parts.append(f"in three hours {next3} cents")

    if parts:
        if len(parts) == 1:
            message += f" {parts[0]}."
        elif len(parts) == 2:
            message += f" {parts[0]}, and {parts[1]}."
        else:
            message += f" {parts[0]}, {parts[1]}, and {parts[2]}."

    if len(entries) < 4:
        message += " I couldn't find price information for all of the next three hours."

    return message


def _fetch_all_price_entries():
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
            dt = _parse_iso_datetime(item.get('DateTime'))
            price = item.get('PriceWithTax')
            if dt is not None and price is not None:
                entries.append({"dt": dt, "price": price})

        if not entries:
            return None, "I'm sorry, I couldn't parse the electricity price data."

        entries.sort(key=lambda x: x['dt'])

        return entries, None

    except requests.exceptions.RequestException:
        return None, "I'm sorry, I couldn't retrieve the electricity price at this moment. Please try again later."


def _get_price_entries(future_hours=4):
    """Fetch hourly entries and return a list of up to `future_hours` entries
    starting from the current hour. Returns (entries, error_message)."""
    entries, error = _fetch_all_price_entries()
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


def get_spot_price_ssml():
    """Return an SSML string to be used as Alexa outputSpeech.ssml.

    Uses short pauses and say-as for numbers to improve clarity.
    """
    entries, error = _get_price_entries(4)
    if error:
        # Wrap error into SSML
        return f"<speak>{error}</speak>"

    def fmt(price_eur):
        return f"{price_eur * 100:.1f}"

    curr = fmt(entries[0]['price'])
    next1 = fmt(entries[1]['price']) if len(entries) > 1 else None
    next2 = fmt(entries[2]['price']) if len(entries) > 2 else None
    next3 = fmt(entries[3]['price']) if len(entries) > 3 else None

    # Build SSML with small breaks and clear number rendering
    parts = []
    # Add a short 100ms break after each announced clause to separate them
    parts.append(f"The current electricity spot price in Finland is <break time=\"200ms\"/> <say-as interpret-as=\"cardinal\">{curr}</say-as> cents per kilowatt-hour. <break time=\"100ms\"/>")

    if next1 is not None:
        parts.append(f"Next hour <break time=\"150ms\"/> <say-as interpret-as=\"cardinal\">{next1}</say-as> cents <break time=\"100ms\"/>")
    if next2 is not None:
        parts.append(f"in two hours <break time=\"150ms\"/> <say-as interpret-as=\"cardinal\">{next2}</say-as> cents <break time=\"100ms\"/>")
    if next3 is not None:
        parts.append(f"in three hours <break time=\"150ms\"/> <say-as interpret-as=\"cardinal\">{next3}</say-as> cents <break time=\"100ms\"/>")

    ssml_body = " ".join(parts)
    if len(entries) < 4:
        ssml_body += " <break time=\"200ms\"/> I couldn't find price information for all of the next three hours."

    return f"<speak>{ssml_body}</speak>"


def _format_hour(dt, tz):
    """Format a datetime into a human-readable local hour string."""
    localized = dt.astimezone(tz)
    return localized.strftime("%H:%M")


def get_cheapest_price_message():
    """Return a human-readable description of today's cheapest hour."""
    entries, error = _fetch_all_price_entries()
    if error:
        return error

    sample_tz = entries[0]['dt'].tzinfo or timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(sample_tz)
    today = now_local.date()

    # Consider only remaining hours starting from the current hour (inclusive).
    hour_start = now_local.replace(minute=0, second=0, microsecond=0)
    todays_entries = [
        e for e in entries
        if e['dt'].astimezone(sample_tz).date() == today
        and e['dt'].astimezone(sample_tz) >= hour_start
    ]
    if not todays_entries:
        return "I'm sorry, I couldn't find any remaining electricity price entries for today."

    cheapest_entry = min(todays_entries, key=lambda e: e['price'])
    cheapest_price = f"{cheapest_entry['price'] * 100:.1f}"
    cheapest_time = _format_hour(cheapest_entry['dt'], sample_tz)

    return (
        "The lowest electricity spot price in Finland today is "
        f"{cheapest_price} cents per kilowatt-hour at {cheapest_time}."
    )


def get_cheapest_price_ssml():
    """Return SSML describing the cheapest hour for the current day."""
    entries, error = _fetch_all_price_entries()
    if error:
        return f"<speak>{error}</speak>"

    sample_tz = entries[0]['dt'].tzinfo or timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(sample_tz)
    today = now_local.date()

    # Consider only remaining hours starting from the current hour (inclusive).
    hour_start = now_local.replace(minute=0, second=0, microsecond=0)
    todays_entries = [
        e for e in entries
        if e['dt'].astimezone(sample_tz).date() == today
        and e['dt'].astimezone(sample_tz) >= hour_start
    ]
    if not todays_entries:
        return "<speak>I'm sorry, I couldn't find any remaining electricity price entries for today.</speak>"

    cheapest_entry = min(todays_entries, key=lambda e: e['price'])
    cheapest_time = _format_hour(cheapest_entry['dt'], sample_tz)
    cheapest_price = f"{cheapest_entry['price'] * 100:.1f}"

    ssml_body = (
        "The lowest electricity spot price in Finland today is "
        f"<say-as interpret-as=\"cardinal\">{cheapest_price}</say-as> cents per kilowatt-hour "
        f"at <say-as interpret-as=\"time\">{cheapest_time}</say-as>."
    )

    return f"<speak>{ssml_body}</speak>"


def _build_ssml_response(ssml):
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "SSML",
                "ssml": ssml
            },
            "shouldEndSession": True
        }
    }


def lambda_handler(event, context):
    """Alexa Lambda Function Entry Point"""

    request = (event or {}).get("request", {})
    request_type = request.get("type")

    if request_type == "IntentRequest":
        intent = request.get("intent", {})
        intent_name = intent.get("name")

        if intent_name == "CheapestPriceIntent":
            return _build_ssml_response(get_cheapest_price_ssml())

        # Default to the existing price overview for the primary intent.
        if intent_name in {"GetSpotPriceIntent", "AMAZON.FallbackIntent"}:
            return _build_ssml_response(get_spot_price_ssml())

    # Handle LaunchRequest or anything unexpected with the standard overview.
    return _build_ssml_response(get_spot_price_ssml())
