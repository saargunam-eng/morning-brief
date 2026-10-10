import time

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from morning_brief.config import settings
from morning_brief.markets import fetch_market_indicators
from morning_brief.rss import fetch_all_feeds
from morning_brief.weather import fetch_coimbatore_weather
from morning_brief.trends import fetch_twitter_trends

app = FastAPI(title="Morning Brief API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory cache to keep it snappy
CACHE = {}
CACHE_TTL = 300  # 5 minutes

def get_cached(key):
    if key in CACHE:
        val, ts = CACHE[key]
        if time.time() - ts < CACHE_TTL:
            return val
    return None

def set_cache(key, val):
    CACHE[key] = (val, time.time())

@app.get("/api/weather")
async def api_weather(lat: float = None, lon: float = None):
    use_lat = lat if lat is not None else settings.coimbatore_lat
    use_lon = lon if lon is not None else settings.coimbatore_lon
    cache_key = f"weather_{use_lat}_{use_lon}"
    cached = get_cached(cache_key)
    if cached: return cached
    
    data = await fetch_coimbatore_weather(
        lat=use_lat, 
        lon=use_lon, 
        tz=settings.timezone
    )
    
    # Add Open-Meteo AQI (Free, no key)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={use_lat}&longitude={use_lon}&current=us_aqi")
            aqi_data = resp.json()
            data["aqi"] = aqi_data.get("current", {}).get("us_aqi", "N/A")
    except Exception:
        data["aqi"] = "N/A"
        
    set_cache(cache_key, data)
    return data

@app.get("/api/markets")
async def api_markets():
    cached = get_cached("markets")
    if cached: return cached
    
    data = await fetch_market_indicators()
    
    # Add Forex (USD to INR) via ExchangeRate-API (Free, no key)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://open.er-api.com/v6/latest/USD")
            rates = resp.json()
            inr = rates.get("rates", {}).get("INR", 0)
            if inr:
                data.append({
                    "symbol": "USDINR",
                    "name": "USD / INR",
                    "price": inr,
                    "change": 0.0,
                    "pct_change": 0.0,
                    "is_up": True
                })
    except Exception:
        pass

    set_cache("markets", data)
    return data

@app.get("/api/news")
async def api_news():
    cached = get_cached("news")
    if cached: return cached
    
    categorized_raw, _, _ = await fetch_all_feeds(settings.feeds)
    set_cache("news", categorized_raw)
    return categorized_raw

@app.get("/api/movies")
async def api_movies():
    cached = get_cached("movies")
    if cached: return cached
    
    async with httpx.AsyncClient() as client:
        # iTunes Top 10 Movies (Completely free, no key, authentic JSON)
        resp = await client.get("https://itunes.apple.com/us/rss/topmovies/limit=10/json")
        data = resp.json()
        
    set_cache("movies", data)
    return data

@app.get("/api/astronomy")
async def api_astronomy(lat: float = None, lon: float = None):
    use_lat = lat if lat is not None else settings.coimbatore_lat
    use_lon = lon if lon is not None else settings.coimbatore_lon
    cache_key = f"astronomy_{use_lat}_{use_lon}"
    cached = get_cached(cache_key)
    if cached: return cached
    
    async with httpx.AsyncClient() as client:
        # Sunrise/Sunset for provided coordinates
        resp = await client.get(f"https://api.sunrise-sunset.org/json?lat={use_lat}&lng={use_lon}&formatted=0")
        sun_data = resp.json()
        
        # NASA Astronomy Picture of the Day (Using DEMO_KEY)
        nasa_resp = await client.get("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY")
        nasa_data = nasa_resp.json()
        
    result = {"sun": sun_data, "nasa": nasa_data}
    set_cache(cache_key, result)
    return result

@app.get("/api/sports")
async def api_sports():
    cached = get_cached("sports")
    if cached: return cached
    
    async with httpx.AsyncClient() as client:
        # ESPN Free API for top sports news/scores (generic top headlines)
        resp = await client.get("https://site.api.espn.com/apis/site/v2/sports/cricket/8039/news")
        data = resp.json()
        
    set_cache("sports", data)
    return data

@app.get("/api/calendar")
async def api_calendar():
    cached = get_cached("calendar")
    if cached: return cached
    
    import datetime
    try:
        import holidays
        year = datetime.datetime.now().year
        india_holidays = holidays.India(years=year)
        
        data = []
        today = datetime.date.today()
        for date, name in sorted(india_holidays.items()):
            if date >= today:
                data.append({"date": str(date), "name": name, "localName": name})
                if len(data) >= 6:
                    break
    except ImportError:
        data = []
            
    set_cache("calendar", data)
    return data

@app.get("/api/trends")
async def api_trends():
    cached = get_cached("twitter_trends")
    if cached: return cached
    
    data = await fetch_twitter_trends()
    set_cache("twitter_trends", data)
    return data

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
