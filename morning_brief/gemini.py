import json
import logging
import re
from typing import Dict, List, Optional, Set
import httpx

logger = logging.getLogger("morning_brief.gemini")

GEMINI_PROMPT_TEMPLATE = """You are a news editor for a busy person living in Coimbatore, Tamil Nadu, India.
From the provided candidates, select the most important, non-duplicate, factual stories.

Return JSON only matching this exact schema:
{{
  "world": [{"headline": "...", "why_it_matters": "...", "source": "...", "url": "..."}],
  "india": [{"headline": "...", "why_it_matters": "...", "source": "...", "url": "..."}],
  "tamil_nadu": [{"headline": "...", "why_it_matters": "...", "source": "...", "url": "..."}],
  "coimbatore": [{"headline": "...", "why_it_matters": "...", "source": "...", "url": "..."}],
  "trending": [{"headline": "...", "why_it_matters": "...", "source": "...", "url": "..."}]
}}

Rules:
- Return exactly 5 items for world, india, tamil_nadu, and coimbatore if enough strong candidates exist; otherwise return fewer.
- Return at most 3 trending items.
- Prioritize: major developments, policy, economy, safety, infrastructure, water, power, transport, health, education, local civic issues, and major public-interest events.
- Exclude: celebrity gossip, sports scores unless major, repeated stories, opinion pieces, vague listicles, and promotional content.
- Each headline must be under 100 characters.
- Each why_it_matters must be under 120 characters.
- Never invent facts, URLs, or sources.
- Use ONLY URLs provided in the input candidates.

Candidate News Items:
{candidates_json}
"""


def create_non_ai_fallback(categorized_candidates: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """Build a non-AI fallback briefing containing newest headlines per category."""
    fallback_result = {
        "world": [],
        "india": [],
        "tamil_nadu": [],
        "coimbatore": [],
        "trending": [],
    }

    for cat in ["world", "india", "tamil_nadu", "coimbatore"]:
        items = categorized_candidates.get(cat, [])
        selected = items[:5]
        for item in selected:
            title = item.get("title", "")
            if len(title) > 100:
                title = title[:97] + "..."
            summary = item.get("summary", title)
            if len(summary) > 120:
                summary = summary[:117] + "..."
            fallback_result[cat].append(
                {
                    "headline": title,
                    "why_it_matters": summary or title,
                    "source": item.get("source", "News Source"),
                    "url": item.get("url", ""),
                }
            )

    logger.info("Generated non-AI fallback briefing.")
    return fallback_result


def clean_json_response(raw_text: str) -> str:
    """Extract raw JSON text from markdown code fences if present."""
    raw_text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    if match:
        return match.group(1).strip()
    return raw_text


def validate_and_sanitize_gemini_output(
    parsed: Dict,
    valid_urls: Set[str],
) -> Dict[str, List[Dict]]:
    """Validate JSON keys, verify URLs exist in candidates, and enforce text limits."""
    categories = ["world", "india", "tamil_nadu", "coimbatore", "trending"]
    sanitized: Dict[str, List[Dict]] = {cat: [] for cat in categories}

    for cat in categories:
        items = parsed.get(cat, [])
        if not isinstance(items, list):
            continue

        max_limit = 3 if cat == "trending" else 5
        for item in items:
            if len(sanitized[cat]) >= max_limit:
                break

            if not isinstance(item, dict):
                continue

            headline = str(item.get("headline", "")).strip()
            why_it_matters = str(item.get("why_it_matters", "")).strip()
            source = str(item.get("source", "")).strip()
            url = str(item.get("url", "")).strip()

            if not headline or not url:
                continue

            # Validate that URL was actually in input candidates
            if url not in valid_urls:
                logger.warning(f"Rejecting AI item with unrecognized URL: {url}")
                continue

            # Enforce length constraints
            if len(headline) > 100:
                headline = headline[:97] + "..."
            if len(why_it_matters) > 120:
                why_it_matters = why_it_matters[:117] + "..."

            sanitized[cat].append(
                {
                    "headline": headline,
                    "why_it_matters": why_it_matters,
                    "source": source or "News",
                    "url": url,
                }
            )

    return sanitized


async def curate_with_gemini(
    categorized_candidates: Dict[str, List[Dict]],
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> Tuple[Dict[str, List[Dict]], bool]:
    """
    Send candidates to Gemini Flash for editorial selection and formatting.
    Returns (curated_dict, gemini_used).
    """
    if not api_key:
        logger.warning("No GEMINI_API_KEY provided; using non-AI fallback.")
        return create_non_ai_fallback(categorized_candidates), False

    # Collect valid URLs and trim candidates (max 25 per category)
    valid_urls: Set[str] = set()
    trimmed_candidates: Dict[str, List[Dict]] = {}

    for cat, items in categorized_candidates.items():
        trimmed = items[:25]
        trimmed_candidates[cat] = []
        for item in trimmed:
            url = item.get("url", "")
            if url:
                valid_urls.add(url)
                trimmed_candidates[cat].append(
                    {
                        "title": item.get("title"),
                        "source": item.get("source"),
                        "published_at": item.get("published_at"),
                        "summary": item.get("summary"),
                        "url": url,
                    }
                )

    prompt_content = GEMINI_PROMPT_TEMPLATE.format(
        candidates_json=json.dumps(trimmed_candidates, indent=2)
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt_content}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                logger.error("Gemini returned empty candidates.")
                break

            part_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            cleaned_json = clean_json_response(part_text)
            parsed = json.loads(cleaned_json)

            sanitized = validate_and_sanitize_gemini_output(parsed, valid_urls)
            logger.info("Successfully curated news briefing using Gemini Flash.")
            return sanitized, True

        except Exception as e:
            logger.warning(f"Gemini API attempt {attempt + 1} failed: {e}")

    logger.error("All Gemini API attempts failed. Falling back to non-AI briefing.")
    return create_non_ai_fallback(categorized_candidates), False
