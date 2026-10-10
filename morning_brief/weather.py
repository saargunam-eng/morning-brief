import logging

import httpx

logger = logging.getLogger("morning_brief.weather")

WMO_WEATHER_DESCRIPTIONS = {
    0: ("Clear sky", "Sunny and clear sky; pleasant weather."),
    1: ("Mainly clear", "Mostly sunny and clear skies."),
    2: ("Partly cloudy", "Partly cloudy throughout the day."),
    3: ("Overcast", "Overcast skies; pleasant temperature."),
    45: ("Foggy", "Foggy conditions early in the day; drive carefully."),
    48: ("Depositing rime fog", "Dense fog expected early in the morning."),
    51: ("Light drizzle", "Light drizzle likely; carry an umbrella just in case."),
    53: ("Moderate drizzle", "Drizzle expected; keep an umbrella handy."),
    55: ("Dense drizzle", "Dense drizzle likely today."),
    61: ("Slight rain", "Light rain showers expected today; carry an umbrella."),
    63: ("Moderate rain", "Moderate rain expected; plan travel accordingly."),
    65: ("Heavy rain", "Heavy rainfall expected; carry rain gear."),
    80: ("Rain showers", "Rain showers likely later today; carry an umbrella."),
    81: ("Moderate rain showers", "Passing rain showers expected today."),
    82: ("Violent rain showers", "Heavy rain showers and gusty winds expected."),
    95: ("Thunderstorm", "Thunderstorms likely today; stay safe indoors if heavy."),
    96: ("Thunderstorm with hail", "Thunderstorms with hail expected."),
    99: ("Heavy thunderstorm", "Severe thunderstorms likely; exercise caution."),
}


def interpret_wmo_code(code: int) -> str:
    """Return a plain English description for a given WMO weather code."""
    if code in WMO_WEATHER_DESCRIPTIONS:
        return WMO_WEATHER_DESCRIPTIONS[code][1]
    return "Variable weather conditions expected today."


async def fetch_coimbatore_weather(lat: float = 11.0168, lon: float = 76.9558, tz: str = "Asia/Kolkata") -> dict:
    """Fetch current & forecast weather for Coimbatore from Open-Meteo API."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code",
        "timezone": tz,
        "forecast_days": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        daily = data.get("daily", {})

        current_temp = current.get("temperature_2m", 28.0)
        humidity = current.get("relative_humidity_2m", 70)
        wind_speed = current.get("wind_speed_10m", 10.0)
        current_code = current.get("weather_code", 0)

        max_temp = daily.get("temperature_2m_max", [30.0])[0] if daily.get("temperature_2m_max") else 30.0
        min_temp = daily.get("temperature_2m_min", [22.0])[0] if daily.get("temperature_2m_min") else 22.0
        precip_prob = (
            daily.get("precipitation_probability_max", [0])[0]
            if daily.get("precipitation_probability_max")
            else 0
        )
        daily_code = daily.get("weather_code", [current_code])[0] if daily.get("weather_code") else current_code

        weather_summary = interpret_wmo_code(daily_code)
        if precip_prob > 40 and "umbrella" not in weather_summary.lower():
            weather_summary += f" ({precip_prob}% chance of rain; carry an umbrella.)"

        return {
            "current_temp": round(current_temp, 1),
            "humidity": humidity,
            "wind_speed": wind_speed,
            "max_temp": round(max_temp, 1),
            "min_temp": round(min_temp, 1),
            "precip_prob": precip_prob,
            "weather_line": weather_summary,
            "success": True,
        }

    except Exception as e:
        logger.error(f"Failed to fetch weather from Open-Meteo: {e}")
        return {
            "current_temp": 28.0,
            "humidity": 70,
            "wind_speed": 10.0,
            "max_temp": 32.0,
            "min_temp": 23.0,
            "precip_prob": 0,
            "weather_line": "Warm and pleasant day expected in Coimbatore.",
            "success": False,
        }
