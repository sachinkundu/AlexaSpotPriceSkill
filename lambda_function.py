import ssml_builder


def _get_slot_value(intent, *slot_names):
    slots = intent.get("slots", {}) if intent else {}
    for name in slot_names:
        slot = slots.get(name) or slots.get(name.lower()) or slots.get(name.upper())
        if slot and slot.get("value"):
            return slot["value"]
    return None


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
        return ssml_builder.build_ssml_response(welcome_ssml, should_end_session=False, reprompt_ssml=None)

    # 2. Intent requests
    if request_type == "IntentRequest":
        intent = request.get("intent", {})
        intent_name = intent.get("name")
        # For all Intent invocations (except Stop/Cancel which end the session),
        # append the configured closing cue inside the SSML.
        if intent_name == "CheapestPriceIntent":
            date_value = _get_slot_value(intent, "date", "day")
            ssml = ssml_builder.get_cheapest_price_ssml(date_value)
            return ssml_builder.build_ssml_response(ssml_builder.with_closing_cue(ssml))

        if intent_name == "GetSpotPriceAtHourIntent":
            date_value = _get_slot_value(intent, "date", "day")
            time_value = _get_slot_value(intent, "time", "hour")
            ssml = ssml_builder.get_spot_price_at_hour_ssml(date_value, time_value)
            return ssml_builder.build_ssml_response(ssml_builder.with_closing_cue(ssml))

        if intent_name == "ShouldIRunMachineIntent":
            ssml = ssml_builder.get_run_machine_ssml()
            return ssml_builder.build_ssml_response(ssml_builder.with_closing_cue(ssml))

        if intent_name in {"GetSpotPriceIntent", "AMAZON.FallbackIntent"}:
            ssml = ssml_builder.get_spot_price_ssml()
            return ssml_builder.build_ssml_response(ssml_builder.with_closing_cue(ssml))

        # Stop/Cancel should end the session without the closing cue
        if intent_name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
            return ssml_builder.build_ssml_response("<speak>Goodbye.</speak>", should_end_session=True)

    # 3. Fallback
    return ssml_builder.build_ssml_response(ssml_builder.get_spot_price_ssml())
