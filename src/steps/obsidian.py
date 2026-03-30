import json
import logging
import re
import subprocess
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader

from src.config import Config
from src.db import Database

logger = logging.getLogger(__name__)

VAULT_PATH = "Topics/Job Applications"
DASHBOARD_PATH = f"{VAULT_PATH}/Dashboard.md"

STATUS_ORDER = [
    ("interviewing", "Interviewing"),
    ("offer", "Offer"),
    ("applied", "Applied"),
    ("new", "New"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
]


def sanitize_filename(name: str) -> str:
    # Replace punctuation with spaces
    cleaned = re.sub(r'[:/\\?*"<>|]', " ", name)
    # Collapse multiple spaces into one
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:80]


def _load_template(template_name: str, config: Config):
    env = Environment(loader=FileSystemLoader(str(config.template_dir)))
    return env.get_template(template_name)


def render_application_note(
    *,
    company: str,
    title: str,
    status: str,
    score: str,
    url: str,
    job_id: str,
    applied_date: str | None,
    status_updated_at: str | None,
    salary_notes: str,
    match_reason: str | None,
    key_requirements: list[str],
    config: Config,
) -> str:
    template = _load_template("application.md", config)
    return template.render(
        company=company,
        title=title,
        status=status,
        score=score,
        url=url,
        job_id=job_id,
        applied_date=applied_date,
        status_updated_at=status_updated_at,
        salary_notes=salary_notes,
        match_reason=match_reason,
        key_requirements=key_requirements or [],
    )


def render_dashboard(apps: list[dict], config: Config) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    groups = []
    for status_key, label in STATUS_ORDER:
        items = []
        for a in apps:
            if a.get("status", "new") != status_key:
                continue
            score = f"{a['relevance_score']:.0%}" if a.get("relevance_score") else "N/A"
            title_clean = sanitize_filename(f"{a['company']} — {a['title']}")
            if status_key == "new":
                date = (a.get("matched_at") or "")[:10]
            else:
                date = (a.get("applied_date") or "")[:10]
            updated = (a.get("status_updated_at") or a.get("matched_at") or "")[:10]
            items.append(
                {
                    "company": a["company"],
                    "title": a["title"],
                    "title_clean": title_clean,
                    "score": score,
                    "date": date,
                    "updated": updated,
                    "status": a.get("status", "new"),
                }
            )
        groups.append({"key": status_key, "label": label, "items": items})

    template = _load_template("dashboard.md", config)
    return template.render(groups=groups, updated=now)


def write_application_note(job_id: str, db: Database, config: Config):
    job = db.get_job(job_id)
    if not job:
        logger.warning(f"Cannot create note: job {job_id} not found")
        return
    app = db.get_application(job_id)
    match = db.get_match(job_id)

    status = app["status"] if app else "new"
    applied_date = app.get("applied_date") if app else None
    status_updated_at = app.get("status_updated_at") if app else None
    salary_notes = app.get("salary_notes", "") if app else ""

    if match:
        score = f"{match['relevance_score']:.0%}"
        match_reason = match.get("match_reason")
        suggestions = json.loads(match.get("suggestions") or "{}")
        key_requirements = suggestions.get("key_requirements", [])
    else:
        score = "N/A"
        match_reason = None
        key_requirements = []

    content = render_application_note(
        company=job["company"],
        title=job["title"],
        status=status,
        score=score,
        url=job["url"],
        job_id=job_id,
        applied_date=applied_date,
        status_updated_at=status_updated_at,
        salary_notes=salary_notes,
        match_reason=match_reason,
        key_requirements=key_requirements,
        config=config,
    )

    note_name = sanitize_filename(f"{job['company']} — {job['title']}")
    note_path = f"{VAULT_PATH}/{note_name}"
    # write_note handles .md extension
    _write_note(note_path, content)


def _write_note(path: str, content: str):
    try:
        subprocess.run(
            [
                "claude",
                "mcp",
                "call",
                "obsidian",
                "write_note",
                "--",
                json.dumps({"path": path, "content": content}),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Failed to write Obsidian note {path}: {e}")


def write_dashboard(db: Database, config: Config):
    apps = db.get_all_applications()
    content = render_dashboard(apps, config)
    _write_note(DASHBOARD_PATH, content)
