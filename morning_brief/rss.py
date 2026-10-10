import asyncio
import logging
from datetime import datetime, timedelta, timezone
from time import mktime
from typing import Dict, List, Tuple
import feedparser
import httpx
from morning_brief.config import FeedConfig

logger = logging.getLogger("morning_brief.rss")


def parse_published_time(entry: Dict) -> datetime:
    """Extract and parse published timestamp into timezone-aware datetime."""
    now = datetime.now(timezone.utc)
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
            return dt
        except Exception:
            pass

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            dt = datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)
            return dt
        except Exception:
            pass

    # Default to current UTC time if unavailable
    return now


async def fetch_single_feed(
    client: httpx.AsyncClient,
    feed_cfg: FeedConfig,
    max_age_hours: int = 24,
) -> Tuple[str, List[Dict], bool]:
    """Fetch and parse a single RSS feed asynchronously."""
    category = feed_cfg.category
    source_name = feed_cfg.name
    url = feed_cfg.url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 MorningBrief/1.0"
        )
    }

    try:
        response = await client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            logger.warning(f"Feed parser reported error for {source_name}: {parsed.bozo_exception}")
            return category, [], False

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        items: List[Dict] = []

        for entry in parsed.entries:
            published_at = parse_published_time(entry)

            # Filter items published within max_age_hours
            if published_at < cutoff:
                continue

            title = entry.get("title", "").strip()
            item_url = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()

            # Clean HTML tags from summary if present
            summary = feedparser.sanitizer._strip_html(summary) if summary else ""
            if len(summary) > 300:
                summary = summary[:297] + "..."

            if title and item_url:
                items.append(
                    {
                        "title": title,
                        "url": item_url,
                        "source": source_name,
                        "published_at": published_at.isoformat(),
                        "summary": summary,
                        "category": category,
                    }
                )

        logger.info(f"Successfully fetched {len(items)} items from {source_name}")
        return category, items, True

    except Exception as e:
        logger.error(f"Failed to fetch feed {source_name} ({url}): {e}")
        return category, [], False


async def fetch_all_feeds(feeds: List[FeedConfig]) -> Tuple[Dict[str, List[Dict]], int, int]:
    """
    Fetch all RSS feeds in parallel with 15s timeout per request.
    Returns categorized candidates dictionary, success count, failure count.
    """
    categorized_items: Dict[str, List[Dict]] = {
        "world": [],
        "india": [],
        "tamil_nadu": [],
        "coimbatore": [],
    }

    timeout = httpx.Timeout(15.0, connect=10.0)
    success_count = 0
    failure_count = 0

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [fetch_single_feed(client, feed) for feed in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                failure_count += 1
                continue

            category, items, success = result
            if success:
                success_count += 1
                if category in categorized_items:
                    categorized_items[category].extend(items)
                else:
                    categorized_items[category] = items
            else:
                failure_count += 1

    return categorized_items, success_count, failure_count
