"""Claude API integration for tool-excitement analysis."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from datetime import date
from typing import Any

import anthropic
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

# ── Prompt ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
    You are a developer tools analyst. Given the following Reddit posts and comments
    from developer communities, identify the specific tools, libraries, frameworks,
    platforms, and SaaS products that developers are most excited about.

    For each tool/solution identified:
    1. Name of the tool/solution
    2. Category — assign each tool to one of these two groups using the suggested
       category labels:
       - Data & AI Infrastructure: "AI/ML", "Data Engineering", "MLOps",
         "Database", "Vector Database", "Data Pipeline", "LLM Framework",
         "AI Platform", "Analytics", "Data Warehouse", "Feature Store",
         "Model Serving"
       - Developer Tools & DevOps: "DevOps", "Frontend", "Backend", "CLI",
         "Monitoring", "Security", "Testing", "Runtime", "Cloud Infrastructure",
         "Editor", "CI/CD", "Payments", "Email", "Other"
    3. Excitement score (1-10) based on sentiment and engagement
    4. excitement_reason: exactly ONE punchy sentence capturing the core reason devs are excited right now
    5. Brief summary of why developers are excited (2-3 sentences)
    6. Number of distinct mentions across posts
    7. Representative quotes or use cases mentioned
    8. company: the name of the company or organisation that makes this tool (e.g. "HashiCorp", "Vercel", "Meta"). Use "Open Source / Community" for community-driven projects with no single owner. Use "Unknown" only if truly unclear.
    9. headquarters: city and country of that company's HQ (e.g. "San Francisco, USA"). Use "Distributed / Open Source" for community projects. Use "Unknown" if not determinable.

    Return your analysis as valid JSON with this EXACT schema (no markdown fences):
    {
      "week": "YYYY-MM-DD",
      "tools": [
        {
          "name": "string",
          "category": "string",
          "excitement_score": number,
          "excitement_reason": "string",
          "summary": "string",
          "mention_count": number,
          "representative_quotes": ["string"],
          "source_subreddits": ["string"],
          "company": "string",
          "headquarters": "string"
        }
      ],
      "emerging_trends": ["string"],
      "notable_shifts": ["string"]
    }

    Focus on SPECIFIC named tools and products, not generic concepts.
    Rank tools by excitement_score descending.
    Return ONLY the JSON object, no additional text.
""").strip()


# ── Retry decorator ────────────────────────────────────────────────────────

_retry_claude = retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


# ── Analyzer ───────────────────────────────────────────────────────────────

class Analyzer:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)

    def analyse(self, posts: list[RedditPost]) -> dict[str, Any]:
        """Analyse posts and return aggregated tool-excitement JSON."""
        batches = self._build_batches(posts)
        logger.info("Sending %d batch(es) to Claude", len(batches))

        batch_results: list[dict[str, Any]] = []
        for i, batch in enumerate(batches, 1):
            logger.info(
                "Processing batch %d / %d (%d posts)", i, len(batches), len(batch)
            )
            result = self._analyse_batch(batch)
            if result:
                batch_results.append(result)

        if not batch_results:
            raise RuntimeError("All Claude batches failed — no analysis produced.")

        aggregated = self._aggregate(batch_results)
        logger.info(
            "Analysis complete — %d tools identified",
            len(aggregated.get("tools", [])),
        )
        return aggregated

    # ── Batching ───────────────────────────────────────────────────────────

    def _build_batches(self, posts: list[RedditPost]) -> list[list[RedditPost]]:
        """Split posts into batches by subreddit, capped at MAX_BATCH_CHARS."""
        by_sub: dict[str, list[RedditPost]] = {}
        for p in posts:
            by_sub.setdefault(p.subreddit, []).append(p)

        batches: list[list[RedditPost]] = []
        current_batch: list[RedditPost] = []
        current_size = 0

        for sub_posts in by_sub.values():
            for post in sub_posts:
                text = post.to_text_block()
                if current_size + len(text) > cfg.MAX_BATCH_CHARS and current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_size = 0
                current_batch.append(post)
                current_size += len(text)

        if current_batch:
            batches.append(current_batch)

        return batches or [[]]

    # ── Single batch ───────────────────────────────────────────────────────

    @_retry_claude
    def _analyse_batch(self, posts: list[RedditPost]) -> dict[str, Any] | None:
        if not posts:
            return None

        content = "\n\n---\n\n".join(p.to_text_block() for p in posts)
        week_str = date.today().strftime("%Y-%m-%d")

        user_message = (
            f"Current week: {week_str}\n\n"
            f"=== REDDIT POSTS ===\n\n{content}"
        )

        logger.debug("Batch prompt length: %d chars", len(user_message))

        response = self._client.messages.create(
            model=cfg.CLAUDE_MODEL,
            max_tokens=8000,
            temperature=1,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()
        return self._parse_json(raw_text)

    # ── JSON parsing ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | None:
        # Strip accidental markdown code fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.error("Could not parse Claude JSON response: %s", exc)
            logger.debug("Raw response: %s", raw[:500])
            return None

    # ── Aggregation ────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge multiple batch results. Tools with same name are merged."""
        week = results[0].get("week", date.today().strftime("%Y-%m-%d"))
        tools_map: dict[str, dict[str, Any]] = {}
        all_trends: list[str] = []
        all_shifts: list[str] = []

        for result in results:
            for tool in result.get("tools", []):
                name = tool.get("name", "").strip()
                if not name:
                    continue
                key = name.lower()
                if key in tools_map:
                    existing = tools_map[key]
                    existing["excitement_score"] = round(
                        (existing["excitement_score"] + tool.get("excitement_score", 5)) / 2, 1
                    )
                    existing["mention_count"] += tool.get("mention_count", 0)
                    existing_quotes = set(existing.get("representative_quotes", []))
                    for q in tool.get("representative_quotes", []):
                        existing_quotes.add(q)
                    existing["representative_quotes"] = list(existing_quotes)[:5]
                    subs = set(existing.get("source_subreddits", []))
                    subs.update(tool.get("source_subreddits", []))
                    existing["source_subreddits"] = sorted(subs)
                else:
                    tools_map[key] = {
                        "name": name,
                        "category": tool.get("category", "Other"),
                        "excitement_score": tool.get("excitement_score", 5),
                        "excitement_reason": tool.get("excitement_reason", ""),
                        "summary": tool.get("summary", ""),
                        "mention_count": tool.get("mention_count", 1),
                        "representative_quotes": tool.get("representative_quotes", [])[:5],
                        "source_subreddits": tool.get("source_subreddits", []),
                        "company": tool.get("company", "Unknown"),
                        "headquarters": tool.get("headquarters", "Unknown"),
                    }

            all_trends.extend(result.get("emerging_trends", []))
            all_shifts.extend(result.get("notable_shifts", []))

        sorted_tools = sorted(
            tools_map.values(),
            key=lambda t: t["excitement_score"],
            reverse=True,
        )

        return {
            "week": week,
            "tools": sorted_tools,
            "emerging_trends": list(dict.fromkeys(all_trends)),
            "notable_shifts": list(dict.fromkeys(all_shifts)),
        }
