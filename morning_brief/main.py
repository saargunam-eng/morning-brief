import asyncio
import logging
import sys
import time
from typing import Dict
from morning_brief.config import settings
from morning_brief.db import (
    get_recent_sent_hashes_and_titles,
    init_db,
    log_run,
    save_sent_items,
)
from morning_brief.dedupe import deduplicate_items
from morning_brief.formatter import build_telegram_html_message
from morning_brief.gemini import curate_with_gemini
from morning_brief.rss import fetch_all_feeds
from morning_brief.telegram import send_telegram_message
from morning_brief.weather import fetch_coimbatore_weather

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("morning_brief.main")


async def run_briefing_pipeline() -> bool:
    """Execute the end-to-end Morning Briefing pipeline."""
    start_time = time.time()
    logger.info("Starting Morning Briefing pipeline...")

    # 1. Initialize SQLite Database
    init_db(settings.db_path)

    # 2. Retrieve history for deduplication
    sent_hashes, sent_titles = get_recent_sent_hashes_and_titles(
        settings.db_path, hours=settings.dedupe_window_hours
    )

    # 3. Fetch RSS Feeds in parallel
    logger.info("Fetching RSS feeds...")
    categorized_raw, feed_success, feed_failure = await fetch_all_feeds(settings.feeds)

    # 4. Deduplicate items per category
    categorized_deduped: Dict[str, list] = {}
    total_candidates = 0

    for category, items in categorized_raw.items():
        deduped = deduplicate_items(
            items,
            sent_hashes=sent_hashes,
            sent_titles=sent_titles,
        )
        categorized_deduped[category] = deduped
        total_candidates += len(deduped)

    logger.info(f"Total deduplicated candidates ready for curation: {total_candidates}")

    # 5. Fetch Weather
    logger.info("Fetching Coimbatore weather...")
    weather = await fetch_coimbatore_weather(
        lat=settings.coimbatore_lat,
        lon=settings.coimbatore_lon,
        tz=settings.timezone,
    )

    # 6. Curate with Gemini Flash
    logger.info("Curating news items with Gemini Flash...")
    curated, gemini_used = await curate_with_gemini(
        categorized_deduped,
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )

    # 7. Format Telegram HTML Message
    message_text = build_telegram_html_message(
        curated=curated,
        weather=weather,
        tz_name=settings.timezone,
    )

    # 8. Send Telegram Notification
    logger.info("Delivering briefing to Telegram...")
    telegram_success, delivery_status = await send_telegram_message(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        text=message_text,
    )

    # 9. Extract sent items and save to DB
    delivered_items = []
    items_count = 0
    if telegram_success:
        for cat, items in curated.items():
            for item in items:
                delivered_items.append(
                    {
                        "url_hash": item.get("url_hash", ""),
                        "normalized_title": item.get("headline", ""),
                        "url": item.get("url", ""),
                        "category": cat,
                        "source": item.get("source", "News"),
                        "published_at": "",
                    }
                )
                items_count += 1

        save_sent_items(settings.db_path, delivered_items)

    duration = round(time.time() - start_time, 2)
    status_str = "SUCCESS" if telegram_success else f"FAILED ({delivery_status})"

    # 10. Log run metrics
    log_run(
        db_path=settings.db_path,
        duration_seconds=duration,
        feed_success_count=feed_success,
        feed_failure_count=feed_failure,
        gemini_used=gemini_used,
        items_sent_count=items_count,
        status=status_str,
    )

    logger.info(f"Pipeline finished in {duration}s. Status: {status_str}")
    return telegram_success


def main():
    command = "run"
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

    if command == "run":
        success = asyncio.run(run_briefing_pipeline())
        sys.exit(0 if success else 1)
    elif command == "schedule":
        from morning_brief.scheduler import start_scheduler
        start_scheduler()
    else:
        print(f"Unknown command '{command}'. Usage: python -m morning_brief.main [run|schedule]")
        sys.exit(1)


if __name__ == "__main__":
    main()
