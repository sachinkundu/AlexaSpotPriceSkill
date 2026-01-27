import pytest
import lambda_function as lf
import ssml_builder

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
