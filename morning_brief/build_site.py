import asyncio
import json
import logging
import sys

from morning_brief.api import (
    api_ai_digest,
    api_astronomy,
    api_calendar,
    api_markets,
    api_movies,
    api_news,
    api_sports,
    api_trends,
    api_weather,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("morning_brief.build_site")


async def generate_site_snapshot():
    logger.info("Fetching latest live data for all dashboard categories...")

    # Fetch live data in parallel
    results = await asyncio.gather(
        api_weather(),
        api_markets(),
        api_news(),
        api_trends(),
        api_astronomy(),
        api_movies(),
        api_sports(),
        api_calendar(),
        return_exceptions=True,
    )

    weather = results[0] if not isinstance(results[0], Exception) else {}
    markets = results[1] if not isinstance(results[1], Exception) else []
    news = results[2] if not isinstance(results[2], Exception) else {}
    trends = results[3] if not isinstance(results[3], Exception) else []
    astronomy = results[4] if not isinstance(results[4], Exception) else {}
    movies = results[5] if not isinstance(results[5], Exception) else {"feed": {"entry": []}}
    sports = results[6] if not isinstance(results[6], Exception) else {"articles": []}
    calendar = results[7] if not isinstance(results[7], Exception) else []

    # Fetch AI Digest
    try:
        digest = await api_ai_digest()
    except Exception as e:
        logger.warning(f"AI digest generation failed: {e}")
        digest = {
            "executive_summary": "Daily brief snapshot generated automatically.",
            "key_insights": [],
            "correlations": [],
            "recommendations": [],
            "metrics": {},
            "chart_data": [],
        }

    snapshot = {
        "weather": weather,
        "markets": markets,
        "news": news,
        "trends": trends,
        "astronomy": astronomy,
        "digest": digest,
        "movies": movies,
        "sports": sports,
        "calendar": calendar,
    }

    # Save to initial_data.json
    logger.info("Writing initial_data.json...")
    with open("initial_data.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False)

    # Embed fresh snapshot into index.html
    logger.info("Injecting updated INITIAL_DATA into index.html...")
    with open("index.html", "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("window.INITIAL_DATA = "):
            new_lines.append(f"window.INITIAL_DATA = {json.dumps(snapshot, ensure_ascii=False)};\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        raise RuntimeError("Could not find 'window.INITIAL_DATA = ' in index.html")

    with open("index.html", "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    logger.info("Successfully updated index.html with fresh live content!")


def main():
    asyncio.run(generate_site_snapshot())


if __name__ == "__main__":
    main()
