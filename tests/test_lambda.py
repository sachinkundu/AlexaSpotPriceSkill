import importlib

import pytest


import lambda_function as lf


def make_event(request_type, intent_name=None):
    event = {"request": {"type": request_type}}
    if intent_name:
        event["request"]["type"] = "IntentRequest"
        event["request"]["intent"] = {"name": intent_name}
    return event


def test_launch_request_has_no_closing_cue():
    # LaunchRequest should not have the closing cue appended
    event = make_event("LaunchRequest")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert not any(v in ssml for v in lf.CLOSING_CUES)
    # LaunchResponse in this skill keeps the session open but does not provide a reprompt
    assert resp["response"].get("reprompt") is None


def test_intent_responses_include_closing_cue(monkeypatch):
    # Patch the SSML-producing helpers to avoid network and produce deterministic SSML
    monkeypatch.setattr(lf, "get_spot_price_ssml", lambda: "<speak>Spot price</speak>")

    event = make_event("IntentRequest", intent_name="GetSpotPriceIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert any(v in ssml for v in lf.CLOSING_CUES)
    # The session should remain open (default)
    assert resp["response"].get("shouldEndSession") is False


def test_stop_intent_ends_session_and_no_closing_cue():
    event = make_event("IntentRequest", intent_name="AMAZON.StopIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert ssml == "<speak>Goodbye.</speak>"
    assert resp["response"].get("shouldEndSession") is True
    assert not any(v in ssml for v in lf.CLOSING_CUES)


def test_get_spot_price_formats_prices(monkeypatch):
    # Prepare deterministic entries for current + next three hours
    entries = [
        {"dt": None, "price": 0.05},  # 5.0 cents
        {"dt": None, "price": 0.06},  # 6.0 cents
        {"dt": None, "price": 0.07},  # 7.0 cents
        {"dt": None, "price": 0.08},  # 8.0 cents
    ]

    # Monkeypatch the helper that fetches entries to avoid network
    monkeypatch.setattr(lf, "_get_price_entries", lambda n=4: (entries[:n], None))

    msg = lf.get_spot_price()

    # Check that current and upcoming hour prices are present and formatted
    assert "The current electricity spot price in Finland is 5.0 cents per kilowatt-hour." in msg
    assert "Next hour 6.0 cents" in msg
    assert "in two hours 7.0 cents" in msg
    assert "in three hours 8.0 cents" in msg


def test_cheapest_price_intent_returns_expected_time_and_price(monkeypatch):
    from datetime import datetime, timedelta, timezone

    # Build deterministic hourly entries starting at current hour (UTC)
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    prices = [0.05, 0.04, 0.03, 0.06]  # cheapest is index 2 -> 3.0 cents
    entries = []
    for i, p in enumerate(prices):
        entries.append({"dt": hour_start + timedelta(hours=i), "price": p})

    # Monkeypatch the data fetcher used by get_cheapest_price_ssml
    monkeypatch.setattr(lf, "_fetch_all_price_entries", lambda: (entries, None))

    event = make_event("IntentRequest", intent_name="CheapestPriceIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]

    # The cheapest price should be 3.0 cents
    assert '<say-as interpret-as="cardinal">3.0</say-as>' in ssml

    # Time string should match the formatted hour for the cheapest entry
    cheapest_dt = entries[2]["dt"]
    cheapest_time = lf._format_hour(cheapest_dt, cheapest_dt.tzinfo or timezone.utc)
    assert f'<say-as interpret-as="time">{cheapest_time}</say-as>' in ssml

    # And the global closing cue should be appended
    assert any(v in ssml for v in lf.CLOSING_CUES)


def test_should_i_run_machine_now_yes(monkeypatch):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # First three hours are all below 7 cents (0.05 EUR = 5 cents)
    entries = [
        {"dt": hour_start + timedelta(hours=i), "price": 0.05}
        for i in range(6)
    ]

    monkeypatch.setattr(lf, "_fetch_all_price_entries", lambda: (entries, None))

    event = make_event("IntentRequest", intent_name="ShouldIRunMachineIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]

    assert "Yes, now is a good time." in ssml
    assert any(v in ssml for v in lf.CLOSING_CUES)


def test_should_i_run_machine_now_schedule_later(monkeypatch):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # First three hours expensive, a later 3-hour window is cheap (<=7 cents)
    prices = [0.09, 0.09, 0.09, 0.05, 0.05, 0.05]
    entries = [
        {"dt": hour_start + timedelta(hours=i), "price": p}
        for i, p in enumerate(prices)
    ]

    monkeypatch.setattr(lf, "_fetch_all_price_entries", lambda: (entries, None))

    event = make_event("IntentRequest", intent_name="ShouldIRunMachineIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]

    # Should not say 'Yes' but should recommend a time (the earliest cheap window starts at hour_start+3)
    assert "Yes, now is a good time." not in ssml
    recommended_time = lf._format_hour(entries[3]["dt"], entries[3]["dt"].tzinfo)
    assert f'<say-as interpret-as="time">{recommended_time}</say-as>' in ssml
    assert any(v in ssml for v in lf.CLOSING_CUES)


def test_should_i_run_machine_no_three_hour_window_remaining(monkeypatch):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # Only two remaining hours today -> should trigger the 'couldn't find a three-hour window' message
    entries = [
        {"dt": hour_start + timedelta(hours=i), "price": 0.10}
        for i in range(2)
    ]

    # Provide only today's entries (no error)
    monkeypatch.setattr(lf, "_fetch_all_price_entries", lambda: (entries, None))

    event = make_event("IntentRequest", intent_name="ShouldIRunMachineIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]

    assert "I couldn't find a three-hour window remaining today." in ssml
    # closing cue should still be appended by the handler
    assert any(v in ssml for v in lf.CLOSING_CUES)
    assert resp["response"].get("shouldEndSession") is False


def test_should_i_run_machine_after_14_check_tomorrow(monkeypatch):
    from datetime import datetime, timedelta, timezone

    # Simulate current time _after_ 14:00 UTC so the skill will consult tomorrow
    desired_now = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)

    # Replace the `datetime` symbol in the module with a tiny shim that
    # exposes a `now(tz)` function returning our desired_now. Setting
    # attributes on the real datetime type is not allowed (TypeError), so
    # replace the symbol instead.
    class FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return desired_now
            return desired_now.astimezone(tz)

    monkeypatch.setattr(lf, "datetime", FakeDateTime)

    # Build entries: today (all expensive), tomorrow has a cheap 3-hour window at 08:00-10:00
    today_date = desired_now.date()
    tomorrow_date = (desired_now + timedelta(days=1)).date()

    entries = []
    # Today's remaining hours (15..23) expensive
    for h in range(15, 24):
        entries.append({"dt": datetime(today_date.year, today_date.month, today_date.day, h, tzinfo=timezone.utc), "price": 0.10})

    # Tomorrow: cheap window at 08,09,10
    for h in range(0, 24):
        price = 0.05 if 8 <= h <= 10 else 0.10
        entries.append({"dt": datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day, h, tzinfo=timezone.utc), "price": price})

    monkeypatch.setattr(lf, "_fetch_all_price_entries", lambda: (entries, None))

    event = make_event("IntentRequest", intent_name="ShouldIRunMachineIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]

    # Should recommend tomorrow and include at least the earliest recommended time
    assert "Tomorrow run it at" in ssml
    # earliest recommended time should be 08:00 formatted by _format_hour
    recommended_time = lf._format_hour(entries[-24 + 8]["dt"], entries[-24 + 8]["dt"].tzinfo)
    assert f'<say-as interpret-as="time">{recommended_time}</say-as>' in ssml
    assert any(v in ssml for v in lf.CLOSING_CUES)


def test_should_i_run_machine_after_14_no_good_times(monkeypatch):
    from datetime import datetime, timedelta, timezone

    # Simulate current time after 14:00 UTC so the skill will consult tomorrow
    desired_now = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)

    class FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return desired_now
            return desired_now.astimezone(tz)

    monkeypatch.setattr(lf, "datetime", FakeDateTime)

    # Build entries: today (15..23) none qualify, tomorrow (0..23) also none qualify
    today_date = desired_now.date()
    tomorrow_date = (desired_now + timedelta(days=1)).date()

    entries = []
    for h in range(15, 24):
        entries.append({"dt": datetime(today_date.year, today_date.month, today_date.day, h, tzinfo=timezone.utc), "price": 0.10})

    for h in range(0, 24):
        entries.append({"dt": datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day, h, tzinfo=timezone.utc), "price": 0.10})

    monkeypatch.setattr(lf, "_fetch_all_price_entries", lambda: (entries, None))

    event = make_event("IntentRequest", intent_name="ShouldIRunMachineIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]

    assert "No good times today or tomorrow." in ssml
    assert any(v in ssml for v in lf.CLOSING_CUES)
    assert resp["response"].get("shouldEndSession") is False
