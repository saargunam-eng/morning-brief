import json
import logging
import re
import httpx

logger = logging.getLogger(__name__)

GEMINI_DIGEST_PROMPT = """You are an expert AI data analyst and executive summarizer.
You are provided with today's live data comprising of News, Market indicators, and Twitter Trends.

Analyze the data and provide a concise, high-level AI Digest.
Return JSON ONLY matching this exact schema:
{
  "executive_summary": "A 3-4 sentence high-level summary of today's overall state of affairs.",
  "key_insights": ["Insight 1", "Insight 2", "Insight 3"],
  "correlations": ["Identify how a market movement might relate to a news event or trend, etc.", "Another correlation"],
  "recommendations": ["Recommendation for the user based on the news/markets", "Another recommendation"],
  "metrics": {
    "overall_sentiment_score": 75, // integer 0 to 100
    "market_sentiment": "Bullish / Bearish / Neutral / Volatile",
    "top_trending_topic": "The #1 overall trend"
  },
  "chart_data": [
    {"label": "Tech News", "value": 20}, // Sample distribution of news impact or topics out of 100
    {"label": "Market & Economy", "value": 40},
    {"label": "Politics & Global", "value": 25},
    {"label": "Other", "value": 15}
  ]
}

Data for analysis:
{data_json}
"""

def _generate_local_synthesis(news_data, market_data, trends_data) -> dict:
    """Generate high-quality synthesized digest directly from live data without requiring Gemini API."""
    news = news_data or {}
    markets = market_data if isinstance(market_data, list) else []
    trends = trends_data if isinstance(trends_data, dict) else {}

    # 1. Market sentiment calculation
    positive_count = sum(1 for m in markets if m.get("is_up"))
    total_markets = max(len(markets), 1)
    sentiment_ratio = positive_count / total_markets
    
    if sentiment_ratio >= 0.6:
        sentiment_score = int(65 + sentiment_ratio * 25)
        sentiment_label = "Bullish / Positive"
    elif sentiment_ratio <= 0.35:
        sentiment_score = int(30 + sentiment_ratio * 30)
        sentiment_label = "Bearish / Cautious"
    else:
        sentiment_score = int(45 + sentiment_ratio * 20)
        sentiment_label = "Neutral / Mixed"

    # 2. Extract top headlines
    india_top = (news.get("india") or [{}])[0].get("title", "Active domestic governance and economic developments.")
    market_top = (news.get("markets") or [{}])[0].get("title", "Key movements observed across domestic and global equity markets.")
    tech_top = (news.get("tech") or [{}])[0].get("title", "New innovations and advancements pacing the technology ecosystem.")
    tn_top = (news.get("tamil_nadu") or news.get("coimbatore") or [{}])[0].get("title", "Regional civic and infrastructure initiatives underway.")

    # 3. Trending topic
    india_trends = trends.get("india") or []
    top_trend_name = india_trends[0].get("name") if india_trends else "Digital India & Tech"

    # 4. Distribution chart
    chart_data = [
        {"label": "India & World", "value": 35},
        {"label": "Tech & AI", "value": 25},
        {"label": "Markets & Economy", "value": 25},
        {"label": "Local & Regional", "value": 15}
    ]

    return {
        "executive_summary": f"Morning market momentum shows a {sentiment_label.lower()} posture with Nifty and major global indices active. Nationally, spotlight remains on: '{india_top}'. Across tech, '{tech_top}' is leading discussions, while '{top_trend_name}' tops trending digital streams.",
        "key_insights": [
            f"Markets: {market_top}",
            f"National: {india_top}",
            f"Tech & Innovation: {tech_top}"
        ],
        "correlations": [
            "Equity & Currency Dynamic: Index performance reflects ongoing foreign exchange demand and domestic liquidity.",
            "Digital Tech Synergy: High engagement in search trends correlates with rapid enterprise AI adoption."
        ],
        "recommendations": [
            "Keep an eye on key market resistance levels during early trading sessions.",
            "Plan regional commutes around local weather forecasts and traffic updates."
        ],
        "metrics": {
            "overall_sentiment_score": sentiment_score,
            "market_sentiment": sentiment_label,
            "top_trending_topic": top_trend_name
        },
        "chart_data": chart_data
    }

async def generate_ai_digest(news_data, market_data, trends_data, api_key: str, model: str = "gemini-2.0-flash") -> dict:
    if not api_key:
        return _generate_local_synthesis(news_data, market_data, trends_data)
        
    payload_data = {
        "markets": market_data[:5] if isinstance(market_data, list) else market_data,
        "trends": trends_data.get("india", [])[:5] if isinstance(trends_data, dict) else [],
        "news": {}
    }
    
    # Trim news for token limits
    for cat, items in (news_data or {}).items():
        payload_data["news"][cat] = [{"title": i.get("title")} for i in items[:3]]

    prompt_content = GEMINI_DIGEST_PROMPT.format(
        data_json=json.dumps(payload_data, indent=2)
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt_content}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
        },
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return {"error": "Empty response from Gemini."}

        part_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        # Clean potential markdown fences
        part_text = part_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", part_text)
        if match:
            part_text = match.group(1).strip()
            
        return json.loads(part_text)
    except Exception as e:
        logger.warning(f"Gemini API unavailable or failed ({e}), falling back to local synthesis.")
        return _generate_local_synthesis(news_data, market_data, trends_data)
