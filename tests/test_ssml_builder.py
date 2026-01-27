import pytest
from datetime import datetime, timedelta, timezone
import ssml_builder
import spot_price_api
import utils

def test_get_spot_price_formats_prices(monkeypatch):
    # Prepare deterministic entries for current + next three hours
    entries = [
        {"dt": None, "price": 0.05},  # 5.0 cents
        {"dt": None, "price": 0.06},  # 6.0 cents
        {"dt": None, "price": 0.07},  # 7.0 cents
        {"dt": None, "price": 0.08},  # 8.0 cents
    ]

    # Monkeypatch the helper that fetches entries
    monkeypatch.setattr(spot_price_api, "get_price_entries", lambda n=4: (entries[:n], None))

    msg = ssml_builder.get_spot_price()

    # Check that current and upcoming hour prices are present and formatted
    assert "The current electricity spot price in Finland is 5.0 cents per kilowatt-hour." in msg
    assert "Next hour 6.0 cents" in msg
    assert "in two hours 7.0 cents" in msg
    assert "in three hours 8.0 cents" in msg


def test_cheapest_price_intent_returns_expected_time_and_price(monkeypatch):
    # Build deterministic hourly entries starting at current hour (UTC)
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    prices = [0.05, 0.04, 0.03, 0.06]  # cheapest is index 2 -> 3.0 cents
    entries = []
    for i, p in enumerate(prices):
        entries.append({"dt": hour_start + timedelta(hours=i), "price": p})

    # Monkeypatch the data fetcher
    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_cheapest_price_ssml()

    # The cheapest price should be 3.0 cents
    assert '<say-as interpret-as="cardinal">3.0</say-as>' in ssml

    # Time string should match the formatted hour for the cheapest entry
    cheapest_dt = entries[2]["dt"]
    cheapest_time = utils.format_hour(cheapest_dt, cheapest_dt.tzinfo or timezone.utc)
    assert f'<say-as interpret-as="time">{cheapest_time}</say-as>' in ssml


def test_should_i_run_machine_now_yes(monkeypatch):
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # First three hours are all below 7 cents (0.05 EUR = 5 cents)
    entries = [
        {"dt": hour_start + timedelta(hours=i), "price": 0.05}
        for i in range(6)
    ]

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_run_machine_ssml()

    assert "Yes, now is a good time." in ssml


def test_should_i_run_machine_now_schedule_later(monkeypatch):
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # First three hours expensive, a later 3-hour window is cheap (<=7 cents)
    prices = [0.09, 0.09, 0.09, 0.05, 0.05, 0.05]
    entries = [
        {"dt": hour_start + timedelta(hours=i), "price": p}
        for i, p in enumerate(prices)
    ]

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_run_machine_ssml()

    # Should not say 'Yes' but should recommend a time (the earliest cheap window starts at hour_start+3)
    assert "Yes, now is a good time." not in ssml
    recommended_time = utils.format_hour(entries[3]["dt"], entries[3]["dt"].tzinfo)
    assert f'<say-as interpret-as="time">{recommended_time}</say-as>' in ssml


def test_should_i_run_machine_no_three_hour_window_remaining(monkeypatch):
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # Only two remaining hours today -> should trigger the 'couldn't find a three-hour window' message
    entries = [
        {"dt": hour_start + timedelta(hours=i), "price": 0.10}
        for i in range(2)
    ]

    # Provide only today's entries (no error)
    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_run_machine_ssml()

    assert "I couldn't find a three-hour window remaining today." in ssml


def test_should_i_run_machine_after_14_check_tomorrow(monkeypatch):
    # Simulate current time _after_ 14:00 UTC so the skill will consult tomorrow
    desired_now = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)

    class FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return desired_now
            return desired_now.astimezone(tz)
            
    # Need to patch datetime in ssml_builder specifically if it imports it, 
    # but here ssml_builder uses datetime.now directly.
    # However, datetime is a built-in type, so we can't easily patch it on the module unless it does `from datetime import datetime`.
    # ssml_builder does `from datetime import datetime`. So we patch ssml_builder.datetime.
    monkeypatch.setattr(ssml_builder, "datetime", FakeDateTime)
    # Also patch utils.datetime if needed? utils.format_hour uses dt.astimezone, doesn't call now.
    # ssml_builder calls utils.format_hour.

    today_date = desired_now.date()
    # utils.datetime also needs to be patched if utils imports it? 
    # utils imports datetime. But utils doesn't call datetime.now(), it only uses datetime type for type hints or fromisoformat.
    # ssml_builder calls `datetime.now`.

    tomorrow_date = (desired_now + timedelta(days=1)).date()

    entries = []
    # Today's remaining hours (15..23) expensive
    for h in range(15, 24):
        entries.append({"dt": datetime(today_date.year, today_date.month, today_date.day, h, tzinfo=timezone.utc), "price": 0.10})

    # Tomorrow: cheap window at 08,09,10
    for h in range(0, 24):
        price = 0.05 if 8 <= h <= 10 else 0.10
        entries.append({"dt": datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day, h, tzinfo=timezone.utc), "price": price})

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_run_machine_ssml()

    # Should recommend tomorrow and include at least the earliest recommended time
    assert "Tomorrow run it at" in ssml
    # earliest recommended time should be 08:00 formatted by utils.format_hour
    # We need to find the entry corresponding to tomorrow 08:00
    # In list `entries`, the first 9 are today (15..23 is 9 hours). No wait 15..23 inclusive is 23-15+1=9.
    # Then tomorrow starts at index 9.
    # 08:00 tomorrow is at index 9+8 = 17.
    target_entry = entries[17]
    recommended_time = utils.format_hour(target_entry["dt"], target_entry["dt"].tzinfo)
    assert f'<say-as interpret-as="time">{recommended_time}</say-as>' in ssml


def test_should_i_run_machine_after_14_no_good_times(monkeypatch):
    desired_now = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)

    class FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return desired_now
            return desired_now.astimezone(tz)

    monkeypatch.setattr(ssml_builder, "datetime", FakeDateTime)

    today_date = desired_now.date()
    tomorrow_date = (desired_now + timedelta(days=1)).date()

    entries = []
    for h in range(15, 24):
        entries.append({"dt": datetime(today_date.year, today_date.month, today_date.day, h, tzinfo=timezone.utc), "price": 0.10})

    for h in range(0, 24):
        entries.append({"dt": datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day, h, tzinfo=timezone.utc), "price": 0.10})

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_run_machine_ssml()

    assert "No good times today or tomorrow." in ssml


def test_spot_price_at_hour_tomorrow_before_14(monkeypatch):
    desired_now = datetime.now(timezone.utc).replace(hour=13, minute=0, second=0, microsecond=0)

    class FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return desired_now
            return desired_now.astimezone(tz)

    monkeypatch.setattr(ssml_builder, "datetime", FakeDateTime)

    entries = []
    for h in range(0, 24):
        entries.append({"dt": datetime(desired_now.year, desired_now.month, desired_now.day, h, tzinfo=timezone.utc), "price": 0.10})
    tomorrow = desired_now + timedelta(days=1)
    for h in range(0, 24):
        entries.append({"dt": datetime(tomorrow.year, tomorrow.month, tomorrow.day, h, tzinfo=timezone.utc), "price": 0.10})

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_spot_price_at_hour_ssml("tomorrow", "11:00")

    assert "Check back after 2 PM since the spot prices are not published yet." in ssml


def test_spot_price_at_hour_success(monkeypatch):
    now = datetime.now(timezone.utc)
    target_date = now.date()
    entries = []
    for h in range(0, 24):
        entries.append({"dt": datetime(target_date.year, target_date.month, target_date.day, h, tzinfo=timezone.utc), "price": 0.05})

    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))

    ssml = ssml_builder.get_spot_price_at_hour_ssml("today", "11:00")

    assert '<say-as interpret-as="time">11:00</say-as>' in ssml
    assert '<say-as interpret-as="cardinal">5.0</say-as>' in ssml
