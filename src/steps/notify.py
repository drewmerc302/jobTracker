import json
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config import Config
from src.db import Database

logger = logging.getLogger(__name__)


def _load_template(config: Config):
    env = Environment(loader=FileSystemLoader(str(config.template_dir)))
    return env.get_template("digest.html")


def _parse_suggestions(match: dict) -> dict:
    try:
        return json.loads(match.get("suggestions") or "{}")
    except json.JSONDecodeError:
        return {}


def build_digest_html(
    matches: list[dict], run_stats: dict, config: Config, follow_ups: list[dict] = None
) -> str:
    template = _load_template(config)
    enriched = []
    for m in matches:
        m_copy = dict(m)
        m_copy["suggestions_parsed"] = _parse_suggestions(m)
        enriched.append(m_copy)
    return template.render(
        matches=enriched,
        run_stats=run_stats,
        date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
        follow_ups=follow_ups or [],
    )


def build_no_match_html(
    run_stats: dict, config: Config, follow_ups: list[dict] = None
) -> str:
    template = _load_template(config)
    return template.render(
        matches=[],
        run_stats=run_stats,
        date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
        follow_ups=follow_ups or [],
    )


def send_email(
    subject: str, html_body: str, attachments: list[tuple[str, Path]], config: Config
):
    msg = MIMEMultipart()
    msg["From"] = config.smtp_user
    msg["To"] = config.email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    for filename, filepath in attachments:
        if filepath and Path(filepath).exists():
            with open(filepath, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.smtp_user, config.smtp_password)
        server.send_message(msg)
    logger.info(f"Email sent to {config.email_to}")


def run_notify(db: Database, run_stats: dict, config: Config) -> bool:
    matches = db.get_unnotified_matches()
    follow_ups = db.get_overdue_follow_ups()

    if matches:
        subject = f"Job Tracker: {len(matches)} new match{'es' if len(matches) > 1 else ''} found — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        html = build_digest_html(matches, run_stats, config, follow_ups=follow_ups)
        attachments = []
        for m in matches:
            company = m.get("company", "unknown").replace(" ", "_")
            title = m.get("title", "role").replace(" ", "_").replace(",", "")[:30]
            if m.get("resume_path"):
                attachments.append(
                    (f"{company}_{title}_resume.pdf", Path(m["resume_path"]))
                )
            if m.get("cover_letter_path"):
                attachments.append(
                    (
                        f"{company}_{title}_cover_letter.pdf",
                        Path(m["cover_letter_path"]),
                    )
                )
    else:
        subject = f"Job Tracker: No new matches — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        html = build_no_match_html(run_stats, config, follow_ups=follow_ups)
        attachments = []

    try:
        send_email(subject, html, attachments, config)
        if matches:
            db.mark_notified([m["job_id"] for m in matches])
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
