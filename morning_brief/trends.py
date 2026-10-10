import logging
import httpx
from bs4 import BeautifulSoup
from typing import Dict, List

logger = logging.getLogger("morning_brief.trends")

async def fetch_twitter_trends() -> Dict[str, List[Dict]]:
    """
    Fetch trending topics from trends24.in for India, World, and Chennai.
    """
    locations = {
        "world": "https://trends24.in/",
        "india": "https://trends24.in/india/",
        "tamil_nadu": "https://trends24.in/india/chennai/"
    }
    
    results = {}
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for loc_name, url in locations.items():
            try:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, "html.parser")
                # Trends24 lists trends in an ordered list with class 'trend-card__list'
                # The first card is the most recent (Current).
                trend_card = soup.find("ul", class_="trend-card__list")
                
                trends = []
                if trend_card:
                    for li in trend_card.find_all("li"):
                        a_tag = li.find("a")
                        if a_tag:
                            trend_name = a_tag.text.strip()
                            trend_url = a_tag.get("href")
                            
                            tweet_count_span = li.find("span", class_="tweet-count")
                            tweet_count = tweet_count_span.text.strip() if tweet_count_span else ""
                            
                            trends.append({
                                "name": trend_name,
                                "url": trend_url,
                                "tweet_count": tweet_count
                            })
                            
                            if len(trends) >= 15:
                                break
                                
                results[loc_name] = trends
                
            except Exception as e:
                logger.error(f"Failed to fetch trends for {loc_name} from {url}: {e}")
                results[loc_name] = []
                
    return results
