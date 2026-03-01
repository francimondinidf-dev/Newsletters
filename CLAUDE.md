# Dev Radar

Weekly developer-tools intelligence report powered by Reddit + Claude.

Every Monday it scrapes top posts from developer subreddits, sends them to
Claude for analysis, and emails a plain-text report to the configured
recipients.

---

## What it does

1. Scrapes weekly top posts from Reddit (no API key needed — uses public JSON)
2. Sends all posts to Claude, which identifies the developer tools being
   discussed, scores excitement (1-10), and spots emerging trends
3. Saves results to a local SQLite database (data/dev_radar.db)
4. Generates a plain-text report in reports/YYYY-MM-DD.txt
5. Emails the report via the local Outlook application

---

## Folder structure

```
dev-radar/
  src/
    config.py        — subreddits, email recipients, Claude model, all settings
    main.py          — orchestrator (scrape → analyse → report → email)
    public_scraper.py — Reddit public JSON scraper (no API key)
    reddit_scraper.py — PRAW-based scraper (needs Reddit API creds)
    mock_scraper.py  — fake posts for testing
    analyzer.py      — Claude API integration, prompt, JSON schema
    database.py      — SQLite persistence
    report.py        — plain-text report generator (.txt)
    emailer.py       — sends report via Outlook COM (win32com)
  data/
    dev_radar.db     — SQLite database (posts + weekly analyses)
  reports/
    YYYY-MM-DD.txt   — one report per week
  run_weekly.bat     — Windows batch file run by Task Scheduler every Monday
  requirements.txt   — Python dependencies
  CLAUDE.md          — this file
```

---

## Subreddits monitored

- r/programming
- r/webdev
- r/devops
- r/dataengineering
- r/MLOps
- r/indiehackers

To add or remove subreddits, edit the `SUBREDDITS` list in `src/config.py`.

---

## Email recipients

Configured in `src/config.py` under `EMAIL_RECIPIENTS`:

- fmondinidefocatiis@eurazeo.com
- jvibert@eurazeo.com

Emails are sent via the local Outlook app (must be installed and logged in).

---

## Setup from scratch

### 1. Prerequisites

- Python 3.11 (installed via `uv` at
  `%APPDATA%\Roaming\uv\python\cpython-3.11.14-windows-x86_64-none\`)
- Outlook installed and logged in with your email account
- An Anthropic API key

### 2. Create the virtual environment

Open a terminal in the project folder, then:

```
uv venv
uv pip install -r requirements.txt --python .venv/Scripts/python.exe
```

### 3. Set your Anthropic API key

Open `run_weekly.bat` and replace the value of `ANTHROPIC_API_KEY` with your key.

### 4. Test it works

```
set PYTHONUTF8=1
set ANTHROPIC_API_KEY=your-key-here
cd "C:\Users\fmondinidefocatiis\Documents\Claude Projects\dev-radar"
.venv\Scripts\python.exe -m src.main --dry-run --use-mock
```

### 5. Run a full analysis

```
.venv\Scripts\python.exe -m src.main
```

### 6. Set up the Monday schedule (Task Scheduler)

Run this once in an elevated (admin) terminal:

```
schtasks /Create /TN "DevRadar Weekly Report" ^
  /TR "\"C:\Users\fmondinidefocatiis\Documents\Claude Projects\dev-radar\run_weekly.bat\"" ^
  /SC WEEKLY /D MON /ST 08:00 /F
```

To verify it was created:
```
schtasks /Query /TN "DevRadar Weekly Report"
```

To run it immediately for testing:
```
schtasks /Run /TN "DevRadar Weekly Report"
```

To remove it:
```
schtasks /Delete /TN "DevRadar Weekly Report" /F
```

---

## Command-line options

```
python -m src.main                  # Full run: scrape + analyse + report
python -m src.main --email          # Full run + email the report via Outlook
python -m src.main --dry-run        # Scrape only, skip Claude (fast test)
python -m src.main --use-mock       # Use fake Reddit data (no network needed)
python -m src.main --report-only    # Regenerate report from latest stored analysis
python -m src.main --report-only --week 2026-02-27   # Specific week
```

---

## Report format

Reports are saved as plain text to `reports/YYYY-MM-DD.txt` and contain:

- Preface explaining the two-section structure
- **Section 1: Data & AI Infrastructure** — top 7 tools (data engineering,
  MLOps, databases, LLM frameworks, AI platforms)
- **Section 2: Developer Tools & DevOps** — top 7 tools (CI/CD, frontend,
  backend, CLI, monitoring, security)
- Each section has a leaderboard and per-tool profiles (company, HQ, score, quotes)
- New entries, trending up/down, dropped off (week-on-week comparison)
- Emerging trends and notable shifts
- Source breakdown by subreddit

---

## Claude model

Defaults to `claude-haiku-4-5-20251001` (Claude Haiku 4.5). Change via `CLAUDE_MODEL` in `src/config.py`
or set the `CLAUDE_MODEL` environment variable.
