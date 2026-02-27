"""
Reddit public JSON scraper — no API credentials required.

Uses Reddit's unauthenticated JSON endpoints:
  https://www.reddit.com/r/{sub}/top.json?t=week&limit=N
  https://www.reddit.com/r/{sub}/comments/{id}.json?sort=top&depth=1

Rate limit: ~1 req/sec to stay well within Reddit's informal limit.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

import src.config as cfg
from src.reddit_scraper import RedditPost

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": cfg.REDDIT_USER_AGENT,
    "Accept": "application/json",
}

_RATE_LIMIT_DELAY = 1.1   # seconds between requests


class PublicRedditScraper:
    """Scrapes Reddit using public JSON endpoints — no OAuth needed."""

    def scrape_all(self) -> list[RedditPost]:
        """Scrape all configured subreddits and return deduplicated posts."""
        all_posts: list[RedditPost] = []

        for sub in cfg.SUBREDDITS:
            try:
                posts = self._scrape_subreddit(sub)
                logger.info(
                    "r/%s — collected %d posts (>= %d upvotes)",
                    sub, len(posts), cfg.MIN_UPVOTES,
                )
                all_posts.extend(posts)
            except Exception as exc:
                logger.error("Failed to scrape r/%s: %s", sub, exc)

            time.sleep(_RATE_LIMIT_DELAY)

        # Deduplicate cross-posts by post_id
        seen: set[str] = set()
        unique: list[RedditPost] = []
        for p in all_posts:
            if p.post_id not in seen:
                seen.add(p.post_id)
                unique.append(p)

        logger.info("Total unique posts collected: %d", len(unique))
        return unique

    # ── Subreddit listing ──────────────────────────────────────────────────

    def _scrape_subreddit(self, subreddit: str) -> list[RedditPost]:
        url = f"https://www.reddit.com/r/{subreddit}/top.json"
        params = {"t": cfg.TIME_FILTER, "limit": cfg.POST_LIMIT}

        data = self._get_json(url, params=params)
        children = data.get("data", {}).get("children", [])

        posts: list[RedditPost] = []
        for item in children:
            pd = item.get("data", {})

            if pd.get("score", 0) < cfg.MIN_UPVOTES:
                continue
            if pd.get("stickied"):
                continue

            time.sleep(_RATE_LIMIT_DELAY)
            comments = self._get_top_comments(subreddit, pd["id"])

            posts.append(RedditPost(
                post_id=pd["id"],
                title=pd.get("title", ""),
                selftext=pd.get("selftext", ""),
                url=pd.get("url", ""),
                score=pd.get("score", 0),
                num_comments=pd.get("num_comments", 0),
                subreddit=subreddit,
                created_utc=datetime.fromtimestamp(
                    pd.get("created_utc", 0), tz=timezone.utc
                ),
                top_comments=comments,
                author=pd.get("author", "[deleted]"),
            ))

        return posts

    # ── Comments ───────────────────────────────────────────────────────────

    def _get_top_comments(self, subreddit: str, post_id: str) -> list[str]:
        url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        params = {
            "sort": "top",
            "limit": cfg.TOP_COMMENTS_PER_POST,
            "depth": 1,
        }

        try:
            data = self._get_json(url, params=params)
            # Response is [post_listing, comments_listing]
            comment_listing = data[1]["data"]["children"] if isinstance(data, list) else []
            comments = []
            for item in comment_listing:
                if item.get("kind") != "t1":
                    continue
                body = item.get("data", {}).get("body", "")
                if body and body not in ("[deleted]", "[removed]"):
                    comments.append(body)
                if len(comments) >= cfg.TOP_COMMENTS_PER_POST:
                    break
            return comments
        except Exception as exc:
            logger.debug("Could not fetch comments for %s: %s", post_id, exc)
            return []

    # ── HTTP ───────────────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _get_json(self, url: str, params: dict | None = None):
        response = requests.get(
            url,
            headers=_HEADERS,
            params=params,
            timeout=15,
        )
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("Rate limited — sleeping %ds", retry_after)
            time.sleep(retry_after)
            response.raise_for_status()
        response.raise_for_status()
        return response.json()
