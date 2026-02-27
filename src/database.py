"""SQLite persistence layer."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import src.config as cfg
from src.reddit_scraper import RedditPost

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    selftext        TEXT,
    url             TEXT,
    score           INTEGER,
    num_comments    INTEGER,
    subreddit       TEXT,
    author          TEXT,
    created_utc     TEXT,
    top_comments    TEXT,
    collected_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week            TEXT NOT NULL,
    collected_at    TEXT NOT NULL,
    raw_json        TEXT NOT NULL,
    UNIQUE(week)
);

CREATE TABLE IF NOT EXISTS tool_mentions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    week                TEXT NOT NULL,
    tool_name           TEXT NOT NULL,
    category            TEXT,
    excitement_score    REAL,
    mention_count       INTEGER,
    summary             TEXT,
    source_subreddits   TEXT,
    UNIQUE(week, tool_name)
);
"""


class Database:
    def __init__(self, db_path: Path = cfg.DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
        logger.debug("Database initialised at %s", self.db_path)

    # ── Posts ──────────────────────────────────────────────────────────────

    def save_posts(self, posts: list[RedditPost]) -> tuple[int, int]:
        """Insert posts, skipping duplicates. Returns (inserted, skipped)."""
        now = datetime.utcnow().isoformat()
        inserted = skipped = 0
        with self._conn() as conn:
            for post in posts:
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO posts
                            (id, title, selftext, url, score, num_comments,
                             subreddit, author, created_utc, top_comments, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            post.post_id,
                            post.title,
                            post.selftext,
                            post.url,
                            post.score,
                            post.num_comments,
                            post.subreddit,
                            post.author,
                            post.created_utc.isoformat(),
                            json.dumps(post.top_comments),
                            now,
                        ),
                    )
                    changes = conn.execute("SELECT changes()").fetchone()[0]
                    if changes:
                        inserted += 1
                    else:
                        skipped += 1
                except sqlite3.Error as exc:
                    logger.warning("Could not save post %s: %s", post.post_id, exc)
        logger.info(
            "Posts saved — inserted: %d, skipped (duplicate): %d", inserted, skipped
        )
        return inserted, skipped

    # ── Analysis ───────────────────────────────────────────────────────────

    def save_analysis(self, analysis: dict[str, Any]) -> bool:
        """Save or replace a weekly analysis. Returns True if new week."""
        week = analysis["week"]
        now = datetime.utcnow().isoformat()
        raw_json = json.dumps(analysis, indent=2)

        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM weekly_analyses WHERE week = ?", (week,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE weekly_analyses SET raw_json = ?, collected_at = ? WHERE week = ?",
                    (raw_json, now, week),
                )
                logger.info("Updated existing analysis for week %s", week)
                is_new = False
            else:
                conn.execute(
                    "INSERT INTO weekly_analyses (week, collected_at, raw_json) VALUES (?, ?, ?)",
                    (week, now, raw_json),
                )
                logger.info("Saved new analysis for week %s", week)
                is_new = True

            for tool in analysis.get("tools", []):
                conn.execute(
                    """
                    INSERT INTO tool_mentions
                        (week, tool_name, category, excitement_score,
                         mention_count, summary, source_subreddits)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(week, tool_name) DO UPDATE SET
                        category          = excluded.category,
                        excitement_score  = excluded.excitement_score,
                        mention_count     = excluded.mention_count,
                        summary           = excluded.summary,
                        source_subreddits = excluded.source_subreddits
                    """,
                    (
                        week,
                        tool["name"],
                        tool.get("category", "Other"),
                        tool.get("excitement_score", 0),
                        tool.get("mention_count", 0),
                        tool.get("summary", ""),
                        json.dumps(tool.get("source_subreddits", [])),
                    ),
                )
        return is_new

    # ── Retrieval ──────────────────────────────────────────────────────────

    def get_latest_analysis(self) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT raw_json FROM weekly_analyses ORDER BY week DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["raw_json"]) if row else None

    def get_analysis_for_week(self, week: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT raw_json FROM weekly_analyses WHERE week = ?", (week,)
            ).fetchone()
        return json.loads(row["raw_json"]) if row else None

    def get_previous_analysis(self, current_week: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT raw_json FROM weekly_analyses WHERE week < ? ORDER BY week DESC LIMIT 1",
                (current_week,),
            ).fetchone()
        return json.loads(row["raw_json"]) if row else None

    def get_all_weeks(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT week FROM weekly_analyses ORDER BY week DESC"
            ).fetchall()
        return [r["week"] for r in rows]

    def analysis_exists_for_week(self, week: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM weekly_analyses WHERE week = ?", (week,)
            ).fetchone()
        return row is not None
