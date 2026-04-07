# Prune Stale Job Listings

## Problem

`--list-matches` shows all matches including jobs that have been closed (where `closed_at IS NOT NULL`). Additionally, the 12-hour scrape cycle can miss closures between runs, so a user may waste time researching a listing only to find the job page is a dead end.

## Goal

1. Fix all job listing queries (`--list-matches`, `--show-all-jobs`, `--applications`) to filter out closed jobs by default.
2. Add `--prune-stale` flag that actively validates job URLs against their ATS platforms and closes dead listings.
3. When a pruned job had an active application (`applied` or `interviewing`), alert the user, update the application status to `closed`, update the Obsidian note and dashboard.

## Design

### URL Validation: `is_job_live` on `BaseScraper`

New **concrete** method on `BaseScraper` with a default implementation that returns `None` (ambiguous/skip). Subclasses override with ATS-specific logic. This means new scrapers gracefully degrade — they just skip validation rather than crashing.

```python
def is_job_live(self, url: str) -> bool | None:
    """Check if a job listing URL is still live.
    Returns True (live), False (dead), None (ambiguous/unsupported).
    """
    return None
```

Returns:
- `True` — job page is live
- `False` — job is confirmed dead (404, redirect to generic page, "no longer available" text)
- `None` — ambiguous (timeout, 5xx, connection error, or scraper doesn't implement validation) — skip, don't close

**Per-scraper implementations:**

- **Greenhouse** (Stripe, Dropbox, DataDog, GitLab): GET the URL. 404/410 → `False`. 200 with content → `True`.
- **Workday** (Capital One): GET the URL. Inspect response body (Workday is a SPA — JS redirects won't be followed by httpx, so check the HTML body for "no longer available" or similar markers). 200 with dead markers → `False`. 200 with job details → `True`.
- **Google**: GET the URL. 200 with empty/error content or "no longer available" → `False`. 200 with job data → `True`.
- **Apple**: GET the URL. 200 with "This position is no longer available" → `False`. 200 with job content → `True`.
- **All scrapers**: 5xx, timeout, connection error → `None`. Wrap each GET in a try/except.

Each implementation is a simple HTTP GET with response inspection. Use `httpx` with a 10s timeout. No retries.

**Rate limiting:** Add a small delay (0.5s) between requests to the same domain to avoid being rate-limited or blocked. Group checks by company so requests to the same ATS are spaced out.

### New DB Method: `close_job(job_id)`

The existing `close_missing_jobs(company, current_ids)` is a batch operation. A new single-job close method is needed:

```python
def close_job(self, job_id: str):
    now = datetime.now(timezone.utc).isoformat()
    self._conn.execute(
        "UPDATE jobs SET closed_at = ? WHERE id = ? AND closed_at IS NULL",
        (now, job_id),
    )
    self._conn.commit()
```

### Company-to-Scraper Mapping

`build_scrapers()` in pipeline.py already creates all scraper instances. The prune logic maps a job's company name to its scraper by building a `dict[str, BaseScraper]` from the scraper list using each scraper's `company_name` attribute.

**Important:** The `jobs.company` column must exactly match `scraper.company_name` for the lookup to work. This is guaranteed by the current code since scrapers set `RawJob.company = self.company_name` during scraping.

Jobs whose company has no matching scraper are skipped with a warning.

### `--prune-stale` Flag and Pruning Flow

New argparse flag: `--prune-stale`, boolean, `store_true`. Works standalone or with `--list-matches`.

When `--prune-stale` is invoked:

1. Build scrapers via `build_scrapers(config)`, create company→scraper map
2. Query all open matches (`j.closed_at IS NULL`)
3. For each match (grouped by company, with 0.5s delay between requests):
   a. Look up scraper by company
   b. Call `scraper.is_job_live(job_url)`
   c. If `False` (dead):
      - Close the job via `db.close_job(job_id)`
      - Check if job has an application with status `applied` or `interviewing`
      - If yes:
        - Update application status to `closed`
        - Print warning: `⚠ CLOSED: Company — Title (status was: applied)`
        - Re-render Obsidian job application note via `write_application_note()` (uses existing Jinja template, which will include the `closed` status)
      - If no active application: print `Pruned: Company — Title`
   d. If `None` (ambiguous): print `Skipped (unreachable): Company — Title`
   e. If `True`: no output (job is fine)
4. If any jobs with active applications were closed, call `write_dashboard(db, config)` to update the Obsidian dashboard
5. Print summary: `Pruned N jobs (M with active applications)`
6. If `--list-matches` was also passed, proceed with normal listing output

### New Application Status: `closed`

Add `closed` as a **system-only** status. It is:
- Recognized in display/query contexts (`STATUS_ORDER` in obsidian.py, `CASE` expressions in `get_all_applications`)
- NOT user-settable via `--status` or `--track` commands — the `valid_statuses` lists in those handlers remain unchanged
- Only set programmatically by the prune logic

### Closed Job Query Filter (Bug Fix)

Add `WHERE j.closed_at IS NULL` to these queries:
- `--list-matches` SQL query in pipeline.py (~line 511)
- `--show-all-jobs` SQL query in pipeline.py (~line 562)
- `get_all_applications()` in db.py — filter out closed jobs from the dashboard query

### Obsidian Note Update

When a job with an active application is pruned, call `write_application_note()` (the existing template-based function in obsidian.py). The Jinja template already renders status — the `closed` status will appear naturally in the rendered output. Do NOT use `mcp__obsidian__patch_note` — that would be overwritten on the next template re-render.

After all pruning, call `write_dashboard(db, config)` once to update the dashboard with new statuses.

### Unchanged

- Automated 12-hour pipeline: `close_missing_jobs` continues to work as before
- `--show-job`, `--tailor-job`: no changes

## Error Handling

- Individual URL validation failures don't abort the prune. Each job is checked independently.
- Ambiguous results (`None`) are logged and skipped — no false closures from temporary outages.
- If building scrapers fails, abort with an error before pruning anything.
- Scrapers without an `is_job_live` override gracefully return `None` (skip).
