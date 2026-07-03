"""
utils/emailer.py — outbound email via AWS SES's SMTP interface (audit G1).

Standard library only (smtplib) — no new dependencies. Configuration comes
from the environment:

    SES_SMTP_HOST      default email-smtp.us-east-2.amazonaws.com
    SES_SMTP_PORT      default 587 (STARTTLS)
    SES_SMTP_USER      SMTP credential from the SES console
    SES_SMTP_PASSWORD  SMTP credential from the SES console
    EMAIL_FROM         verified sender, e.g. "Route 1 <alerts@route1pathways.app>"

Until SES_SMTP_USER / SES_SMTP_PASSWORD / EMAIL_FROM are all set, sending is
a no-op that logs what it would have sent — the app works unchanged before
SES is configured and in local dev.

Sending runs on a daemon thread with its own SMTP connection, so a donation
request never waits on SMTP and a mail outage can't fail the money path.
"""

import logging
import os
import smtplib
import threading
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _config():
    return {
        "host":     os.getenv("SES_SMTP_HOST", "email-smtp.us-east-2.amazonaws.com"),
        "port":     int(os.getenv("SES_SMTP_PORT", "587")),
        "user":     os.getenv("SES_SMTP_USER"),
        "password": os.getenv("SES_SMTP_PASSWORD"),
        "sender":   os.getenv("EMAIL_FROM"),
    }


def is_configured() -> bool:
    cfg = _config()
    return bool(cfg["user"] and cfg["password"] and cfg["sender"])


def send_emails(messages) -> None:
    """Send a batch of (to_address, subject, body) tuples. Fire-and-forget."""
    if not messages:
        return
    if not is_configured():
        for to, subject, _body in messages:
            logger.info("EMAIL (SES not configured — skipped) → %s: %s", to, subject)
        return
    threading.Thread(target=_send_now, args=(list(messages),), daemon=True).start()


def _send_now(messages) -> None:
    cfg = _config()
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
            smtp.starttls()
            smtp.login(cfg["user"], cfg["password"])
            for to, subject, body in messages:
                try:
                    msg = EmailMessage()
                    msg["From"] = cfg["sender"]
                    msg["To"] = to
                    msg["Subject"] = subject
                    msg.set_content(body)
                    smtp.send_message(msg)
                    logger.info("EMAIL sent → %s: %s", to, subject)
                except Exception:
                    logger.exception("EMAIL failed → %s: %s", to, subject)
    except Exception:
        logger.exception("EMAIL batch failed (%d messages)", len(messages))
