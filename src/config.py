"""Configuration: load environment variables and define constants."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"
DB_PATH = DATA_DIR / "dev_radar.db"

DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# ── Load .env ──────────────────────────────────────────────────────────────
load_dotenv(ROOT_DIR / ".env")

# ── Reddit config ──────────────────────────────────────────────────────────
SUBREDDITS: list[str] = [
    "programming",
    "webdev",
    "devops",
    "dataengineering",
    "MLOps",
    "indiehackers",
]

# ── Email config ────────────────────────────────────────────────────────────
EMAIL_RECIPIENTS: list[str] = [
    "fmondinidefocatiis@eurazeo.com",
    "jvibert@eurazeo.com",
]
TIME_FILTER: str = os.getenv("TIME_FILTER", "week")
POST_LIMIT: int = int(os.getenv("POST_LIMIT", "50"))
MIN_UPVOTES: int = int(os.getenv("MIN_UPVOTES", "20"))
TOP_COMMENTS_PER_POST: int = int(os.getenv("TOP_COMMENTS", "10"))
REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "dev-radar/1.0")

# ── Claude config ──────────────────────────────────────────────────────────
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
MAX_BATCH_CHARS: int = int(os.getenv("MAX_BATCH_CHARS", "400000"))

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Credential globals (populated by load_secrets) ─────────────────────────
REDDIT_CLIENT_ID: str = ""
REDDIT_CLIENT_SECRET: str = ""
ANTHROPIC_API_KEY: str = ""


def _require(name: str) -> str:
    val = os.getenv(name, "")
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Copy .env.example to .env and fill in your credentials."
        )
    return val


def load_secrets() -> None:
    """Validate and populate credential globals. Call once at startup.

    Only ANTHROPIC_API_KEY is required. Reddit credentials are optional —
    if absent the public JSON scraper is used instead of PRAW.
    """
    global REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, ANTHROPIC_API_KEY
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
    ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")


def setup_logging() -> None:
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
