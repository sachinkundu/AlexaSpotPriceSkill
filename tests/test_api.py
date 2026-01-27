import pytest
from datetime import datetime, timezone
import spot_price_api

def test_parse_iso_datetime():
    assert spot_price_api.parse_iso_datetime(None) is None
    
    # With stored Z
    dt = spot_price_api.parse_iso_datetime("2023-01-01T12:00:00Z")
    assert dt.year == 2023
    assert dt.month == 1
    
    # With offset
    dt2 = spot_price_api.parse_iso_datetime("2023-01-01T12:00:00+02:00")
    assert dt2.tzinfo is not None
    
    # Invalid
    assert spot_price_api.parse_iso_datetime("invalid") is None

def test_fetch_all_price_entries_success(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return [
                {"DateTime": "2023-01-01T12:00:00Z", "PriceWithTax": 0.05},
                {"DateTime": "2023-01-01T13:00:00Z", "PriceWithTax": 0.06}
            ]
            
    monkeypatch.setattr("requests.get", lambda url, params, timeout: MockResponse())
    
    entries, error = spot_price_api.fetch_all_price_entries()
    assert error is None
    assert len(entries) == 2
    assert entries[0]['price'] == 0.05

def test_fetch_all_price_entries_error(monkeypatch):
    import requests
    def mock_get(*args, **kwargs):
        raise requests.exceptions.RequestException("Error")
        
    monkeypatch.setattr("requests.get", mock_get)
    entries, error = spot_price_api.fetch_all_price_entries()
    assert entries is None
    assert "couldn't retrieve" in error

def test_get_price_entries_logic(monkeypatch):
    # Setup entries
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    
    # Create entries for current hour and next 5 hours
    entries = []
    for i in range(6):
        entries.append({"dt": hour_start + timedelta(hours=i), "price": 0.01 * i})
        
    # Mock fetch
    monkeypatch.setattr(spot_price_api, "fetch_all_price_entries", lambda: (entries, None))
    
    # Test getting 4 hours
    result, error = spot_price_api.get_price_entries(4)
    assert error is None
    assert len(result) == 4
    assert result[0]['dt'] == hour_start
    assert result[0]['price'] == 0.0
