"""Plain-text report generation and rich console summary."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

import src.config as cfg

logger = logging.getLogger(__name__)
console = Console()

_CATEGORY_EMOJI: dict[str, str] = {
    "devops": "⚙️",
    "frontend": "🎨",
    "backend": "🖥️",
    "ai/ml": "🤖",
    "ai": "🤖",
    "database": "🗄️",
    "monitoring": "📊",
    "security": "🔒",
    "cloud": "☁️",
    "testing": "🧪",
    "cli": "💻",
    "editor": "📝",
    "runtime": "⚡",
    "payments": "💳",
    "email": "📧",
    "other": "🔧",
}

# Keywords that classify a tool into the Data & AI Infrastructure section
_DATA_AI_KEYWORDS = {
    "ai", "ml", "data", "database", "llm", "model", "mlops", "analytics",
    "vector", "feature", "pipeline", "warehouse", "embeddings", "serving",
}

MAX_SECTION_TOOLS = 7


def _category_emoji(category: str) -> str:
    return _CATEGORY_EMOJI.get(category.lower(), "🔧")


def _score_bar(score: float, width: int = 10) -> str:
    filled = round(score / 10 * width)
    return "█" * filled + "░" * (width - filled)


def _is_data_ai(tool: dict[str, Any]) -> bool:
    cat = tool.get("category", "").lower()
    words = set(cat.replace("/", " ").replace("-", " ").split())
    return bool(words & _DATA_AI_KEYWORDS)


# ── Console output ─────────────────────────────────────────────────────────

def print_console_summary(analysis: dict[str, Any]) -> None:
    week = analysis.get("week", "unknown")
    tools = analysis.get("tools", [])[:15]

    console.print()
    console.rule(f"[bold cyan]🔭 Dev Radar — Week of {week}[/bold cyan]")
    console.print()

    table = Table(
        title=f"Top Developer Tools — {week}",
        box=box.ROUNDED,
        show_lines=True,
        highlight=True,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Tool", style="bold white", min_width=20)
    table.add_column("Category", style="cyan", min_width=14)
    table.add_column("Score", justify="center", min_width=14)
    table.add_column("Mentions", justify="right", width=9)
    table.add_column("Why exciting", min_width=50)

    for rank, tool in enumerate(tools, 1):
        score = tool.get("excitement_score", 0)
        score_str = f"{_score_bar(score)} {score:.1f}"
        emoji = _category_emoji(tool.get("category", ""))

        if score >= 8:
            score_style = "bold green"
        elif score >= 6:
            score_style = "yellow"
        else:
            score_style = "dim"

        reason = tool.get("excitement_reason", tool.get("summary", ""))

        table.add_row(
            str(rank),
            f"{emoji} {tool['name']}",
            tool.get("category", "Other"),
            Text(score_str, style=score_style),
            str(tool.get("mention_count", 0)),
            reason,
        )

    console.print(table)

    trends = analysis.get("emerging_trends", [])
    shifts = analysis.get("notable_shifts", [])

    if trends:
        console.print()
        console.print("[bold yellow]📈 Emerging Trends[/bold yellow]")
        for t in trends:
            console.print(f"  • {t}")

    if shifts:
        console.print()
        console.print("[bold magenta]🔄 Notable Shifts[/bold magenta]")
        for s in shifts:
            console.print(f"  • {s}")

    console.print()


# ── Plain-text report ──────────────────────────────────────────────────────

_W = 80  # page width


def _rule(char: str = "=") -> str:
    return char * _W


def _section(title: str) -> str:
    return f"\n{title}\n" + "-" * len(title)


def _section_banner(title: str) -> list[str]:
    bar = "=" * _W
    return ["", bar, title.center(_W), bar]


def _wrap(text: str, indent: int = 0) -> str:
    """Word-wrap text to _W columns with a leading indent."""
    import textwrap
    prefix = " " * indent
    return textwrap.fill(text, width=_W, initial_indent=prefix, subsequent_indent=prefix)


def _leaderboard_block(tools: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = [_section("TOP TOOLS"), ""]
    col_rank = 3
    col_name = 38
    col_cat  = 18
    col_score = 7
    header = (
        f"  {'#':<{col_rank}}  "
        f"{'Tool':<{col_name}}  "
        f"{'Category':<{col_cat}}  "
        f"{'Score':>{col_score}}  "
        f"Mentions"
    )
    lines += [header, "  " + "-" * (len(header) - 2)]
    for rank, tool in enumerate(tools, 1):
        score = tool.get("excitement_score", 0)
        name = tool["name"]
        if len(name) > col_name:
            name = name[:col_name - 1] + "…"
        cat = tool.get("category", "Other")
        if len(cat) > col_cat:
            cat = cat[:col_cat - 1] + "…"
        lines.append(
            f"  {rank:<{col_rank}}  "
            f"{name:<{col_name}}  "
            f"{cat:<{col_cat}}  "
            f"{score:.1f}/10  "
            f"{tool.get('mention_count', 0)}"
        )
    return lines


def _profiles_block(
    tools: list[dict[str, Any]],
    prev_tools: dict[str, dict[str, Any]],
    previous: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = [_section("TOOL PROFILES")]
    for rank, tool in enumerate(tools, 1):
        score = tool.get("excitement_score", 0)
        bar = _score_bar(score, width=10)
        key = tool["name"].lower()

        badge = ""
        if key in prev_tools:
            delta = score - prev_tools[key].get("excitement_score", 0)
            if delta >= 0.5:
                badge = f"  [+{delta:.1f}]"
            elif delta <= -0.5:
                badge = f"  [{delta:.1f}]"
        elif previous:
            badge = "  [NEW]"

        subs = ", ".join(f"r/{s}" for s in tool.get("source_subreddits", []))
        reason = tool.get("excitement_reason", "")
        summary = tool.get("summary", "")
        quotes = tool.get("representative_quotes", [])
        company = tool.get("company", "Unknown")
        hq = tool.get("headquarters", "Unknown")

        lines += [
            "",
            f"  {rank}. {tool['name']}{badge}",
            f"     {'Category':<10}: {tool.get('category', 'Other')}",
            f"     {'Company':<10}: {company}",
            f"     {'HQ':<10}: {hq}",
            f"     {'Score':<10}: {bar}  {score:.1f}/10",
            f"     {'Mentions':<10}: {tool.get('mention_count', 0)}",
            f"     {'Sources':<10}: {subs or '—'}",
        ]
        if reason:
            lines += ["", _wrap(reason, indent=5)]
        if summary:
            lines += ["", _wrap(summary, indent=5)]
        if quotes:
            lines.append("")
            for q in quotes[:3]:
                q_clean = q.replace("\n", " ").strip()[:280]
                lines += [_wrap(f'"{q_clean}"', indent=6)]
        lines.append("")
        lines.append("  " + "-" * (_W - 2))
    return lines


def generate_report(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> Path:
    week = current.get("week", date.today().strftime("%Y-%m-%d"))
    tools = current.get("tools", [])

    prev_tools: dict[str, dict[str, Any]] = {}
    if previous:
        for t in previous.get("tools", []):
            prev_tools[t["name"].lower()] = t

    prev_names = set(prev_tools.keys())
    curr_names = {t["name"].lower() for t in tools}

    new_entries = [t for t in tools if t["name"].lower() not in prev_names]
    returning = [t for t in tools if t["name"].lower() in prev_names]

    trending_up, trending_down = [], []
    for t in returning:
        key = t["name"].lower()
        delta = t.get("excitement_score", 0) - prev_tools[key].get("excitement_score", 0)
        if delta >= 1.0:
            trending_up.append((t, delta))
        elif delta <= -1.0:
            trending_down.append((t, abs(delta)))

    trending_up.sort(key=lambda x: x[1], reverse=True)
    trending_down.sort(key=lambda x: x[1], reverse=True)

    dropped = (
        [prev_tools[n] for n in prev_names if n not in curr_names]
        if previous else []
    )

    # Split tools into two sections, top MAX_SECTION_TOOLS each
    data_ai_tools = [t for t in tools if _is_data_ai(t)][:MAX_SECTION_TOOLS]
    devtools_tools = [t for t in tools if not _is_data_ai(t)][:MAX_SECTION_TOOLS]

    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines += [
        _rule("="),
        f"  DEV RADAR  --  Week of {week}".center(_W),
        (
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  |  "
            f"{len(tools)} tools  |  {len(cfg.SUBREDDITS)} subreddits"
        ).center(_W),
        _rule("="),
    ]

    # ── Preface ──────────────────────────────────────────────────────────────
    lines += [
        _section("ABOUT THIS REPORT"),
        "",
        _wrap("This week's Dev Radar is split into two sections:", indent=2),
        "",
        _wrap(
            "1. Data & AI Infrastructure — tools shaping how data is stored, "
            "processed, and consumed by AI/ML systems: data engineering, MLOps, "
            "vector databases, LLM frameworks, and AI platforms.",
            indent=4,
        ),
        "",
        _wrap(
            "2. Developer Tools & DevOps — tools that improve how software is "
            "built, deployed, and operated: CI/CD, frontend frameworks, backend "
            "tooling, CLI utilities, monitoring, and security.",
            indent=4,
        ),
        "",
        _wrap(
            f"Each section highlights the top {MAX_SECTION_TOOLS} tools ranked "
            "by community excitement score this week.",
            indent=2,
        ),
    ]

    # ── Quick stats ──────────────────────────────────────────────────────────
    lines += [
        _section("QUICK STATS"),
        "",
        f"  Tools analysed  : {len(tools)}",
        f"  New this week   : {len(new_entries)}",
        f"  Trending up     : {len(trending_up)}",
        f"  Trending down   : {len(trending_down)}",
        f"  Dropped off     : {len(dropped)}",
    ]

    # ── SECTION 1: Data & AI Infrastructure ─────────────────────────────────
    lines += _section_banner("SECTION 1: DATA & AI INFRASTRUCTURE")
    if data_ai_tools:
        lines += _leaderboard_block(data_ai_tools)
        lines += _profiles_block(data_ai_tools, prev_tools, previous)
    else:
        lines += ["", "  No Data & AI tools identified this week.", ""]

    # ── SECTION 2: Developer Tools & DevOps ─────────────────────────────────
    lines += _section_banner("SECTION 2: DEVELOPER TOOLS & DEVOPS")
    if devtools_tools:
        lines += _leaderboard_block(devtools_tools)
        lines += _profiles_block(devtools_tools, prev_tools, previous)
    else:
        lines += ["", "  No Developer Tools identified this week.", ""]

    # ── Movement sections ────────────────────────────────────────────────────
    if new_entries:
        lines += [_section("NEW THIS WEEK"), ""]
        for t in new_entries[:10]:
            lines.append(
                f"  + {t['name']}  ({t.get('category','Other')})  "
                f"-- score {t.get('excitement_score',0):.1f}"
            )

    if trending_up:
        lines += [_section("TRENDING UP"), ""]
        for t, delta in trending_up[:5]:
            lines.append(
                f"  ^ {t['name']}  -- "
                f"{t.get('excitement_score',0):.1f}/10  (+{delta:.1f} vs last week)"
            )

    if trending_down:
        lines += [_section("TRENDING DOWN"), ""]
        for t, delta in trending_down[:5]:
            lines.append(
                f"  v {t['name']}  -- "
                f"{t.get('excitement_score',0):.1f}/10  (-{delta:.1f} vs last week)"
            )

    if dropped:
        lines += [_section("DROPPED OFF"), ""]
        for t in dropped[:5]:
            lines.append(f"  - {t['name']}  (was {t.get('excitement_score',0):.1f})")

    # ── Trends & shifts ───────────────────────────────────────────────────────
    trends = current.get("emerging_trends", [])
    if trends:
        lines += [_section("EMERGING TRENDS"), ""]
        for trend in trends:
            lines += [_wrap(trend, indent=4), ""]

    shifts = current.get("notable_shifts", [])
    if shifts:
        lines += [_section("NOTABLE SHIFTS"), ""]
        for shift in shifts:
            lines += [_wrap(shift, indent=4), ""]

    # ── Source breakdown ──────────────────────────────────────────────────────
    sub_counts: dict[str, int] = {}
    for tool in tools:
        for sub in tool.get("source_subreddits", []):
            sub_counts[sub] = sub_counts.get(sub, 0) + 1

    if sub_counts:
        lines += [_section("SOURCE BREAKDOWN"), ""]
        for sub, count in sorted(sub_counts.items(), key=lambda x: x[1], reverse=True):
            bar = "#" * count
            lines.append(f"  r/{sub:<20} {bar} ({count})")

    # ── Footer ────────────────────────────────────────────────────────────────
    lines += [
        "",
        _rule("="),
        "  Generated by dev-radar  |  Powered by Reddit + Claude".center(_W),
        _rule("="),
    ]

    report_path = cfg.REPORTS_DIR / f"{week}.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report saved to %s", report_path)
    return report_path
