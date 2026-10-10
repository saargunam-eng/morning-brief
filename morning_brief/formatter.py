import html
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger("morning_brief.formatter")


def escape_html(text: str) -> str:
    """Safely escape text for Telegram HTML mode."""
    if not text:
        return ""
    return html.escape(str(text))


def format_category_section(
    title_header: str,
    items: list[dict],
    max_items: int = 5,
    is_bullet: bool = False,
) -> str:
    """Format a list of items into an HTML section."""
    if not items:
        return ""

    lines = [title_header]
    for idx, item in enumerate(items[:max_items], start=1):
        headline = escape_html(item.get("headline", ""))
        why = escape_html(item.get("why_it_matters", ""))
        url = escape_html(item.get("url", ""))

        if is_bullet:
            prefix = "•"
        else:
            prefix = f"{idx}."

        lines.append(f'{prefix} <a href="{url}">{headline}</a> — {why}')

    lines.append("")
    return "\n".join(lines)


def build_telegram_html_message(
    curated: dict[str, list[dict]],
    weather: dict,
    tz_name: str = "Asia/Kolkata",
) -> str:
    """
    Format news and weather into a single Telegram HTML message under 4,000 characters.
    Handles progressive section truncation if length exceeds limit.
    """
    now = datetime.now(ZoneInfo(tz_name))
    date_str = now.strftime("%d %b %Y")
    day_name = now.strftime("%A, %d %B %Y")

    cur_temp = weather.get("current_temp", 28.0)
    max_temp = weather.get("max_temp", 32.0)
    min_temp = weather.get("min_temp", 22.0)
    weather_line = escape_html(weather.get("weather_line", "Pleasant weather in Coimbatore."))

    header = (
        f"☀️ <b>Coimbatore — {date_str}</b>\n"
        f"{cur_temp}°C now | High {max_temp}°C / Low {min_temp}°C\n"
        f"{weather_line}\n"
        f"📅 {day_name}\n\n"
    )

    # Progressive truncation loop
    # Truncation strategies:
    # 1. full (5 items per category, include trending)
    # 2. no trending (5 items per category, omit trending)
    # 3. 4 items per category, no trending
    # 4. 3 items per category, no trending
    strategies = [
        (5, True),
        (5, False),
        (4, False),
        (3, False),
    ]

    final_message = ""

    for max_cat_items, include_trending in strategies:
        sec_world = format_category_section("🌍 <b>World</b>", curated.get("world", []), max_items=max_cat_items)
        sec_india = format_category_section("🇮🇳 <b>India</b>", curated.get("india", []), max_items=max_cat_items)
        sec_tn = format_category_section("🏛️ <b>Tamil Nadu</b>", curated.get("tamil_nadu", []), max_items=max_cat_items)
        sec_cbe = format_category_section("🏙️ <b>Coimbatore</b>", curated.get("coimbatore", []), max_items=max_cat_items)

        sec_trending = ""
        if include_trending and curated.get("trending"):
            sec_trending = format_category_section("🔥 <b>Worth knowing</b>", curated.get("trending", []), max_items=3, is_bullet=True)

        candidate_msg = f"{header}{sec_world}{sec_india}{sec_tn}{sec_cbe}{sec_trending}".strip()

        if len(candidate_msg) <= 3900:
            final_message = candidate_msg
            break
        else:
            logger.warning(
                f"Message length ({len(candidate_msg)}) exceeds 3900 chars; retrying with tighter limits."
            )

    if not final_message:
        # Emergency hard slice if all strategies still exceeded
        final_message = candidate_msg[:3900] + "..."

    logger.info(f"Formatted final Telegram HTML message ({len(final_message)} characters).")
    return final_message
