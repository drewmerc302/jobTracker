# Interview Prep, Deduplication, and Follow-up Tracking Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three features to jobTracker: auto-generated interview prep notes when a job moves to `interviewing`, cross-board job deduplication after each scrape, and follow-up date tracking with CLI and email digest surfacing.

**Architecture:** Three independent capabilities implemented as new steps (`dedup.py`, `interview_prep.py`) plus DB migrations and pipeline wiring. All features slot into the existing pipeline/DB/step pattern — no new external services, no breaking changes to existing commands.

**Tech Stack:** Python, SQLite (sqlite3), anthropic SDK (Claude Sonnet, tool_use), Jinja2, existing `_write_note` subprocess for Obsidian.

**Spec:** `docs/superpowers/specs/2026-03-31-interview-prep-dedup-followup-design.md`

---

## File Map

| File | Change |
|------|--------|
| `src/db.py` | Add migration for `follow_up_after`/`followed_up_at` columns; add `get_overdue_follow_ups`, `set_follow_up_date`, `mark_followed_up` methods |
| `src/steps/dedup.py` | New — `_normalize_title`, `_score_job`, `run_dedup` |
| `src/steps/interview_prep.py` | New — `generate_interview_prep` with tool-use LLM call + Obsidian section patch |
| `src/steps/notify.py` | Pass `follow_ups` to template; update `build_digest_html` and `build_no_match_html` |
| `src/pipeline.py` | Add `dedup` to `--step` choices; add `--interview-prep`, `--research`, `--follow-ups`, `--followed-up`, `--set-followup` args; trigger `generate_interview_prep` on `interviewing` transition; auto-set `follow_up_after` on `applied`/`interviewing` transitions |
| `templates/digest.html` | Add "Follow Up Today" section above matches |
| `tests/test_dedup.py` | New — dedup unit tests |
| `tests/test_follow_up.py` | New — follow-up DB and CLI tests |
| `tests/test_interview_prep.py` | New — interview prep unit tests |
| `tests/test_db.py` | Extend — test new DB methods |

---

## Task 1: DB — Follow-up Column Migration

**Files:**
- Modify: `src/db.py`
- Test: `tests/test_db.py`

Add `follow_up_after` (TEXT nullable, ISO date) and `followed_up_at` (TEXT nullable, ISO timestamp) columns to the `applications` table via a safe `ALTER TABLE` migration run on startup.

- [ ] **Step 1.1: Write failing tests for migration and new DB methods**

Add to `tests/test_db.py`:

```python
def test_follow_up_columns_exist(db):
    cols = {
        row[1]
        for row in db._conn.execute("PRAGMA table_info(applications)").fetchall()
    }
    assert "follow_up_after" in cols
    assert "followed_up_at" in cols


def test_get_overdue_follow_ups_empty(db):
    assert db.get_overdue_follow_ups() == []


def test_get_overdue_follow_ups_returns_overdue(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:1", "applied")
    db.set_follow_up_date("stripe:1", "2000-01-01")  # far in the past

    overdue = db.get_overdue_follow_ups()
    assert len(overdue) == 1
    assert overdue[0]["job_id"] == "stripe:1"


def test_get_overdue_follow_ups_excludes_terminal_statuses(db):
    now = datetime.now(timezone.utc)
    for jid, status in [("stripe:2", "rejected"), ("stripe:3", "withdrawn"), ("stripe:4", "offer")]:
        db.upsert_job(id=jid, company="Stripe", title="EM", url="https://x.com", scraped_at=now)
        db.insert_match(job_id=jid, relevance_score=0.9, match_reason="good")
        db.set_application_status(jid, status)
        db.set_follow_up_date(jid, "2000-01-01")

    assert db.get_overdue_follow_ups() == []


def test_mark_followed_up_resets_date(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:5", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.insert_match(job_id="stripe:5", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:5", "applied")
    db.set_follow_up_date("stripe:5", "2000-01-01")

    db.mark_followed_up("stripe:5", reset_days=7)
    app = db.get_application("stripe:5")
    assert app["followed_up_at"] is not None
    assert app["follow_up_after"] > "2000-01-01"  # reset to future


def test_mark_followed_up_no_reset_when_no_date(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:6", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.insert_match(job_id="stripe:6", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:6", "applied")
    # do NOT set follow_up_after

    db.mark_followed_up("stripe:6", reset_days=7)
    app = db.get_application("stripe:6")
    assert app["followed_up_at"] is not None
    assert app["follow_up_after"] is None  # was null, stays null
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```bash
cd /Users/drewmerc/workspace/jobTracker
uv run pytest tests/test_db.py::test_follow_up_columns_exist tests/test_db.py::test_get_overdue_follow_ups_empty -v
```

Expected: FAIL — `Database` has no `get_overdue_follow_ups` method.

- [ ] **Step 1.3: Implement migration and new methods in `src/db.py`**

Add `_migrate_follow_up_columns` call at end of `__init__`:

```python
def __init__(self, path: Path):
    self.path = path
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self._conn = sqlite3.connect(str(path))
    self._conn.row_factory = sqlite3.Row
    self._conn.execute("PRAGMA journal_mode=WAL")
    self._create_tables()
    self._migrate_follow_up_columns()  # add this line
```

Add migration method:

```python
def _migrate_follow_up_columns(self):
    existing = {
        row[1]
        for row in self._conn.execute("PRAGMA table_info(applications)").fetchall()
    }
    if "follow_up_after" not in existing:
        self._conn.execute(
            "ALTER TABLE applications ADD COLUMN follow_up_after TEXT"
        )
    if "followed_up_at" not in existing:
        self._conn.execute(
            "ALTER TABLE applications ADD COLUMN followed_up_at TEXT"
        )
    self._conn.commit()
```

Add new query/update methods after `update_salary_notes`:

```python
def set_follow_up_date(self, job_id: str, date_str: str):
    """Set follow_up_after to a specific ISO date string (YYYY-MM-DD)."""
    self._conn.execute(
        "UPDATE applications SET follow_up_after = ? WHERE job_id = ?",
        (date_str, job_id),
    )
    self._conn.commit()

def mark_followed_up(self, job_id: str, reset_days: int = 7):
    """Record follow-up action. Resets follow_up_after only if it was previously set."""
    now = datetime.now(timezone.utc)
    app = self.get_application(job_id)
    if not app:
        return
    new_follow_up = None
    if app.get("follow_up_after") is not None:
        from datetime import timedelta
        new_follow_up = (now + timedelta(days=reset_days)).strftime("%Y-%m-%d")
    self._conn.execute(
        "UPDATE applications SET followed_up_at = ?, follow_up_after = ? WHERE job_id = ?",
        (now.isoformat(), new_follow_up, job_id),
    )
    self._conn.commit()

def get_overdue_follow_ups(self) -> list[dict]:
    """Return applications with follow_up_after <= today and non-terminal status."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = self._conn.execute(
        """
        SELECT a.job_id, j.company, j.title, j.url, a.status,
               a.applied_date, a.follow_up_after,
               julianday(?) - julianday(a.follow_up_after) AS days_overdue
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.follow_up_after IS NOT NULL
          AND a.follow_up_after <= ?
          AND a.status IN ('new', 'applied', 'interviewing')
        ORDER BY a.follow_up_after ASC
        """,
        (today, today),
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 1.4: Run all new DB tests**

```bash
uv run pytest tests/test_db.py -v
```

Expected: All pass.

- [ ] **Step 1.5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat: add follow-up columns to applications table with migration and DB methods"
```

---

## Task 2: Deduplication Step

**Files:**
- Create: `src/steps/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_dedup.py`:

```python
import pytest
from datetime import datetime, timezone

from src.db import Database
from src.steps.dedup import _normalize_title, _score_job, run_dedup


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _make_job(db, job_id, company, title, **kwargs):
    db.upsert_job(
        id=job_id, company=company, title=title,
        url=f"https://example.com/{job_id}",
        scraped_at=datetime.now(timezone.utc),
        **kwargs,
    )
    db.commit()


# --- normalize_title tests ---

def test_normalize_strips_senior():
    assert _normalize_title("Senior Engineering Manager") == "engineering manager"

def test_normalize_strips_sr():
    assert _normalize_title("Sr. Engineering Manager") == "engineering manager"

def test_normalize_strips_trailing_roman():
    assert _normalize_title("Engineering Manager II") == "engineering manager"

def test_normalize_preserves_department():
    assert _normalize_title("Engineering Manager, Growth") == "engineering manager growth"

def test_normalize_two_different_departments():
    assert _normalize_title("Engineering Manager, Growth") != _normalize_title("Engineering Manager, Platform")

def test_normalize_strips_punctuation():
    assert _normalize_title("Engineering Manager - Platform") == "engineering manager platform"


# --- score_job tests ---

def test_score_all_fields():
    job = {"salary": "200k", "description": "x" * 600, "location": "NYC", "department": "Eng"}
    assert _score_job(job) == 6

def test_score_no_fields():
    job = {"salary": None, "description": None, "location": None, "department": None}
    assert _score_job(job) == 0

def test_score_short_description_no_bonus():
    job = {"salary": None, "description": "short", "location": None, "department": None}
    assert _score_job(job) == 0


# --- run_dedup integration tests ---

def test_dedup_no_duplicates(db):
    _make_job(db, "stripe:1", "Stripe", "Engineering Manager, Growth")
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager, Platform")
    merged, removed = run_dedup(db)
    assert merged == 0
    assert removed == 0


def test_dedup_finds_seniority_duplicate(db):
    _make_job(db, "stripe:1", "Stripe", "Senior Engineering Manager",
              description="x" * 600, salary="200k", location="NYC")
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager",
              description=None, salary=None, location=None)
    merged, removed = run_dedup(db)
    assert merged == 1
    assert removed == 1
    # canonical (stripe:1) survives
    assert db.get_job("stripe:1") is not None
    assert db.get_job("stripe:2") is None


def test_dedup_keeps_canonical_match(db):
    _make_job(db, "stripe:1", "Stripe", "Senior Engineering Manager",
              description="x" * 600, salary="200k")
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="strong")
    db.insert_match(job_id="stripe:2", relevance_score=0.5, match_reason="weak")
    run_dedup(db)
    match = db.get_match("stripe:1")
    assert match is not None
    assert match["relevance_score"] == 0.9
    assert db.get_match("stripe:2") is None


def test_dedup_migrates_orphan_match_to_canonical(db):
    _make_job(db, "stripe:1", "Stripe", "Senior Engineering Manager",
              description="x" * 600, salary="200k")
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    # Only duplicate has a match
    db.insert_match(job_id="stripe:2", relevance_score=0.7, match_reason="decent")
    run_dedup(db)
    assert db.get_match("stripe:1") is not None
    assert db.get_match("stripe:2") is None


def test_dedup_migrates_application_to_canonical(db):
    _make_job(db, "stripe:1", "Stripe", "Senior Engineering Manager",
              description="x" * 600, salary="200k")
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    db.set_application_status("stripe:2", "applied")
    run_dedup(db)
    app = db.get_application("stripe:1")
    assert app is not None
    assert app["status"] == "applied"
    assert db.get_application("stripe:2") is None


def test_dedup_keeps_more_advanced_application_status(db):
    _make_job(db, "stripe:1", "Stripe", "Senior Engineering Manager",
              description="x" * 600, salary="200k")
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    db.set_application_status("stripe:1", "applied")
    db.set_application_status("stripe:2", "interviewing")
    run_dedup(db)
    app = db.get_application("stripe:1")
    assert app["status"] == "interviewing"


def test_dedup_no_cross_company(db):
    _make_job(db, "stripe:1", "Stripe", "Engineering Manager")
    _make_job(db, "datadog:1", "DataDog", "Engineering Manager")
    merged, removed = run_dedup(db)
    assert merged == 0
```

- [ ] **Step 2.2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_dedup.py -v
```

Expected: FAIL — `src/steps/dedup.py` does not exist.

- [ ] **Step 2.3: Implement `src/steps/dedup.py`**

```python
import logging
import re
from datetime import datetime, timezone

from src.db import Database

logger = logging.getLogger(__name__)

_SENIORITY_WORDS = {
    "senior", "sr", "junior", "jr", "staff", "principal", "lead", "associate"
}
_ROMAN = re.compile(r"\s+\b(i{1,3}|iv|vi{0,3}|ix)\b$", re.IGNORECASE)
_PUNCT = re.compile(r"[,\-./\\()\[\]]")
_WHITESPACE = re.compile(r"\s+")

_STATUS_RANK = {
    "interviewing": 5,
    "offer": 4,
    "applied": 3,
    "new": 2,
    "rejected": 1,
    "withdrawn": 0,
}


def _normalize_title(title: str) -> str:
    title = _ROMAN.sub("", title)
    title = _PUNCT.sub(" ", title)
    words = title.lower().split()
    words = [w for w in words if w.rstrip(".") not in _SENIORITY_WORDS]
    return _WHITESPACE.sub(" ", " ".join(words)).strip()


def _score_job(job: dict) -> int:
    score = 0
    if job.get("salary"):
        score += 2
    desc = job.get("description") or ""
    if len(desc) > 500:
        score += 2
    if job.get("location"):
        score += 1
    if job.get("department"):
        score += 1
    return score


def _pick_canonical(jobs: list[dict]) -> tuple[dict, list[dict]]:
    ranked = sorted(jobs, key=lambda j: (_score_job(j), -_parse_ts(j["first_seen_at"])), reverse=True)
    return ranked[0], ranked[1:]


def _parse_ts(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _merge_group(db: Database, canonical: dict, duplicates: list[dict]) -> int:
    """Merge duplicate jobs into canonical. Returns number removed."""
    removed = 0
    for dup in duplicates:
        cid = canonical["id"]
        did = dup["id"]
        try:
            with db._conn:  # transaction per group
                _merge_matches(db, cid, did)
                _merge_applications(db, cid, did)
                _merge_status_history(db, cid, did)
                db._conn.execute("DELETE FROM jobs WHERE id = ?", (did,))
            removed += 1
            logger.info(f"Dedup: merged {did} → {cid}")
        except Exception as e:
            logger.warning(f"Dedup: failed to merge {did} → {cid}: {e}")
    return removed


def _merge_matches(db: Database, canonical_id: str, dup_id: str):
    canonical_match = db.get_match(canonical_id)
    dup_match = db.get_match(dup_id)
    if canonical_match and dup_match:
        # Keep higher score; delete loser first to avoid PK conflict
        if dup_match["relevance_score"] > canonical_match["relevance_score"]:
            db._conn.execute("DELETE FROM matches WHERE job_id = ?", (canonical_id,))
            db._conn.execute("UPDATE matches SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id))
        else:
            db._conn.execute("DELETE FROM matches WHERE job_id = ?", (dup_id,))
    elif dup_match:
        db._conn.execute("UPDATE matches SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id))


def _merge_applications(db: Database, canonical_id: str, dup_id: str):
    canonical_app = db.get_application(canonical_id)
    dup_app = db.get_application(dup_id)
    if canonical_app and dup_app:
        c_rank = _STATUS_RANK.get(canonical_app["status"], 0)
        d_rank = _STATUS_RANK.get(dup_app["status"], 0)
        if d_rank > c_rank:
            # dup has better status — delete canonical, re-point dup
            db._conn.execute("DELETE FROM applications WHERE job_id = ?", (canonical_id,))
            db._conn.execute("UPDATE applications SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id))
        else:
            db._conn.execute("DELETE FROM applications WHERE job_id = ?", (dup_id,))
    elif dup_app:
        db._conn.execute("UPDATE applications SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id))


def _merge_status_history(db: Database, canonical_id: str, dup_id: str):
    db._conn.execute(
        "UPDATE status_history SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id)
    )
    # Drop exact duplicate history rows (same old_status + new_status + changed_at)
    db._conn.execute("""
        DELETE FROM status_history
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM status_history
            WHERE job_id = ?
            GROUP BY old_status, new_status, changed_at
        )
        AND job_id = ?
    """, (canonical_id, canonical_id))


def run_dedup(db: Database) -> tuple[int, int]:
    """Find and merge duplicate jobs. Returns (groups_merged, records_removed)."""
    rows = db._conn.execute(
        "SELECT id, company, title, description, salary, location, department, first_seen_at FROM jobs"
    ).fetchall()

    # Group by (company, normalized_title)
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        job = dict(row)
        key = (job["company"], _normalize_title(job["title"]))
        groups.setdefault(key, []).append(job)

    total_merged = 0
    total_removed = 0
    for key, jobs in groups.items():
        if len(jobs) < 2:
            continue
        canonical, duplicates = _pick_canonical(jobs)
        removed = _merge_group(db, canonical, duplicates)
        if removed:
            total_merged += 1
            total_removed += removed

    if total_merged:
        logger.info(f"Dedup: {total_merged} duplicate groups found, {total_removed} records removed")
    return total_merged, total_removed
```

- [ ] **Step 2.4: Run dedup tests**

```bash
uv run pytest tests/test_dedup.py -v
```

Expected: All pass.

- [ ] **Step 2.5: Run full test suite to check for regressions**

```bash
uv run pytest -v
```

Expected: All pass.

- [ ] **Step 2.6: Commit**

```bash
git add src/steps/dedup.py tests/test_dedup.py
git commit -m "feat: add cross-board job deduplication step"
```

---

## Task 3: Wire Dedup into Scrape + Pipeline CLI

**Files:**
- Modify: `src/steps/scrape.py:17-71`
- Modify: `src/pipeline.py:36,377-391`

- [ ] **Step 3.1: Write failing test for dedup running after full pipeline scrape**

Add to `tests/test_pipeline.py` (read that file first for fixture patterns — use `MagicMock` for scrapers like `test_steps_scrape.py` does):

```python
def test_full_pipeline_runs_dedup_after_scrape(tmp_path, monkeypatch):
    """Dedup should run automatically after scraping in the full pipeline."""
    from unittest.mock import MagicMock, patch
    from src.scrapers.base import RawJob
    from datetime import datetime, timezone

    db = Database(tmp_path / "dedup_test.db")
    dedup_calls = []

    def fake_dedup(d):
        dedup_calls.append(True)
        return (0, 0)

    mock_scraper = MagicMock()
    mock_scraper.company_name = "Stripe"
    mock_scraper.fetch_jobs.return_value = [
        RawJob(external_id="1", company="Stripe", title="EM", url="https://x.com",
               location=None, remote=None, salary=None, description=None,
               department=None, seniority=None,
               scraped_at=datetime.now(timezone.utc))
    ]

    with patch("src.pipeline.Database", return_value=db), \
         patch("src.pipeline.Config") as MockConfig, \
         patch("src.pipeline.build_scrapers", return_value=[mock_scraper]), \
         patch("src.pipeline.run_dedup", fake_dedup), \
         patch("src.pipeline.get_active_resume_yaml", return_value=(tmp_path / "r.yaml", {})), \
         patch("src.pipeline.run_filter", return_value=[]), \
         patch("src.pipeline.run_notify", return_value=True):
        MockConfig.return_value.db_path = tmp_path / "dedup_test.db"
        args = parse_args(["--dry-run"])
        run_pipeline(args)

    assert len(dedup_calls) == 1
```

- [ ] **Step 3.2: Run test to confirm it fails**

```bash
uv run pytest tests/test_pipeline.py::test_full_pipeline_runs_dedup_after_scrape -v
```

Expected: FAIL — `run_dedup` not imported or called in `pipeline.py`.

- [ ] **Step 3.3: Add `dedup` to `--step` choices, standalone handler, and post-scrape call in `src/pipeline.py`**

**Do NOT add `run_dedup` to `scrape.py`.** The pipeline owns dedup orchestration per the spec.

At top of `pipeline.py`, add import alongside other step imports:
```python
from src.steps.dedup import run_dedup
```

In `parse_args()`, change the `--step` choices list (line 36):
```python
    parser.add_argument(
        "--step",
        choices=["scrape", "filter", "tailor", "notify", "dedup"],
        help="Run a single step",
    )
```

In `run_pipeline()`, add a standalone `--step dedup` handler before `run_id = db.start_run()` (insert after the `args.renotify` block):

```python
    if args.step == "dedup":
        merged, removed = run_dedup(db)
        print(f"Dedup complete: {merged} duplicate groups merged, {removed} records removed")
        return
```

After `run_scrape` completes in the full pipeline (line ~380), add dedup before the `--step scrape` early return:

```python
        if not args.step or args.step == "scrape":
            scrapers = build_scrapers(config)
            scrape_result = run_scrape(db, scrapers)
            logger.info(
                f"Scrape complete: {scrape_result['jobs_scraped']} jobs, {scrape_result['new_jobs']} new"
            )
            run_dedup(db)  # deduplicate after each scrape, before early return
            if args.step == "scrape":
                db.complete_run(...)
                return
```

- [ ] **Step 3.5: Run tests**

```bash
uv run pytest tests/test_steps_scrape.py tests/test_dedup.py -v
```

Expected: All pass.

- [ ] **Step 3.6: Commit**

```bash
git add src/pipeline.py
git commit -m "feat: wire dedup into scrape step and add --step dedup CLI command"
```

---

## Task 4: Follow-up CLI Commands

**Files:**
- Modify: `src/pipeline.py`
- Create: `tests/test_follow_up.py`

- [ ] **Step 4.1: Write failing CLI tests**

Create `tests/test_follow_up.py`:

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from src.db import Database
from src.pipeline import parse_args, run_pipeline


@pytest.fixture
def db_with_applied_job(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.commit()
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:1", "applied")
    db.set_follow_up_date("stripe:1", "2000-01-01")
    return db


def test_parse_args_follow_ups():
    args = parse_args(["--follow-ups"])
    assert args.follow_ups is True


def test_parse_args_followed_up():
    args = parse_args(["--followed-up", "stripe:1"])
    assert args.followed_up == "stripe:1"


def test_parse_args_set_followup():
    args = parse_args(["--set-followup", "stripe:1", "2026-05-01"])
    assert args.set_followup == ["stripe:1", "2026-05-01"]


def test_follow_ups_prints_overdue(db_with_applied_job, tmp_path, capsys):
    with patch("src.pipeline.Database", return_value=db_with_applied_job), \
         patch("src.pipeline.Config") as MockConfig:
        MockConfig.return_value.db_path = tmp_path / "test.db"
        args = parse_args(["--follow-ups"])
        # run_pipeline needs a real db — test via db method directly
    overdue = db_with_applied_job.get_overdue_follow_ups()
    assert len(overdue) == 1
    assert overdue[0]["company"] == "Stripe"


def test_followed_up_resets_date(db_with_applied_job):
    db_with_applied_job.mark_followed_up("stripe:1", reset_days=7)
    app = db_with_applied_job.get_application("stripe:1")
    assert app["followed_up_at"] is not None
    assert app["follow_up_after"] > "2000-01-01"


def test_set_followup_updates_date(db_with_applied_job):
    db_with_applied_job.set_follow_up_date("stripe:1", "2026-06-01")
    app = db_with_applied_job.get_application("stripe:1")
    assert app["follow_up_after"] == "2026-06-01"
```

- [ ] **Step 4.2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_follow_up.py -v
```

Expected: FAIL — `parse_args` doesn't accept `--follow-ups`.

- [ ] **Step 4.3: Add CLI args to `src/pipeline.py`**

In `parse_args()`, add after the `--applications` argument:

```python
    parser.add_argument(
        "--follow-ups",
        action="store_true",
        help="List applications with overdue follow-up dates",
    )
    parser.add_argument(
        "--followed-up",
        metavar="JOB_ID",
        help="Mark a job as followed up and reset follow-up date",
    )
    parser.add_argument(
        "--set-followup",
        nargs=2,
        metavar=("JOB_ID", "DATE"),
        help='Set follow-up date for a job (e.g. --set-followup "Stripe:123" 2026-05-01)',
    )
    parser.add_argument(
        "--interview-prep",
        metavar="JOB_ID",
        help="Generate interview prep note for a job",
    )
    parser.add_argument(
        "--research",
        action="store_true",
        help="Add web research when generating interview prep (use with --interview-prep)",
    )
```

In `run_pipeline()`, add handlers after `args.applications` block:

```python
    if args.follow_ups:
        overdue = db.get_overdue_follow_ups()
        if not overdue:
            print("No overdue follow-ups.")
            return
        print(f"\n{'Company':<14} {'Title':<38} {'Status':<14} {'Applied':<12} {'Overdue':>8}  Follow-up date")
        print("-" * 100)
        for f in overdue:
            applied = (f.get("applied_date") or "")[:10]
            days = int(f.get("days_overdue") or 0)
            print(f"  {f['company']:<12} {f['title'][:36]:<38} {f['status']:<14} {applied:<12} {days:>6}d  {f['follow_up_after']}")
        return

    if args.followed_up:
        job_id = args.followed_up
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        db.mark_followed_up(job_id)
        print(f"Followed up: {job['company']} — {job['title']}. Next follow-up reset to +7 days if date was set.")
        return

    if args.set_followup:
        job_id, date_str = args.set_followup
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        db.set_follow_up_date(job_id, date_str)
        print(f"Follow-up date set: {job['company']} — {job['title']} → {date_str}")
        return
```

- [ ] **Step 4.4: Run tests**

```bash
uv run pytest tests/test_follow_up.py -v
```

Expected: All pass.

- [ ] **Step 4.5: Commit**

```bash
git add src/pipeline.py tests/test_follow_up.py
git commit -m "feat: add --follow-ups, --followed-up, --set-followup CLI commands"
```

---

## Task 5: Auto-set Follow-up on Status Transitions

**Files:**
- Modify: `src/pipeline.py` (status and track handlers)

When status transitions to `applied` or `interviewing`, automatically set `follow_up_after` to `applied_date + 7 days`. The `--track` interactive flow also prompts for the number of days.

- [ ] **Step 5.1: Write failing test**

Add to `tests/test_follow_up.py`:

```python
def test_status_applied_auto_sets_follow_up(tmp_path):
    db = Database(tmp_path / "test2.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:10", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.commit()
    db.insert_match(job_id="stripe:10", relevance_score=0.9, match_reason="good")

    with patch("src.pipeline.Database", return_value=db), \
         patch("src.pipeline.Config") as MockConfig, \
         patch("src.steps.obsidian.write_application_note"), \
         patch("src.steps.obsidian.write_dashboard"):
        MockConfig.return_value.db_path = tmp_path / "test2.db"
        args = parse_args(["--status", "stripe:10", "applied"])
        run_pipeline(args)

    app = db.get_application("stripe:10")
    assert app["follow_up_after"] is not None


def test_status_interviewing_auto_sets_follow_up(tmp_path):
    db = Database(tmp_path / "test3.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:11", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.commit()
    db.insert_match(job_id="stripe:11", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:11", "applied")

    with patch("src.pipeline.Database", return_value=db), \
         patch("src.pipeline.Config") as MockConfig, \
         patch("src.steps.obsidian.write_application_note"), \
         patch("src.steps.obsidian.write_dashboard"), \
         patch("src.steps.interview_prep.generate_interview_prep"):
        MockConfig.return_value.db_path = tmp_path / "test3.db"
        args = parse_args(["--status", "stripe:11", "interviewing"])
        run_pipeline(args)

    app = db.get_application("stripe:11")
    assert app["follow_up_after"] is not None
```

- [ ] **Step 5.2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_follow_up.py::test_status_applied_auto_sets_follow_up -v
```

Expected: FAIL.

- [ ] **Step 5.3: Add auto-set logic to `--status` handler in `src/pipeline.py`**

In the `args.status` handler, after `db.set_application_status(job_id, new_status)`, add:

```python
        # Auto-set follow-up date for active statuses
        if new_status in ("applied", "interviewing"):
            from datetime import timedelta
            app = db.get_application(job_id)
            base_date = app.get("applied_date") or datetime.now(timezone.utc).isoformat()
            try:
                base_dt = datetime.fromisoformat(base_date.replace("Z", "+00:00"))
            except ValueError:
                base_dt = datetime.now(timezone.utc)
            follow_up = (base_dt + timedelta(days=7)).strftime("%Y-%m-%d")
            db.set_follow_up_date(job_id, follow_up)
```

Similarly in the `args.track` handler, after `db.set_application_status(job_id, new_status)` and when `new_status in ("applied", "interviewing")`, prompt for days:

```python
        if new_status in ("applied", "interviewing"):
            days_input = input("Follow up in how many days? [7]: ").strip()
            follow_up_days = int(days_input) if days_input.isdigit() else 7
            from datetime import timedelta
            app = db.get_application(job_id)
            base_date = app.get("applied_date") or datetime.now(timezone.utc).isoformat()
            try:
                base_dt = datetime.fromisoformat(base_date.replace("Z", "+00:00"))
            except ValueError:
                base_dt = datetime.now(timezone.utc)
            follow_up = (base_dt + timedelta(days=follow_up_days)).strftime("%Y-%m-%d")
            db.set_follow_up_date(job_id, follow_up)
            print(f"Follow-up date set: {follow_up}")
```

- [ ] **Step 5.4: Run tests**

```bash
uv run pytest tests/test_follow_up.py -v
```

Expected: All pass.

- [ ] **Step 5.5: Commit**

```bash
git add src/pipeline.py tests/test_follow_up.py
git commit -m "feat: auto-set follow-up date on applied/interviewing status transitions"
```

---

## Task 6: Follow-up Section in Email Digest

**Files:**
- Modify: `src/steps/notify.py`
- Modify: `templates/digest.html`

- [ ] **Step 6.1: Write failing test**

Add to `tests/test_notify.py` (read file first for existing pattern):

```python
def test_build_digest_html_includes_follow_ups(config):
    follow_ups = [
        {"company": "Stripe", "title": "EM", "days_overdue": 3, "url": "https://x.com",
         "status": "applied", "follow_up_after": "2026-03-28"}
    ]
    run_stats = {"jobs_scraped": 0, "new_jobs": 0, "matches_found": 0, "duration": "1s"}
    html = build_digest_html([], run_stats, config, follow_ups=follow_ups)
    assert "Follow Up Today" in html
    assert "Stripe" in html
    assert "3" in html  # days overdue


def test_build_digest_html_no_follow_ups_hides_section(config):
    run_stats = {"jobs_scraped": 0, "new_jobs": 0, "matches_found": 0, "duration": "1s"}
    html = build_digest_html([], run_stats, config, follow_ups=[])
    assert "Follow Up Today" not in html


def test_build_no_match_html_includes_follow_ups(config):
    follow_ups = [
        {"company": "Stripe", "title": "EM", "days_overdue": 2, "url": "https://x.com",
         "status": "applied", "follow_up_after": "2026-03-29"}
    ]
    run_stats = {"jobs_scraped": 10, "new_jobs": 0, "matches_found": 0, "duration": "2s"}
    html = build_no_match_html(run_stats, config, follow_ups=follow_ups)
    assert "Follow Up Today" in html
    assert "Stripe" in html
```

- [ ] **Step 6.2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_notify.py::test_build_digest_html_includes_follow_ups -v
```

Expected: FAIL — `build_digest_html` doesn't accept `follow_ups` parameter.

- [ ] **Step 6.3: Update `src/steps/notify.py`**

Update `build_digest_html` signature and template call:

```python
def build_digest_html(matches: list[dict], run_stats: dict, config: Config,
                      follow_ups: list[dict] = None) -> str:
    template = _load_template(config)
    enriched = []
    for m in matches:
        m_copy = dict(m)
        m_copy["suggestions_parsed"] = _parse_suggestions(m)
        enriched.append(m_copy)
    return template.render(
        matches=enriched,
        run_stats=run_stats,
        follow_ups=follow_ups or [],
        date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
    )
```

Update `build_no_match_html` similarly:

```python
def build_no_match_html(run_stats: dict, config: Config,
                        follow_ups: list[dict] = None) -> str:
    template = _load_template(config)
    return template.render(
        matches=[],
        run_stats=run_stats,
        follow_ups=follow_ups or [],
        date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
    )
```

Update `run_notify` to query and pass follow-ups:

```python
def run_notify(db: Database, run_stats: dict, config: Config) -> bool:
    matches = db.get_unnotified_matches()
    follow_ups = db.get_overdue_follow_ups()  # add this line

    if matches:
        subject = f"Job Tracker: {len(matches)} new match{'es' if len(matches) > 1 else ''} found — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        html = build_digest_html(matches, run_stats, config, follow_ups=follow_ups)  # pass follow_ups
        ...
    else:
        subject = f"Job Tracker: No new matches — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        html = build_no_match_html(run_stats, config, follow_ups=follow_ups)  # pass follow_ups
        ...
```

- [ ] **Step 6.4: Update `templates/digest.html`**

Read the full digest.html first, then add the follow-up section immediately after the `<h1>` and before the matches count paragraph. Add this CSS to the `<style>` block:

```css
  .followup-section { background: #fff8e1; border: 1px solid #ffe082; border-radius: 8px; padding: 16px; margin: 16px 0; }
  .followup-section h2 { color: #e65100; margin: 0 0 10px 0; font-size: 1em; }
  .followup-table { width: 100%; border-collapse: collapse; }
  .followup-table td { padding: 6px 10px; border-bottom: 1px solid #ffe082; font-size: 0.9em; }
  .overdue-badge { background: #e65100; color: white; padding: 1px 6px; border-radius: 4px; font-size: 0.8em; }
```

Add this block after the `<h1>` line:

```html
{% if follow_ups %}
<div class="followup-section">
  <h2>&#128276; Follow Up Today ({{ follow_ups|length }})</h2>
  <table class="followup-table">
  {% for f in follow_ups %}
  <tr>
    <td><a href="{{ f.url }}">{{ f.company }} — {{ f.title }}</a></td>
    <td>{{ f.status }}</td>
    <td><span class="overdue-badge">{{ f.days_overdue|int }}d overdue</span></td>
  </tr>
  {% endfor %}
  </table>
</div>
{% endif %}
```

- [ ] **Step 6.5: Run tests**

```bash
uv run pytest tests/test_notify.py -v
```

Expected: All pass.

- [ ] **Step 6.6: Commit**

```bash
git add src/steps/notify.py templates/digest.html tests/test_notify.py
git commit -m "feat: add follow-up section to email digest"
```

---

## Task 7: Interview Prep Step

**Files:**
- Create: `src/steps/interview_prep.py`
- Create: `tests/test_interview_prep.py`

- [ ] **Step 7.1: Write failing tests**

Create `tests/test_interview_prep.py`:

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.db import Database
from src.steps.interview_prep import generate_interview_prep, _patch_obsidian_section


@pytest.fixture
def db(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:1", company="Stripe", title="EM, Platform",
        url="https://stripe.com/jobs/1",
        description="We need an EM to lead Platform engineering...",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="good match")
    return db


def test_patch_obsidian_section_replaces_existing():
    note = "# Title\n\n## Some Section\ncontent\n\n## Interview Prep\nold content\n\n## Notes\nmore"
    result = _patch_obsidian_section(note, "## Interview Prep", "new content")
    assert "old content" not in result
    assert "new content" in result
    assert "## Notes\nmore" in result


def test_patch_obsidian_section_appends_if_missing():
    note = "# Title\n\n## Notes\ncontent"
    result = _patch_obsidian_section(note, "## Interview Prep", "new content")
    assert "## Interview Prep" in result
    assert "new content" in result


def test_generate_interview_prep_calls_llm(db, tmp_path):
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {
        "likely_questions": ["Tell me about a time you dealt with ambiguity"],
        "star_stories": [
            {
                "question": "Tell me about a time you dealt with ambiguity",
                "resume_bullet": "Led platform migration",
                "situation": "S", "task": "T", "action": "A", "result": "R"
            }
        ],
        "talking_points": ["Deep platform experience", "Cross-functional leadership"],
        "red_flags": ["Limited ML experience"],
    }
    mock_response.content = [mock_tool_use]
    mock_response.stop_reason = "tool_use"

    fake_resume = {"experience": [{"company": "Acme", "title": "EM", "bullets": ["Led platform migration"]}]}

    with patch("src.steps.interview_prep.anthropic.Anthropic") as MockAnthropic, \
         patch("src.steps.interview_prep.get_active_resume_yaml", return_value=(tmp_path / "r.yaml", fake_resume)), \
         patch("src.steps.interview_prep._read_obsidian_note", return_value="# Stripe — EM, Platform\n\n## Interview Prep\n\n## Notes\n"), \
         patch("src.steps.interview_prep._write_obsidian_note") as mock_write:
        MockAnthropic.return_value.messages.create.return_value = mock_response
        generate_interview_prep(db, "stripe:1")
        assert mock_write.called
        written_content = mock_write.call_args[0][1]
        assert "Tell me about a time" in written_content
        assert "Deep platform experience" in written_content


def test_generate_interview_prep_handles_missing_job(db):
    """Should not raise if job not found."""
    generate_interview_prep(db, "nonexistent:999")  # should not raise
```

- [ ] **Step 7.2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_interview_prep.py -v
```

Expected: FAIL — `src/steps/interview_prep.py` does not exist.

- [ ] **Step 7.3: Implement `src/steps/interview_prep.py`**

```python
import json
import logging
import re
import subprocess
from pathlib import Path

import anthropic
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import Config
from src.db import Database
from src.steps.tailor import get_active_resume_yaml

logger = logging.getLogger(__name__)

_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError)),
    reraise=True,
)

PREP_TOOL = {
    "name": "interview_prep",
    "description": "Generate structured interview preparation content for a job",
    "input_schema": {
        "type": "object",
        "properties": {
            "likely_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Predicted behavioral and technical interview questions based on the JD",
            },
            "star_stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "resume_bullet": {"type": "string"},
                        "situation": {"type": "string"},
                        "task": {"type": "string"},
                        "action": {"type": "string"},
                        "result": {"type": "string"},
                    },
                    "required": ["question", "resume_bullet", "situation", "task", "action", "result"],
                },
                "description": "STAR story mappings from resume experience to interview questions",
            },
            "talking_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-5 key things to emphasize about your background for this specific role",
            },
            "red_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Gaps or weaknesses relative to the JD to prepare for",
            },
        },
        "required": ["likely_questions", "star_stories", "talking_points", "red_flags"],
    },
}


def _read_obsidian_note(path: str) -> str:
    """Read a note from Obsidian vault via CLI. Returns empty string if not found."""
    try:
        result = subprocess.run(
            ["claude", "mcp", "call", "obsidian", "read_note", "--",
             json.dumps({"path": path})],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            # MCP response is JSON — extract content
            data = json.loads(result.stdout)
            if isinstance(data, list) and data:
                return data[0].get("text", "")
            return result.stdout
    except Exception as e:
        logger.debug(f"Could not read Obsidian note {path}: {e}")
    return ""


def _write_obsidian_note(path: str, content: str):
    try:
        subprocess.run(
            ["claude", "mcp", "call", "obsidian", "write_note", "--",
             json.dumps({"path": path, "content": content})],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        logger.warning(f"Failed to write Obsidian note {path}: {e}")


def _patch_obsidian_section(note: str, section_header: str, new_content: str) -> str:
    """Replace section_header block in note with new_content, or append if missing."""
    # Match section from header to next ## header or end of string
    pattern = re.compile(
        rf"({re.escape(section_header)})\n.*?(?=\n## |\Z)", re.DOTALL
    )
    replacement = f"{section_header}\n{new_content}"
    if pattern.search(note):
        return pattern.sub(replacement, note)
    return note.rstrip() + f"\n\n{section_header}\n{new_content}\n"


def _format_prep_content(prep: dict) -> str:
    lines = []

    if prep.get("talking_points"):
        lines.append("### Key Talking Points")
        for tp in prep["talking_points"]:
            lines.append(f"- {tp}")
        lines.append("")

    if prep.get("red_flags"):
        lines.append("### Gaps to Prepare For")
        for rf in prep["red_flags"]:
            lines.append(f"- {rf}")
        lines.append("")

    if prep.get("likely_questions"):
        lines.append("### Likely Questions")
        for q in prep["likely_questions"]:
            lines.append(f"- {q}")
        lines.append("")

    if prep.get("star_stories"):
        lines.append("### STAR Stories")
        for story in prep["star_stories"]:
            lines.append(f"\n**Q: {story['question']}**")
            lines.append(f"*From: {story['resume_bullet']}*")
            lines.append(f"- **S:** {story['situation']}")
            lines.append(f"- **T:** {story['task']}")
            lines.append(f"- **A:** {story['action']}")
            lines.append(f"- **R:** {story['result']}")

    return "\n".join(lines)


@_llm_retry
def _call_llm(job: dict, resume_data: dict, extra_context: str = "") -> dict:
    client = anthropic.Anthropic()

    resume_text = yaml.dump(resume_data, default_flow_style=False)[:4000]

    prompt = f"""You are preparing an engineering manager candidate for an interview.

Job: {job['company']} — {job['title']}
Description:
{(job.get('description') or '')[:3000]}

Candidate's resume (YAML):
{resume_text}
"""
    if extra_context:
        prompt += f"\nAdditional company context:\n{extra_context}\n"

    prompt += "\nGenerate structured interview prep content using the interview_prep tool."

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        tools=[PREP_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            return block.input

    raise ValueError("LLM did not return tool_use block")


def _web_research(company: str) -> str:
    """Basic web research for company context. Returns summary string."""
    import urllib.request
    import urllib.parse
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(company)}"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
            return data.get("extract", "")[:500]
    except Exception:
        return ""


def generate_interview_prep(db: Database, job_id: str, research: bool = False,
                            config: "Config | None" = None):
    """Generate and write interview prep content for a job to its Obsidian note."""
    job = db.get_job(job_id)
    if not job:
        logger.warning(f"interview_prep: job {job_id} not found")
        return

    try:
        if config is None:
            config = Config()
        _, resume_data = get_active_resume_yaml(config)
    except Exception as e:
        logger.warning(f"interview_prep: could not load resume: {e}")
        resume_data = {}

    extra_context = ""
    if research:
        logger.info(f"interview_prep: fetching company research for {job['company']}")
        extra_context = _web_research(job["company"])

    try:
        prep = _call_llm(job, resume_data, extra_context)
    except Exception as e:
        logger.error(f"interview_prep: LLM call failed for {job_id}: {e}")
        return

    from src.steps.obsidian import sanitize_filename, VAULT_PATH
    note_name = sanitize_filename(f"{job['company']} — {job['title']}")
    note_path = f"{VAULT_PATH}/{note_name}"

    existing = _read_obsidian_note(note_path)
    if not existing:
        # Note doesn't exist yet — create a minimal shell
        existing = f"# {job['company']} — {job['title']}\n\n## Interview Prep\n\n## Notes\n"

    new_content = _format_prep_content(prep)
    patched = _patch_obsidian_section(existing, "## Interview Prep", new_content)
    _write_obsidian_note(note_path, patched)

    logger.info(f"interview_prep: wrote prep note for {job_id}")
```

- [ ] **Step 7.4: Run tests**

```bash
uv run pytest tests/test_interview_prep.py -v
```

Expected: All pass.

- [ ] **Step 7.5: Commit**

```bash
git add src/steps/interview_prep.py tests/test_interview_prep.py
git commit -m "feat: add interview prep generation step"
```

---

## Task 8: Wire Interview Prep into Pipeline

**Files:**
- Modify: `src/pipeline.py` (status handler + `--interview-prep` command)

- [ ] **Step 8.1: Write failing test**

Add to `tests/test_interview_prep.py`:

```python
def test_status_interviewing_triggers_prep(tmp_path):
    db = Database(tmp_path / "test4.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:20", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.commit()
    db.insert_match(job_id="stripe:20", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:20", "applied")

    prep_calls = []
    with patch("src.pipeline.Database", return_value=db), \
         patch("src.pipeline.Config") as MockConfig, \
         patch("src.steps.obsidian.write_application_note"), \
         patch("src.steps.obsidian.write_dashboard"), \
         patch("src.pipeline.generate_interview_prep", side_effect=lambda *a, **k: prep_calls.append(a)):
        from src.pipeline import parse_args, run_pipeline
        MockConfig.return_value.db_path = tmp_path / "test4.db"
        args = parse_args(["--status", "stripe:20", "interviewing"])
        run_pipeline(args)

    assert len(prep_calls) == 1


def test_interview_prep_command(tmp_path):
    db = Database(tmp_path / "test5.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:21", company="Stripe", title="EM", url="https://x.com", scraped_at=now)
    db.commit()

    prep_calls = []
    with patch("src.pipeline.Database", return_value=db), \
         patch("src.pipeline.Config") as MockConfig, \
         patch("src.pipeline.generate_interview_prep", side_effect=lambda *a, **k: prep_calls.append(a)):
        from src.pipeline import parse_args, run_pipeline
        MockConfig.return_value.db_path = tmp_path / "test5.db"
        args = parse_args(["--interview-prep", "stripe:21"])
        run_pipeline(args)

    assert len(prep_calls) == 1
```

- [ ] **Step 8.2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_interview_prep.py::test_status_interviewing_triggers_prep -v
```

Expected: FAIL.

- [ ] **Step 8.3: Wire into `src/pipeline.py`**

Add import at top of file (near other step imports):
```python
from src.steps.interview_prep import generate_interview_prep
```

In the `args.status` handler, after the follow-up auto-set block from Task 5, add:

```python
        # Trigger interview prep on interviewing transition
        if new_status == "interviewing":
            logger.info(f"Generating interview prep for {job_id}...")
            generate_interview_prep(db, job_id)
```

In the `args.track` handler, after the follow-up auto-set block, add the same:

```python
        if new_status == "interviewing":
            logger.info(f"Generating interview prep for {job_id}...")
            generate_interview_prep(db, job_id)
```

Add the `--interview-prep` command handler block after `args.set_followup` and before `args.renotify`:

```python
    if args.interview_prep:
        job_id = args.interview_prep
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        research = getattr(args, "research", False)
        logger.info(f"Generating interview prep for {job_id} (research={research})...")
        generate_interview_prep(db, job_id, research=research)
        print(f"Interview prep written to Obsidian: {job['company']} — {job['title']}")
        return
```

- [ ] **Step 8.4: Run tests**

```bash
uv run pytest tests/test_interview_prep.py -v
```

Expected: All pass.

- [ ] **Step 8.5: Run full test suite**

```bash
uv run pytest -v
```

Expected: All pass.

- [ ] **Step 8.6: Commit**

```bash
git add src/pipeline.py tests/test_interview_prep.py
git commit -m "feat: wire interview prep into --status/--track interviewing transition and --interview-prep command"
```

---

## Task 9: Final Integration Check

- [ ] **Step 9.1: Dry-run dedup on real DB**

```bash
uv run jobtracker --step dedup
```

Expected: Reports N duplicate groups merged (or 0 if no dups). No errors.

- [ ] **Step 9.2: Check follow-ups command**

```bash
uv run jobtracker --follow-ups
```

Expected: Prints overdue items or "No overdue follow-ups."

- [ ] **Step 9.3: Verify all tests pass clean**

```bash
uv run pytest -v
```

Expected: All pass, no warnings about missing columns or import errors.

- [ ] **Step 9.4: Final commit**

```bash
git add -p  # review any unstaged changes
git commit -m "chore: final integration check — all features complete"
```

---

## Summary of New Commands

| Command | Description |
|---------|-------------|
| `uv run jobtracker --step dedup` | Run dedup standalone on existing DB |
| `uv run jobtracker --follow-ups` | List overdue follow-up applications |
| `uv run jobtracker --followed-up "Company:id"` | Mark as followed up, reset date |
| `uv run jobtracker --set-followup "Company:id" 2026-05-01` | Set specific follow-up date |
| `uv run jobtracker --interview-prep "Company:id"` | Generate interview prep note |
| `uv run jobtracker --interview-prep "Company:id" --research` | Same, with web research |
