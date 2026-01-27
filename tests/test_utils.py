from datetime import datetime, timezone
import pytest
import utils

def test_format_hour():
    dt = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    # Testing with UTC for simplicity, or mock tz
    formatted = utils.format_hour(dt, timezone.utc)
    assert formatted == "12:00"

def test_parse_hour_from_time_value():
    assert utils.parse_hour_from_time_value("12:00") == 12
    assert utils.parse_hour_from_time_value("00:00") == 0
    assert utils.parse_hour_from_time_value("23:59") == 23
    assert utils.parse_hour_from_time_value("24:00") is None
    assert utils.parse_hour_from_time_value(None) is None
    assert utils.parse_hour_from_time_value("invalid") is None

def test_parse_date_value():
    now = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    
    # "today"
    assert utils.parse_date_value("today", now) == now.date()
    assert utils.parse_date_value(None, now) == now.date()
    
    # "tomorrow"
    expected_tomorrow = datetime(2023, 1, 2).date()
    assert utils.parse_date_value("tomorrow", now) == expected_tomorrow
    
    # ISO date
    assert utils.parse_date_value("2023-01-05", now) == datetime(2023, 1, 5).date()
    assert utils.parse_date_value("invalid", now) is None
