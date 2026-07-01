from __future__ import annotations

from tools.weather import WeatherTool


def test_weather_returns_known_city() -> None:
    result = WeatherTool().execute({"city": "Shanghai"})

    assert result == {
        "ok": True,
        "city": "Shanghai",
        "condition": "Cloudy",
        "temperature_c": 29,
        "updated_at": "2026-06-30T00:00:00Z",
        "source": "mock",
    }


def test_weather_accepts_location_for_compatibility() -> None:
    result = WeatherTool().execute({"location": "London"})

    assert result["ok"] is True
    assert result["city"] == "London"
    assert result["source"] == "mock"


def test_weather_returns_default_for_unknown_city() -> None:
    result = WeatherTool().execute({"city": "Smallville"})

    assert result["ok"] is True
    assert result["city"] == "Smallville"
    assert result["condition"] == "Partly cloudy"
    assert result["temperature_c"] == 22
