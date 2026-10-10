import asyncio
import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from morning_brief.config import settings
from morning_brief.rss import fetch_all_feeds
from morning_brief.weather import fetch_coimbatore_weather
from morning_brief.markets import fetch_market_indicators
import httpx

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
async def api_weather():
    cached = get_cached("weather")
    if cached: return cached
    
    data = await fetch_coimbatore_weather(
        lat=settings.coimbatore_lat, 
        lon=settings.coimbatore_lon, 
        tz=settings.timezone
    )
    set_cache("weather", data)
    return data

@app.get("/api/markets")
async def api_markets():
    cached = get_cached("markets")
    if cached: return cached
    
    data = await fetch_market_indicators()
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
async def api_astronomy():
    cached = get_cached("astronomy")
    if cached: return cached
    
    async with httpx.AsyncClient() as client:
        # Sunrise/Sunset for Coimbatore (Free, no key)
        resp = await client.get(f"https://api.sunrise-sunset.org/json?lat={settings.coimbatore_lat}&lng={settings.coimbatore_lon}&formatted=0")
        sun_data = resp.json()
        
        # NASA Astronomy Picture of the Day (Using DEMO_KEY)
        nasa_resp = await client.get("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY")
        nasa_data = nasa_resp.json()
        
    result = {"sun": sun_data, "nasa": nasa_data}
    set_cache("astronomy", result)
    return result

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
