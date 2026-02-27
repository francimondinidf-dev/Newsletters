"""Send the Dev Radar report via the local Outlook application (win32com)."""

from __future__ import annotations

import logging
from pathlib import Path

import src.config as cfg

logger = logging.getLogger(__name__)


def send_report(report_path: Path, week: str) -> None:
    """Email report_path contents to all configured recipients via Outlook."""
    try:
        import win32com.client
    except ImportError:
        logger.error(
            "pywin32 not installed — run: uv pip install pywin32 --python .venv/Scripts/python.exe"
        )
        return

    body = report_path.read_text(encoding="utf-8")
    recipients = "; ".join(cfg.EMAIL_RECIPIENTS)

    outlook = win32com.client.Dispatch("outlook.application")
    mail = outlook.CreateItem(0)  # 0 = olMailItem
    mail.To = recipients
    mail.Subject = f"Dev Radar — Week of {week}"
    mail.Body = body
    mail.Send()

    logger.info("Report emailed to: %s", recipients)
