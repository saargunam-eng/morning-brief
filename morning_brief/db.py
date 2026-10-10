import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger("morning_brief.db")


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Initialize SQLite tables and indexes if they do not exist."""
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT UNIQUE NOT NULL,
                normalized_title TEXT NOT NULL,
                url TEXT NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                published_at TEXT,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_hash ON sent_items(url_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_at ON sent_items(sent_at);")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runs_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration_seconds REAL NOT NULL,
                feed_success_count INTEGER NOT NULL,
                feed_failure_count INTEGER NOT NULL,
                gemini_used BOOLEAN NOT NULL,
                items_sent_count INTEGER NOT NULL,
                status TEXT NOT NULL
            );
            """
        )
        conn.commit()
        logger.info(f"Database initialized at {db_path}")


def get_recent_sent_hashes_and_titles(db_path: str, hours: int = 72) -> Tuple[Set[str], List[str]]:
    """Retrieve hashes and normalized titles sent within the last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    sent_hashes: Set[str] = set()
    sent_titles: List[str] = []

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT url_hash, normalized_title FROM sent_items WHERE sent_at >= ?",
            (cutoff_str,),
        )
        for row in cursor.fetchall():
            sent_hashes.add(row["url_hash"])
            sent_titles.append(row["normalized_title"])

    return sent_hashes, sent_titles


def save_sent_items(db_path: str, items: List[Dict]) -> None:
    """Save newly sent items to SQLite."""
    if not items:
        return

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for item in items:
            cursor.execute(
                """
                INSERT OR IGNORE INTO sent_items
                (url_hash, normalized_title, url, category, source, published_at, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    item["url_hash"],
                    item["normalized_title"],
                    item["url"],
                    item.get("category", "general"),
                    item.get("source", "Unknown"),
                    item.get("published_at", ""),
                ),
            )
        conn.commit()
        logger.info(f"Saved {len(items)} sent items to database.")


def log_run(
    db_path: str,
    duration_seconds: float,
    feed_success_count: int,
    feed_failure_count: int,
    gemini_used: bool,
    items_sent_count: int,
    status: str,
) -> None:
    """Log workflow run summary."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO runs_log
            (duration_seconds, feed_success_count, feed_failure_count, gemini_used, items_sent_count, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                duration_seconds,
                feed_success_count,
                feed_failure_count,
                1 if gemini_used else 0,
                items_sent_count,
                status,
            ),
        )
        conn.commit()
        logger.info(f"Log run saved: status={status}, items_sent={items_sent_count}")
