# Job Tracker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python pipeline that scrapes 4 career sites every 12 hours, filters for engineering manager roles, tailors resumes/cover letters per match, and emails a digest.

**Architecture:** 4-step pipeline (scrape → filter → tailor → notify) with SQLite state, Anthropic SDK for LLM evaluation, existing resume-skills for PDF generation, SMTP for email. Scheduled via macOS launchd.

**Tech Stack:** Python 3.12+, uv, httpx, anthropic SDK, jinja2, tenacity (retries), SQLite, Typst (system), smtplib

**Spec:** `docs/superpowers/specs/2026-03-30-job-tracker-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Project metadata, dependencies |
| `.env` | API keys, SMTP credentials |
| `.gitignore` | Exclude data/, output/, .env |
| `src/__init__.py` | Package marker |
| `src/config.py` | All configuration: env vars, keywords, thresholds, paths |
| `src/db.py` | SQLite schema, CRUD for jobs/matches/runs |
| `src/scrapers/__init__.py` | Scraper registry |
| `src/scrapers/base.py` | `RawJob` dataclass + `BaseScraper` ABC |
| `src/scrapers/greenhouse.py` | Parameterized Greenhouse scraper (Dropbox, DataDog, Stripe) |
| `src/scrapers/workday.py` | Capital One Workday CXS scraper |
| `src/steps/scrape.py` | Step 1: run all scrapers, dedup against DB |
| `src/steps/filter.py` | Step 2: keyword pre-filter + LLM evaluation |
| `src/steps/tailor.py` | Step 3: resume reordering + cover letter generation |
| `src/steps/notify.py` | Step 4: build HTML digest + send email |
| `src/pipeline.py` | Orchestrator: runs steps in sequence, CLI flags |
| `templates/digest.html` | Jinja2 HTML email template |
| `run.sh` | launchd wrapper script |
| `launchd/com.drewmerc.jobtracker.plist` | macOS scheduled task |
| `tests/test_db.py` | DB layer tests |
| `tests/test_scrapers.py` | Scraper tests (with fixtures) |
| `tests/test_filter.py` | Keyword + LLM filter tests |
| `tests/test_tailor.py` | Resume tailoring tests |
| `tests/test_notify.py` | Email digest tests |
| `tests/test_pipeline.py` | Integration tests |
| `tests/fixtures/` | Sample API responses, resume YAML |

---

### Task 0: Project Scaffolding

**Files:**
- Create: `pyproject.toml`, `.env`, `.gitignore`, `src/__init__.py`, `src/scrapers/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/drewmerc/workspace/jobTracker
git init
```

- [ ] **Step 2: Create pyproject.toml**

Create `pyproject.toml`:
```toml
[project]
name = "jobtracker"
version = "0.1.0"
description = "Automated job tracker for engineering manager roles"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.50.0",
    "httpx>=0.28.0",
    "jinja2>=3.1.0",
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0",
    "tenacity>=9.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
]

[project.scripts]
jobtracker = "src.pipeline:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

- [ ] **Step 3: Create .env template**

Create `.env`:
```
ANTHROPIC_API_KEY=
SMTP_USER=
SMTP_PASSWORD=
```

- [ ] **Step 4: Create .gitignore**

Create `.gitignore`:
```
.env
data/
output/
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 5: Create package init files**

Create `src/__init__.py` and `src/scrapers/__init__.py` as empty files.

Create `tests/__init__.py` and `tests/fixtures/` directory.

- [ ] **Step 6: Run `uv sync` and verify**

```bash
uv sync --dev
uv run python -c "import httpx, anthropic, jinja2, dotenv, tenacity; print('deps OK')"
uv run python -c "from src.config import Config; print('package import OK')"
```

Expected: `deps OK` then `package import OK`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src/ tests/
git commit -m "chore: scaffold jobtracker project with dependencies"
```

Note: Do NOT commit `.env`.

---

### Task 1: Configuration Module

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_config.py`:
```python
from src.config import Config


def test_config_loads_defaults():
    config = Config()
    assert config.relevance_threshold == 0.6
    assert config.llm_model == "claude-sonnet-4-6"
    assert config.email_to == "andrew.m.mercurio@gmail.com"
    assert config.db_path.name == "jobtracker.db"
    assert len(config.keyword_patterns) > 0
    assert "engineering manager" in config.keyword_patterns


def test_config_greenhouse_companies():
    config = Config()
    gh = config.greenhouse_boards
    assert "dropbox" in gh
    assert "datadog" in gh
    assert "stripe" in gh


def test_config_keyword_match():
    config = Config()
    assert config.matches_keyword("Senior Engineering Manager")
    assert config.matches_keyword("Director of Engineering")
    assert not config.matches_keyword("Software Engineer")
    assert not config.matches_keyword("VP of Engineering")


def test_config_seniority_excluded():
    config = Config()
    assert config.is_seniority_excluded("VP of Engineering")
    assert config.is_seniority_excluded("Principal Engineer")
    assert not config.is_seniority_excluded("Senior Engineering Manager")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement config module**

Create `src/config.py`:
```python
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class Config:
    # API keys (from .env)
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))

    # Email
    email_to: str = "andrew.m.mercurio@gmail.com"

    # LLM
    llm_model: str = "claude-sonnet-4-6"
    relevance_threshold: float = 0.6

    # Resume
    resume_versions_path: Path = field(default_factory=lambda: Path.home() / ".resume_versions")
    resume_project: str = "drewmercResume"
    resume_formatter_dir: Path = field(
        default_factory=lambda: Path.home() / ".claude/plugins/marketplaces/resume-helper-skills/resume-formatter"
    )
    resume_coverletter_dir: Path = field(
        default_factory=lambda: Path.home() / ".claude/plugins/marketplaces/resume-helper-skills/resume-coverletter"
    )
    resume_state_dir: Path = field(
        default_factory=lambda: Path.home() / ".claude/plugins/marketplaces/resume-helper-skills/resume-state"
    )
    resume_template: str = "executive"
    cover_letter_template: str = "executive-cover"

    # Paths
    db_path: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "jobtracker.db")
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    template_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "templates")

    # Greenhouse boards
    greenhouse_boards: dict[str, str] = field(default_factory=lambda: {
        "dropbox": "Dropbox",
        "datadog": "DataDog",
        "stripe": "Stripe",
    })

    # Workday companies
    workday_companies: dict[str, dict] = field(default_factory=lambda: {
        "capitalone": {
            "display_name": "Capital One",
            "base_url": "https://capitalone.wd12.myworkdayjobs.com",
            "path": "/wday/cxs/capitalone/Capital_One",
        },
    })

    # Filter settings
    keyword_patterns: list[str] = field(default_factory=lambda: [
        "engineering manager",
        "manager of engineering",
        "director of engineering",
        "head of engineering",
        "software engineering manager",
        "technical manager",
        "engineering lead",
        "development manager",
    ])

    seniority_exclusions: list[str] = field(default_factory=lambda: [
        "staff", "principal", "vp", "vice president",
        "c-level", "cto", "ceo", "coo",
        "junior", "associate", "intern",
    ])

    def matches_keyword(self, title: str) -> bool:
        """Check if a job title matches any keyword pattern."""
        title_lower = title.lower()
        # Exclude seniority mismatches first
        if self.is_seniority_excluded(title):
            return False
        return any(kw in title_lower for kw in self.keyword_patterns)

    def is_seniority_excluded(self, title: str) -> bool:
        """Check if title contains an excluded seniority level."""
        title_lower = title.lower()
        for excl in self.seniority_exclusions:
            # Match as whole word to avoid false positives
            if re.search(rf"\b{re.escape(excl)}\b", title_lower):
                return True
        return False
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_config.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add configuration module with keyword filtering"
```

---

### Task 2: Database Layer

**Files:**
- Create: `src/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db.py`:
```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.db import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    return Database(db_path)


def test_creates_tables(db):
    conn = sqlite3.connect(db.path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert "jobs" in table_names
    assert "matches" in table_names
    assert "runs" in table_names


def test_upsert_job_new(db):
    job_id = "dropbox:123"
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id=job_id, company="Dropbox", title="EM", url="https://example.com",
        location="Remote", remote=True, salary="200k", description="desc",
        department="Eng", seniority="Senior", scraped_at=now,
    )
    job = db.get_job(job_id)
    assert job is not None
    assert job["title"] == "EM"
    assert job["first_seen_at"] is not None


def test_upsert_job_updates_last_seen(db):
    job_id = "dropbox:123"
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id=job_id, company="Dropbox", title="EM", url="https://example.com",
        scraped_at=now,
    )
    first = db.get_job(job_id)
    db.upsert_job(
        id=job_id, company="Dropbox", title="EM", url="https://example.com",
        scraped_at=now,
    )
    second = db.get_job(job_id)
    assert second["last_seen_at"] >= first["last_seen_at"]


def test_get_new_job_ids(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    new_ids = db.get_new_job_ids(["dropbox:1", "dropbox:2", "dropbox:3"])
    assert set(new_ids) == {"dropbox:2", "dropbox:3"}


def test_close_missing_jobs(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    db.upsert_job(id="dropbox:2", company="Dropbox", title="EM2", url="u", scraped_at=now)
    db.close_missing_jobs("Dropbox", current_ids=["dropbox:1"])
    job1 = db.get_job("dropbox:1")
    job2 = db.get_job("dropbox:2")
    assert job1["closed_at"] is None
    assert job2["closed_at"] is not None


def test_insert_match(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    db.insert_match(
        job_id="dropbox:1", relevance_score=0.85, match_reason="good fit",
        suggestions='{"edits": []}',
    )
    match = db.get_match("dropbox:1")
    assert match is not None
    assert match["relevance_score"] == 0.85


def test_start_and_complete_run(db):
    run_id = db.start_run()
    assert run_id is not None
    db.complete_run(run_id, jobs_scraped=100, new_jobs=5, matches_found=2, email_sent=True)
    run = db.get_run(run_id)
    assert run["jobs_scraped"] == 100
    assert run["email_sent"] == 1
    assert run["completed_at"] is not None


def test_get_unnotified_matches(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    db.insert_match(job_id="dropbox:1", relevance_score=0.9, match_reason="great")
    unnotified = db.get_unnotified_matches()
    assert len(unnotified) == 1
    assert unnotified[0]["job_id"] == "dropbox:1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_db.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement database module**

Create `src/db.py`:
```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                location TEXT,
                remote BOOLEAN,
                salary TEXT,
                description TEXT,
                department TEXT,
                seniority TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                closed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS matches (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id),
                relevance_score REAL NOT NULL,
                match_reason TEXT NOT NULL,
                resume_path TEXT,
                cover_letter_path TEXT,
                suggestions TEXT,
                matched_at TEXT NOT NULL,
                notified_at TEXT
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                jobs_scraped INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                matches_found INTEGER DEFAULT 0,
                email_sent BOOLEAN DEFAULT 0,
                error TEXT
            );
        """)

    def upsert_job(self, *, id: str, company: str, title: str, url: str,
                   scraped_at: datetime, location: str = None, remote: bool = None,
                   salary: str = None, description: str = None, department: str = None,
                   seniority: str = None):
        now = scraped_at.isoformat()
        self._conn.execute("""
            INSERT INTO jobs (id, company, title, url, location, remote, salary,
                            description, department, seniority, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                description = COALESCE(excluded.description, jobs.description),
                salary = COALESCE(excluded.salary, jobs.salary),
                location = COALESCE(excluded.location, jobs.location),
                closed_at = NULL
        """, (id, company, title, url, location, remote, salary,
              description, department, seniority, now, now))
        self._conn.commit()

    def get_job(self, job_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def get_new_job_ids(self, candidate_ids: list[str]) -> list[str]:
        existing = set()
        # Query in batches to avoid SQLite variable limit
        for i in range(0, len(candidate_ids), 500):
            batch = candidate_ids[i:i + 500]
            placeholders = ",".join("?" * len(batch))
            rows = self._conn.execute(
                f"SELECT id FROM jobs WHERE id IN ({placeholders})", batch
            ).fetchall()
            existing.update(r["id"] for r in rows)
        return [cid for cid in candidate_ids if cid not in existing]

    def close_missing_jobs(self, company: str, current_ids: list[str]):
        """Mark jobs as closed if they weren't in the latest scrape for this company."""
        now = datetime.now(timezone.utc).isoformat()
        if not current_ids:
            self._conn.execute(
                "UPDATE jobs SET closed_at = ? WHERE company = ? AND closed_at IS NULL",
                (now, company)
            )
        else:
            placeholders = ",".join("?" * len(current_ids))
            self._conn.execute(
                f"""UPDATE jobs SET closed_at = ?
                    WHERE company = ? AND closed_at IS NULL
                    AND id NOT IN ({placeholders})""",
                [now, company] + current_ids
            )
        self._conn.commit()

    def insert_match(self, *, job_id: str, relevance_score: float,
                     match_reason: str, suggestions: str = None,
                     resume_path: str = None, cover_letter_path: str = None):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            INSERT OR REPLACE INTO matches
            (job_id, relevance_score, match_reason, suggestions, resume_path,
             cover_letter_path, matched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, relevance_score, match_reason, suggestions,
              resume_path, cover_letter_path, now))
        self._conn.commit()

    def update_match_paths(self, job_id: str, *, resume_path: str = None,
                           cover_letter_path: str = None):
        updates = []
        params = []
        if resume_path:
            updates.append("resume_path = ?")
            params.append(resume_path)
        if cover_letter_path:
            updates.append("cover_letter_path = ?")
            params.append(cover_letter_path)
        if updates:
            params.append(job_id)
            self._conn.execute(
                f"UPDATE matches SET {', '.join(updates)} WHERE job_id = ?", params
            )
            self._conn.commit()

    def update_match_suggestions(self, job_id: str, suggestions: str):
        self._conn.execute(
            "UPDATE matches SET suggestions = ? WHERE job_id = ?", (suggestions, job_id)
        )
        self._conn.commit()

    def get_match(self, job_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM matches WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def get_unnotified_matches(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT m.*, j.company, j.title, j.url, j.location, j.salary, j.description
            FROM matches m JOIN jobs j ON m.job_id = j.id
            WHERE m.notified_at IS NULL
            ORDER BY m.relevance_score DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def mark_notified(self, job_ids: list[str]):
        now = datetime.now(timezone.utc).isoformat()
        for job_id in job_ids:
            self._conn.execute(
                "UPDATE matches SET notified_at = ? WHERE job_id = ?", (now, job_id)
            )
        self._conn.commit()

    def start_run(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute("INSERT INTO runs (started_at) VALUES (?)", (now,))
        self._conn.commit()
        return cursor.lastrowid

    def complete_run(self, run_id: int, *, jobs_scraped: int, new_jobs: int,
                     matches_found: int, email_sent: bool, error: str = None):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            UPDATE runs SET completed_at = ?, jobs_scraped = ?, new_jobs = ?,
                           matches_found = ?, email_sent = ?, error = ?
            WHERE id = ?
        """, (now, jobs_scraped, new_jobs, matches_found, email_sent, error, run_id))
        self._conn.commit()

    def get_run(self, run_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def get_last_failed_run_with_matches(self) -> dict | None:
        row = self._conn.execute("""
            SELECT * FROM runs
            WHERE matches_found > 0 AND email_sent = 0
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_db.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer for jobs, matches, and runs"
```

---

### Task 3: Scraper Base + Greenhouse Scraper

**Files:**
- Create: `src/scrapers/base.py`, `src/scrapers/greenhouse.py`
- Create: `tests/fixtures/greenhouse_response.json`
- Test: `tests/test_scrapers.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/greenhouse_response.json` — a minimal Greenhouse API response:
```json
{
  "jobs": [
    {
      "id": 12345,
      "title": "Engineering Manager, Platform",
      "absolute_url": "https://jobs.dropbox.com/listing/12345",
      "location": {"name": "Remote - US"},
      "internal_job_id": 99999,
      "updated_at": "2026-03-29T10:00:00-04:00",
      "first_published": "2026-03-25T09:00:00-04:00",
      "company_name": "Dropbox",
      "content": "<h3>About the role</h3><p>Lead a team of 8 engineers...</p><p>Salary: $180,000-$240,000</p>",
      "departments": [{"id": 1, "name": "Engineering"}],
      "offices": [{"id": 1, "name": "Remote"}],
      "metadata": []
    },
    {
      "id": 12346,
      "title": "Software Engineer",
      "absolute_url": "https://jobs.dropbox.com/listing/12346",
      "location": {"name": "San Francisco, CA"},
      "internal_job_id": 99998,
      "updated_at": "2026-03-28T10:00:00-04:00",
      "first_published": "2026-03-20T09:00:00-04:00",
      "company_name": "Dropbox",
      "content": "<p>Write code</p>",
      "departments": [{"id": 1, "name": "Engineering"}],
      "offices": [{"id": 2, "name": "San Francisco"}],
      "metadata": []
    }
  ],
  "meta": {"total": 2}
}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_scrapers.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.scrapers.base import RawJob, BaseScraper
from src.scrapers.greenhouse import GreenhouseScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_raw_job_db_id():
    job = RawJob(
        external_id="12345", company="Dropbox", title="EM",
        url="https://example.com", location=None, remote=None,
        salary=None, description=None, department=None,
        seniority=None, scraped_at=datetime.now(timezone.utc),
    )
    assert job.db_id == "Dropbox:12345"


def test_greenhouse_parse_jobs():
    with open(FIXTURES / "greenhouse_response.json") as f:
        data = json.load(f)
    scraper = GreenhouseScraper(board_slug="dropbox", company_name="Dropbox")
    jobs = scraper._parse_response(data)
    assert len(jobs) == 2
    assert jobs[0].external_id == "12345"
    assert jobs[0].company == "Dropbox"
    assert jobs[0].title == "Engineering Manager, Platform"
    assert jobs[0].url == "https://jobs.dropbox.com/listing/12345"
    assert jobs[0].location == "Remote - US"
    assert jobs[0].department == "Engineering"
    assert "Lead a team" in jobs[0].description


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_fetch_jobs(mock_get):
    with open(FIXTURES / "greenhouse_response.json") as f:
        data = json.load(f)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = data
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    scraper = GreenhouseScraper(board_slug="dropbox", company_name="Dropbox")
    jobs = scraper.fetch_jobs()
    assert len(jobs) == 2
    mock_get.assert_called_once()
    assert "dropbox" in mock_get.call_args[0][0]


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_handles_failure(mock_get):
    mock_get.side_effect = Exception("Connection refused")
    scraper = GreenhouseScraper(board_slug="dropbox", company_name="Dropbox")
    jobs = scraper.fetch_jobs()
    assert jobs == []
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_scrapers.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement base.py**

Create `src/scrapers/base.py`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawJob:
    external_id: str
    company: str
    title: str
    url: str
    location: str | None
    remote: bool | None
    salary: str | None
    description: str | None
    department: str | None
    seniority: str | None
    scraped_at: datetime

    @property
    def db_id(self) -> str:
        return f"{self.company}:{self.external_id}"


class BaseScraper(ABC):
    company_name: str

    @abstractmethod
    def fetch_jobs(self) -> list[RawJob]:
        """Fetch all jobs from this company. Returns empty list on failure."""
        ...
```

- [ ] **Step 5: Implement greenhouse.py**

Create `src/scrapers/greenhouse.py`:
```python
import logging
import re
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards"

_http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


class GreenhouseScraper(BaseScraper):
    def __init__(self, board_slug: str, company_name: str):
        self.board_slug = board_slug
        self.company_name = company_name

    def fetch_jobs(self) -> list[RawJob]:
        url = f"{GREENHOUSE_API}/{self.board_slug}/jobs?content=true"
        try:
            resp = self._fetch_with_retry(url)
            return self._parse_response(resp.json())
        except Exception as e:
            logger.error(f"Failed to fetch {self.company_name} jobs: {e}")
            return []

    @_http_retry
    def _fetch_with_retry(self, url: str) -> httpx.Response:
        resp = httpx.get(url, timeout=30, headers={"User-Agent": "JobTracker/1.0"})
        resp.raise_for_status()
        return resp

    def _parse_response(self, data: dict) -> list[RawJob]:
        jobs = []
        now = datetime.now(timezone.utc)
        for item in data.get("jobs", []):
            salary = self._extract_salary(item.get("content", ""))
            seniority = self._extract_metadata(item, "IC or MG")
            jobs.append(RawJob(
                external_id=str(item["id"]),
                company=self.company_name,
                title=item["title"],
                url=item.get("absolute_url", ""),
                location=item.get("location", {}).get("name"),
                remote=self._is_remote(item),
                salary=salary,
                description=item.get("content"),
                department=(item.get("departments") or [{}])[0].get("name") if item.get("departments") else None,
                seniority=seniority,
                scraped_at=now,
            ))
        return jobs

    def _extract_salary(self, html_content: str) -> str | None:
        patterns = [
            r"\$[\d,]+\s*[-–]\s*\$[\d,]+",
            r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:to|[-–])\s*\$[\d,]+(?:\.\d{2})?)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(0)
        return None

    def _is_remote(self, item: dict) -> bool | None:
        location = item.get("location", {}).get("name", "")
        if location and "remote" in location.lower():
            return True
        return None

    def _extract_metadata(self, item: dict, field_name: str) -> str | None:
        for meta in item.get("metadata") or []:
            if meta.get("name") == field_name:
                return meta.get("value")
        return None
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_scrapers.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/scrapers/ tests/test_scrapers.py tests/fixtures/
git commit -m "feat: add Greenhouse scraper for Dropbox, DataDog, Stripe"
```

---

### Task 4: Workday Scraper (Capital One)

**Files:**
- Create: `src/scrapers/workday.py`
- Create: `tests/fixtures/workday_search_response.json`, `tests/fixtures/workday_detail_response.json`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Create test fixtures**

Create `tests/fixtures/workday_search_response.json`:
```json
{
  "total": 2,
  "jobPostings": [
    {
      "title": "Senior Manager, Software Engineering",
      "externalPath": "Senior-Manager-Software-Engineering-R239042",
      "locationsText": "McLean, VA",
      "postedOn": "Posted 3 Days Ago",
      "bulletFields": ["R239042"],
      "timeType": "Full time"
    },
    {
      "title": "Data Analyst",
      "externalPath": "Data-Analyst-R239043",
      "locationsText": "Richmond, VA",
      "postedOn": "Posted Today",
      "bulletFields": ["R239043"],
      "timeType": "Full time"
    }
  ]
}
```

Create `tests/fixtures/workday_detail_response.json`:
```json
{
  "jobPostingInfo": {
    "id": "R239042",
    "title": "Senior Manager, Software Engineering",
    "jobReqId": "R239042",
    "jobDescription": "<p>Lead multiple engineering teams...</p><p>Base salary: $180,000-$220,000</p>",
    "location": "McLean, VA",
    "additionalLocations": ["Richmond, VA", "Remote"],
    "timeType": "Full time",
    "postedOn": "2026-03-27",
    "externalUrl": "https://capitalone.wd12.myworkdayjobs.com/Capital_One/job/Senior-Manager-Software-Engineering-R239042"
  }
}
```

- [ ] **Step 2: Write failing tests**

Append to `tests/test_scrapers.py`:
```python
from src.scrapers.workday import WorkdayScraper


def test_workday_parse_search():
    with open(FIXTURES / "workday_search_response.json") as f:
        data = json.load(f)
    scraper = WorkdayScraper(
        company_name="Capital One",
        base_url="https://capitalone.wd12.myworkdayjobs.com",
        path="/wday/cxs/capitalone/Capital_One",
    )
    listings = scraper._parse_search_results(data)
    assert len(listings) == 2
    assert listings[0]["external_id"] == "R239042"
    assert listings[0]["title"] == "Senior Manager, Software Engineering"


def test_workday_parse_detail():
    with open(FIXTURES / "workday_detail_response.json") as f:
        data = json.load(f)
    scraper = WorkdayScraper(
        company_name="Capital One",
        base_url="https://capitalone.wd12.myworkdayjobs.com",
        path="/wday/cxs/capitalone/Capital_One",
    )
    job = scraper._parse_detail(data, "R239042")
    assert job.external_id == "R239042"
    assert job.company == "Capital One"
    assert "Lead multiple engineering teams" in job.description
    assert job.location == "McLean, VA"


@patch("src.scrapers.workday.httpx.Client")
def test_workday_handles_failure(mock_client_class):
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = Exception("Connection refused")
    mock_client_class.return_value = mock_client

    scraper = WorkdayScraper(
        company_name="Capital One",
        base_url="https://capitalone.wd12.myworkdayjobs.com",
        path="/wday/cxs/capitalone/Capital_One",
    )
    jobs = scraper.fetch_jobs()
    assert jobs == []
```

- [ ] **Step 3: Run tests to verify new tests fail**

```bash
uv run pytest tests/test_scrapers.py::test_workday_parse_search -v
```

Expected: FAIL

- [ ] **Step 4: Implement workday.py**

Create `src/scrapers/workday.py`:
```python
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

_http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


class WorkdayScraper(BaseScraper):
    def __init__(self, company_name: str, base_url: str, path: str):
        self.company_name = company_name
        self.base_url = base_url
        self.path = path
        self.page_size = 20
        self.request_delay = 1.5  # seconds between requests

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(
                timeout=30,
                headers={"User-Agent": "JobTracker/1.0", "Content-Type": "application/json"},
            ) as client:
                listings = self._fetch_all_listings(client)
                logger.info(f"Found {len(listings)} listings for {self.company_name}")
                jobs = []
                for i, listing in enumerate(listings):
                    if i > 0:
                        time.sleep(self.request_delay)
                    job = self._fetch_detail(client, listing)
                    if job:
                        jobs.append(job)
                return jobs
        except Exception as e:
            logger.error(f"Failed to fetch {self.company_name} jobs: {e}")
            return []

    def _fetch_all_listings(self, client: httpx.Client) -> list[dict]:
        all_listings = []
        offset = 0
        while True:
            url = f"{self.base_url}{self.path}/jobs"
            resp = client.post(url, json={
                "appliedFacets": {},
                "limit": self.page_size,
                "offset": offset,
                "searchText": "manager",  # Pre-filter to reduce volume (~1500 → ~200 results)
            })
            resp.raise_for_status()
            data = resp.json()
            listings = self._parse_search_results(data)
            all_listings.extend(listings)
            total = data.get("total", 0)
            offset += self.page_size
            if offset >= total:
                break
            time.sleep(self.request_delay)
        return all_listings

    def _parse_search_results(self, data: dict) -> list[dict]:
        results = []
        for posting in data.get("jobPostings", []):
            results.append({
                "external_id": (posting.get("bulletFields") or [""])[0],
                "title": posting.get("title", ""),
                "external_path": posting.get("externalPath", ""),
                "location": posting.get("locationsText"),
            })
        return results

    def _fetch_detail(self, client: httpx.Client, listing: dict) -> RawJob | None:
        path = listing.get("external_path", "")
        if not path:
            return None
        try:
            url = f"{self.base_url}{self.path}/job/{path}"
            resp = client.get(url)
            resp.raise_for_status()
            return self._parse_detail(resp.json(), listing["external_id"])
        except Exception as e:
            logger.warning(f"Failed to fetch detail for {listing['external_id']}: {e}")
            now = datetime.now(timezone.utc)
            return RawJob(
                external_id=listing["external_id"],
                company=self.company_name,
                title=listing["title"],
                url=f"{self.base_url}{self.path}/job/{path}",
                location=listing.get("location"),
                remote=None, salary=None, description=None,
                department=None, seniority=None, scraped_at=now,
            )

    def _parse_detail(self, data: dict, external_id: str) -> RawJob:
        info = data.get("jobPostingInfo", {})
        now = datetime.now(timezone.utc)
        description = info.get("jobDescription", "")
        salary = self._extract_salary(description)
        location = info.get("location", "")
        additional = info.get("additionalLocations", [])
        remote = any("remote" in (loc or "").lower() for loc in [location] + additional)

        return RawJob(
            external_id=external_id,
            company=self.company_name,
            title=info.get("title", ""),
            url=info.get("externalUrl", ""),
            location=location,
            remote=remote or None,
            salary=salary,
            description=description,
            department=None,
            seniority=None,
            scraped_at=now,
        )

    def _extract_salary(self, html_content: str) -> str | None:
        patterns = [
            r"\$[\d,]+\s*[-–]\s*\$[\d,]+",
            r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:to|[-–])\s*\$[\d,]+(?:\.\d{2})?)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(0)
        return None
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_scrapers.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/scrapers/workday.py tests/fixtures/workday_*.json tests/test_scrapers.py
git commit -m "feat: add Workday scraper for Capital One"
```

---

### Task 5: Scrape Step (Orchestrator)

**Files:**
- Create: `src/steps/scrape.py`, `src/steps/__init__.py`
- Test: `tests/test_steps_scrape.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_steps_scrape.py`:
```python
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.db import Database
from src.scrapers.base import RawJob
from src.steps.scrape import run_scrape


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _make_job(external_id="123", company="Dropbox", title="EM"):
    return RawJob(
        external_id=external_id, company=company, title=title,
        url="https://example.com", location="Remote", remote=True,
        salary="200k", description="Lead a team", department="Eng",
        seniority=None, scraped_at=datetime.now(timezone.utc),
    )


def test_scrape_stores_new_jobs(db):
    mock_scraper = MagicMock()
    mock_scraper.company_name = "Dropbox"
    mock_scraper.fetch_jobs.return_value = [_make_job("1"), _make_job("2")]

    result = run_scrape(db, scrapers=[mock_scraper])
    assert result["jobs_scraped"] == 2
    assert result["new_jobs"] == 2
    assert len(result["new_job_ids"]) == 2
    assert db.get_job("Dropbox:1") is not None


def test_scrape_deduplicates(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="Dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)

    mock_scraper = MagicMock()
    mock_scraper.company_name = "Dropbox"
    mock_scraper.fetch_jobs.return_value = [_make_job("1"), _make_job("2")]

    result = run_scrape(db, scrapers=[mock_scraper])
    assert result["jobs_scraped"] == 2
    assert result["new_jobs"] == 1


def test_scrape_handles_scraper_failure(db):
    good_scraper = MagicMock()
    good_scraper.company_name = "Dropbox"
    good_scraper.fetch_jobs.return_value = [_make_job("1")]

    bad_scraper = MagicMock()
    bad_scraper.company_name = "Stripe"
    bad_scraper.fetch_jobs.return_value = []  # Failed scrapers return []

    result = run_scrape(db, scrapers=[good_scraper, bad_scraper])
    assert result["jobs_scraped"] == 1
    assert "Stripe" in result["failed_companies"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_steps_scrape.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement scrape step**

Create `src/steps/__init__.py` (empty file).

Create `src/steps/scrape.py`:
```python
import logging

from src.db import Database
from src.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)


def run_scrape(db: Database, scrapers: list[BaseScraper]) -> dict:
    """Run all scrapers, store jobs in DB, return stats."""
    total_scraped = 0
    all_new_ids = []
    failed_companies = []

    for scraper in scrapers:
        company = scraper.company_name
        logger.info(f"Scraping {company}...")
        jobs = scraper.fetch_jobs()

        if not jobs:
            logger.warning(f"No jobs returned from {company}")
            failed_companies.append(company)
            continue

        # Check which jobs are new BEFORE upserting
        candidate_ids = [job.db_id for job in jobs]
        new_ids = db.get_new_job_ids(candidate_ids)

        # Upsert all jobs (updates last_seen_at for existing)
        for job in jobs:
            db.upsert_job(
                id=job.db_id, company=job.company, title=job.title, url=job.url,
                location=job.location, remote=job.remote, salary=job.salary,
                description=job.description, department=job.department,
                seniority=job.seniority, scraped_at=job.scraped_at,
            )

        # Close jobs that disappeared (only for successful scrapers)
        db.close_missing_jobs(company, current_ids=candidate_ids)

        all_new_ids.extend(new_ids)
        total_scraped += len(jobs)
        logger.info(f"{company}: {len(jobs)} total, {len(new_ids)} new")

    return {
        "jobs_scraped": total_scraped,
        "new_jobs": len(all_new_ids),
        "new_job_ids": all_new_ids,
        "failed_companies": failed_companies,
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_steps_scrape.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/steps/ tests/test_steps_scrape.py
git commit -m "feat: add scrape step with dedup and closure detection"
```

---

### Task 6: Filter Step (Keyword + LLM)

**Files:**
- Create: `src/steps/filter.py`
- Test: `tests/test_filter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_filter.py`:
```python
import json
from unittest.mock import patch, MagicMock

import pytest

from src.config import Config
from src.steps.filter import keyword_filter, llm_evaluate, run_filter


def test_keyword_filter_matches():
    config = Config()
    jobs = [
        {"id": "1", "title": "Engineering Manager, Platform", "description": "desc"},
        {"id": "2", "title": "Software Engineer", "description": "desc"},
        {"id": "3", "title": "Director of Engineering", "description": "desc"},
        {"id": "4", "title": "VP of Engineering", "description": "desc"},
    ]
    matches = keyword_filter(jobs, config)
    matched_ids = [j["id"] for j in matches]
    assert "1" in matched_ids
    assert "3" in matched_ids
    assert "2" not in matched_ids  # Not a manager role
    assert "4" not in matched_ids  # VP excluded


def test_keyword_filter_skips_no_description():
    config = Config()
    jobs = [
        {"id": "1", "title": "Engineering Manager", "description": None},
        {"id": "2", "title": "Engineering Manager", "description": "Lead a team"},
    ]
    matches = keyword_filter(jobs, config)
    assert len(matches) == 1
    assert matches[0]["id"] == "2"


@patch("src.steps.filter.anthropic")
def test_llm_evaluate_returns_structured_result(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    tool_result = {
        "relevant": True,
        "score": 0.85,
        "reason": "Strong EM match",
        "key_requirements": ["team leadership"],
        "interview_talking_points": ["scaling teams"],
    }
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.type = "tool_use"
    mock_content.input = tool_result
    mock_response.content = [mock_content]
    mock_response.stop_reason = "tool_use"
    mock_client.messages.create.return_value = mock_response

    config = Config()
    config.anthropic_api_key = "test-key"
    result = llm_evaluate(
        job={"title": "EM", "company": "Dropbox", "description": "Lead team", "location": "Remote", "salary": "200k"},
        resume_summary="Experienced EM with 10 years...",
        config=config,
    )
    assert result["relevant"] is True
    assert result["score"] == 0.85
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_filter.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement filter step**

Create `src/steps/filter.py`:
```python
import json
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import Config
from src.db import Database

logger = logging.getLogger(__name__)

_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError)),
    reraise=True,
)

EVAL_TOOL = {
    "name": "evaluate_job",
    "description": "Evaluate a job listing for relevance to the candidate",
    "input_schema": {
        "type": "object",
        "properties": {
            "relevant": {"type": "boolean", "description": "Whether this job is relevant"},
            "score": {"type": "number", "description": "Relevance score 0.0-1.0"},
            "reason": {"type": "string", "description": "Why this job matches or doesn't"},
            "key_requirements": {
                "type": "array", "items": {"type": "string"},
                "description": "Top requirements from the job description",
            },
            "interview_talking_points": {
                "type": "array", "items": {"type": "string"},
                "description": "What the candidate should emphasize in interviews",
            },
        },
        "required": ["relevant", "score", "reason", "key_requirements", "interview_talking_points"],
    },
}


def keyword_filter(jobs: list[dict], config: Config) -> list[dict]:
    """Pre-filter jobs by title keywords. Skips jobs without descriptions."""
    matches = []
    for job in jobs:
        if not job.get("description"):
            logger.debug(f"Skipping {job['id']}: no description")
            continue
        if config.matches_keyword(job["title"]):
            matches.append(job)
    logger.info(f"Keyword filter: {len(jobs)} → {len(matches)}")
    return matches


@_llm_retry
def llm_evaluate(job: dict, resume_summary: str, config: Config) -> dict:
    """Evaluate a single job with Claude. Returns evaluation dict."""
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    response = client.messages.create(
        model=config.llm_model,
        max_tokens=1024,
        tools=[EVAL_TOOL],
        tool_choice={"type": "tool", "name": "evaluate_job"},
        messages=[{
            "role": "user",
            "content": f"""Evaluate this job listing for relevance to the candidate.

CANDIDATE PROFILE:
{resume_summary}

JOB LISTING:
Title: {job['title']}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', 'Unknown')}
Salary: {job.get('salary', 'Not listed')}

Description:
{job.get('description', 'No description available')}""",
        }],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    logger.warning(f"No tool_use in LLM response for {job.get('title')}")
    return {"relevant": False, "score": 0.0, "reason": "Failed to evaluate",
            "key_requirements": [], "interview_talking_points": []}


def run_filter(db: Database, new_job_ids: list[str], resume_summary: str,
               config: Config) -> list[dict]:
    """Run keyword + LLM filter on new jobs. Returns list of match dicts."""
    # Fetch new jobs from DB
    jobs = []
    for job_id in new_job_ids:
        job = db.get_job(job_id)
        if job:
            jobs.append(job)

    # Step 1: keyword filter
    candidates = keyword_filter(jobs, config)
    if not candidates:
        logger.info("No jobs passed keyword filter")
        return []

    # Step 2: LLM evaluation
    matches = []
    for job in candidates:
        try:
            result = llm_evaluate(job, resume_summary, config)
            if result.get("relevant") and result.get("score", 0) >= config.relevance_threshold:
                db.insert_match(
                    job_id=job["id"],
                    relevance_score=result["score"],
                    match_reason=result["reason"],
                    suggestions=json.dumps({
                        "key_requirements": result.get("key_requirements", []),
                        "interview_talking_points": result.get("interview_talking_points", []),
                    }),
                )
                matches.append({"job": job, "evaluation": result})
                logger.info(f"Match: {job['title']} @ {job['company']} (score: {result['score']})")
            else:
                logger.debug(f"Rejected: {job['title']} (score: {result.get('score', 0)})")
        except Exception as e:
            logger.error(f"LLM evaluation failed for {job['id']}: {e}")

    logger.info(f"LLM filter: {len(candidates)} → {len(matches)}")
    return matches
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_filter.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/steps/filter.py tests/test_filter.py
git commit -m "feat: add keyword + LLM filter pipeline step"
```

---

### Task 7: Tailor Step (Resume + Cover Letter)

**Files:**
- Create: `src/steps/tailor.py`
- Test: `tests/test_tailor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tailor.py`:
```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.config import Config
from src.steps.tailor import reorder_resume_yaml, run_tailor_for_job


def test_reorder_resume_yaml():
    """Test that bullets are reordered in the YAML data structure."""
    resume_data = {
        "experience": [
            {
                "company": "Acme Corp",
                "title": "Engineering Manager",
                "bullets": ["bullet_a", "bullet_b", "bullet_c"],
            }
        ]
    }
    reorder_map = {
        "Acme Corp - Engineering Manager": ["bullet_c", "bullet_a", "bullet_b"]
    }
    result = reorder_resume_yaml(resume_data, reorder_map)
    assert result["experience"][0]["bullets"] == ["bullet_c", "bullet_a", "bullet_b"]


def test_reorder_resume_yaml_missing_key():
    """Unknown keys in the reorder map are ignored."""
    resume_data = {
        "experience": [
            {
                "company": "Acme Corp",
                "title": "EM",
                "bullets": ["a", "b"],
            }
        ]
    }
    reorder_map = {"Nonexistent - Role": ["x", "y"]}
    result = reorder_resume_yaml(resume_data, reorder_map)
    assert result["experience"][0]["bullets"] == ["a", "b"]


@patch("src.steps.tailor.anthropic")
def test_llm_analysis_returns_structured_output(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    analysis = {
        "reordered_bullets": {"Acme - EM": ["c", "a", "b"]},
        "suggested_edits": [{"original": "a", "suggested": "a+", "reason": "kw"}],
        "keyword_gaps": ["agile"],
    }
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.type = "tool_use"
    mock_content.input = analysis
    mock_response.content = [mock_content]
    mock_client.messages.create.return_value = mock_response

    from src.steps.tailor import llm_resume_analysis
    config = Config()
    config.anthropic_api_key = "test-key"
    result = llm_resume_analysis("yaml content", "job description", config)
    assert "reordered_bullets" in result
    assert "suggested_edits" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tailor.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement tailor step**

Create `src/steps/tailor.py`:
```python
import copy
import json
import logging
import subprocess
from pathlib import Path

import anthropic
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import Config
from src.db import Database

logger = logging.getLogger(__name__)

_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError)),
    reraise=True,
)

ANALYSIS_TOOL = {
    "name": "resume_analysis",
    "description": "Analyze resume against job description and suggest improvements",
    "input_schema": {
        "type": "object",
        "properties": {
            "reordered_bullets": {
                "type": "object",
                "description": "Map of 'Company - Title' to reordered bullet list",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
            },
            "suggested_edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original": {"type": "string"},
                        "suggested": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["original", "suggested", "reason"],
                },
            },
            "keyword_gaps": {
                "type": "array", "items": {"type": "string"},
                "description": "Keywords in the JD missing from the resume",
            },
        },
        "required": ["reordered_bullets", "suggested_edits", "keyword_gaps"],
    },
}


def get_active_resume_yaml(config: Config) -> tuple[Path, dict]:
    """Resolve and load the active resume YAML. Returns (path, data)."""
    project_json = config.resume_versions_path / "projects" / config.resume_project / "project.json"
    with open(project_json) as f:
        project = json.load(f)
    active_version = project["active_version"]

    # Find the version directory (may have a tag suffix)
    versions_dir = config.resume_versions_path / "projects" / config.resume_project / "versions"
    candidates = list(versions_dir.glob(f"{active_version}*"))
    if not candidates:
        raise FileNotFoundError(f"No version directory found for {active_version}")
    version_dir = candidates[0]
    yaml_path = version_dir / "resume.yaml"

    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return yaml_path, data


def reorder_resume_yaml(resume_data: dict, reorder_map: dict) -> dict:
    """Return a copy of resume_data with bullets reordered per reorder_map."""
    result = copy.deepcopy(resume_data)
    for exp in result.get("experience", []):
        key = f"{exp.get('company', '')} - {exp.get('title', '')}"
        if key in reorder_map:
            new_order = reorder_map[key]
            existing = exp.get("bullets", [])
            # Only include bullets that exist in the original
            reordered = [b for b in new_order if b in existing]
            # Append any bullets not in the reorder map
            remaining = [b for b in existing if b not in reordered]
            exp["bullets"] = reordered + remaining
    return result


@_llm_retry
def llm_resume_analysis(resume_yaml_str: str, job_description: str, config: Config) -> dict:
    """Ask Claude to analyze resume vs job description."""
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    response = client.messages.create(
        model=config.llm_model,
        max_tokens=4096,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "resume_analysis"},
        messages=[{
            "role": "user",
            "content": f"""Analyze this resume against the job description. Reorder bullets to prioritize
relevance to the JD, suggest wording improvements for better keyword alignment,
and identify keyword gaps.

RESUME (YAML):
{resume_yaml_str}

JOB DESCRIPTION:
{job_description}""",
        }],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {"reordered_bullets": {}, "suggested_edits": [], "keyword_gaps": []}


def generate_resume_pdf(resume_data: dict, output_dir: Path, config: Config) -> Path | None:
    """Generate a tailored resume PDF using the formatter scripts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = output_dir / "resume.yaml"
    typ_path = output_dir / "resume.typ"
    pdf_path = output_dir / "resume.pdf"

    with open(yaml_path, "w") as f:
        yaml.dump(resume_data, f, default_flow_style=False, allow_unicode=True)

    try:
        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_formatter_dir),
             "scripts/yaml_to_typst.py", str(yaml_path), config.resume_template,
             "--output", str(typ_path)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_formatter_dir),
             "scripts/compile_typst.py", str(typ_path), "--output", str(pdf_path)],
            check=True, capture_output=True, text=True,
        )
        return pdf_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Resume PDF generation failed: {e.stderr}")
        return None


def generate_cover_letter_pdf(resume_yaml_path: Path, job_description: str,
                               company: str, position: str,
                               output_dir: Path, config: Config) -> Path | None:
    """Generate a cover letter PDF using the coverletter scripts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jd_path = output_dir / "job_description.txt"
    typ_path = output_dir / "cover_letter.typ"
    pdf_path = output_dir / "cover_letter.pdf"

    jd_path.write_text(job_description)

    try:
        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_coverletter_dir),
             "scripts/generate_cover_letter.py", str(resume_yaml_path),
             "--template", config.cover_letter_template,
             "--company", company,
             "--position", position,
             "--job-file", str(jd_path),
             "--output", str(typ_path)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_coverletter_dir),
             "scripts/compile_cover_letter.py", str(typ_path),
             "--output", str(pdf_path)],
            check=True, capture_output=True, text=True,
        )
        return pdf_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Cover letter generation failed: {e.stderr}")
        return None


def run_tailor_for_job(job: dict, evaluation: dict, resume_yaml_path: Path,
                       resume_data: dict, output_dir: Path,
                       config: Config, db: Database) -> dict:
    """Tailor resume + generate cover letter for a single job match."""
    job_dir = output_dir / f"{job['company']}_{job['id'].replace(':', '_')}"

    # LLM analysis
    resume_yaml_str = yaml.dump(resume_data, default_flow_style=False)
    analysis = llm_resume_analysis(resume_yaml_str, job.get("description", ""), config)

    # Reorder bullets and generate PDF
    tailored = reorder_resume_yaml(resume_data, analysis.get("reordered_bullets", {}))
    resume_pdf = generate_resume_pdf(tailored, job_dir, config)

    # Generate cover letter
    cover_letter_pdf = generate_cover_letter_pdf(
        resume_yaml_path, job.get("description", ""),
        job["company"], job["title"], job_dir, config,
    )

    # Update DB with paths and full suggestions
    suggestions = json.dumps({
        "suggested_edits": analysis.get("suggested_edits", []),
        "keyword_gaps": analysis.get("keyword_gaps", []),
        "key_requirements": evaluation.get("key_requirements", []),
        "interview_talking_points": evaluation.get("interview_talking_points", []),
    })
    db.update_match_paths(
        job["id"],
        resume_path=str(resume_pdf) if resume_pdf else None,
        cover_letter_path=str(cover_letter_pdf) if cover_letter_pdf else None,
    )
    db.update_match_suggestions(job["id"], suggestions)

    return {
        "job_id": job["id"],
        "resume_pdf": resume_pdf,
        "cover_letter_pdf": cover_letter_pdf,
        "analysis": analysis,
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_tailor.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/steps/tailor.py tests/test_tailor.py
git commit -m "feat: add resume tailoring and cover letter generation step"
```

---

### Task 8: Notify Step (Email Digest)

**Files:**
- Create: `src/steps/notify.py`, `templates/digest.html`
- Test: `tests/test_notify.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_notify.py`:
```python
import json
from unittest.mock import patch, MagicMock

import pytest

from src.config import Config
from src.steps.notify import build_digest_html, build_no_match_html


def test_build_no_match_html():
    html = build_no_match_html(
        run_stats={"jobs_scraped": 100, "new_jobs": 5, "matches_found": 0, "duration": "45s"},
        config=Config(),
    )
    assert "No new matches" in html
    assert "100" in html  # jobs scraped


def test_build_digest_html():
    matches = [
        {
            "job_id": "Dropbox:123",
            "company": "Dropbox",
            "title": "Engineering Manager",
            "url": "https://example.com",
            "location": "Remote",
            "salary": "$200k",
            "relevance_score": 0.9,
            "match_reason": "Strong EM fit",
            "suggestions": json.dumps({
                "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
                "keyword_gaps": ["agile"],
                "key_requirements": ["team leadership"],
                "interview_talking_points": ["scaling teams"],
            }),
            "resume_path": "/tmp/resume.pdf",
            "cover_letter_path": "/tmp/cover.pdf",
        }
    ]
    run_stats = {"jobs_scraped": 100, "new_jobs": 5, "matches_found": 1, "duration": "45s"}
    html = build_digest_html(matches, run_stats, Config())
    assert "Engineering Manager" in html
    assert "Dropbox" in html
    assert "Strong EM fit" in html
    assert "team leadership" in html


@patch("src.steps.notify.smtplib.SMTP_SSL")
def test_send_email(mock_smtp_class):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    from src.steps.notify import send_email
    config = Config()
    config.smtp_user = "test@gmail.com"
    config.smtp_password = "testpass"

    send_email(
        subject="Test",
        html_body="<p>Hello</p>",
        attachments=[],
        config=config,
    )
    mock_smtp.send_message.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_notify.py -v
```

Expected: FAIL

- [ ] **Step 3: Create Jinja2 email template**

Create `templates/digest.html`:
```html
<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #333; max-width: 700px; margin: 0 auto; padding: 20px; }
  h1 { color: #1a1a2e; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }
  h2 { color: #16213e; margin-top: 30px; }
  .summary-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
  .summary-table th, .summary-table td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
  .summary-table th { background: #f5f5f5; }
  .score { font-weight: bold; }
  .score-high { color: #2e7d32; }
  .score-med { color: #f57f17; }
  .job-section { border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin: 20px 0; }
  .job-header { margin: 0 0 10px 0; }
  .meta { color: #666; font-size: 0.9em; }
  .section-label { font-weight: bold; color: #16213e; margin-top: 15px; }
  .edit-item { background: #f9f9f9; padding: 10px; border-radius: 4px; margin: 8px 0; }
  .edit-original { color: #c62828; text-decoration: line-through; }
  .edit-suggested { color: #2e7d32; }
  .edit-reason { color: #666; font-size: 0.85em; font-style: italic; }
  .keyword-gap { display: inline-block; background: #fff3e0; padding: 2px 8px; border-radius: 4px; margin: 2px; font-size: 0.85em; }
  .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #e0e0e0; color: #999; font-size: 0.85em; }
  a { color: #1565c0; }
</style>
</head>
<body>

<h1>Job Tracker Digest &mdash; {{ date }}</h1>

{% if matches %}
<p><strong>{{ matches|length }}</strong> new match{{ 'es' if matches|length > 1 else '' }} found.</p>

<table class="summary-table">
<tr><th>Company</th><th>Title</th><th>Location</th><th>Salary</th><th>Score</th></tr>
{% for m in matches %}
<tr>
  <td>{{ m.company }}</td>
  <td><a href="{{ m.url }}">{{ m.title }}</a></td>
  <td>{{ m.location or 'N/A' }}</td>
  <td>{{ m.salary or 'N/A' }}</td>
  <td class="score {{ 'score-high' if m.relevance_score >= 0.8 else 'score-med' }}">{{ '%.0f'|format(m.relevance_score * 100) }}%</td>
</tr>
{% endfor %}
</table>

{% for m in matches %}
<div class="job-section">
  <h2 class="job-header">{{ m.company }} &mdash; {{ m.title }}</h2>
  <p class="meta">
    Score: {{ '%.0f'|format(m.relevance_score * 100) }}% |
    Location: {{ m.location or 'N/A' }} |
    Salary: {{ m.salary or 'N/A' }}<br>
    <a href="{{ m.url }}">View Listing</a>
  </p>

  <p class="section-label">Why this matches:</p>
  <p>{{ m.match_reason }}</p>

  {% if m.suggestions_parsed.key_requirements %}
  <p class="section-label">Key requirements:</p>
  <ul>
  {% for req in m.suggestions_parsed.key_requirements %}
    <li>{{ req }}</li>
  {% endfor %}
  </ul>
  {% endif %}

  {% if m.suggestions_parsed.interview_talking_points %}
  <p class="section-label">Interview talking points:</p>
  <ul>
  {% for tp in m.suggestions_parsed.interview_talking_points %}
    <li>{{ tp }}</li>
  {% endfor %}
  </ul>
  {% endif %}

  {% if m.suggestions_parsed.suggested_edits %}
  <p class="section-label">Suggested resume edits:</p>
  {% for edit in m.suggestions_parsed.suggested_edits %}
  <div class="edit-item">
    <span class="edit-original">{{ edit.original }}</span><br>
    <span class="edit-suggested">{{ edit.suggested }}</span><br>
    <span class="edit-reason">{{ edit.reason }}</span>
  </div>
  {% endfor %}
  {% endif %}

  {% if m.suggestions_parsed.keyword_gaps %}
  <p class="section-label">Keyword gaps:</p>
  <p>{% for kw in m.suggestions_parsed.keyword_gaps %}<span class="keyword-gap">{{ kw }}</span>{% endfor %}</p>
  {% endif %}

  {% if m.resume_path or m.cover_letter_path %}
  <p class="section-label">Attachments:</p>
  <p>
    {% if m.resume_path %}Resume PDF attached{% endif %}
    {% if m.resume_path and m.cover_letter_path %} | {% endif %}
    {% if m.cover_letter_path %}Cover letter PDF attached{% endif %}
  </p>
  {% endif %}
</div>
{% endfor %}

{% else %}
<p>No new matches found this run.</p>
{% endif %}

<div class="footer">
  <p>
    Jobs scraped: {{ run_stats.jobs_scraped }} |
    New jobs: {{ run_stats.new_jobs }} |
    Matches: {{ run_stats.matches_found }} |
    Duration: {{ run_stats.duration }}
  </p>
</div>

</body>
</html>
```

- [ ] **Step 4: Implement notify step**

Create `src/steps/notify.py`:
```python
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


def build_digest_html(matches: list[dict], run_stats: dict, config: Config) -> str:
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
    )


def build_no_match_html(run_stats: dict, config: Config) -> str:
    template = _load_template(config)
    return template.render(
        matches=[],
        run_stats=run_stats,
        date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
    )


def send_email(subject: str, html_body: str, attachments: list[tuple[str, Path]],
               config: Config):
    """Send HTML email with PDF attachments via Gmail SMTP."""
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
    """Build and send the email digest. Returns True if email sent successfully."""
    matches = db.get_unnotified_matches()

    if matches:
        subject = f"Job Tracker: {len(matches)} new match{'es' if len(matches) > 1 else ''} found — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        html = build_digest_html(matches, run_stats, config)

        # Collect attachments
        attachments = []
        for m in matches:
            company = m.get("company", "unknown").replace(" ", "_")
            title = m.get("title", "role").replace(" ", "_").replace(",", "")[:30]
            if m.get("resume_path"):
                attachments.append((f"{company}_{title}_resume.pdf", Path(m["resume_path"])))
            if m.get("cover_letter_path"):
                attachments.append((f"{company}_{title}_cover_letter.pdf", Path(m["cover_letter_path"])))
    else:
        subject = f"Job Tracker: No new matches — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        html = build_no_match_html(run_stats, config)
        attachments = []

    try:
        send_email(subject, html, attachments, config)
        if matches:
            db.mark_notified([m["job_id"] for m in matches])
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_notify.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/steps/notify.py templates/digest.html tests/test_notify.py
git commit -m "feat: add email digest notification step with HTML template"
```

---

### Task 9: Pipeline Orchestrator + CLI

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_pipeline.py`:
```python
from unittest.mock import patch, MagicMock
import pytest

from src.pipeline import parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.dry_run is False
    assert args.renotify is False
    assert args.step is None


def test_parse_args_dry_run():
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parse_args_step():
    args = parse_args(["--step", "scrape"])
    assert args.step == "scrape"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement pipeline**

Create `src/pipeline.py`:
```python
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.config import Config
from src.db import Database
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.workday import WorkdayScraper
from src.steps.scrape import run_scrape
from src.steps.filter import run_filter
from src.steps.tailor import get_active_resume_yaml, run_tailor_for_job
from src.steps.notify import run_notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Job Tracker Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run scrape + filter only, skip tailor + notify")
    parser.add_argument("--renotify", action="store_true",
                        help="Re-send last failed email digest")
    parser.add_argument("--step", choices=["scrape", "filter", "tailor", "notify"],
                        help="Run a single step")
    return parser.parse_args(argv)


def build_scrapers(config: Config) -> list:
    scrapers = []
    for slug, name in config.greenhouse_boards.items():
        scrapers.append(GreenhouseScraper(board_slug=slug, company_name=name))
    for key, info in config.workday_companies.items():
        scrapers.append(WorkdayScraper(
            company_name=info["display_name"],
            base_url=info["base_url"],
            path=info["path"],
        ))
    return scrapers


def get_resume_summary(resume_data: dict) -> str:
    """Extract a brief candidate summary from resume YAML for LLM context."""
    parts = []
    if summary := resume_data.get("summary"):
        parts.append(summary)
    if skills := resume_data.get("skills"):
        if isinstance(skills, list):
            parts.append("Skills: " + ", ".join(str(s) for s in skills[:15]))
        elif isinstance(skills, dict):
            for cat, items in skills.items():
                if isinstance(items, list):
                    parts.append(f"{cat}: {', '.join(str(i) for i in items[:10])}")
    if experience := resume_data.get("experience"):
        for exp in experience[:3]:
            parts.append(f"{exp.get('title', '')} at {exp.get('company', '')}")
    return "\n".join(parts)


def run_pipeline(args):
    start_time = time.time()
    config = Config()
    db = Database(config.db_path)

    if args.renotify:
        logger.info("Re-notify mode: resending last failed digest")
        run_stats = {"jobs_scraped": 0, "new_jobs": 0, "matches_found": 0,
                     "duration": "renotify"}
        success = run_notify(db, run_stats, config)
        logger.info(f"Renotify {'succeeded' if success else 'failed'}")
        return

    run_id = db.start_run()

    try:
        # Load resume
        resume_yaml_path, resume_data = get_active_resume_yaml(config)
        resume_summary = get_resume_summary(resume_data)

        # Step 1: Scrape
        if not args.step or args.step == "scrape":
            scrapers = build_scrapers(config)
            scrape_result = run_scrape(db, scrapers)
            logger.info(f"Scrape complete: {scrape_result['jobs_scraped']} jobs, {scrape_result['new_jobs']} new")
            if args.step == "scrape":
                db.complete_run(run_id, jobs_scraped=scrape_result["jobs_scraped"],
                               new_jobs=scrape_result["new_jobs"], matches_found=0, email_sent=False)
                return
        else:
            scrape_result = {"jobs_scraped": 0, "new_jobs": 0, "new_job_ids": [], "failed_companies": []}

        # Step 2: Filter
        if not args.step or args.step == "filter":
            # When running filter standalone, find unfiltered jobs from DB
            new_job_ids = scrape_result["new_job_ids"]
            if args.step == "filter" and not new_job_ids:
                # Get jobs that have no match record yet (unfiltered)
                rows = db._conn.execute(
                    "SELECT id FROM jobs WHERE id NOT IN (SELECT job_id FROM matches) AND closed_at IS NULL"
                ).fetchall()
                new_job_ids = [r["id"] for r in rows]
                logger.info(f"Filter standalone: found {len(new_job_ids)} unfiltered jobs in DB")
            matches = run_filter(db, new_job_ids, resume_summary, config)
            logger.info(f"Filter complete: {len(matches)} matches")
            if args.step == "filter":
                db.complete_run(run_id, jobs_scraped=0, new_jobs=0,
                               matches_found=len(matches), email_sent=False)
                return
        else:
            matches = []

        if args.dry_run:
            logger.info("Dry run — skipping tailor and notify")
            duration = f"{time.time() - start_time:.1f}s"
            db.complete_run(run_id, jobs_scraped=scrape_result["jobs_scraped"],
                           new_jobs=scrape_result["new_jobs"],
                           matches_found=len(matches), email_sent=False)
            return

        # Step 3: Tailor
        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        output_dir = config.output_dir / run_date
        if not args.step or args.step == "tailor":
            # When running tailor standalone, get matches without PDFs
            if args.step == "tailor" and not matches:
                unnotified = db.get_unnotified_matches()
                matches = [{"job": dict(m), "evaluation": json.loads(m.get("suggestions") or "{}")}
                           for m in unnotified if not m.get("resume_path")]
                logger.info(f"Tailor standalone: found {len(matches)} untailored matches")
            for match in matches:
            try:
                run_tailor_for_job(
                    job=match["job"], evaluation=match["evaluation"],
                    resume_yaml_path=resume_yaml_path, resume_data=resume_data,
                    output_dir=output_dir, config=config, db=db,
                )
            except Exception as e:
                logger.error(f"Tailor failed for {match['job']['id']}: {e}")
            if args.step == "tailor":
                db.complete_run(run_id, jobs_scraped=0, new_jobs=0,
                               matches_found=len(matches), email_sent=False)
                return

        # Step 4: Notify
        duration = f"{time.time() - start_time:.1f}s"
        run_stats = {
            "jobs_scraped": scrape_result["jobs_scraped"],
            "new_jobs": scrape_result["new_jobs"],
            "matches_found": len(matches),
            "duration": duration,
        }
        email_sent = run_notify(db, run_stats, config)

        db.complete_run(run_id, jobs_scraped=scrape_result["jobs_scraped"],
                       new_jobs=scrape_result["new_jobs"],
                       matches_found=len(matches), email_sent=email_sent)
        logger.info(f"Pipeline complete in {duration}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        db.complete_run(run_id, jobs_scraped=0, new_jobs=0,
                       matches_found=0, email_sent=False, error=str(e))
        raise


def main():
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add pipeline orchestrator with CLI flags"
```

---

### Task 10: Scheduling (launchd + run.sh)

**Files:**
- Create: `run.sh`, `launchd/com.drewmerc.jobtracker.plist`

- [ ] **Step 1: Create run.sh**

Create `run.sh`:
```bash
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd /Users/drewmerc/workspace/jobTracker

# Truncate logs to ~1MB
for logfile in data/logs/stdout.log data/logs/stderr.log; do
    if [ -f "$logfile" ] && [ "$(stat -f%z "$logfile" 2>/dev/null || echo 0)" -gt 1048576 ]; then
        tail -c 1048576 "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
    fi
done

mkdir -p data/logs
uv run jobtracker 2>&1
```

- [ ] **Step 2: Make executable**

```bash
chmod +x run.sh
```

- [ ] **Step 3: Create launchd plist**

Create `launchd/com.drewmerc.jobtracker.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.drewmerc.jobtracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/drewmerc/workspace/jobTracker/run.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>43200</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/drewmerc/workspace/jobTracker/data/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/drewmerc/workspace/jobTracker/data/logs/stderr.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/drewmerc/workspace/jobTracker</string>
</dict>
</plist>
```

- [ ] **Step 4: Commit**

```bash
git add run.sh launchd/
git commit -m "feat: add launchd scheduling with run.sh wrapper"
```

- [ ] **Step 5: Install launchd plist (manual step)**

Run these commands manually when ready to activate:
```bash
cp launchd/com.drewmerc.jobtracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.drewmerc.jobtracker.plist
```

---

### Task 11: End-to-End Smoke Test

- [ ] **Step 1: Set up .env with real credentials**

Fill in `.env` with your real Anthropic API key and Gmail app password.

- [ ] **Step 2: Dry-run test**

```bash
uv run jobtracker --dry-run
```

Expected: Scrapes all 4 sites, runs keyword + LLM filter, prints match count, does NOT generate PDFs or send email. Check `data/jobtracker.db` has populated `jobs` and `runs` tables.

- [ ] **Step 3: Verify DB state**

```bash
uv run python -c "
from src.db import Database
from src.config import Config
db = Database(Config().db_path)
jobs = db._conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
runs = db._conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
matches = db._conn.execute('SELECT COUNT(*) FROM matches').fetchone()[0]
print(f'Jobs: {jobs}, Runs: {runs}, Matches: {matches}')
"
```

- [ ] **Step 4: Full pipeline test**

```bash
uv run jobtracker
```

Expected: Full pipeline runs, generates PDFs in `output/`, sends email to `andrew.m.mercurio@gmail.com`.

- [ ] **Step 5: Verify email received**

Check inbox for the digest email with summary table, per-job analysis, and PDF attachments.

- [ ] **Step 6: Run all unit tests**

```bash
uv run pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "chore: finalize jobtracker with smoke test verification"
```
