import hashlib
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger("morning_brief.dedupe")

STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "is", "are",
    "was", "were", "with", "by", "from", "as", "after", "says", "over", "it",
    "its", "that", "this", "be", "has", "have", "had", "will", "would", "about",
    "more", "new", "top", "latest", "brief", "today", "day"
}


def normalize_text(text: str) -> str:
    """Lowercase, strip non-alphanumeric characters, and collapse spaces."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def create_url_hash(title: str, url: str) -> str:
    """Create a unique hash from normalized title and URL path."""
    norm_title = normalize_text(title)
    parsed = urlparse(url)
    clean_url_path = parsed.netloc + parsed.path
    combined = f"{norm_title}:{clean_url_path}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


def get_meaningful_tokens(normalized_title: str) -> set[str]:
    """Extract non-stopword tokens from normalized title."""
    words = normalized_title.split()
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def calculate_token_overlap(tokens1: set[str], tokens2: set[str]) -> float:
    """Calculate token overlap similarity ratio between two sets of tokens."""
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    min_len = min(len(tokens1), len(tokens2))
    return len(intersection) / min_len


def is_near_duplicate_title(
    norm_title: str,
    existing_titles: list[str],
    threshold: float = 0.80,
) -> bool:
    """Check if normalized title shares > threshold token overlap with existing titles."""
    tokens = get_meaningful_tokens(norm_title)
    if not tokens:
        return False

    for existing in existing_titles:
        ex_tokens = get_meaningful_tokens(existing)
        if calculate_token_overlap(tokens, ex_tokens) >= threshold:
            return True

    return False


def deduplicate_items(
    items: list[dict],
    sent_hashes: set[str],
    sent_titles: list[str],
    similarity_threshold: float = 0.80,
) -> list[dict]:
    """
    Filter candidate items against DB history and intra-batch duplicates.
    Keeps higher quality / earlier items.
    """
    unique_items: list[dict] = []
    seen_hashes: set[str] = set(sent_hashes)
    seen_titles: list[str] = list(sent_titles)

    for item in items:
        norm_title = normalize_text(item.get("title", ""))
        url = item.get("url", "")
        url_hash = create_url_hash(norm_title, url)

        item["normalized_title"] = norm_title
        item["url_hash"] = url_hash

        # 1. Exact hash check
        if url_hash in seen_hashes:
            logger.debug(f"Skipping exact duplicate hash: {url_hash} ({norm_title})")
            continue

        # 2. Token overlap check against sent & seen titles
        if is_near_duplicate_title(norm_title, seen_titles, threshold=similarity_threshold):
            logger.debug(f"Skipping near-duplicate title: '{norm_title}'")
            continue

        # Add to unique list and update tracking sets
        seen_hashes.add(url_hash)
        seen_titles.append(norm_title)
        unique_items.append(item)

    logger.info(f"Deduplication completed: {len(items)} -> {len(unique_items)} items.")
    return unique_items
