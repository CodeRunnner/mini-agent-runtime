"""Offline mock weather tool."""

from __future__ import annotations

from typing import Any


class WeatherTool:
    name = "weather"
    description = "Look up weather for a location."
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City for the weather lookup."},
            "location": {
                "type": "string",
                "description": "Backward-compatible location field for the weather lookup.",
            },
        },
        "anyOf": [{"required": ["city"]}, {"required": ["location"]}],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any]) -> Any:
        """Return deterministic mock weather data."""
        if not isinstance(arguments, dict):
            return {"ok": False, "error": "arguments must be an object"}

        city = arguments.get("city") or arguments.get("location")
        if not isinstance(city, str) or not city.strip():
            return {"ok": False, "error": "city must be a non-empty string"}

        requested_city = city.strip()
        weather = _MOCK_WEATHER.get(
            requested_city.casefold(),
            {
                "city": requested_city,
                "condition": "Partly cloudy",
                "temperature_c": 22,
            },
        )

        return {
            "ok": True,
            "city": weather["city"],
            "condition": weather["condition"],
            "temperature_c": weather["temperature_c"],
            "updated_at": "2026-06-30T00:00:00Z",
            "source": "mock",
        }


_MOCK_WEATHER = {
    "shanghai": {"city": "Shanghai", "condition": "Cloudy", "temperature_c": 29},
    "beijing": {"city": "Beijing", "condition": "Sunny", "temperature_c": 31},
    "london": {"city": "London", "condition": "Light rain", "temperature_c": 18},
    "new york": {"city": "New York", "condition": "Clear", "temperature_c": 25},
}
