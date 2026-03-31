# Job Tracker — Design Specification

**Date**: 2026-03-30
**Status**: Approved
**Author**: Drew Mercurio + Claude

## Overview

A Python application that monitors career pages at target companies every 12 hours, identifies engineering manager roles relevant to Drew's profile, tailors his resume and generates cover letters for each match, and sends an email digest with analysis and attachments.

## Target Companies (Verified 2026-03-30)

| Company | Backend | API Endpoint | Method | Jobs | JD in list? |
|---------|---------|-------------|--------|------|-------------|
| Dropbox | Greenhouse | `boards-api.greenhouse.io/v1/boards/dropbox/jobs?content=true` | GET | ~93 | Yes |
| DataDog | Greenhouse | `boards-api.greenhouse.io/v1/boards/datadog/jobs?content=true` | GET | ~464 | Yes |
| Capital One | Workday (wd12) | `capitalone.wd12.myworkdayjobs.com/wday/cxs/capitalone/Capital_One/jobs` | POST | ~1,458 | No (detail fetch) |
| Stripe | Greenhouse | `boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true` | GET | ~509 | Yes |

**Notes:**
- All 4 sites have unauthenticated JSON APIs. No headless browser needed.
- 3 of 4 are Greenhouse with identical API shape — single parameterized scraper covers Dropbox, DataDog, and Stripe.
- Capital One (Workday CXS) is POST-based, paginated at max 20 results/page, requires a per-job detail fetch for full JD. Cloudflare bot management in front — use moderate request rates.
- DataDog's metadata includes an `IC or MG` field useful for pre-filtering manager roles before LLM evaluation.
- Stripe's Greenhouse board (509 jobs) may not include all listings shown on stripe.com (891) — multi-location dupes or alternate channels. Greenhouse is sufficient for our purposes.

## Architecture

Pipeline-based batch application with 4 discrete steps that pass data forward. Each step can be run independently for debugging and re-runs.

```
scrape → filter → tailor → notify
```

Scheduled via macOS launchd (every 12 hours). Uses the Anthropic Python SDK for LLM calls and SMTP with a Gmail app password for email delivery.

## Project Structure

```
jobTracker/
├── src/
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py           # Abstract scraper interface + RawJob dataclass
│   │   ├── greenhouse.py     # Shared scraper for Dropbox, DataDog, Stripe
│   │   └── workday.py        # Capital One (Workday CXS API)
│   ├── steps/
│   │   ├── scrape.py         # Run all scrapers, output raw jobs
│   │   ├── filter.py         # Keyword pre-filter + LLM evaluation
│   │   ├── tailor.py         # Resume reorder/suggest + cover letter
│   │   └── notify.py         # Build HTML digest + send email
│   ├── db.py                 # SQLite: seen jobs, run history
│   ├── config.py             # Company URLs, keywords, email, API key
│   └── pipeline.py           # Orchestrates steps in sequence
├── templates/
│   └── digest.html           # Jinja2 email template
├── run.sh                    # Wrapper script for launchd
├── launchd/
│   └── com.drewmerc.jobtracker.plist
├── data/                     # SQLite DB lives here (gitignored)
├── output/                   # Generated PDFs/cover letters per run (gitignored)
├── pyproject.toml
└── .env                      # ANTHROPIC_API_KEY, SMTP creds (gitignored)
```

## Dependencies

Managed via `uv`:

- `anthropic` — LLM calls for filtering and resume analysis
- `httpx` — HTTP client for all career site APIs (Greenhouse + Workday)
- `jinja2` — email template rendering
- `python-dotenv` — environment variable loading
- `sqlite3` — stdlib, no install needed
- `typst` — system dependency (installed via `brew install typst`), required by resume/cover letter PDF compilation
- Resume skills invoked via `subprocess` (`uv run` into existing scripts)

## Component Design

### 1. Scraper Layer

Each scraper implements a common interface:

```python
@dataclass
class RawJob:
    external_id: str          # Platform-specific ID (e.g. Greenhouse job ID, Workday requisition ID)
    company: str
    title: str
    url: str
    location: str | None
    remote: bool | None
    salary: str | None
    description: str | None   # Full JD text; nullable if detail fetch fails
    department: str | None
    seniority: str | None
    scraped_at: datetime

    @property
    def db_id(self) -> str:
        """Primary key for the jobs table: 'company:external_id'"""
        return f"{self.company}:{self.external_id}"

class BaseScraper(ABC):
    @abstractmethod
    def fetch_jobs(self) -> list[RawJob]: ...
```

**External ID sourcing per site:**

| Site | ID Source |
|------|-----------|
| Dropbox (Greenhouse) | `job.id` from Greenhouse API JSON (numeric) |
| DataDog (Greenhouse) | `job.id` from Greenhouse API JSON (numeric) |
| Stripe (Greenhouse) | `job.id` from Greenhouse API JSON (numeric) |
| Capital One (Workday) | `bulletFields[0]` requisition ID (e.g. "R239042") |

**Scraper implementations:**

**`greenhouse.py`** — Single parameterized scraper for Dropbox, DataDog, and Stripe:
- Endpoint: `GET https://boards-api.greenhouse.io/v1/boards/{board_slug}/jobs?content=true`
- Returns all jobs in a single request with full HTML descriptions, departments, and offices
- No auth, no pagination needed
- Fields mapped: `id` → `external_id`, `title`, `absolute_url` → `url`, `location.name` → `location`, `content` → `description` (HTML), `departments[0].name` → `department`, `metadata` → extract seniority/remote where available
- DataDog bonus: `metadata` array includes `IC or MG` field — extract and map to `seniority`
- Instantiated 3 times with different board slugs in config

**`workday.py`** — Capital One scraper:
- Search: `POST https://capitalone.wd12.myworkdayjobs.com/wday/cxs/capitalone/Capital_One/jobs` with JSON body `{"appliedFacets": {}, "limit": 20, "offset": N, "searchText": "manager"}` (pre-filters to reduce ~1500 → ~200 results)
- Paginate through all results (max 20 per page, ~73 pages for current volume)
- Detail: `GET https://capitalone.wd12.myworkdayjobs.com/wday/cxs/capitalone/Capital_One/job/{externalPath}` for full JD
- Can pre-filter with `appliedFacets.jobFamilyGroup` for Technology roles to reduce pagination volume
- Fields mapped: `bulletFields[0]` → `external_id`, `title`, `locationsText` → `location`, `jobDescription` → `description` (from detail), `timeType`
- Cloudflare bot management in front — use 1-2 second delays between requests

Each scraper returns `list[RawJob]`. If a scraper fails, it logs the error and the pipeline continues with remaining sites.

The `description` field contains the full JD text needed for LLM evaluation. For Greenhouse sites it's included in the list response. For Capital One, a detail fetch per job is required. If the detail fetch fails for a specific job, `description` is set to `None` and the job is still stored but skipped during LLM filtering (logged as a warning).

**HTTP resilience**: Scrapers use `httpx` with retry (3 attempts, exponential backoff) and a 30-second timeout. Requests include a browser-like `User-Agent` header. A 1-second delay between requests to the same host avoids rate limiting (especially important for Capital One's Cloudflare-protected Workday endpoint).

### 2. Database & State

Single SQLite database at `data/jobtracker.db`.

**`jobs` table** — every job ever seen:

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | `company:external_id` |
| company | TEXT | |
| title | TEXT | |
| url | TEXT | |
| location | TEXT | nullable |
| remote | BOOLEAN | nullable |
| salary | TEXT | nullable |
| description | TEXT | nullable; jobs without description skipped during filtering |
| department | TEXT | nullable |
| seniority | TEXT | nullable |
| first_seen_at | DATETIME | |
| last_seen_at | DATETIME | updated each run |
| closed_at | DATETIME | set when job disappears |

**`matches` table** — jobs that passed LLM filter:

| Column | Type | Notes |
|--------|------|-------|
| job_id | TEXT PK FK | references jobs(id), one match per job |
| relevance_score | FLOAT | 0.0–1.0 |
| match_reason | TEXT | LLM explanation |
| resume_path | TEXT | path to tailored PDF |
| cover_letter_path | TEXT | path to cover letter PDF |
| suggestions | TEXT | JSON: resume edit suggestions |
| matched_at | DATETIME | |
| notified_at | DATETIME | set when emailed |

**`runs` table** — audit log:

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| started_at | DATETIME | |
| completed_at | DATETIME | |
| jobs_scraped | INTEGER | |
| new_jobs | INTEGER | |
| matches_found | INTEGER | |
| email_sent | BOOLEAN | |
| error | TEXT | null on success |

**Dedup logic**: After scraping, check each job's `db_id` against the `jobs` table. Only new jobs proceed to the filter step. Existing jobs get their `last_seen_at` updated.

**Closure detection**: Only mark a job as closed if its scraper succeeded this run AND the job was not in the results. If a scraper failed/errored, skip closure detection for that company entirely to avoid false positives from transient failures.

### 3. Filter Pipeline

**Step 1 — Keyword pre-filter** on title (case-insensitive, partial match):

```
engineering manager, manager of engineering,
director of engineering, head of engineering,
software engineering manager, technical manager,
engineering lead, development manager
```

Seniority exclusions (when available): Staff, Principal, VP, C-level, Junior, Associate, Intern.

**Step 2 — LLM evaluation** on short list. For each job passing keyword filter:

- Model: `claude-sonnet-4-6`
- Structured output: Use Anthropic SDK `tool_use` with a defined tool schema to guarantee valid JSON responses
- Input: job title, company, description, location, salary + candidate summary from resume YAML
- Output (structured JSON via tool_use):
  ```json
  {
    "relevant": true,
    "score": 0.85,
    "reason": "Strong match for EM role with team scaling experience",
    "key_requirements": ["team scaling", "cross-functional leadership"],
    "interview_talking_points": ["Led 3x team growth at Capital One"]
  }
  ```
- Threshold: score >= 0.6 passes to tailor step

Keyword list, seniority exclusions, and score threshold all configurable in `config.py`.

### 4. Resume Tailoring

**Source**: Active resume YAML, resolved by reading `~/.resume_versions/projects/drewmercResume/project.json` → `active_version` field (currently `v7`), then loading `~/.resume_versions/projects/drewmercResume/versions/v7_ai_workflow_story/resume.yaml`. Alternatively, invoke the existing `get_active.py` script from the resume-state skill: `uv run --directory /Users/drewmerc/.claude/plugins/marketplaces/resume-helper-skills/resume-state scripts/get_active.py` which returns the active YAML path.

**Part A — LLM Analysis** (Anthropic API):

Input: resume YAML + job description. Output (structured JSON):
```json
{
  "reordered_bullets": {
    "Company Name - Role Title": ["bullet3", "bullet1", "bullet2"]
  },
  "suggested_edits": [
    {
      "original": "Led team of 8 engineers...",
      "suggested": "Led cross-functional team of 8 engineers...",
      "reason": "JD emphasizes cross-functional collaboration"
    }
  ],
  "keyword_gaps": ["distributed systems", "OKR planning"]
}
```

**Part B — PDF Generation**:
1. Create temp copy of resume YAML with bullets reordered (original wording preserved)
2. Call existing formatter scripts via subprocess:
   - `uv run --directory /Users/drewmerc/.claude/plugins/marketplaces/resume-helper-skills/resume-formatter scripts/yaml_to_typst.py <yaml_path> executive -o <output.typ>`
   - `uv run --directory /Users/drewmerc/.claude/plugins/marketplaces/resume-helper-skills/resume-formatter scripts/compile_typst.py <output.typ>`
3. Output: `output/<run_date>/<company>_<job_id>/resume.pdf`

Suggested edits are NOT applied to the PDF — they appear in the email digest for human review.

### 5. Cover Letter Generation

Reuses existing resume-coverletter scripts via subprocess:
1. Write job description to temp file at `output/<run_date>/<company>_<job_id>/job_description.txt`
2. Generate:
   ```
   uv run --directory /Users/drewmerc/.claude/plugins/marketplaces/resume-helper-skills/resume-coverletter \
     scripts/generate_cover_letter.py <resume.yaml> \
     --template executive-cover \
     --company "Company Name" \
     --position "Job Title" \
     --job-file <job_description.txt> \
     --output <cover_letter.typ>
   ```
3. Compile:
   ```
   uv run --directory /Users/drewmerc/.claude/plugins/marketplaces/resume-helper-skills/resume-coverletter \
     scripts/compile_cover_letter.py <cover_letter.typ> --output <cover_letter.pdf>
   ```
4. Output: `output/<run_date>/<company>_<job_id>/cover_letter.pdf`

### 6. Email Digest

**Sending**: Python `smtplib` + `email.mime`, Gmail app password from `.env`. From address: `SMTP_USER` (same as auth username). Sent to `andrew.m.mercurio@gmail.com`.

**Always sends** — even when no matches are found (confirms system is running).

**No-match email**: Subject "Job Tracker: No new matches — {date}", body contains run stats only.

**Match email structure**:
- Subject: `Job Tracker: {N} new matches found — {date}`
- Summary table: company, title, location, salary, relevance score
- Per-job sections:
  - Why this matches (LLM reason)
  - Key requirements from JD
  - Interview talking points
  - Suggested resume edits with reasoning
  - Keyword gaps
  - Attached: tailored resume PDF + cover letter PDF (individual MIME attachments, named `<company>_<title>_resume.pdf` and `<company>_<title>_cover_letter.pdf`)
- Footer: run stats (jobs scraped, new jobs, matches, execution time)

Template: Jinja2 HTML at `templates/digest.html`.

### 7. Scheduling

macOS launchd plist at `~/Library/LaunchAgents/com.drewmerc.jobtracker.plist`:

- `StartInterval`: 43200 (12 hours)
- `RunAtLoad`: true (fires on login/reboot)
- `KeepAlive`: false (batch job, not daemon)
- Logs: `data/logs/stdout.log`, `data/logs/stderr.log` (truncated to last 1MB by `run.sh` before each run)

Wrapper script `run.sh`:
```bash
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd /Users/drewmerc/workspace/jobTracker
uv run jobtracker 2>&1
```

The `PATH` export is required because launchd runs with a minimal environment — `uv`, `typst`, and other Homebrew tools won't be found otherwise.

Install: `launchctl load ~/Library/LaunchAgents/com.drewmerc.jobtracker.plist`

## Configuration

All tunable values in `config.py` / `.env`:

| Setting | Location | Default |
|---------|----------|---------|
| ANTHROPIC_API_KEY | .env | — |
| SMTP_USER | .env | — |
| SMTP_PASSWORD | .env | — (Gmail app password) |
| EMAIL_TO | config.py | andrew.m.mercurio@gmail.com |
| KEYWORD_PATTERNS | config.py | [list above] |
| SENIORITY_EXCLUSIONS | config.py | [list above] |
| RELEVANCE_THRESHOLD | config.py | 0.6 |
| LLM_MODEL | config.py | claude-sonnet-4-6 |
| RESUME_VERSIONS_PATH | config.py | ~/.resume_versions |
| RESUME_PROJECT | config.py | drewmercResume |
| DB_PATH | config.py | data/jobtracker.db |

## CLI Flags

The pipeline supports these flags when run directly:

| Flag | Description |
|------|-------------|
| `--dry-run` | Run scrape + filter only; skip tailor + notify. Useful for testing scrapers without burning LLM tokens on resume generation. |
| `--renotify` | Re-send the digest for the most recent run that had matches but failed to send email (i.e., `matches_found > 0` and `email_sent = false`). |
| `--step <name>` | Run a single step (scrape, filter, tailor, notify) using cached data from the most recent run. |

## Error Handling

- Individual scraper failures don't block the pipeline — logged and skipped
- LLM API errors: retry with exponential backoff (3 attempts), then skip that job
- Resume/cover letter generation failure: log error, include job in digest without attachments
- SMTP failure: log error, pipeline still records the run (can re-send next run)
- All errors surfaced in the `runs` table `error` column

## Future Considerations (Not in Scope)

- Web dashboard for browsing job history
- Additional companies (easy to add — implement new scraper)
- Slack notifications alongside email
- Auto-apply (intentionally excluded — always human in the loop)
