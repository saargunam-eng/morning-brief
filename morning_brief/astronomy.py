import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger("morning_brief.astronomy")


async def fetch_coimbatore_solar_times(lat: float = 11.0168, lon: float = 76.9558) -> dict:
    """Dynamically fetch sunrise and sunset times for Coimbatore from Sunrise-Sunset API."""
    url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", {})
                sunrise_raw = results.get("sunrise", "")
                sunset_raw = results.get("sunset", "")

                if sunrise_raw and sunset_raw:
                    dt_sr = datetime.fromisoformat(sunrise_raw).astimezone(ZoneInfo("Asia/Kolkata"))
                    dt_ss = datetime.fromisoformat(sunset_raw).astimezone(ZoneInfo("Asia/Kolkata"))

                    return {
                        "sunrise": dt_sr.strftime("%I:%M %p"),
                        "sunset": dt_ss.strftime("%I:%M %p"),
                        "day_length": results.get("day_length", ""),
                        "success": True,
                    }
    except Exception as e:
        logger.warning(f"Failed to fetch solar times: {e}")

    return {
        "sunrise": "06:10 AM",
        "sunset": "06:08 PM",
        "day_length": "11:58:00",
        "success": False,
    }
