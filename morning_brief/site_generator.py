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
from morning_brief.markets import fetch_market_indicators
from morning_brief.formatter import build_telegram_html_message

logger = logging.getLogger("morning_brief.site_generator")


def generate_html_dashboard(
    categorized_news: Dict[str, List[Dict]],
    weather: Dict,
    markets: List[Dict],
    telegram_preview_text: str,
    output_path: str = "index.html",
) -> None:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%I:%M %p IST")

    cur_temp = weather.get("current_temp", 28.0)
    max_temp = weather.get("max_temp", 32.0)
    min_temp = weather.get("min_temp", 22.0)
    weather_line = weather.get("weather_line", "Pleasant weather in Coimbatore.")
    humidity = weather.get("humidity", 70)

    # 1. Market Ticker HTML
    ticker_items_html = ""
    for m in markets:
        symbol = html.escape(m.get("symbol", ""))
        name = html.escape(m.get("name", ""))
        price = m.get("price", 0.0)
        chg = m.get("change", 0.0)
        pct = m.get("pct_change", 0.0)
        is_up = m.get("is_up", True)

        badge_cls = "up" if is_up else "down"
        sign = "+" if chg > 0 else ""

        ticker_items_html += f"""
        <div class="ticker-card {badge_cls}">
            <div class="ticker-top">
                <span class="ticker-name">{name}</span>
                <span class="ticker-badge">{sign}{pct:.2f}%</span>
            </div>
            <div class="ticker-price">{price:,.2f} <span class="ticker-chg">{sign}{chg:,.2f}</span></div>
        </div>
        """

    # Categories metadata
    cat_meta = {
        "markets": ("📈 Markets & Economy", "Nifty 50, Sensex, global stocks & financial developments", "tab-markets"),
        "coimbatore": ("🏙️ Coimbatore Local", "Civic issues, infrastructure, power & water updates", "tab-local"),
        "tamil_nadu": ("🏛️ Tamil Nadu State", "State governance, regional economy & policy news", "tab-local"),
        "india": ("🇮🇳 India National", "Top national stories, economy & public policy", "tab-national"),
        "world": ("🌍 World News", "Major global developments & geopolitics", "tab-national"),
        "trending": ("🔥 Trending & Worth Knowing", "Top viral, tech & web trends across India", "tab-trending"),
    }

    # Generate HTML cards for each category
    news_sections_html = ""
    for cat_key, (cat_title, cat_subtitle, cat_group) in cat_meta.items():
        items = categorized_news.get(cat_key, [])
        items_html = ""

        if not items:
            items_html = '<p class="no-items">No recent news items found for this section in the last 24 hours.</p>'
        else:
            limit = 5 if cat_key in ["markets", "trending"] else 5
            for idx, item in enumerate(items[:limit], start=1):
                title = html.escape(item.get("title", ""))
                url = html.escape(item.get("url", "#"))
                source = html.escape(item.get("source", "News"))
                summary = html.escape(item.get("summary", ""))

                items_html += f"""
                <article class="news-card">
                    <div class="card-meta">
                        <span class="card-num">#{idx}</span>
                        <span class="card-src">{source}</span>
                    </div>
                    <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
                    <p class="card-desc">{summary if summary else title}</p>
                    <div class="card-link">
                        <a href="{url}" target="_blank" rel="noopener">Read story &rarr;</a>
                    </div>
                </article>
                """

        news_sections_html += f"""
        <section class="cat-section {cat_group}" data-category="{cat_key}">
            <div class="cat-head">
                <h2>{cat_title}</h2>
                <p>{cat_subtitle}</p>
            </div>
            <div class="card-grid">
                {items_html}
            </div>
        </section>
        """

    telegram_preview_html = html.escape(telegram_preview_text)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    <title>Morning Brief — Markets, News & Coimbatore Digest</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #090d16;
            --card-dark: #131b2e;
            --border-dark: #1e293b;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-red: #ef4444;
            --accent-orange: #f97316;
            --accent-purple: #a855f7;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            line-height: 1.5;
            padding-bottom: 50px;
        }}

        /* Header */
        header {{
            background: linear-gradient(180deg, #111827 0%, #090d16 100%);
            border-bottom: 1px solid var(--border-dark);
            padding: 24px 16px 16px;
            text-align: center;
        }}

        .header-inner {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .pill-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(56, 189, 248, 0.12);
            color: var(--accent-blue);
            font-size: 0.75rem;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 20px;
            border: 1px solid rgba(56, 189, 248, 0.25);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(90deg, #ffffff, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }}

        .sub-header {{
            color: var(--text-sub);
            font-size: 0.9rem;
            margin-bottom: 16px;
        }}

        /* Market Ticker Bar */
        .ticker-bar {{
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding: 8px 16px 16px;
            max-width: 1200px;
            margin: 0 auto;
            scrollbar-width: thin;
        }}

        .ticker-bar::-webkit-scrollbar {{
            height: 4px;
        }}
        .ticker-bar::-webkit-scrollbar-thumb {{
            background: var(--border-dark);
            border-radius: 2px;
        }}

        .ticker-card {{
            min-width: 160px;
            flex: 0 0 auto;
            background: var(--card-dark);
            border: 1px solid var(--border-dark);
            border-radius: 10px;
            padding: 10px 14px;
            transition: border-color 0.2s ease;
        }}

        .ticker-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}

        .ticker-name {{
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--text-sub);
            text-transform: uppercase;
        }}

        .ticker-badge {{
            font-size: 0.7rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .ticker-card.up .ticker-badge {{
            background: rgba(34, 197, 94, 0.15);
            color: var(--accent-green);
        }}

        .ticker-card.down .ticker-badge {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
        }}

        .ticker-price {{
            font-size: 1rem;
            font-weight: 700;
            color: var(--text-main);
        }}

        .ticker-chg {{
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--text-sub);
            margin-left: 4px;
        }}

        /* Main App Layout */
        .app-container {{
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 16px;
        }}

        /* Compact Weather Bar */
        .compact-weather {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid var(--border-dark);
            border-radius: 12px;
            padding: 14px 20px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
        }}

        .cw-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .cw-temp {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent-orange);
        }}

        .cw-desc {{
            font-size: 0.88rem;
            color: var(--text-main);
            font-weight: 500;
        }}

        .cw-stats {{
            display: flex;
            gap: 16px;
            font-size: 0.8rem;
            color: var(--text-sub);
        }}

        .cw-stats strong {{
            color: var(--text-main);
        }}

        /* Tab Filter Bar */
        .tab-bar {{
            display: flex;
            gap: 8px;
            overflow-x: auto;
            margin-bottom: 24px;
            padding-bottom: 4px;
            border-bottom: 1px solid var(--border-dark);
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-sub);
            font-size: 0.85rem;
            font-weight: 600;
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
        }}

        .tab-btn:hover {{
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }}

        .tab-btn.active {{
            background: var(--accent-blue);
            color: #000;
        }}

        /* Category Grid */
        .cat-section {{
            margin-bottom: 36px;
        }}

        .cat-head {{
            margin-bottom: 14px;
            border-left: 3px solid var(--accent-blue);
            padding-left: 10px;
        }}

        .cat-head h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.3rem;
            font-weight: 700;
        }}

        .cat-head p {{
            font-size: 0.8rem;
            color: var(--text-sub);
        }}

        .card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 16px;
        }}

        .news-card {{
            background: var(--card-dark);
            border: 1px solid var(--border-dark);
            border-radius: 10px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.15s ease, border-color 0.15s ease;
        }}

        .news-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent-blue);
        }}

        .card-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}

        .card-num {{
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--accent-blue);
        }}

        .card-src {{
            font-size: 0.7rem;
            color: var(--text-sub);
            background: rgba(255, 255, 255, 0.05);
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .card-title {{
            font-size: 0.95rem;
            font-weight: 600;
            line-height: 1.35;
            margin-bottom: 8px;
        }}

        .card-title a {{
            color: var(--text-main);
            text-decoration: none;
        }}

        .card-title a:hover {{
            color: var(--accent-blue);
        }}

        .card-desc {{
            font-size: 0.82rem;
            color: var(--text-sub);
            margin-bottom: 12px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .card-link {{
            text-align: right;
            margin-top: auto;
        }}

        .card-link a {{
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--accent-blue);
            text-decoration: none;
        }}

        /* Payload Box */
        .payload-box {{
            background: #030712;
            border: 1px solid var(--border-dark);
            border-radius: 10px;
            padding: 20px;
            margin-top: 40px;
        }}

        .payload-box h3 {{
            font-size: 1rem;
            font-weight: 700;
            color: var(--accent-green);
            margin-bottom: 8px;
        }}

        pre.code-block {{
            background: #090d16;
            color: #38bdf8;
            padding: 12px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.8rem;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 250px;
            overflow-y: auto;
        }}

        footer {{
            text-align: center;
            color: var(--text-sub);
            font-size: 0.75rem;
            margin-top: 30px;
        }}

        @media (max-width: 600px) {{
            h1 {{ font-size: 1.6rem; }}
            .card-grid {{ grid-template-columns: 1fr; }}
            .cw-stats {{ width: 100%; justify-content: space-between; margin-top: 4px; }}
        }}
    </style>
</head>
<body>

    <header>
        <div class="header-inner">
            <div class="pill-badge">☀️ Morning Brief v1.1</div>
            <h1>Coimbatore & Global Dashboard</h1>
            <p class="sub-header">Markets • Coimbatore • Tamil Nadu • National • Global • Updated {time_str}</p>
        </div>
    </header>

    <!-- Financial Market Ticker Bar -->
    <div class="ticker-bar">
        {ticker_items_html}
    </div>

    <div class="app-container">

        <!-- Compact Weather Bar -->
        <div class="compact-weather">
            <div class="cw-left">
                <span class="cw-temp">{cur_temp}°C</span>
                <div>
                    <div class="cw-desc">☀️ Coimbatore Weather</div>
                    <div style="font-size: 0.8rem; color: var(--text-sub);">{weather_line}</div>
                </div>
            </div>
            <div class="cw-stats">
                <span>High: <strong>{max_temp}°C</strong></span>
                <span>Low: <strong>{min_temp}°C</strong></span>
                <span>Humidity: <strong>{humidity}%</strong></span>
            </div>
        </div>

        <!-- Filter Tabs -->
        <div class="tab-bar">
            <button class="tab-btn active" onclick="filterCategory('all', this)">All Feeds</button>
            <button class="tab-btn" onclick="filterCategory('markets', this)">📈 Markets</button>
            <button class="tab-btn" onclick="filterCategory('coimbatore', this)">🏙️ Local & TN</button>
            <button class="tab-btn" onclick="filterCategory('india', this)">🇮🇳 India & World</button>
            <button class="tab-btn" onclick="filterCategory('trending', this)">🔥 Trending</button>
        </div>

        <!-- Category Sections -->
        {news_sections_html}

        <!-- Telegram Payload Box -->
        <div class="payload-box">
            <h3>💬 Automated Telegram Bot Payload (07:30 IST Target)</h3>
            <pre class="code-block">{telegram_preview_html}</pre>
        </div>

        <footer>
            <p>Morning Briefing Service — Live Yahoo Finance • Open-Meteo Weather • The Hindu • Moneycontrol • Google Trends</p>
        </footer>

    </div>

    <script>
        function filterCategory(cat, btn) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            document.querySelectorAll('.cat-section').forEach(sec => {{
                const secCat = sec.getAttribute('data-category');
                if (cat === 'all') {{
                    sec.style.display = 'block';
                }} else if (cat === 'coimbatore' && (secCat === 'coimbatore' || secCat === 'tamil_nadu')) {{
                    sec.style.display = 'block';
                }} else if (cat === 'india' && (secCat === 'india' || secCat === 'world')) {{
                    sec.style.display = 'block';
                }} else if (secCat === cat) {{
                    sec.style.display = 'block';
                }} else {{
                    sec.style.display = 'none';
                }}
            }});
        }}
    </script>

</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Successfully generated updated v1.1 site at '{output_path}'")


async def run_site_generation() -> None:
    logger.info("Fetching markets, weather, and news feeds for v1.1 build...")
    init_db(settings.db_path)
    sent_hashes, sent_titles = get_recent_sent_hashes_and_titles(settings.db_path, hours=72)

    # Parallel fetch of RSS, Weather, and Markets
    categorized_raw, _, _ = await fetch_all_feeds(settings.feeds)
    weather = await fetch_coimbatore_weather(lat=settings.coimbatore_lat, lon=settings.coimbatore_lon, tz=settings.timezone)
    markets = await fetch_market_indicators()

    categorized_deduped = {}
    for cat, items in categorized_raw.items():
        categorized_deduped[cat] = deduplicate_items(items, sent_hashes, sent_titles)

    # Sample Telegram digest
    curated_sample = {}
    for cat in ["markets", "world", "india", "tamil_nadu", "coimbatore"]:
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
        markets=markets,
        telegram_preview_text=telegram_preview,
        output_path="index.html",
    )


def main():
    asyncio.run(run_site_generation())


if __name__ == "__main__":
    main()
