import pytest
from datetime import datetime, timezone, timedelta
import lambda_function as lf
import ssml_builder
import spot_price_api

def make_event(request_type, intent_name=None, slots=None):
    event = {"request": {"type": request_type}}
    if intent_name:
        event["request"]["type"] = "IntentRequest"
        event["request"]["intent"] = {"name": intent_name}
        if slots:
            event["request"]["intent"]["slots"] = slots
    return event


def test_launch_request_has_no_closing_cue():
    # LaunchRequest should not have the closing cue appended
    event = make_event("LaunchRequest")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert not any(v in ssml for v in ssml_builder.CLOSING_CUES)
    # LaunchResponse in this skill keeps the session open but does not provide a reprompt (passed None)
    # Wait, original passed None, so undefined reprompt?
    # New code: reprompt_ssml=None in build_ssml_response call.
    assert resp["response"].get("reprompt") is None


def test_intent_responses_include_closing_cue(monkeypatch):
    # Patch the SSML-producing helper in ssml_builder
    monkeypatch.setattr(ssml_builder, "get_spot_price_ssml", lambda: "<speak>Spot price</speak>")

    event = make_event("IntentRequest", intent_name="GetSpotPriceIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert any(v in ssml for v in ssml_builder.CLOSING_CUES)
    # The session should remain open (default)
    assert resp["response"].get("shouldEndSession") is False


def test_stop_intent_ends_session_and_no_closing_cue():
    event = make_event("IntentRequest", intent_name="AMAZON.StopIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert ssml == "<speak>Goodbye.</speak>"
    assert resp["response"].get("shouldEndSession") is True
    assert not any(v in ssml for v in ssml_builder.CLOSING_CUES)


def test_cheapest_price_tomorrow_before_2pm_integration(monkeypatch):
    # Simulate current time before 2 PM
    desired_now = datetime.now(timezone.utc).replace(hour=13, minute=0, second=0, microsecond=0)

    class FakeDateTime(datetime):
        _mock_now = desired_now
        @classmethod
        def now(cls, tz=None):
            if cls._mock_now:
                return cls._mock_now.astimezone(tz) if tz else cls._mock_now
            return datetime.now(tz)

    monkeypatch.setattr(ssml_builder, "datetime", FakeDateTime)

    # Mock API data
    entries = []
    for h in range(0, 24):
        entries.append({"dt": datetime(desired_now.year, desired_now.month, desired_now.day, h, tzinfo=timezone.utc), "price": 0.10})
    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    # Create event with "tomorrow" as date slot
    event = make_event("IntentRequest", intent_name="CheapestPriceIntent",
                      slots={"date": {"value": "tomorrow"}})
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert "after 2 PM" in ssml
    assert "not published yet" in ssml
    assert any(v in ssml for v in ssml_builder.CLOSING_CUES)


def test_cheapest_price_tomorrow_after_2pm_integration(monkeypatch):
    # Simulate current time after 2 PM
    desired_now = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)

    class FakeDateTime(datetime):
        _mock_now = desired_now
        @classmethod
        def now(cls, tz=None):
            if cls._mock_now:
                return cls._mock_now.astimezone(tz) if tz else cls._mock_now
            return datetime.now(tz)

    monkeypatch.setattr(ssml_builder, "datetime", FakeDateTime)

    # Mock API data - today expensive, tomorrow cheap
    today_date = desired_now.date()
    tomorrow_date = (desired_now + timedelta(days=1)).date()

    entries = []
    # Today's remaining hours (15..23)
    for h in range(15, 24):
        entries.append({"dt": datetime(today_date.year, today_date.month, today_date.day, h, tzinfo=timezone.utc), "price": 0.10})

    # Tomorrow: cheapest at 08:00 (0.03 EUR = 3 cents)
    for h in range(0, 24):
        price = 0.03 if h == 8 else 0.10
        entries.append({"dt": datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day, h, tzinfo=timezone.utc), "price": price})

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    # Create event with "tomorrow" as date slot
    event = make_event("IntentRequest", intent_name="CheapestPriceIntent",
                      slots={"date": {"value": "tomorrow"}})
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert "3.0" in ssml  # 0.03 * 100 = 3.0 cents
    assert "tomorrow" in ssml
    assert any(v in ssml for v in ssml_builder.CLOSING_CUES)


def test_cheapest_price_today_integration(monkeypatch):
    # Test that "today" or no date defaults to today's cheapest
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # Create entries for remaining hours today with varying prices
    prices = [0.08, 0.05, 0.09, 0.07]  # cheapest is 0.05 at index 1
    entries = []
    for i, p in enumerate(prices):
        entries.append({"dt": hour_start + timedelta(hours=i), "price": p})

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    # Test without date slot (defaults to today)
    event = make_event("IntentRequest", intent_name="CheapestPriceIntent")
    resp = lf.lambda_handler(event, None)

    ssml = resp["response"]["outputSpeech"]["ssml"]
    assert "5.0" in ssml  # 0.05 * 100 = 5.0 cents
    assert "today" in ssml
    assert any(v in ssml for v in ssml_builder.CLOSING_CUES)
