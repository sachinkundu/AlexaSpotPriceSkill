import random
from datetime import datetime, timezone
import spot_price_api
import utils

# A set of variants for the closing cue so the skill doesn't repeat the exact
# same sentence every time.
CLOSING_CUES = [
    '<break time="90ms"/> Anything else? <break time="220ms"/> You can also say stop.',
    '<break time="120ms"/> Want anything more? <break time="220ms"/> Or say stop to finish.',
    '<break time="80ms"/> I\'m still here — anything else I can help with? <break time="220ms"/> Say stop to end.',
    '<break time="100ms"/> Would you like anything else? <break time="220ms"/> You can say stop.',
    '<break time="70ms"/> Need anything else? <break time="220ms"/>',
    '<break time="110ms"/> Anything more I can do for you? <break time="220ms"/> Say stop if you\'re done.',
    '<break time="90ms"/> Anything else? <break time="220ms"/> Otherwise say stop.',
    '<break time="80ms"/> Got more questions? <break time="220ms"/> Or say stop when you\'re finished.',
]


def _choose_closing_cue():
    return random.choice(CLOSING_CUES)


def with_closing_cue(ssml):
    """Ensure the global CLOSING_CUE is appended inside the spoken SSML."""
    if ssml is None:
        return ssml

    s = ssml.strip()
    chosen = _choose_closing_cue()
    if s.startswith("<speak"):
        if "</speak>" in s:
            head, tail = s.rsplit("</speak>", 1)
            return f"{head} {chosen}</speak>{tail}"
        else:
            return f"{s} {chosen}"
    return f"<speak>{s} {chosen}</speak>"


def build_ssml_response(ssml, should_end_session=False, reprompt_ssml="<speak>Still Listening.</speak>"):
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


def get_spot_price():
    # Plain text version
    entries, error = spot_price_api.get_price_entries(4)
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


def get_spot_price_ssml():
    entries, error = spot_price_api.get_price_entries(4)
    if error:
        return f"<speak>{error}</speak>"

    def fmt(price_eur):
        return f"{price_eur * 100:.1f}"

    curr = fmt(entries[0]['price'])
    next1 = fmt(entries[1]['price']) if len(entries) > 1 else None
    next2 = fmt(entries[2]['price']) if len(entries) > 2 else None
    next3 = fmt(entries[3]['price']) if len(entries) > 3 else None

    parts = []
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


def get_cheapest_price_ssml():
    entries, error = spot_price_api.fetch_all_price_entries()
    if error:
        return f"<speak>{error}</speak>"

    sample_tz = entries[0]['dt'].tzinfo or timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(sample_tz)
    today = now_local.date()

    hour_start = now_local.replace(minute=0, second=0, microsecond=0)
    todays_entries = [
        e for e in entries
        if e['dt'].astimezone(sample_tz).date() == today
        and e['dt'].astimezone(sample_tz) >= hour_start
    ]
    if not todays_entries:
        return "<speak>I'm sorry, I couldn't find any remaining electricity price entries for today.</speak>"

    cheapest_entry = min(todays_entries, key=lambda e: e['price'])
    cheapest_time = utils.format_hour(cheapest_entry['dt'], sample_tz)
    cheapest_price = f"{cheapest_entry['price'] * 100:.1f}"

    ssml_body = (
        "The lowest electricity spot price in Finland today is "
        f"<say-as interpret-as=\"cardinal\">{cheapest_price}</say-as> cents per kilowatt-hour "
        f"at <say-as interpret-as=\"time\">{cheapest_time}</say-as>."
    )

    return f"<speak>{ssml_body}</speak>"


def get_run_machine_ssml():
    entries, error = spot_price_api.fetch_all_price_entries()
    if error:
        return f"<speak>{error}</speak>"

    sample_tz = entries[0]['dt'].tzinfo or timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(sample_tz)
    hour_start = now_local.replace(minute=0, second=0, microsecond=0)

    todays_entries = [
        e for e in entries
        if e['dt'].astimezone(sample_tz).date() == now_local.date()
        and e['dt'].astimezone(sample_tz) >= hour_start
    ]

    if not todays_entries:
        return "<speak>I'm sorry, I couldn't find any remaining electricity price entries for today.</speak>"

    if len(todays_entries) >= 3:
        first_three = todays_entries[:3]
        if all((e['price'] * 100) < 7.0 for e in first_three):
            return "<speak>Yes, now is a good time.</speak>"

    today_windows = []
    if len(todays_entries) >= 3:
        for i in range(0, len(todays_entries) - 2):
            window = todays_entries[i:i+3]
            if all((e['price'] * 100) <= 7.0 for e in window):
                today_windows.append(i)

    if today_windows:
        start_dt = todays_entries[today_windows[0]]['dt']
        start_time_str = utils.format_hour(start_dt, sample_tz)
        return f"<speak>No, run it at <say-as interpret-as=\"time\">{start_time_str}</say-as>.</speak>"

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
            times = [utils.format_hour(dt, sample_tz) for dt in tomorrow_windows[:3]]
            wrapped = " or then at ".join([f'<say-as interpret-as="time">{t}</say-as>' for t in times])
            return f"<speak>Today is not a good time. Tomorrow run it at {wrapped}.</speak>"
        else:
            return "<speak>No good times today or tomorrow.</speak>"

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
    start_time_str = utils.format_hour(start_dt, sample_tz)

    return f"<speak>No, run it at <say-as interpret-as=\"time\">{start_time_str}</say-as>.</speak>"


def get_spot_price_at_hour_ssml(date_value, time_value):
    entries, error = spot_price_api.fetch_all_price_entries()
    if error:
        return f"<speak>{error}</speak>"

    sample_tz = entries[0]['dt'].tzinfo or timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(sample_tz)

    hour = utils.parse_hour_from_time_value(time_value)
    target_date = utils.parse_date_value(date_value, now_local)
    if hour is None or target_date is None:
        return "<speak>I'm sorry, I couldn't understand the requested time.</speak>"

    if date_value == "tomorrow" and now_local.hour < 14:
        return "<speak>Check back after 2 PM since the spot prices are not published yet.</speak>"

    target_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        tzinfo=sample_tz,
    )
    target_hour_start = target_dt.replace(minute=0, second=0, microsecond=0)

    target_entry = None
    for entry in entries:
        entry_dt = entry['dt'].astimezone(sample_tz).replace(minute=0, second=0, microsecond=0)
        if entry_dt == target_hour_start:
            target_entry = entry
            break

    if not target_entry:
        return "<speak>I'm sorry, I couldn't find a spot price for that hour.</speak>"

    price_cents = f"{target_entry['price'] * 100:.1f}"
    time_str = target_hour_start.strftime("%H:%M")
    if date_value == "tomorrow":
        date_phrase = "tomorrow"
    elif date_value == "today" or not date_value:
        date_phrase = "today"
    else:
        date_phrase = target_date.strftime("%Y-%m-%d")

    ssml_body = (
        "The electricity spot price in Finland "
        f"{date_phrase} at <say-as interpret-as=\"time\">{time_str}</say-as> is "
        f"<say-as interpret-as=\"cardinal\">{price_cents}</say-as> cents per kilowatt-hour."
    )
    return f"<speak>{ssml_body}</speak>"
