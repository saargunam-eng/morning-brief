import asyncio
import logging
from typing import Dict, List
import httpx

logger = logging.getLogger("morning_brief.markets")

MARKET_SYMBOLS = [
    {"symbol": "^NSEI", "name": "Nifty 50", "region": "India"},
    {"symbol": "^BSESN", "name": "Sensex", "region": "India"},
    {"symbol": "^GSPC", "name": "S&P 500", "region": "US"},
    {"symbol": "^IXIC", "name": "Nasdaq", "region": "US"},
    {"symbol": "USDINR=X", "name": "USD / INR", "region": "FX"},
    {"symbol": "GC=F", "name": "Gold (oz)", "region": "Commodity"},
]


async def fetch_single_market_quote(client: httpx.AsyncClient, sym_info: Dict) -> Dict:
    symbol = sym_info["symbol"]
    name = sym_info["name"]
    region = sym_info["region"]

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 MorningBrief/1.1"
        )
    }

    try:
        resp = await client.get(url, headers=headers, follow_redirects=True, timeout=8.0)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0.0)
                prev_close = meta.get("previousClose") or meta.get("chartPreviousClose") or price

                change = price - prev_close if price and prev_close else 0.0
                pct_change = (change / prev_close) * 100 if prev_close else 0.0

                return {
                    "symbol": symbol,
                    "name": name,
                    "region": region,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "pct_change": round(pct_change, 2),
                    "is_up": change >= 0,
                    "success": True,
                }
    except Exception as e:
        logger.warning(f"Failed to fetch market quote for {name} ({symbol}): {e}")

    return {
        "symbol": symbol,
        "name": name,
        "region": region,
        "price": 0.0,
        "change": 0.0,
        "pct_change": 0.0,
        "is_up": True,
        "success": False,
    }


async def fetch_market_indicators() -> List[Dict]:
    """Fetch live financial market indices asynchronously."""
    async with httpx.AsyncClient() as client:
        tasks = [fetch_single_market_quote(client, sym) for sym in MARKET_SYMBOLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        quotes = []
        for res in results:
            if isinstance(res, dict) and res.get("success"):
                quotes.append(res)
        return quotes
