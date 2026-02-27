"""
Orchestrator — scrape → analyse → store → report.

Usage:
    python -m src.main                  # Full run (uses mock data until Reddit creds added)
    python -m src.main --dry-run        # Show raw scraped data, skip Claude
    python -m src.main --report-only    # Regenerate report from latest stored analysis
    python -m src.main --use-mock       # Force mock data even if Reddit creds present
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

from rich.console import Console

import src.config as cfg
from src.database import Database
from src.report import generate_report, print_console_summary

console = Console()
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dev-radar",
        description="Weekly developer tools tracker powered by Reddit + Claude",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape/generate posts but skip Claude analysis — print raw data instead",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Regenerate report from latest stored analysis (no scraping)",
    )
    parser.add_argument(
        "--use-mock",
        action="store_true",
        help="Force use of mock Reddit data (useful for testing)",
    )
    parser.add_argument(
        "--week",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Target week for --report-only",
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help="Send the report by email via Outlook after generating it",
    )
    return parser.parse_args()


def _has_praw_creds() -> bool:
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    return bool(client_id and secret and client_id not in ("mock", "placeholder"))


def _get_posts(use_mock: bool):
    """Return posts from mock data, PRAW, or the public JSON scraper."""
    if use_mock:
        from src.mock_scraper import build_mock_posts
        console.print("[yellow]Using mock Reddit data[/yellow]")
        return build_mock_posts()

    if _has_praw_creds():
        console.print("[cyan]Using Reddit API (PRAW)[/cyan]")
        from src.reddit_scraper import RedditScraper
        return RedditScraper().scrape_all()

    console.print("[cyan]Using Reddit public JSON (no API key needed)[/cyan]")
    from src.public_scraper import PublicRedditScraper
    return PublicRedditScraper().scrape_all()


# ── Run modes ──────────────────────────────────────────────────────────────

def run_full(db: Database, use_mock: bool) -> Path:
    """Scrape → analyse → store → report. Returns report path."""
    from pathlib import Path
    week = date.today().strftime("%Y-%m-%d")

    # Step 1: Collect posts
    console.rule("[bold cyan]Step 1 / 4 — Collecting Posts[/bold cyan]")
    posts = _get_posts(use_mock)
    if not posts:
        console.print("[red]No posts collected — aborting.[/red]")
        sys.exit(1)
    console.print(f"[green]✓[/green] Collected [bold]{len(posts)}[/bold] posts")

    # Step 2: Save posts to DB
    console.rule("[bold cyan]Step 2 / 4 — Saving Posts to DB[/bold cyan]")
    inserted, skipped = db.save_posts(posts)
    console.print(
        f"[green]✓[/green] Posts: [bold]{inserted}[/bold] new, "
        f"[dim]{skipped}[/dim] already stored"
    )

    # Step 3: Claude analysis
    console.rule("[bold cyan]Step 3 / 4 — Claude Analysis[/bold cyan]")
    if db.analysis_exists_for_week(week):
        console.print(
            f"[yellow]⚠[/yellow] Analysis for [bold]{week}[/bold] already exists — "
            "overwriting with fresh run…"
        )

    from src.analyzer import Analyzer
    analyser = Analyzer()
    analysis = analyser.analyse(posts)
    analysis["week"] = week
    db.save_analysis(analysis)
    console.print(
        f"[green]✓[/green] Identified "
        f"[bold]{len(analysis.get('tools', []))}[/bold] tools"
    )

    # Step 4: Report
    console.rule("[bold cyan]Step 4 / 4 — Generating Report[/bold cyan]")
    previous = db.get_previous_analysis(week)
    print_console_summary(analysis)
    report_path = generate_report(analysis, previous)
    console.print(f"[green]✓[/green] Report saved → [bold]{report_path}[/bold]")
    return report_path


def run_dry(db: Database, use_mock: bool) -> None:
    """Collect posts and print raw data — skip Claude."""
    console.rule("[bold yellow]DRY RUN — Posts Only (Claude Skipped)[/bold yellow]")
    posts = _get_posts(use_mock)

    if not posts:
        console.print("[red]No posts collected.[/red]")
        return

    db.save_posts(posts)
    console.print(f"\n[bold]Collected {len(posts)} posts:[/bold]\n")
    for i, post in enumerate(posts, 1):
        console.print(
            f"[cyan]{i:>3}.[/cyan] [bold]{post.title[:80]}[/bold]\n"
            f"     [dim]r/{post.subreddit}[/dim] · "
            f"score [green]{post.score}[/green] · "
            f"{post.num_comments} comments\n"
            f"     {post.url[:80]}\n"
        )


def run_report_only(db: Database, week: str | None) -> Path:
    """Regenerate the report from stored analysis — no scraping."""
    console.rule("[bold magenta]REPORT-ONLY Mode[/bold magenta]")

    if week:
        analysis = db.get_analysis_for_week(week)
        if not analysis:
            console.print(f"[red]No analysis found for week {week}.[/red]")
            available = db.get_all_weeks()
            if available:
                console.print(f"Available weeks: {', '.join(available)}")
            sys.exit(1)
    else:
        analysis = db.get_latest_analysis()
        if not analysis:
            console.print(
                "[red]No analyses stored yet. Run a full analysis first.[/red]"
            )
            sys.exit(1)
        week = analysis["week"]
        console.print(f"Using latest analysis: [bold]{week}[/bold]")

    previous = db.get_previous_analysis(week)
    print_console_summary(analysis)
    report_path = generate_report(analysis, previous)
    console.print(f"[green]✓[/green] Report saved → [bold]{report_path}[/bold]")
    return report_path


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    cfg.setup_logging()
    args = parse_args()

    # For report-only mode we don't need API credentials
    if args.report_only:
        os.environ.setdefault("REDDIT_CLIENT_ID", "placeholder")
        os.environ.setdefault("REDDIT_CLIENT_SECRET", "placeholder")
        os.environ.setdefault("ANTHROPIC_API_KEY", "placeholder")

    try:
        cfg.load_secrets()
    except EnvironmentError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        sys.exit(1)

    db = Database()

    report_path = None
    if args.report_only:
        report_path = run_report_only(db, args.week)
    elif args.dry_run:
        run_dry(db, use_mock=args.use_mock)
    else:
        report_path = run_full(db, use_mock=args.use_mock)

    if args.email and report_path:
        from src.emailer import send_report
        week = report_path.stem  # filename without extension = week date
        send_report(report_path, week)


if __name__ == "__main__":
    main()
