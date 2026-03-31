# Application Status Tracker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add job application status tracking (new → applied → interviewing → offer → rejected → withdrawn) with CLI commands and auto-generated Obsidian notes.

**Architecture:** Extends existing jobTracker with an `applications` table + `status_history` audit log in SQLite, three new CLI commands (`--status`, `--track`, `--applications`), and Obsidian integration via MCP tools for per-application notes and a dashboard.

**Tech Stack:** Python 3.12+, SQLite, Jinja2, Obsidian MCP tools (mcp__obsidian__write_note, mcp__obsidian__update_frontmatter, mcp__obsidian__patch_note)

**Spec:** `docs/superpowers/specs/2026-03-30-application-tracker-design.md`

---

## File Map

| File | Change | Responsibility |
|------|--------|---------------|
| `src/db.py` | Modify | Add `applications` + `status_history` tables, CRUD methods |
| `src/pipeline.py` | Modify | Add `--status`, `--track`, `--applications` CLI handlers, update `--show-job` and `--list-matches` |
| `src/steps/obsidian.py` | Create | Obsidian note generation/update via MCP subprocess calls |
| `templates/application.md` | Create | Jinja2 template for per-application Obsidian note |
| `templates/dashboard.md` | Create | Jinja2 template for dashboard Obsidian note |
| `tests/test_db.py` | Modify | Add tests for applications CRUD |
| `tests/test_application_tracker.py` | Create | Tests for status updates, obsidian note rendering |

---

### Task 0: Database — Applications + Status History Tables

**Files:**
- Modify: `src/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_db.py`:
```python
VALID_STATUSES = ["new", "applied", "interviewing", "offer", "rejected", "withdrawn"]


def test_set_application_status(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    app = db.get_application("stripe:1")
    assert app is not None
    assert app["status"] == "applied"
    assert app["applied_date"] is not None


def test_set_application_status_updates(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    db.set_application_status("stripe:1", "interviewing")
    app = db.get_application("stripe:1")
    assert app["status"] == "interviewing"
    assert app["applied_date"] is not None  # preserved from applied


def test_status_history_logged(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    db.set_application_status("stripe:1", "interviewing")
    history = db.get_status_history("stripe:1")
    assert len(history) == 2
    assert history[0]["new_status"] == "applied"
    assert history[1]["old_status"] == "applied"
    assert history[1]["new_status"] == "interviewing"


def test_get_all_applications(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM1", url="u", scraped_at=now)
    db.upsert_job(id="stripe:2", company="Stripe", title="EM2", url="u", scraped_at=now)
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="great")
    db.insert_match(job_id="stripe:2", relevance_score=0.8, match_reason="good")
    db.set_application_status("stripe:1", "applied")
    # stripe:2 has no application record — should appear as "new"
    apps = db.get_all_applications()
    assert len(apps) == 2
    statuses = {a["job_id"]: a["status"] for a in apps}
    assert statuses["stripe:1"] == "applied"
    assert statuses["stripe:2"] == "new"


def test_update_salary_notes(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    db.update_salary_notes("stripe:1", "$200-250k base + equity")
    app = db.get_application("stripe:1")
    assert app["salary_notes"] == "$200-250k base + equity"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_db.py -v -k "application or status_history or salary"
```

- [ ] **Step 3: Implement DB methods**

Add to `src/db.py` `_create_tables`:
```python
CREATE TABLE IF NOT EXISTS applications (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    status TEXT NOT NULL,
    applied_date TEXT,
    salary_notes TEXT,
    status_updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TEXT NOT NULL
);
```

Add methods to `Database` class:
```python
def set_application_status(self, job_id: str, status: str):
    now = datetime.now(timezone.utc).isoformat()
    existing = self.get_application(job_id)
    old_status = existing["status"] if existing else None

    if existing:
        updates = {"status": status, "status_updated_at": now}
        if status == "applied" and not existing.get("applied_date"):
            updates["applied_date"] = now
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        self._conn.execute(
            f"UPDATE applications SET {set_clause} WHERE job_id = ?",
            list(updates.values()) + [job_id]
        )
    else:
        applied_date = now if status == "applied" else None
        self._conn.execute(
            "INSERT INTO applications (job_id, status, applied_date, status_updated_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, status, applied_date, now, now)
        )

    self._conn.execute(
        "INSERT INTO status_history (job_id, old_status, new_status, changed_at) VALUES (?, ?, ?, ?)",
        (job_id, old_status, status, now)
    )
    self._conn.commit()

def get_application(self, job_id: str) -> dict | None:
    row = self._conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None

def get_status_history(self, job_id: str) -> list[dict]:
    rows = self._conn.execute(
        "SELECT * FROM status_history WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    return [dict(r) for r in rows]

def get_all_applications(self) -> list[dict]:
    """Get all matches with their application status. Untracked matches show as 'new'."""
    rows = self._conn.execute("""
        SELECT m.job_id, j.company, j.title, j.url, j.location, m.relevance_score,
               COALESCE(a.status, 'new') as status,
               a.applied_date, a.status_updated_at, a.salary_notes,
               m.matched_at, m.resume_path, m.cover_letter_path
        FROM matches m
        JOIN jobs j ON m.job_id = j.id
        LEFT JOIN applications a ON m.job_id = a.job_id
        ORDER BY
            CASE COALESCE(a.status, 'new')
                WHEN 'interviewing' THEN 1
                WHEN 'offer' THEN 2
                WHEN 'applied' THEN 3
                WHEN 'new' THEN 4
                WHEN 'rejected' THEN 5
                WHEN 'withdrawn' THEN 6
            END,
            m.relevance_score DESC
    """).fetchall()
    return [dict(r) for r in rows]

def update_salary_notes(self, job_id: str, notes: str):
    self._conn.execute(
        "UPDATE applications SET salary_notes = ? WHERE job_id = ?", (notes, job_id)
    )
    self._conn.commit()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_db.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
# commit message: "feat: add applications and status_history tables with CRUD"
```

---

### Task 1: Obsidian Note Generation

**Files:**
- Create: `src/steps/obsidian.py`
- Create: `templates/application.md`
- Create: `templates/dashboard.md`
- Create: `tests/test_application_tracker.py`

- [ ] **Step 1: Create Jinja2 templates**

Create `templates/application.md`:
```markdown
---
company: {{ company }}
title: "{{ title }}"
status: {{ status }}
score: {{ score }}
applied_date: {{ applied_date or '' }}
url: {{ url }}
job_id: {{ job_id }}
tags: [job-application, {{ company | lower | replace(' ', '-') }}]
---

# {{ company }} — {{ title }}

## Status: {{ status | capitalize }}
{% if applied_date %}- **Applied:** {{ applied_date }}{% endif %}
- **Status updated:** {{ status_updated_at or 'N/A' }}

## Contacts

## Salary & Compensation
{{ salary_notes or '' }}

## Interview Prep

## Notes

## Match Analysis
{% if score != 'N/A' %}Score: {{ score }} | [View Listing]({{ url }})

{% if key_requirements %}Key requirements:
{% for req in key_requirements %}- {{ req }}
{% endfor %}{% endif %}

{% if match_reason %}Why this matches:
{{ match_reason }}{% endif %}
{% else %}No match analysis available — job was tracked directly.

[View Listing]({{ url }})
{% endif %}
```

Create `templates/dashboard.md`:
```markdown
---
tags: [job-application, dashboard]
updated: {{ updated }}
---

# Job Application Dashboard

*Auto-generated by jobTracker. Last updated: {{ updated }}*

{% for status_group in groups %}
## {{ status_group.label }} ({{ status_group.items | length }})
{% if status_group.items %}
| Company | Title | Score | {{ 'Applied' if status_group.key != 'new' else 'Matched' }} | Updated |
|---------|-------|-------|---------{% if status_group.key != 'new' %}|---------|{% else %}|{% endif %}

{% for item in status_group.items %}| {{ item.company }} | {% if item.status != 'new' %}[[{{ item.company }} — {{ item.title_clean }}]]{% else %}{{ item.title }}{% endif %} | {{ item.score }} | {{ item.date }} | {{ item.updated }} |
{% endfor %}{% endif %}

{% endfor %}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_application_tracker.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.config import Config
from src.db import Database
from src.steps.obsidian import render_application_note, render_dashboard, sanitize_filename


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_sanitize_filename():
    assert sanitize_filename("Stripe — Engineering Manager: Payments/Billing") == "Stripe — Engineering Manager Payments Billing"
    assert len(sanitize_filename("A" * 100)) <= 80


def test_render_application_note():
    html = render_application_note(
        company="Stripe",
        title="Engineering Manager, Agentic Commerce",
        status="applied",
        score="92%",
        url="https://stripe.com/jobs/search?gh_jid=7334661",
        job_id="Stripe:7334661",
        applied_date="2026-03-31",
        status_updated_at="2026-03-31",
        salary_notes="",
        match_reason="Strong match",
        key_requirements=["team leadership", "payments"],
        config=Config(),
    )
    assert "Stripe" in html
    assert "applied" in html.lower()
    assert "team leadership" in html


def test_render_application_note_no_match():
    html = render_application_note(
        company="Stripe",
        title="EM",
        status="applied",
        score="N/A",
        url="https://example.com",
        job_id="Stripe:999",
        applied_date="2026-03-31",
        status_updated_at="2026-03-31",
        salary_notes="",
        match_reason=None,
        key_requirements=[],
        config=Config(),
    )
    assert "tracked directly" in html


def test_render_dashboard():
    apps = [
        {"company": "Stripe", "title": "EM1", "relevance_score": 0.92, "status": "applied",
         "applied_date": "2026-03-31", "status_updated_at": "2026-03-31", "job_id": "Stripe:1"},
        {"company": "DataDog", "title": "EM2", "relevance_score": 0.62, "status": "new",
         "applied_date": None, "status_updated_at": None, "matched_at": "2026-03-30", "job_id": "DataDog:2"},
    ]
    html = render_dashboard(apps, Config())
    assert "Applied" in html
    assert "New" in html
    assert "Stripe" in html
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_application_tracker.py -v
```

- [ ] **Step 4: Implement obsidian.py**

Create `src/steps/obsidian.py`:
```python
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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
    """Remove characters invalid in filenames, truncate to 80 chars."""
    cleaned = re.sub(r'[:/\\?*"<>|]', '', name)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:80]


def _load_template(template_name: str, config: Config) -> str:
    env = Environment(loader=FileSystemLoader(str(config.template_dir)))
    return env.get_template(template_name)


def render_application_note(*, company: str, title: str, status: str, score: str,
                            url: str, job_id: str, applied_date: str | None,
                            status_updated_at: str | None, salary_notes: str,
                            match_reason: str | None, key_requirements: list[str],
                            config: Config) -> str:
    template = _load_template("application.md", config)
    return template.render(
        company=company, title=title, status=status, score=score,
        url=url, job_id=job_id, applied_date=applied_date,
        status_updated_at=status_updated_at, salary_notes=salary_notes,
        match_reason=match_reason, key_requirements=key_requirements or [],
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
            items.append({
                "company": a["company"], "title": a["title"], "title_clean": title_clean,
                "score": score, "date": date, "updated": updated,
                "status": a.get("status", "new"),
            })
        groups.append({"key": status_key, "label": label, "items": items})

    template = _load_template("dashboard.md", config)
    return template.render(groups=groups, updated=now)


def write_application_note(job_id: str, db: Database, config: Config):
    """Create or update an Obsidian note for a job application."""
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
        company=job["company"], title=job["title"], status=status, score=score,
        url=job["url"], job_id=job_id, applied_date=applied_date,
        status_updated_at=status_updated_at, salary_notes=salary_notes,
        match_reason=match_reason, key_requirements=key_requirements, config=config,
    )

    note_name = sanitize_filename(f"{job['company']} — {job['title']}")
    note_path = f"{VAULT_PATH}/{note_name}.md"

    try:
        # Check if note exists — if so, only update frontmatter and status section
        result = subprocess.run(
            ["claude", "mcp", "call", "obsidian", "read_note",
             "--", json.dumps({"path": note_path})],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and "error" not in result.stdout.lower():
            # Note exists — update frontmatter only
            _update_existing_note(note_path, status, applied_date, status_updated_at)
            return
    except Exception:
        pass  # Note doesn't exist or MCP call failed — create it

    _write_note(note_path, content)


def _write_note(path: str, content: str):
    """Write a note to Obsidian via MCP."""
    try:
        subprocess.run(
            ["claude", "mcp", "call", "obsidian", "write_note",
             "--", json.dumps({"path": path, "content": content})],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        logger.warning(f"Failed to write Obsidian note {path}: {e}")


def _update_existing_note(path: str, status: str, applied_date: str | None,
                          status_updated_at: str | None):
    """Update frontmatter and status section of an existing note."""
    try:
        # Update frontmatter
        subprocess.run(
            ["claude", "mcp", "call", "obsidian", "update_frontmatter",
             "--", json.dumps({"path": path, "frontmatter": {
                 "status": status,
                 "applied_date": applied_date or "",
             }})],
            capture_output=True, text=True, timeout=10,
        )
        # Patch status section
        status_content = f"\n## Status: {status.capitalize()}\n"
        if applied_date:
            status_content += f"- **Applied:** {applied_date}\n"
        status_content += f"- **Status updated:** {status_updated_at or 'N/A'}\n"

        subprocess.run(
            ["claude", "mcp", "call", "obsidian", "patch_note",
             "--", json.dumps({
                 "path": path,
                 "operation": "replace",
                 "targetType": "heading",
                 "target": "Status",
                 "content": status_content,
             })],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        logger.warning(f"Failed to update Obsidian note {path}: {e}")


def write_dashboard(db: Database, config: Config):
    """Regenerate the Obsidian dashboard note."""
    apps = db.get_all_applications()
    content = render_dashboard(apps, config)
    _write_note(DASHBOARD_PATH, content)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_application_tracker.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/steps/obsidian.py templates/application.md templates/dashboard.md tests/test_application_tracker.py
# commit message: "feat: add Obsidian note generation for application tracking"
```

---

### Task 2: CLI Commands (--status, --track, --applications)

**Files:**
- Modify: `src/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_pipeline.py`:
```python
def test_parse_args_status():
    args = parse_args(["--status", "Stripe:123", "applied"])
    assert args.status == ["Stripe:123", "applied"]


def test_parse_args_track():
    args = parse_args(["--track", "Stripe:123"])
    assert args.track == "Stripe:123"


def test_parse_args_applications():
    args = parse_args(["--applications"])
    assert args.applications is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_pipeline.py -v -k "status or track or applications"
```

- [ ] **Step 3: Add argparse flags**

In `parse_args()`, add after the existing `--show-job` line:
```python
parser.add_argument("--status", nargs=2, metavar=("JOB_ID", "STATUS"),
                    help="Set application status (e.g. --status \"Stripe:123\" applied)")
parser.add_argument("--track", metavar="JOB_ID",
                    help="Interactive status update with prompts")
parser.add_argument("--applications", action="store_true",
                    help="Show application status dashboard")
```

- [ ] **Step 4: Add handlers in run_pipeline**

Add before the `if args.renotify:` block:
```python
if args.status:
    job_id, new_status = args.status
    valid_statuses = ["new", "applied", "interviewing", "offer", "rejected", "withdrawn"]
    if new_status not in valid_statuses:
        logger.error(f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}")
        return
    job = db.get_job(job_id)
    if not job:
        logger.error(f"Job not found: {job_id}")
        return
    db.set_application_status(job_id, new_status)
    print(f"Status updated: {job['company']} — {job['title']} → {new_status}")
    from src.steps.obsidian import write_application_note, write_dashboard
    write_application_note(job_id, db, config)
    write_dashboard(db, config)
    return

if args.track:
    job_id = args.track
    job = db.get_job(job_id)
    if not job:
        logger.error(f"Job not found: {job_id}")
        return
    app = db.get_application(job_id)
    current = app["status"] if app else "new"
    print(f"\n{job['company']} — {job['title']}")
    print(f"Current status: {current}\n")

    valid_statuses = ["new", "applied", "interviewing", "offer", "rejected", "withdrawn"]
    for i, s in enumerate(valid_statuses, 1):
        marker = " ←" if s == current else ""
        print(f"  {i}. {s}{marker}")
    print()

    choice = input("Enter number (or Enter to keep current): ").strip()
    if choice and choice.isdigit() and 1 <= int(choice) <= len(valid_statuses):
        new_status = valid_statuses[int(choice) - 1]
        db.set_application_status(job_id, new_status)
        print(f"Status → {new_status}")
    else:
        new_status = current

    salary = input("Salary notes (Enter to skip): ").strip()
    if salary:
        if not app:
            db.set_application_status(job_id, new_status)
        db.update_salary_notes(job_id, salary)
        print(f"Salary notes saved")

    from src.steps.obsidian import write_application_note, write_dashboard
    write_application_note(job_id, db, config)
    write_dashboard(db, config)

    note_name = f"{job['company']} — {job['title']}"
    print(f"\nObsidian note: Topics/Job Applications/{note_name}.md")
    return

if args.applications:
    apps = db.get_all_applications()
    if not apps:
        print("No tracked applications.")
        return
    current_status = None
    for a in apps:
        status = a.get("status", "new")
        if status != current_status:
            count = sum(1 for x in apps if x.get("status", "new") == status)
            print(f"\n{status.upper()} ({count})")
            current_status = status
        score = f"{a['relevance_score']:.0%}" if a.get("relevance_score") else "N/A"
        company = a["company"][:12]
        title = a["title"][:40]
        if a.get("applied_date"):
            date_info = f"applied {a['applied_date'][:10]}"
        elif a.get("matched_at"):
            date_info = f"matched {a['matched_at'][:10]}"
        else:
            date_info = ""
        print(f"  {score:>5}  {company:<12} {title:<40} {date_info}")
    return
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_pipeline.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
# commit message: "feat: add --status, --track, --applications CLI commands"
```

---

### Task 3: Update --show-job and --list-matches

**Files:**
- Modify: `src/pipeline.py`

- [ ] **Step 1: Update --show-job handler**

In the `if args.show_job:` block, after the line that prints `Score:`, add:
```python
app = db.get_application(job_id)
app_status = app["status"] if app else "not tracked"
app_date = f" ({app['applied_date'][:10]})" if app and app.get("applied_date") else ""
print(f"Status:   {app_status}{app_date}")
```

- [ ] **Step 2: Update --list-matches handler**

Update the `--list-matches` SQL query to LEFT JOIN applications and add status column to output:
```python
rows = db._conn.execute("""
    SELECT m.job_id, j.company, j.title, j.location, m.relevance_score,
           CASE WHEN m.resume_path IS NOT NULL THEN 'yes' ELSE 'no' END as has_pdf,
           COALESCE(a.status, 'new') as status
    FROM matches m JOIN jobs j ON m.job_id = j.id
    LEFT JOIN applications a ON m.job_id = a.job_id
    ORDER BY m.relevance_score DESC
""").fetchall()
```

Update the print header and row:
```python
print(f"{'Score':>5}  {'PDF':>3}  {'Status':<12} {'Company':<12} {'Title':<35} {'Tailor Command'}")
print("-" * 115)
for r in rows:
    job_id, company, title, location, score, has_pdf, status = r
    title_display = title[:33] + ".." if len(title) > 35 else title
    print(f"{score:>5.0%}  {has_pdf:>3}  {status:<12} {company:<12} {title_display:<35} uv run jobtracker --tailor-job \"{job_id}\"")
```

- [ ] **Step 3: Run all tests**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add src/pipeline.py
# commit message: "feat: add status column to --show-job and --list-matches"
```

---

### Task 4: Update /jobs Skill and Obsidian Topic

**Files:**
- Modify: `.claude/skills/jobs.md`
- Obsidian: Update `Topics/jobTracker.md` via MCP

- [ ] **Step 1: Update jobs skill**

Add to `.claude/skills/jobs.md` after the "Generate tailored resume + cover letter" section:

```markdown
### Set application status
```bash
uv run jobtracker --status "COMPANY:ID" applied
```
Valid statuses: new, applied, interviewing, offer, rejected, withdrawn

### Interactive tracking (with prompts)
```bash
uv run jobtracker --track "COMPANY:ID"
```

### View application dashboard
```bash
uv run jobtracker --applications
```
```

Update the workflow section:
```markdown
## Typical workflow

1. **See what matched:** `uv run jobtracker --list-matches`
2. **Read the analysis:** `uv run jobtracker --show-job "Stripe:7609424"`
3. **Generate PDFs:** `uv run jobtracker --tailor-job "Stripe:7609424" --adopt 1,3,5`
4. **Mark as applied:** `uv run jobtracker --status "Stripe:7609424" applied`
5. **Track progress:** `uv run jobtracker --applications`
6. **Add details:** `uv run jobtracker --track "Stripe:7609424"` (contacts, salary, interview prep in Obsidian)
```

- [ ] **Step 2: Update Obsidian topic note**

Update `Topics/jobTracker.md` via MCP with new commands and workflow.

- [ ] **Step 3: Commit skill file**

```bash
git add .claude/skills/jobs.md
# commit message: "docs: update /jobs skill with application tracking commands"
```
