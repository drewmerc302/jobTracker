# Prune Stale Job Listings Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--prune-stale` to validate job listing URLs against their ATS platforms, close dead listings, alert on closed jobs with active applications, and fix closed-job filtering across all listing queries.

**Architecture:** Add concrete `is_job_live(url)` to `BaseScraper` (default `None`), override in each scraper with ATS-specific HTTP checks. New `close_job(job_id)` in DB. Prune logic in pipeline.py iterates open matches, validates via scraper, closes dead jobs, updates applications/Obsidian. Fix all listing queries to filter `closed_at IS NULL`.

**Tech Stack:** Python, httpx, SQLite, pytest

**Spec:** `docs/superpowers/specs/2026-04-07-prune-stale-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/scrapers/base.py` | Modify | Add concrete `is_job_live` default method |
| `src/scrapers/greenhouse.py` | Modify | Override `is_job_live` for Greenhouse ATS |
| `src/scrapers/workday.py` | Modify | Override `is_job_live` for Workday ATS |
| `src/scrapers/google.py` | Modify | Override `is_job_live` for Google Careers |
| `src/scrapers/apple.py` | Modify | Override `is_job_live` for Apple Jobs |
| `src/db.py` | Modify (add after line 170) | Add `close_job(job_id)` method |
| `src/steps/obsidian.py` | Modify (line 17-24) | Add `closed` to `STATUS_ORDER` |
| `src/pipeline.py` | Modify (argparse, list-matches, show-all-jobs, new prune handler) | Wire `--prune-stale`, fix `closed_at` filtering |
| `tests/test_scrapers.py` | Modify | Add `is_job_live` tests per scraper |
| `tests/test_db.py` | Modify | Add `close_job` test |
| `tests/test_pipeline.py` | Modify | Add `--prune-stale` arg parsing test |

---

### Task 1: Add `close_job(job_id)` to DB

**Files:**
- Modify: `src/db.py` (add after `close_missing_jobs`, line 170)
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_db.py`:

```python
def test_close_job(tmp_path):
    from datetime import datetime, timezone
    from src.db import Database

    db = Database(tmp_path / "test.db")
    db.upsert_job(
        id="Stripe:123", company="Stripe", title="EM", url="https://example.com",
        location="NYC", remote=False, salary=None, description="test",
        department=None, seniority=None,
        scraped_at=datetime.now(timezone.utc),
    )
    # Job should be open
    job = db.get_job("Stripe:123")
    assert job["closed_at"] is None

    db.close_job("Stripe:123")
    job = db.get_job("Stripe:123")
    assert job["closed_at"] is not None

    # Closing again should be a no-op (already closed)
    first_closed_at = job["closed_at"]
    db.close_job("Stripe:123")
    job = db.get_job("Stripe:123")
    assert job["closed_at"] == first_closed_at
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_db.py::test_close_job -v`
Expected: FAIL with `AttributeError: 'Database' object has no attribute 'close_job'`

- [ ] **Step 3: Implement `close_job`**

Add to `src/db.py` after `close_missing_jobs` (after line 170):

```python
    def close_job(self, job_id: str):
        """Mark a single job as closed."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE jobs SET closed_at = ? WHERE id = ? AND closed_at IS NULL",
            (now, job_id),
        )
        self._conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_db.py::test_close_job -v`
Expected: PASS

- [ ] **Step 5: Run full DB test suite**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_db.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/drewmerc/workspace/jobTracker
git add src/db.py tests/test_db.py
# msg: "feat: add close_job method to Database for single-job closure"
```

---

### Task 2: Add `is_job_live` to BaseScraper and implement per-scraper overrides

**Files:**
- Modify: `src/scrapers/base.py:25-31`
- Modify: `src/scrapers/greenhouse.py`
- Modify: `src/scrapers/workday.py`
- Modify: `src/scrapers/google.py`
- Modify: `src/scrapers/apple.py`
- Test: `tests/test_scrapers.py`

- [ ] **Step 1: Write failing tests for Greenhouse `is_job_live`**

Add to `tests/test_scrapers.py`:

```python
@patch("src.scrapers.greenhouse.httpx")
def test_greenhouse_is_job_live_returns_true_on_200(mock_httpx):
    from src.scrapers.greenhouse import GreenhouseScraper

    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://job-boards.greenhouse.io/stripe/jobs/123") is True


@patch("src.scrapers.greenhouse.httpx")
def test_greenhouse_is_job_live_returns_false_on_404(mock_httpx):
    from src.scrapers.greenhouse import GreenhouseScraper

    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://job-boards.greenhouse.io/stripe/jobs/123") is False


@patch("src.scrapers.greenhouse.httpx")
def test_greenhouse_is_job_live_returns_none_on_error(mock_httpx):
    from src.scrapers.greenhouse import GreenhouseScraper

    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    mock_httpx.get.side_effect = Exception("timeout")

    assert scraper.is_job_live("https://job-boards.greenhouse.io/stripe/jobs/123") is None
```

- [ ] **Step 2: Write failing tests for Workday `is_job_live`**

Add to `tests/test_scrapers.py`:

```python
@patch("src.scrapers.workday.httpx")
def test_workday_is_job_live_returns_true_on_200_with_content(mock_httpx):
    from src.scrapers.workday import WorkdayScraper

    scraper = WorkdayScraper(
        company_name="Netflix", base_url="https://netflix.wd1.myworkdayjobs.com",
        path="/wday/cxs/netflix/netflix", keyword_patterns=[],
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Job details here: Engineering Manager</html>"
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://netflix.wd1.myworkdayjobs.com/wday/cxs/netflix/netflix/job/123") is True


@patch("src.scrapers.workday.httpx")
def test_workday_is_job_live_returns_false_on_not_available(mock_httpx):
    from src.scrapers.workday import WorkdayScraper

    scraper = WorkdayScraper(
        company_name="Netflix", base_url="https://netflix.wd1.myworkdayjobs.com",
        path="/wday/cxs/netflix/netflix", keyword_patterns=[],
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>This page is no longer available</html>"
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://netflix.wd1.myworkdayjobs.com/wday/cxs/netflix/netflix/job/123") is False
```

- [ ] **Step 3: Write failing tests for Google `is_job_live`**

Add to `tests/test_scrapers.py`:

```python
@patch("src.scrapers.google.httpx")
def test_google_is_job_live_returns_false_on_no_longer_available(mock_httpx):
    from src.scrapers.google import GoogleScraper

    scraper = GoogleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>This job is no longer available</html>"
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://www.google.com/about/careers/applications/jobs/results/123") is False


@patch("src.scrapers.google.httpx")
def test_google_is_job_live_returns_true_on_valid_content(mock_httpx):
    from src.scrapers.google import GoogleScraper

    scraper = GoogleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Engineering Manager - Apply now</html>"
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://www.google.com/about/careers/applications/jobs/results/123") is True
```

- [ ] **Step 4: Write failing tests for Apple `is_job_live`**

Add to `tests/test_scrapers.py`:

```python
@patch("src.scrapers.apple.httpx")
def test_apple_is_job_live_returns_false_on_not_available(mock_httpx):
    from src.scrapers.apple import AppleScraper

    scraper = AppleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>This position is no longer available</html>"
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://jobs.apple.com/en-us/details/123") is False


@patch("src.scrapers.apple.httpx")
def test_apple_is_job_live_returns_true_on_valid_content(mock_httpx):
    from src.scrapers.apple import AppleScraper

    scraper = AppleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Engineering Manager - Apply</html>"
    mock_httpx.get.return_value = mock_resp

    assert scraper.is_job_live("https://jobs.apple.com/en-us/details/123") is True
```

- [ ] **Step 5: Run all new tests to verify they fail**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_scrapers.py -v -k "is_job_live"`
Expected: FAIL with `AttributeError: ... has no attribute 'is_job_live'`

- [ ] **Step 6: Add default `is_job_live` to BaseScraper**

In `src/scrapers/base.py`, add after the `fetch_jobs` abstract method (after line 30):

```python
    def is_job_live(self, url: str) -> bool | None:
        """Check if a job listing URL is still live.
        Returns True (live), False (dead), None (ambiguous/unsupported).
        Subclasses override with ATS-specific logic.
        """
        return None
```

- [ ] **Step 7: Implement Greenhouse `is_job_live`**

Add to `src/scrapers/greenhouse.py` in the `GreenhouseScraper` class:

```python
    def is_job_live(self, url: str) -> bool | None:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code in (404, 410):
                return False
            if resp.status_code == 200:
                return True
            return None
        except Exception:
            return None
```

- [ ] **Step 8: Implement Workday `is_job_live`**

Add to `src/scrapers/workday.py` in the `WorkdayScraper` class:

```python
    def is_job_live(self, url: str) -> bool | None:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code in (404, 410):
                return False
            if resp.status_code == 200:
                text = resp.text.lower()
                if "no longer available" in text or "page not found" in text:
                    return False
                return True
            return None
        except Exception:
            return None
```

- [ ] **Step 9: Implement Google `is_job_live`**

Add to `src/scrapers/google.py` in the `GoogleScraper` class:

```python
    def is_job_live(self, url: str) -> bool | None:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code in (404, 410):
                return False
            if resp.status_code == 200:
                text = resp.text.lower()
                if "no longer available" in text or "not found" in text or len(resp.text) < 500:
                    return False
                return True
            return None
        except Exception:
            return None
```

- [ ] **Step 10: Implement Apple `is_job_live`**

Add to `src/scrapers/apple.py` in the `AppleScraper` class:

```python
    def is_job_live(self, url: str) -> bool | None:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code in (404, 410):
                return False
            if resp.status_code == 200:
                text = resp.text.lower()
                if "no longer available" in text:
                    return False
                return True
            return None
        except Exception:
            return None
```

- [ ] **Step 11: Run all new tests**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_scrapers.py -v -k "is_job_live"`
Expected: All PASS

- [ ] **Step 12: Run full scraper test suite**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_scrapers.py -v`
Expected: All PASS

- [ ] **Step 13: Commit**

```bash
cd /Users/drewmerc/workspace/jobTracker
git add src/scrapers/base.py src/scrapers/greenhouse.py src/scrapers/workday.py src/scrapers/google.py src/scrapers/apple.py tests/test_scrapers.py
# msg: "feat: add is_job_live URL validation to all scrapers"
```

---

### Task 3: Add `closed` status to display/query contexts and fix closed-job filtering

**Files:**
- Modify: `src/steps/obsidian.py:17-24` (STATUS_ORDER)
- Modify: `src/db.py:329-348` (get_all_applications CASE and filter)
- Modify: `src/pipeline.py:510-519` (--list-matches query)
- Modify: `src/pipeline.py:561-571` (--show-all-jobs query)
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Add `closed` to `STATUS_ORDER` in obsidian.py**

In `src/steps/obsidian.py`, change `STATUS_ORDER` (lines 17-24) to include `closed` after `withdrawn`:

```python
STATUS_ORDER = [
    ("interviewing", "Interviewing"),
    ("offer", "Offer"),
    ("applied", "Applied"),
    ("new", "New"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
    ("closed", "Closed"),
]
```

- [ ] **Step 2: Add `closed` to `get_all_applications` CASE and filter closed jobs**

In `src/db.py`, replace `get_all_applications` (lines 329-349) with:

```python
    def get_all_applications(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT m.job_id, j.company, j.title, j.url, j.location, m.relevance_score,
                   COALESCE(a.status, 'new') as status,
                   a.applied_date, a.status_updated_at, a.salary_notes,
                   m.matched_at, m.resume_path, m.cover_letter_path
            FROM matches m
            JOIN jobs j ON m.job_id = j.id
            LEFT JOIN applications a ON m.job_id = a.job_id
            WHERE j.closed_at IS NULL
               OR COALESCE(a.status, 'new') IN ('applied', 'interviewing', 'offer', 'closed')
            ORDER BY
                CASE COALESCE(a.status, 'new')
                    WHEN 'interviewing' THEN 1
                    WHEN 'offer' THEN 2
                    WHEN 'applied' THEN 3
                    WHEN 'new' THEN 4
                    WHEN 'closed' THEN 5
                    WHEN 'rejected' THEN 6
                    WHEN 'withdrawn' THEN 7
                END,
                m.relevance_score DESC
        """).fetchall()
        return [dict(r) for r in rows]
```

Note: The WHERE clause keeps closed jobs visible in the dashboard IF the user had an active application or was marked `closed` — this way the user can see their `closed` applications. Jobs that were closed without any application are hidden.

- [ ] **Step 3: Fix `--list-matches` query to filter closed jobs**

In `src/pipeline.py`, find the `--list-matches` SQL query (~line 511) and add the `closed_at` filter. Change:

```sql
FROM matches m JOIN jobs j ON m.job_id = j.id
LEFT JOIN applications a ON m.job_id = a.job_id
ORDER BY m.relevance_score DESC
```

To:

```sql
FROM matches m JOIN jobs j ON m.job_id = j.id
LEFT JOIN applications a ON m.job_id = a.job_id
WHERE j.closed_at IS NULL
ORDER BY m.relevance_score DESC
```

- [ ] **Step 4: Fix `--show-all-jobs` query to filter closed jobs**

In `src/pipeline.py`, find the `--show-all-jobs` SQL query (~line 563) and add the filter. Change:

```sql
SELECT m.job_id FROM matches m
JOIN jobs j ON m.job_id = j.id
WHERE m.relevance_score >= ?
ORDER BY m.relevance_score DESC
```

To:

```sql
SELECT m.job_id FROM matches m
JOIN jobs j ON m.job_id = j.id
WHERE m.relevance_score >= ?
  AND j.closed_at IS NULL
ORDER BY m.relevance_score DESC
```

- [ ] **Step 5: Run full test suite for regressions**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/drewmerc/workspace/jobTracker
git add src/steps/obsidian.py src/db.py src/pipeline.py
# msg: "fix: filter closed jobs from all listing queries, add closed status"
```

---

### Task 4: Wire `--prune-stale` flag and pruning logic in pipeline

**Files:**
- Modify: `src/pipeline.py` (argparse, new handler before `--list-matches`)
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test for `--prune-stale` arg parsing**

Add to `tests/test_pipeline.py`:

```python
def test_parse_args_prune_stale():
    args = parse_args(["--prune-stale"])
    assert args.prune_stale is True


def test_parse_args_prune_stale_default():
    args = parse_args([])
    assert args.prune_stale is False


def test_parse_args_prune_stale_with_list_matches():
    args = parse_args(["--list-matches", "--prune-stale"])
    assert args.prune_stale is True
    assert args.list_matches is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_pipeline.py -v -k "prune_stale"`
Expected: FAIL with `AttributeError: Namespace has no attribute 'prune_stale'`

- [ ] **Step 3: Add `--prune-stale` flag to argparse**

In `src/pipeline.py`, add after the `--fresh` argument (before `return parser.parse_args(argv)`):

```python
    parser.add_argument(
        "--prune-stale",
        action="store_true",
        help="Validate job listing URLs and close dead listings. Works standalone or with --list-matches.",
    )
```

- [ ] **Step 4: Run arg parsing tests**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_pipeline.py -v -k "prune_stale"`
Expected: All PASS

- [ ] **Step 5: Write integration test for pruning logic**

Add to `tests/test_pipeline.py`:

```python
def test_prune_stale_closes_dead_jobs_and_alerts_on_applied(tmp_path, monkeypatch, capsys):
    """Prune logic should close dead jobs and alert when applied jobs are closed."""
    from unittest.mock import MagicMock, patch
    from src.db import Database
    from src.config import Config
    from datetime import datetime, timezone

    db = Database(tmp_path / "prune_test.db")
    now = datetime.now(timezone.utc)

    # Insert two jobs: one dead (applied), one live
    db.upsert_job(id="Stripe:dead", company="Stripe", title="Dead EM",
                  url="https://dead.example.com", location="NYC", remote=False,
                  salary=None, description="test", department=None, seniority=None,
                  scraped_at=now)
    db.upsert_job(id="Stripe:live", company="Stripe", title="Live EM",
                  url="https://live.example.com", location="NYC", remote=False,
                  salary=None, description="test", department=None, seniority=None,
                  scraped_at=now)

    # Create matches
    db.insert_match(job_id="Stripe:dead", relevance_score=0.9, match_reason="test")
    db.insert_match(job_id="Stripe:live", relevance_score=0.9, match_reason="test")

    # Mark dead job as applied
    db.set_application_status("Stripe:dead", "applied")

    # Mock scraper that returns False for dead, True for live
    mock_scraper = MagicMock()
    mock_scraper.company_name = "Stripe"
    def is_job_live(url):
        return False if "dead" in url else True
    mock_scraper.is_job_live = is_job_live

    with patch("src.pipeline.build_scrapers", return_value=[mock_scraper]), \
         patch("src.steps.obsidian.write_application_note"), \
         patch("src.steps.obsidian.write_dashboard"):
        from src.pipeline import run_pipeline, parse_args
        args = parse_args(["--prune-stale"])
        monkeypatch.setattr("src.pipeline.Config", lambda: MagicMock(db_path=tmp_path / "prune_test.db"))
        # Run directly with patched config
        # Actually, call the handler logic more directly via run_pipeline
        # This is complex to wire up — at minimum verify the DB state
        pass

    # Verify dead job was closed
    job = db.get_job("Stripe:dead")
    assert job["closed_at"] is not None

    # Verify live job was NOT closed
    job = db.get_job("Stripe:live")
    assert job["closed_at"] is None

    # Verify applied job status changed to closed
    app = db.get_application("Stripe:dead")
    assert app["status"] == "closed"
```

Note: The implementer should wire this test to actually call the pruning handler through `run_pipeline` or extract the prune logic into a testable function. The exact mocking approach depends on how `Config` and DB are initialized. The key assertions above define what the test must verify.

- [ ] **Step 6: Add the pruning handler to `run_pipeline`**

In `src/pipeline.py`, add a new handler block just before the `if args.list_matches:` block. This handler should run when `--prune-stale` is passed (standalone or with `--list-matches`):

```python
    if args.prune_stale:
        import time as _time
        scrapers = build_scrapers(config)
        scraper_map = {s.company_name: s for s in scrapers}

        # Get all open matches
        rows = db._conn.execute("""
            SELECT m.job_id, j.company, j.title, j.url,
                   COALESCE(a.status, 'new') as app_status
            FROM matches m
            JOIN jobs j ON m.job_id = j.id
            LEFT JOIN applications a ON m.job_id = a.job_id
            WHERE j.closed_at IS NULL
            ORDER BY j.company, m.relevance_score DESC
        """).fetchall()

        pruned = 0
        active_closed = 0
        current_company = None
        for row in rows:
            job_id = row["job_id"]
            company = row["company"]
            title = row["title"]
            url = row["url"]
            app_status = row["app_status"]

            scraper = scraper_map.get(company)
            if not scraper:
                print(f"Skipped (no scraper): {company} — {title}")
                continue

            # Rate limit: 0.5s delay between requests to same company
            if company == current_company:
                _time.sleep(0.5)
            current_company = company

            result = scraper.is_job_live(url)
            if result is False:
                db.close_job(job_id)
                if app_status in ("applied", "interviewing"):
                    db.set_application_status(job_id, "closed")
                    print(f"\u26a0 CLOSED: {company} — {title} (status was: {app_status})")
                    from src.steps.obsidian import write_application_note
                    write_application_note(job_id, db, config)
                    active_closed += 1
                else:
                    print(f"Pruned: {company} — {title}")
                pruned += 1
            elif result is None:
                print(f"Skipped (unreachable): {company} — {title}")

        # Update dashboard if any active applications were closed
        if active_closed > 0:
            from src.steps.obsidian import write_dashboard
            write_dashboard(db, config)

        print(f"\nPruned {pruned} jobs ({active_closed} with active applications)")

        if not args.list_matches:
            return
```

- [ ] **Step 7: Run full test suite**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/drewmerc/workspace/jobTracker
git add src/pipeline.py tests/test_pipeline.py
# msg: "feat: add --prune-stale flag for validating job listing URLs"
```

---

### Task 5: Manual smoke test

**Files:** None (verification only)

- [ ] **Step 1: Verify `--list-matches` filters closed jobs**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --list-matches`

Expected: Output should NOT include any jobs that have `closed_at` set. Compare count with a direct DB query:

```bash
cd /Users/drewmerc/workspace/jobTracker && uv run python -c "
from src.db import Database; from src.config import Config
db = Database(Config().db_path)
total = db._conn.execute('SELECT COUNT(*) FROM matches').fetchone()[0]
closed = db._conn.execute('SELECT COUNT(*) FROM matches m JOIN jobs j ON m.job_id = j.id WHERE j.closed_at IS NOT NULL').fetchone()[0]
print(f'Total matches: {total}, Closed: {closed}, Should show: {total - closed}')
"
```

- [ ] **Step 2: Run `--prune-stale` standalone**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --prune-stale`

Expected: Iterates all open matches, prints results for each (Pruned/Skipped/nothing for live jobs), shows summary at end. Dead listings should be closed.

- [ ] **Step 3: Run `--prune-stale` again to verify idempotence**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --prune-stale`

Expected: Fewer or no jobs to prune (already closed on previous run).

- [ ] **Step 4: Verify `--list-matches --prune-stale` combo**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --list-matches --prune-stale`

Expected: Prune runs first, then listing output shows only live jobs.

- [ ] **Step 5: Verify closed applied job triggers alert and Obsidian update**

If any applied jobs were pruned in step 2, verify:
- Terminal showed `⚠ CLOSED: Company — Title (status was: applied)`
- Check Obsidian note was updated: the note should show `closed` status
- Check dashboard was updated

If no applied jobs were pruned, manually verify by checking the Obsidian dashboard for any `closed` entries.
