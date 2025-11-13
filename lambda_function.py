import json
import requests
import random
from datetime import datetime, timezone

# A set of variants for the closing cue so the skill doesn't repeat the exact
# same sentence every time. Each variant includes a short pause after the
# "Anything else?" question to give emphasis.
CLOSING_CUES = [
    # Friendly, concise
    '<break time="90ms"/> Anything else? <break time="220ms"/> You can also say stop.',
    # Slightly more conversational
    '<break time="120ms"/> Want anything more? <break time="220ms"/> Or say stop to finish.',
    # Casual, human phrasing
    '<break time="80ms"/> I\'m still here — anything else I can help with? <break time="220ms"/> Say stop to end.',
    # Polite offer with pause
    '<break time="100ms"/> Would you like anything else? <break time="220ms"/> You can say stop.',
    # Short and warm
    '<break time="70ms"/> Need anything else? <break time="220ms"/>',
    # Encouraging, alternative phrasing
    '<break time="110ms"/> Anything more I can do for you? <break time="220ms"/> Say stop if you\'re done.',
    # Minimal prompt plus stop hint
    '<break time="90ms"/> Anything else? <break time="220ms"/> Otherwise say stop.',
    # Very casual
    '<break time="80ms"/> Got more questions? <break time="220ms"/> Or say stop when you\'re finished.',
]


def _choose_closing_cue():
    # Use random.choice for variety; tests check for presence of any variant.
    return random.choice(CLOSING_CUES)

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


def get_run_machine_ssml():
    """Return SSML advising whether to run a machine now.

    - If the current hour and the next two hours all have spot prices below 7 cents,
      return: "Yes, now is a good time.".
    - Otherwise, find the start time today (from now until 23:59) of the 3-hour
      contiguous window with the lowest combined price and return:
      "No, run it at TIME" (TIME is formatted as HH:MM).
    """
    entries, error = _fetch_all_price_entries()
    if error:
        return f"<speak>{error}</speak>"

    sample_tz = entries[0]['dt'].tzinfo or timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(sample_tz)
    hour_start = now_local.replace(minute=0, second=0, microsecond=0)

    # Remaining entries for today starting from the current hour (inclusive).
    todays_entries = [
        e for e in entries
        if e['dt'].astimezone(sample_tz).date() == now_local.date()
        and e['dt'].astimezone(sample_tz) >= hour_start
    ]

    if not todays_entries:
        return "<speak>I'm sorry, I couldn't find any remaining electricity price entries for today.</speak>"

    # If we have at least current + next 2 hours, check immediate threshold (7 cents = 0.07 EUR)
    if len(todays_entries) >= 3:
        first_three = todays_entries[:3]
        if all((e['price'] * 100) < 7.0 for e in first_three):
            return "<speak>Yes, now is a good time.</speak>"

    # Find any remaining 3-hour windows today where each hour is <= 7 cents.
    today_windows = []
    if len(todays_entries) >= 3:
        for i in range(0, len(todays_entries) - 2):
            window = todays_entries[i:i+3]
            if all((e['price'] * 100) <= 7.0 for e in window):
                today_windows.append(i)

    if today_windows:
        # Recommend the earliest qualifying window today.
        start_dt = todays_entries[today_windows[0]]['dt']
        start_time_str = _format_hour(start_dt, sample_tz)
        return f"<speak>No, run it at <say-as interpret-as=\"time\">{start_time_str}</say-as>.</speak>"

    # If no qualifying 3-hour window today, and it's 14:00 or later, consult tomorrow's published prices
    if now_local.hour >= 14:
        from datetime import timedelta

        tomorrow_date = (now_local + timedelta(days=1)).date()
        tomorrow_entries = [
            e for e in entries
            if e['dt'].astimezone(sample_tz).date() == tomorrow_date
        ]

        tomorrow_windows = []
        if len(tomorrow_entries) >= 3:
            for i in range(0, len(tomorrow_entries) - 2):
                window = tomorrow_entries[i:i+3]
                if all((e['price'] * 100) <= 7.0 for e in window):
                    tomorrow_windows.append(tomorrow_entries[i]['dt'])

        if tomorrow_windows:
            # Build a list of up to 3 start times and wrap each in say-as time
            times = [_format_hour(dt, sample_tz) for dt in tomorrow_windows[:3]]
            wrapped = " or then at ".join([f'<say-as interpret-as="time">{t}</say-as>' for t in times])
            return f"<speak>Today is not a good time. Tomorrow run it at {wrapped}.</speak>"
        else:
            # Explicitly inform the user if neither today nor tomorrow has any
            # qualifying 3-hour windows.
            return "<speak>No good times today or tomorrow.</speak>"

    # Fallback: find the cheapest contiguous 3-hour window remaining today (by sum)
    if len(todays_entries) < 3:
        return "<speak>I'm sorry, I couldn't find a three-hour window remaining today.</speak>"

    best_idx = None
    best_sum = None
    for i in range(0, len(todays_entries) - 2):
        window = todays_entries[i:i+3]
        s = sum(e['price'] for e in window)
        if best_sum is None or s < best_sum:
            best_sum = s
            best_idx = i

    start_dt = todays_entries[best_idx]['dt']
    start_time_str = _format_hour(start_dt, sample_tz)

    return f"<speak>No, run it at <say-as interpret-as=\"time\">{start_time_str}</say-as>.</speak>"


def _build_ssml_response(ssml, should_end_session=False, reprompt_ssml="<speak>Still Listening.</speak>"):
    response = {
        "outputSpeech": {
            "type": "SSML",
            "ssml": ssml
        },
        "shouldEndSession": should_end_session
    }

    if not should_end_session and reprompt_ssml:
        response["reprompt"] = {
            "outputSpeech": {
                "type": "SSML",
                "ssml": reprompt_ssml
            }
        }

    return {
        "version": "1.0",
        "response": response
    }


def _with_closing_cue(ssml):
    """Ensure the global CLOSING_CUE is appended inside the spoken SSML.

    - If `ssml` already contains a <speak>..</speak> wrapper, insert the cue
      just before the final closing tag.
    - Otherwise, wrap the content in <speak>..</speak> and append the cue.
    """
    if ssml is None:
        return ssml

    s = ssml.strip()
    # If it already looks like an SSML speak block, insert before the final </speak>
    chosen = _choose_closing_cue()
    if s.startswith("<speak"):
        if "</speak>" in s:
            head, tail = s.rsplit("</speak>", 1)
            return f"{head} {chosen}</speak>{tail}"
        else:
            return f"{s} {chosen}"
    # Otherwise wrap and append cue
    return f"<speak>{s} {chosen}</speak>"


def lambda_handler(event, context):
    """Alexa Lambda Function Entry Point"""

    request = (event or {}).get("request", {})
    request_type = request.get("type")

    # 1. Handle LaunchRequest separately
    if request_type == "LaunchRequest":
        welcome_ssml = """
        <speak>
            Ready.
        </speak>
        """
        return _build_ssml_response(welcome_ssml, should_end_session=False, reprompt_ssml=None)

    # 2. Intent requests
    if request_type == "IntentRequest":
        intent = request.get("intent", {})
        intent_name = intent.get("name")
        # For all Intent invocations (except Stop/Cancel which end the session),
        # append the configured closing cue inside the SSML.
        if intent_name == "CheapestPriceIntent":
            ssml = get_cheapest_price_ssml()
            return _build_ssml_response(_with_closing_cue(ssml))

        if intent_name == "ShouldIRunMachineIntent":
            ssml = get_run_machine_ssml()
            return _build_ssml_response(_with_closing_cue(ssml))

        if intent_name in {"GetSpotPriceIntent", "AMAZON.FallbackIntent"}:
            ssml = get_spot_price_ssml()
            return _build_ssml_response(_with_closing_cue(ssml))

        # Stop/Cancel should end the session without the closing cue
        if intent_name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
            return _build_ssml_response("<speak>Goodbye.</speak>", should_end_session=True)

    # 3. Fallback
    return _build_ssml_response(get_spot_price_ssml())
