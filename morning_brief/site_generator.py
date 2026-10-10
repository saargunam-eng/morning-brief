import asyncio
import html
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, List

from morning_brief.config import settings
from morning_brief.db import init_db, get_recent_sent_hashes_and_titles
from morning_brief.dedupe import deduplicate_items
from morning_brief.rss import fetch_all_feeds
from morning_brief.weather import fetch_coimbatore_weather
from morning_brief.formatter import build_telegram_html_message

logger = logging.getLogger("morning_brief.site_generator")


def generate_html_dashboard(
    categorized_news: Dict[str, List[Dict]],
    weather: Dict,
    telegram_preview_text: str,
    output_path: str = "index.html",
) -> None:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    date_str = now.strftime("%d %B %Y")
    time_str = now.strftime("%I:%M %p IST")

    cur_temp = weather.get("current_temp", 28.0)
    max_temp = weather.get("max_temp", 32.0)
    min_temp = weather.get("min_temp", 22.0)
    weather_line = weather.get("weather_line", "Pleasant weather in Coimbatore.")
    humidity = weather.get("humidity", 70)
    wind_speed = weather.get("wind_speed", 10.0)

    # Categories config
    cat_meta = {
        "world": ("🌍 World News", "Major global developments & international affairs"),
        "india": ("🇮🇳 India National", "Top national stories, policy & national economy"),
        "tamil_nadu": ("🏛️ Tamil Nadu State", "State government news, regional policies & events"),
        "coimbatore": ("🏙️ Coimbatore Local", "Civic issues, local infrastructure, power & water updates"),
    }

    # Generate HTML cards for news
    news_sections_html = ""
    for cat_key, (cat_title, cat_subtitle) in cat_meta.items():
        items = categorized_news.get(cat_key, [])
        items_html = ""

        if not items:
            items_html = '<p class="no-items">No recent news items found for this section in the last 24 hours.</p>'
        else:
            for idx, item in enumerate(items[:6], start=1):
                title = html.escape(item.get("title", ""))
                url = html.escape(item.get("url", "#"))
                source = html.escape(item.get("source", "News"))
                summary = html.escape(item.get("summary", ""))
                pub_time = html.escape(item.get("published_at", ""))

                items_html += f"""
                <article class="news-card">
                    <div class="news-header">
                        <span class="news-index">#{idx}</span>
                        <span class="news-source">{source}</span>
                    </div>
                    <h3 class="news-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
                    <p class="news-summary">{summary if summary else title}</p>
                    <div class="news-footer">
                        <a href="{url}" target="_blank" rel="noopener" class="read-more">Read full story &rarr;</a>
                    </div>
                </article>
                """

        news_sections_html += f"""
        <section class="category-block" id="{cat_key}">
            <div class="category-header">
                <h2>{cat_title}</h2>
                <p>{cat_subtitle}</p>
            </div>
            <div class="news-grid">
                {items_html}
            </div>
        </section>
        """

    # Telegram preview formatted text
    telegram_preview_html = html.escape(telegram_preview_text)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Brief — Coimbatore Personal News & Weather</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --card-border: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-orange: #fb923c;
            --accent-green: #4ade80;
            --accent-purple: #c084fc;
            --glass-bg: rgba(30, 41, 59, 0.7);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding-bottom: 60px;
        }}

        header {{
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
            border-bottom: 1px solid var(--card-border);
            padding: 40px 20px 30px;
            text-align: center;
            position: relative;
        }}

        .header-container {{
            max-width: 1100px;
            margin: 0 auto;
        }}

        .badge {{
            display: inline-block;
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent-blue);
            font-size: 0.85rem;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid rgba(56, 189, 248, 0.3);
            margin-bottom: 15px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.8rem;
            font-weight: 700;
            background: linear-gradient(90deg, #f8fafc, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: var(--text-muted);
            font-size: 1.1rem;
            margin-bottom: 25px;
        }}

        .time-bar {{
            font-size: 0.95rem;
            color: var(--accent-orange);
            font-weight: 500;
        }}

        .container {{
            max-width: 1100px;
            margin: 30px auto;
            padding: 0 20px;
        }}

        /* Weather Section */
        .weather-banner {{
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.1) 0%, rgba(192, 132, 252, 0.1) 100%);
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 16px;
            padding: 25px 30px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 40px;
            backdrop-filter: blur(10px);
        }}

        .weather-info h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.6rem;
            color: var(--text-main);
            margin-bottom: 6px;
        }}

        .weather-desc {{
            color: var(--accent-blue);
            font-weight: 500;
            font-size: 1.05rem;
        }}

        .weather-stats {{
            display: flex;
            gap: 25px;
        }}

        .stat-box {{
            text-align: center;
            padding: 10px 15px;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .stat-box .val {{
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--accent-orange);
        }}

        .stat-box .lbl {{
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        /* Category Section */
        .category-block {{
            margin-bottom: 45px;
        }}

        .category-header {{
            margin-bottom: 20px;
            border-left: 4px solid var(--accent-blue);
            padding-left: 14px;
        }}

        .category-header h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.8rem;
            color: var(--text-main);
        }}

        .category-header p {{
            color: var(--text-muted);
            font-size: 0.95rem;
        }}

        .news-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }}

        .news-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .news-card:hover {{
            transform: translateY(-4px);
            border-color: var(--accent-blue);
        }}

        .news-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .news-index {{
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--accent-blue);
        }}

        .news-source {{
            font-size: 0.75rem;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-muted);
            padding: 3px 8px;
            border-radius: 4px;
        }}

        .news-title {{
            font-size: 1.05rem;
            font-weight: 600;
            line-height: 1.4;
            margin-bottom: 10px;
        }}

        .news-title a {{
            color: var(--text-main);
            text-decoration: none;
        }}

        .news-title a:hover {{
            color: var(--accent-blue);
        }}

        .news-summary {{
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-bottom: 15px;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .news-footer {{
            margin-top: auto;
            text-align: right;
        }}

        .read-more {{
            font-size: 0.85rem;
            color: var(--accent-blue);
            text-decoration: none;
            font-weight: 600;
        }}

        .read-more:hover {{
            text-decoration: underline;
        }}

        /* Telegram Preview Box */
        .telegram-preview-box {{
            background: #090d16;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 25px;
            margin-top: 50px;
        }}

        .telegram-preview-box h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.3rem;
            color: var(--accent-green);
            margin-bottom: 15px;
        }}

        pre.telegram-code {{
            background: #030712;
            color: #38bdf8;
            padding: 18px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.9rem;
            white-space: pre-wrap;
            word-wrap: break-word;
            border: 1px solid #1f2937;
            max-height: 400px;
            overflow-y: auto;
        }}

        footer {{
            text-align: center;
            padding: 30px 20px 0;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--card-border);
            margin-top: 40px;
        }}

        .no-items {{
            color: var(--text-muted);
            font-style: italic;
        }}

        @media (max-width: 768px) {{
            h1 {{ font-size: 2.1rem; }}
            .weather-banner {{ flex-direction: column; gap: 20px; text-align: center; }}
            .news-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>

    <header>
        <div class="header-container">
            <span class="badge">☀️ Daily Personal News Briefing — v1.0</span>
            <h1>Morning Brief: Coimbatore</h1>
            <p class="subtitle">Curated News & Real-Time Weather Digest</p>
            <p class="time-bar">Updated Live: {date_str} at {time_str}</p>
        </div>
    </header>

    <div class="container">

        <!-- Weather Banner -->
        <section class="weather-banner">
            <div class="weather-info">
                <h3>☀️ Coimbatore Weather Forecast</h3>
                <p class="weather-desc">{weather_line}</p>
            </div>
            <div class="weather-stats">
                <div class="stat-box">
                    <div class="val">{cur_temp}°C</div>
                    <div class="lbl">Now</div>
                </div>
                <div class="stat-box">
                    <div class="val">{max_temp}°C</div>
                    <div class="lbl">High</div>
                </div>
                <div class="stat-box">
                    <div class="stat-box">
                    <div class="val">{min_temp}°C</div>
                    <div class="lbl">Low</div>
                </div>
                <div class="stat-box">
                    <div class="val">{humidity}%</div>
                    <div class="lbl">Humidity</div>
                </div>
            </div>
        </section>

        <!-- News Categories -->
        {news_sections_html}

        <!-- Telegram Format Preview -->
        <section class="telegram-preview-box">
            <h3>💬 Live Telegram Message Payload Preview (HTML Mode)</h3>
            <p style="color: var(--text-muted); margin-bottom: 12px; font-size: 0.9rem;">
                This is the exact string payload delivered to your Telegram Bot every morning at 07:30 IST:
            </p>
            <pre class="telegram-code">{telegram_preview_html}</pre>
        </section>

        <footer>
            <p>Morning Brief Project — Powered by Open-Meteo Weather API, The Hindu RSS & Google News RSS</p>
        </footer>

    </div>

</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Successfully generated static GitHub Pages site at '{output_path}'")


async def run_site_generation() -> None:
    logger.info("Initializing DB & fetching live data for GitHub Pages build...")
    init_db(settings.db_path)
    sent_hashes, sent_titles = get_recent_sent_hashes_and_titles(settings.db_path, hours=72)

    categorized_raw, _, _ = await fetch_all_feeds(settings.feeds)

    categorized_deduped = {}
    for cat, items in categorized_raw.items():
        categorized_deduped[cat] = deduplicate_items(items, sent_hashes, sent_titles)

    weather = await fetch_coimbatore_weather(
        lat=settings.coimbatore_lat,
        lon=settings.coimbatore_lon,
        tz=settings.timezone,
    )

    # Format sample telegram digest from raw deduplicated items
    curated_sample = {}
    for cat in ["world", "india", "tamil_nadu", "coimbatore"]:
        items = categorized_deduped.get(cat, [])
        curated_sample[cat] = [
            {
                "headline": item.get("title", "")[:95],
                "why_it_matters": item.get("summary", item.get("title", ""))[:115],
                "source": item.get("source", "News"),
                "url": item.get("url", ""),
            }
            for item in items[:5]
        ]

    telegram_preview = build_telegram_html_message(curated_sample, weather, settings.timezone)

    generate_html_dashboard(
        categorized_news=categorized_deduped,
        weather=weather,
        telegram_preview_text=telegram_preview,
        output_path="index.html",
    )


def main():
    asyncio.run(run_site_generation())


if __name__ == "__main__":
    main()
