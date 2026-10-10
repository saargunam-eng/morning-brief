import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


class FeedConfig(BaseModel):
    name: str
    category: str
    url: str


class Settings(BaseModel):
    # Credentials & API Keys
    telegram_bot_token: str = Field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = Field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

    # Models & Timezone
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    timezone: str = Field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Kolkata"))
    briefing_time: str = Field(default_factory=lambda: os.getenv("BRIEFING_TIME", "07:30"))
    dedupe_window_hours: int = Field(default_factory=lambda: int(os.getenv("DEDUPE_WINDOW_HOURS", "72")))

    # Location (Coimbatore default)
    coimbatore_lat: float = Field(default_factory=lambda: float(os.getenv("COIMBATORE_LAT", "11.0168")))
    coimbatore_lon: float = Field(default_factory=lambda: float(os.getenv("COIMBATORE_LON", "76.9558")))

    # Database Path
    db_path: str = Field(default_factory=lambda: os.getenv("DB_PATH", "morning_brief.db"))

    # Configured RSS Feeds
    feeds: list[FeedConfig] = [
        FeedConfig(
            name="Moneycontrol Markets",
            category="markets",
            url="https://www.moneycontrol.com/rss/MCtopnews.xml",
        ),
        FeedConfig(
            name="Economic Times Markets",
            category="markets",
            url="https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        ),
        FeedConfig(
            name="The Hindu World",
            category="world",
            url="https://www.thehindu.com/news/international/feeder/default.rss",
        ),
        FeedConfig(
            name="The Hindu India",
            category="india",
            url="https://www.thehindu.com/news/national/feeder/default.rss",
        ),
        FeedConfig(
            name="The Hindu Tamil Nadu",
            category="tamil_nadu",
            url="https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss",
        ),
        FeedConfig(
            name="The Hindu Coimbatore",
            category="coimbatore",
            url="https://www.thehindu.com/news/cities/Coimbatore/feeder/default.rss",
        ),
        FeedConfig(
            name="Google News India",
            category="india",
            url="https://news.google.com/rss/search?q=India+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
        ),
        FeedConfig(
            name="Google News Tamil Nadu",
            category="tamil_nadu",
            url="https://news.google.com/rss/search?q=Tamil+Nadu+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
        ),
        FeedConfig(
            name="Google News Coimbatore",
            category="coimbatore",
            url="https://news.google.com/rss/search?q=Coimbatore+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
        ),
        FeedConfig(
            name="Google Trends India",
            category="trending",
            url="https://trends.google.com/trending/rss?geo=IN",
        ),
    ]


def load_settings(config_file: str = "config.yaml") -> Settings:
    settings = Settings()
    config_path = Path(config_file)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if "feeds" in data and isinstance(data["feeds"], list):
                settings.feeds = [FeedConfig(**item) for item in data["feeds"]]
            for k, v in data.items():
                if k != "feeds" and hasattr(settings, k) and v is not None:
                    setattr(settings, k, v)
    return settings


settings = load_settings()
