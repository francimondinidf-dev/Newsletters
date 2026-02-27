"""Reddit data collection using PRAW with rate-limit handling."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generator

import praw
import praw.exceptions
import prawcore.exceptions
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

import src.config as cfg

logger = logging.getLogger(__name__)


# ── Data model ─────────────────────────────────────────────────────────────

@dataclass
class RedditPost:
    post_id: str
    title: str
    selftext: str
    url: str
    score: int
    num_comments: int
    subreddit: str
    created_utc: datetime
    top_comments: list[str] = field(default_factory=list)
    author: str = ""

    def to_text_block(self) -> str:
        """Format post + comments as a single text block for LLM input."""
        lines = [
            f"## [{self.subreddit}] {self.title}",
            f"Score: {self.score} | Comments: {self.num_comments}",
            f"URL: {self.url}",
        ]
        if self.selftext.strip():
            lines.append(f"\n{self.selftext[:1500]}")
        if self.top_comments:
            lines.append("\n**Top comments:**")
            for i, c in enumerate(self.top_comments, 1):
                lines.append(f"{i}. {c[:500]}")
        return "\n".join(lines)


# ── Retry decorator ────────────────────────────────────────────────────────

_RETRY_EXCEPTIONS = (
    prawcore.exceptions.RequestException,
    prawcore.exceptions.ServerError,
    prawcore.exceptions.TooManyRequests,
)

_retry_reddit = retry(
    retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


# ── Scraper ────────────────────────────────────────────────────────────────

class RedditScraper:
    def __init__(self) -> None:
        self._reddit: praw.Reddit | None = None

    def _get_reddit(self) -> praw.Reddit:
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=cfg.REDDIT_CLIENT_ID,
                client_secret=cfg.REDDIT_CLIENT_SECRET,
                user_agent=cfg.REDDIT_USER_AGENT,
                ratelimit_seconds=300,
            )
            logger.info("PRAW client initialised (read-only mode)")
        return self._reddit

    def scrape_all(self) -> list[RedditPost]:
        """Scrape all configured subreddits and return deduplicated posts."""
        all_posts: list[RedditPost] = []
        for sub in cfg.SUBREDDITS:
            try:
                posts = list(self._scrape_subreddit(sub))
                logger.info(
                    "r/%s — collected %d posts (>= %d upvotes)",
                    sub, len(posts), cfg.MIN_UPVOTES,
                )
                all_posts.extend(posts)
            except Exception as exc:
                logger.error("Failed to scrape r/%s: %s", sub, exc)
            time.sleep(1)  # polite delay between subreddits

        # Deduplicate by post_id (cross-posts can appear in multiple subs)
        seen: set[str] = set()
        unique: list[RedditPost] = []
        for p in all_posts:
            if p.post_id not in seen:
                seen.add(p.post_id)
                unique.append(p)

        logger.info("Total unique posts collected: %d", len(unique))
        return unique

    def _scrape_subreddit(
        self, subreddit_name: str
    ) -> Generator[RedditPost, None, None]:
        reddit = self._get_reddit()
        subreddit = reddit.subreddit(subreddit_name)
        submissions = self._fetch_top_posts(subreddit)
        for submission in submissions:
            if submission.score < cfg.MIN_UPVOTES:
                continue
            post = self._submission_to_post(submission, subreddit_name)
            if post:
                yield post

    @_retry_reddit
    def _fetch_top_posts(self, subreddit: praw.models.Subreddit):
        return list(
            subreddit.top(time_filter=cfg.TIME_FILTER, limit=cfg.POST_LIMIT)
        )

    def _submission_to_post(
        self,
        submission: praw.models.Submission,
        subreddit_name: str,
    ) -> RedditPost | None:
        try:
            top_comments = self._get_top_comments(submission)
            return RedditPost(
                post_id=submission.id,
                title=submission.title,
                selftext=submission.selftext or "",
                url=submission.url,
                score=submission.score,
                num_comments=submission.num_comments,
                subreddit=subreddit_name,
                created_utc=datetime.fromtimestamp(
                    submission.created_utc, tz=timezone.utc
                ),
                top_comments=top_comments,
                author=str(submission.author) if submission.author else "[deleted]",
            )
        except Exception as exc:
            logger.warning("Skipping post %s: %s", submission.id, exc)
            return None

    @_retry_reddit
    def _get_top_comments(
        self, submission: praw.models.Submission
    ) -> list[str]:
        try:
            submission.comment_sort = "top"
            submission.comments.replace_more(limit=0)
            comments = []
            for comment in submission.comments.list()[: cfg.TOP_COMMENTS_PER_POST]:
                if hasattr(comment, "body") and comment.body not in (
                    "[deleted]",
                    "[removed]",
                ):
                    comments.append(comment.body)
            return comments
        except Exception as exc:
            logger.debug(
                "Could not fetch comments for %s: %s", submission.id, exc
            )
            return []
