import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ssml_builder
import copy

# Mock data for testing
MOCK_PRICES = []
# Create 48 hours of dummy data starting from today 00:00
base_time = datetime(2023, 10, 27, 0, 0, tzinfo=timezone.utc)
for i in range(48):
    dt = base_time + timedelta(hours=i)
    # Price pattern: Higher in day, lower at night.
    # Tomorrow's cheapest is set clearly different to verify we aren't getting today's.
    price = 10.0 if i < 24 else 5.0 
    MOCK_PRICES.append({"dt": dt, "price": price})

@pytest.fixture
def mock_api():
    with patch('ssml_builder.spot_price_api.fetch_all_price_entries') as mock:
        mock.return_value = (MOCK_PRICES, None)
        yield mock

@pytest.fixture
def mock_utils_today_tomorrow():
    """Mock utils.parse_date_value to handle 'today' and 'tomorrow' correctly relative to our fixed now."""
    original_parse = ssml_builder.utils.parse_date_value
    
    def side_effect(date_value, now):
        if date_value == "tomorrow":
            return now.date() + timedelta(days=1)
        if date_value == "today" or not date_value:
            return now.date()
        return original_parse(date_value, now)
        
    with patch('ssml_builder.utils.parse_date_value', side_effect=side_effect) as mock:
        yield mock

class FakeDatetime(datetime):
    _mock_now = None
    @classmethod
    def now(cls, tz=None):
        if cls._mock_now:
            return cls._mock_now.astimezone(tz)
        return datetime.now(tz)

def test_tomorrow_before_2pm(mock_api, mock_utils_today_tomorrow):
    """
    Scenario: It is 10:00 AM. User asks for cheapest price tomorrow.
    Expectation: "Check back after 2 PM..."
    """
    fixed_now = base_time.replace(hour=10)
    FakeDatetime._mock_now = fixed_now
    
    with patch('ssml_builder.datetime', FakeDatetime):
        response = ssml_builder.get_cheapest_price_ssml(date_value="tomorrow")

        assert "after 2 PM" in response
        assert "not published yet" in response

def test_tomorrow_after_2pm(mock_api, mock_utils_today_tomorrow):
    """
    Scenario: It is 3:00 PM. User asks for cheapest price tomorrow.
    Expectation: Should return the cheapest price for tomorrow.
    """
    fixed_now = base_time.replace(hour=15)
    FakeDatetime._mock_now = fixed_now

    # Adjust mock prices for realism
    local_prices = copy.deepcopy(MOCK_PRICES)
    for p in local_prices:
        p['price'] = 0.10 if p['dt'] < base_time + timedelta(hours=24) else 0.05
    
    with patch('ssml_builder.spot_price_api.fetch_all_price_entries') as mock_api_deep:
        mock_api_deep.return_value = (local_prices, None)
        
        with patch('ssml_builder.datetime', FakeDatetime):
            response = ssml_builder.get_cheapest_price_ssml(date_value="tomorrow")
             
            assert "5.0" in response # 0.05 * 100
            assert "tomorrow" in response or "2023-10-28" in response

def test_today_default(mock_api, mock_utils_today_tomorrow):
    """
    Scenario: User asks without date or explicitly today.
    Expectation: Returns today's cheapest.
    """
    fixed_now = base_time.replace(hour=10)
    FakeDatetime._mock_now = fixed_now
    
    local_prices = copy.deepcopy(MOCK_PRICES)
    for p in local_prices:
        p['price'] = 0.10 if p['dt'] < base_time + timedelta(hours=24) else 0.05

    with patch('ssml_builder.spot_price_api.fetch_all_price_entries') as mock_api_deep:
        mock_api_deep.return_value = (local_prices, None)
        
        with patch('ssml_builder.datetime', FakeDatetime):
            # 1. No arg
            response = ssml_builder.get_cheapest_price_ssml(None)
            
            assert "10.0" in response
            assert "today" in response
