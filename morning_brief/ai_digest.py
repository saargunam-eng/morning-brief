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

async def generate_ai_digest(news_data, market_data, trends_data, api_key: str, model: str = "gemini-2.0-flash") -> dict:
    if not api_key:
        return {"error": "GEMINI_API_KEY is missing."}
        
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
        logger.error(f"Failed to generate AI digest: {e}")
        return {"error": str(e)}
