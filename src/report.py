"""Plain-text (archival) and HTML (email) report generation, plus rich console summary."""

from __future__ import annotations

import html as _html_lib
import logging
import textwrap
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


# ── Console output ──────────────────────────────────────────────────────────

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


# ── Plain-text report (archival) ────────────────────────────────────────────

_W = 80


def _rule(char: str = "=") -> str:
    return char * _W


def _section(title: str) -> str:
    return f"\n{title}\n" + "-" * len(title)


def _section_banner(title: str) -> list[str]:
    bar = "=" * _W
    return ["", bar, title.center(_W), bar]


def _wrap(text: str, indent: int = 0) -> str:
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


# ── HTML report (email) ─────────────────────────────────────────────────────

def _he(text: str) -> str:
    """HTML-escape a value."""
    return _html_lib.escape(str(text))


def _html_score_badge(score: float) -> str:
    color = "#27ae60" if score >= 8.5 else "#e67e22" if score >= 7.0 else "#7f8c8d"
    return (
        f'<span style="background:{color}; color:#fff; padding:2px 8px; '
        f'border-radius:10px; font-size:12px; font-weight:bold;">'
        f'{score:.1f}/10</span>'
    )


def _html_chip(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}; color:#fff; padding:1px 6px; '
        f'border-radius:3px; font-size:11px; font-weight:bold; margin-left:6px;">'
        f'{_he(text)}</span>'
    )


def _html_leaderboard(tools: list[dict[str, Any]], prev_tools: dict) -> str:
    rows = ""
    for rank, tool in enumerate(tools, 1):
        key = tool["name"].lower()
        score = tool.get("excitement_score", 0)

        badge = ""
        if key in prev_tools:
            delta = score - prev_tools[key].get("excitement_score", 0)
            if delta >= 0.5:
                badge = _html_chip(f"+{delta:.1f}", "#2980b9")
            elif delta <= -0.5:
                badge = _html_chip(f"{delta:.1f}", "#c0392b")
        else:
            badge = _html_chip("NEW", "#27ae60")

        bg = "#fafafa" if rank % 2 == 0 else "#ffffff"
        rows += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 10px; color:#999; font-weight:bold; width:28px;">{rank}</td>'
            f'<td style="padding:8px 10px;"><strong>{_he(tool["name"])}</strong>{badge}</td>'
            f'<td style="padding:8px 10px; color:#666;">{_he(tool.get("category", "Other"))}</td>'
            f'<td style="padding:8px 10px; text-align:center;">{_html_score_badge(score)}</td>'
            f'<td style="padding:8px 10px; text-align:right; color:#999;">{tool.get("mention_count", 0)}</td>'
            f'</tr>'
        )
    return (
        '<table style="width:100%; border-collapse:collapse; font-size:13px; margin:12px 0;">'
        '<thead><tr style="background:#f0f0f0; text-align:left;">'
        '<th style="padding:8px 10px; border-bottom:2px solid #ddd; width:28px;">#</th>'
        '<th style="padding:8px 10px; border-bottom:2px solid #ddd;">Tool</th>'
        '<th style="padding:8px 10px; border-bottom:2px solid #ddd;">Category</th>'
        '<th style="padding:8px 10px; border-bottom:2px solid #ddd; text-align:center;">Score</th>'
        '<th style="padding:8px 10px; border-bottom:2px solid #ddd; text-align:right;">Mentions</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
    )


def _html_profiles(
    tools: list[dict[str, Any]],
    prev_tools: dict,
    previous: dict[str, Any] | None,
) -> str:
    parts = [
        '<p style="font-size:12px; font-weight:bold; text-transform:uppercase; '
        'letter-spacing:1px; color:#888; margin:20px 0 8px;">Tool Profiles</p>'
    ]

    for rank, tool in enumerate(tools, 1):
        key = tool["name"].lower()
        score = tool.get("excitement_score", 0)

        badge = ""
        if key in prev_tools:
            delta = score - prev_tools[key].get("excitement_score", 0)
            if delta >= 0.5:
                badge = _html_chip(f"+{delta:.1f}", "#2980b9")
            elif delta <= -0.5:
                badge = _html_chip(f"{delta:.1f}", "#c0392b")
        elif previous:
            badge = _html_chip("NEW", "#27ae60")

        meta_parts = []
        if tool.get("company"):
            meta_parts.append(_he(tool["company"]))
        if tool.get("headquarters"):
            meta_parts.append(_he(tool["headquarters"]))
        meta_parts.append(f"{tool.get('mention_count', 0)} mentions")
        subs = ", ".join(f"r/{s}" for s in tool.get("source_subreddits", []))
        if subs:
            meta_parts.append(_he(subs))
        meta = " &nbsp;·&nbsp; ".join(meta_parts)

        reason = _he(tool.get("excitement_reason", ""))
        summary = _he(tool.get("summary", ""))

        quotes_html = ""
        for q in tool.get("representative_quotes", [])[:2]:
            q_clean = _he(q.replace("\n", " ").strip()[:200])
            quotes_html += (
                f'<div style="border-left:3px solid #ddd; padding:4px 12px; '
                f'margin:4px 0; color:#777; font-style:italic; font-size:13px;">'
                f'"{q_clean}"</div>'
            )

        body = ""
        if reason:
            body += (
                f'<div style="font-weight:bold; font-style:italic; color:#444; '
                f'margin-top:10px; line-height:1.5;">{reason}</div>'
            )
        if summary:
            body += f'<div style="margin-top:6px; line-height:1.6; color:#555;">{summary}</div>'
        if quotes_html:
            body += f'<div style="margin-top:8px;">{quotes_html}</div>'

        parts.append(
            f'<div style="border:1px solid #e8e8e8; border-radius:4px; margin:10px 0; padding:14px 16px;">'
            f'<table style="width:100%; border-collapse:collapse;"><tr>'
            f'<td><strong style="font-size:14px;">{rank}. {_he(tool["name"])}</strong>{badge}</td>'
            f'<td style="text-align:right; white-space:nowrap;">{_html_score_badge(score)}</td>'
            f'</tr></table>'
            f'<div style="color:#999; font-size:12px; margin-top:4px;">{meta}</div>'
            f'{body}'
            f'</div>'
        )

    return "".join(parts)


def _generate_html(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    devtools_tools: list[dict[str, Any]],
    data_ai_tools: list[dict[str, Any]],
    prev_tools: dict,
    new_entries: list,
    trending_up: list,
    trending_down: list,
    dropped: list,
) -> str:
    week = current.get("week", date.today().strftime("%Y-%m-%d"))
    tools = current.get("tools", [])
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    devops_para = _he(current.get("devops_ai_disruption", ""))
    data_para = _he(current.get("data_ai_disruption", ""))

    parts = [f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Dev Radar — Week of {week}</title></head>
<body style="font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#333; max-width:680px; margin:0 auto; padding:0; background:#fff;">

<div style="background:#0f1923; color:#fff; padding:28px 24px; text-align:center;">
  <div style="font-size:24px; font-weight:bold; letter-spacing:2px;">&#128301; DEV RADAR</div>
  <div style="font-size:15px; color:#8ab4cc; margin-top:8px; letter-spacing:1px;">Week of {week}</div>
  <div style="font-size:12px; color:#5a7a8a; margin-top:4px;">{len(tools)} tools identified &nbsp;&middot;&nbsp; {len(cfg.SUBREDDITS)} subreddits monitored</div>
</div>

<table style="width:100%; background:#1a2a3a; border-collapse:collapse;"><tr>
  <td style="padding:12px 24px; color:#aaa; font-size:13px; text-align:center;">
    <strong style="color:#fff;">{len(new_entries)}</strong>&nbsp;new
    &nbsp;&nbsp;&middot;&nbsp;&nbsp;
    <strong style="color:#5dbb63;">{len(trending_up)}</strong>&nbsp;&#8593; trending up
    &nbsp;&nbsp;&middot;&nbsp;&nbsp;
    <strong style="color:#e07070;">{len(trending_down)}</strong>&nbsp;&#8595; trending down
    &nbsp;&nbsp;&middot;&nbsp;&nbsp;
    <strong style="color:#888;">{len(dropped)}</strong>&nbsp;dropped off
  </td>
</tr></table>

<div style="padding:0 24px 24px 24px;">
"""]

    # ── SECTION 1: Developer Tools & DevOps ────────────────────────────────
    parts.append(
        '<div style="background:#1e3a5f; color:#fff; padding:16px 24px; margin:28px -24px 0 -24px;">'
        '<div style="font-size:17px; font-weight:bold; letter-spacing:1px;">'
        '&#9881;&#65039;&nbsp; SECTION 1 &mdash; DEVELOPER TOOLS &amp; DEVOPS'
        '</div></div>'
    )

    if devops_para:
        parts.append(
            f'<div style="background:#edf3fb; border-left:4px solid #1e3a5f; '
            f'padding:14px 18px; margin:16px 0; font-style:italic; line-height:1.7; color:#334455;">'
            f'{devops_para}</div>'
        )

    parts.append(
        '<p style="font-size:12px; font-weight:bold; text-transform:uppercase; '
        'letter-spacing:1px; color:#888; margin:16px 0 4px;">Leaderboard</p>'
    )
    if devtools_tools:
        parts.append(_html_leaderboard(devtools_tools, prev_tools))
        parts.append(_html_profiles(devtools_tools, prev_tools, previous))
    else:
        parts.append("<p><em>No Developer Tools identified this week.</em></p>")

    # ── SECTION 2: Data & AI Infrastructure ────────────────────────────────
    parts.append(
        '<div style="background:#1a3a2a; color:#fff; padding:16px 24px; margin:32px -24px 0 -24px;">'
        '<div style="font-size:17px; font-weight:bold; letter-spacing:1px;">'
        '&#128202;&nbsp; SECTION 2 &mdash; DATA &amp; AI INFRASTRUCTURE'
        '</div></div>'
    )

    if data_para:
        parts.append(
            f'<div style="background:#edfbf3; border-left:4px solid #1a3a2a; '
            f'padding:14px 18px; margin:16px 0; font-style:italic; line-height:1.7; color:#334455;">'
            f'{data_para}</div>'
        )

    parts.append(
        '<p style="font-size:12px; font-weight:bold; text-transform:uppercase; '
        'letter-spacing:1px; color:#888; margin:16px 0 4px;">Leaderboard</p>'
    )
    if data_ai_tools:
        parts.append(_html_leaderboard(data_ai_tools, prev_tools))
        parts.append(_html_profiles(data_ai_tools, prev_tools, previous))
    else:
        parts.append("<p><em>No Data &amp; AI tools identified this week.</em></p>")

    # ── Week-on-week movement ───────────────────────────────────────────────
    if new_entries or trending_up or trending_down or dropped:
        parts.append(
            '<div style="background:#f5f5f5; padding:14px 24px; margin:28px -24px 0 -24px; '
            'border-top:2px solid #e0e0e0;">'
            '<strong style="font-size:14px;">&#128200; Week-on-Week Movement</strong></div>'
            '<div style="padding:10px 0;">'
        )
        if new_entries:
            items = ", ".join(
                f"<strong>{_he(t['name'])}</strong>&nbsp;({t.get('excitement_score', 0):.1f})"
                for t in new_entries[:8]
            )
            parts.append(f'<p style="margin:6px 0;"><strong>&#128196; New this week:</strong> {items}</p>')
        if trending_up:
            items = ", ".join(
                f"<strong>{_he(t['name'])}</strong>&nbsp;(+{d:.1f})" for t, d in trending_up[:5]
            )
            parts.append(f'<p style="margin:6px 0;"><strong>&#128200; Trending up:</strong> {items}</p>')
        if trending_down:
            items = ", ".join(
                f"<strong>{_he(t['name'])}</strong>&nbsp;(&minus;{d:.1f})" for t, d in trending_down[:5]
            )
            parts.append(f'<p style="margin:6px 0;"><strong>&#128201; Trending down:</strong> {items}</p>')
        if dropped:
            items = ", ".join(_he(t["name"]) for t in dropped[:5])
            parts.append(f'<p style="margin:6px 0;"><strong>Dropped off:</strong> {items}</p>')
        parts.append("</div>")

    # ── Trends & Shifts (top 5 each) ────────────────────────────────────────
    trends = current.get("emerging_trends", [])[:5]
    shifts = current.get("notable_shifts", [])[:5]
    if trends or shifts:
        parts.append(
            '<div style="background:#f5f5f5; padding:14px 24px; margin:28px -24px 0 -24px; '
            'border-top:2px solid #e0e0e0;">'
            '<strong style="font-size:14px;">&#128161; Trends &amp; Shifts</strong></div>'
        )
        if trends:
            parts.append(
                '<p style="font-weight:bold; margin:14px 0 4px;">Emerging Trends</p>'
                '<ul style="margin:0; padding-left:20px; line-height:1.9;">'
            )
            for t in trends:
                parts.append(f"<li>{_he(t)}</li>")
            parts.append("</ul>")
        if shifts:
            parts.append(
                '<p style="font-weight:bold; margin:14px 0 4px;">Notable Shifts</p>'
                '<ul style="margin:0; padding-left:20px; line-height:1.9;">'
            )
            for s in shifts:
                parts.append(f"<li>{_he(s)}</li>")
            parts.append("</ul>")

    parts.append("</div>")  # end padding div

    parts.append(
        f'<div style="background:#0f1923; color:#5a7a8a; text-align:center; '
        f'padding:16px; font-size:12px; margin-top:32px;">'
        f'Dev Radar &nbsp;&middot;&nbsp; Powered by Reddit + Claude &nbsp;&middot;&nbsp; {generated_at}'
        f'</div></body></html>'
    )

    return "".join(parts)


# ── Main entry point ────────────────────────────────────────────────────────

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

    # Section 1 = DevOps / Developer Tools, Section 2 = Data & AI
    devtools_tools = [t for t in tools if not _is_data_ai(t)][:MAX_SECTION_TOOLS]
    data_ai_tools  = [t for t in tools if _is_data_ai(t)][:MAX_SECTION_TOOLS]

    # ── Plain-text report (archival .txt) ────────────────────────────────────
    lines: list[str] = []

    lines += [
        _rule("="),
        f"  DEV RADAR  --  Week of {week}".center(_W),
        (
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  |  "
            f"{len(tools)} tools  |  {len(cfg.SUBREDDITS)} subreddits"
        ).center(_W),
        _rule("="),
    ]

    lines += [
        _section("ABOUT THIS REPORT"),
        "",
        _wrap("This week's Dev Radar is split into two sections:", indent=2),
        "",
        _wrap(
            "1. Developer Tools & DevOps — tools that improve how software is "
            "built, deployed, and operated: CI/CD, frontend frameworks, backend "
            "tooling, CLI utilities, monitoring, and security.",
            indent=4,
        ),
        "",
        _wrap(
            "2. Data & AI Infrastructure — tools shaping how data is stored, "
            "processed, and consumed by AI/ML systems: data engineering, MLOps, "
            "vector databases, LLM frameworks, and AI platforms.",
            indent=4,
        ),
        "",
        _wrap(
            f"Each section highlights the top {MAX_SECTION_TOOLS} tools ranked "
            "by community excitement score this week.",
            indent=2,
        ),
    ]

    lines += [
        _section("QUICK STATS"),
        "",
        f"  Tools analysed  : {len(tools)}",
        f"  New this week   : {len(new_entries)}",
        f"  Trending up     : {len(trending_up)}",
        f"  Trending down   : {len(trending_down)}",
        f"  Dropped off     : {len(dropped)}",
    ]

    lines += _section_banner("SECTION 1: DEVELOPER TOOLS & DEVOPS")
    if devtools_tools:
        lines += _leaderboard_block(devtools_tools)
        lines += _profiles_block(devtools_tools, prev_tools, previous)
    else:
        lines += ["", "  No Developer Tools identified this week.", ""]

    lines += _section_banner("SECTION 2: DATA & AI INFRASTRUCTURE")
    if data_ai_tools:
        lines += _leaderboard_block(data_ai_tools)
        lines += _profiles_block(data_ai_tools, prev_tools, previous)
    else:
        lines += ["", "  No Data & AI tools identified this week.", ""]

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

    sub_counts: dict[str, int] = {}
    for tool in tools:
        for sub in tool.get("source_subreddits", []):
            sub_counts[sub] = sub_counts.get(sub, 0) + 1

    if sub_counts:
        lines += [_section("SOURCE BREAKDOWN"), ""]
        for sub, count in sorted(sub_counts.items(), key=lambda x: x[1], reverse=True):
            bar = "#" * count
            lines.append(f"  r/{sub:<20} {bar} ({count})")

    lines += [
        "",
        _rule("="),
        "  Generated by dev-radar  |  Powered by Reddit + Claude".center(_W),
        _rule("="),
    ]

    txt_path = cfg.REPORTS_DIR / f"{week}.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report saved to %s", txt_path)

    # ── HTML report (email) ──────────────────────────────────────────────────
    html_content = _generate_html(
        current, previous,
        devtools_tools, data_ai_tools,
        prev_tools, new_entries, trending_up, trending_down, dropped,
    )
    html_path = cfg.REPORTS_DIR / f"{week}.html"
    html_path.write_text(html_content, encoding="utf-8")

    return html_path
