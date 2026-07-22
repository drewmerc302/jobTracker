This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Launch TUI (default — no flags)
uv run jobtracker

# Run full pipeline via CLI (scrape → dedup → filter → tailor → notify)
uv run jobtracker --dry-run

# Run single step
uv run jobtracker --step scrape|dedup|filter|tailor|notify

# Dry run (scrape + filter only)
uv run jobtracker --dry-run

# Query tools
uv run jobtracker --list-matches
uv run jobtracker --show-job "Stripe:7609424"
uv run jobtracker --show-job "Stripe:7609424" --markdown
uv run jobtracker --show-all-jobs
uv run jobtracker --show-all-jobs --score 80
uv run jobtracker --show-all-jobs --score 80 --markdown > matches.md
uv run jobtracker --tailor-job "Stripe:7609424"
uv run jobtracker --tailor-job "Stripe:7609424" --adopt 1,3,5

# Application tracking
uv run jobtracker --applications
uv run jobtracker --status "Stripe:123" applied
uv run jobtracker --track "Stripe:123"

# Follow-up tracking
uv run jobtracker --follow-ups
uv run jobtracker --set-followup "Stripe:123" 2026-04-07
uv run jobtracker --followed-up "Stripe:123"

# Interview prep
uv run jobtracker --interview-prep "Stripe:123"
uv run jobtracker --interview-prep "Stripe:123" --research

# Tests
uv run pytest
uv run pytest tests/test_filter.py::test_name -v
```

## Architecture

Automated job tracker for engineering manager roles. Scrapes job boards → deduplicates → filters via LLM → tailors resumes/cover letters → sends email digest with PDFs → generates Obsidian notes.

**Data flow:** `scrape.py` → `dedup.py` → `filter.py` → `tailor.py` → `notify.py` + `obsidian.py`

**Pipeline orchestration:** `src/pipeline.py` — CLI arg parsing and step sequencing. Entry point: `main()` registered as `jobtracker` in pyproject.toml. Running with no flags launches the Textual TUI; any CLI flag triggers the old pipeline path for automation/launchd.

### TUI (`src/tui/`)

Textual-based terminal UI with 5 screens: Dashboard (summary cards, recent matches, follow-ups), Matches (sortable/filterable DataTable), Job Detail (analysis, edit checkboxes, PDF auto-open), Applications (grouped by status), Pipeline (run triggers, history). Global navigation via `d/m/a/p/q` keys. All long-running ops (scrape, LLM analysis, PDF generation) run in Textual Workers.

### Steps (`src/steps/`)

- `scrape.py` — concurrent job fetching via `ThreadPoolExecutor`, upserts to DB
- `dedup.py` — merges duplicate jobs by normalized title (`_normalize_title()`, `_score_job()`, `_pick_canonical()`). Preserves application status and match data from the canonical job.
- `filter.py` — keyword pre-filter + Claude Haiku LLM evaluation (threshold: 0.6), writes to `matches` table. Uses `evaluate_job` tool schema.
- `tailor.py` — Claude Sonnet analysis via `resume_analysis` tool, bullet reordering, suggested edits, PDF generation via external formatter scripts. `--adopt` flag selectively applies LLM-suggested edits before PDF generation.
- `notify.py` — renders `templates/digest.html` Jinja2 template (includes follow-up reminders with overdue badges), sends via Gmail SMTP with PDF attachments.
- `obsidian.py` — generates Markdown notes from `templates/application.md` and `dashboard.md`. Pushes to Obsidian vault via MCP (`claude mcp call obsidian read_note/write_note`).
- `interview_prep.py` — LLM-generated interview prep (STAR stories, talking points, likely questions, red flags). Patches into existing Obsidian application notes.

### Scrapers (`src/scrapers/`)

All extend `BaseScraper` (ABC) from `base.py` and return `RawJob` dataclass instances. All use `tenacity` retry (3 attempts, exponential backoff).

| Scraper | File | Companies | Method |
|---------|------|-----------|--------|
| Greenhouse | `greenhouse.py` | Dropbox, DataDog, Stripe, GitLab | REST API (`boards-api.greenhouse.io`) |
| Workday | `workday.py` | Capital One, Netflix | HTTP pagination (20/page) + detail fetch |
| Apple | `apple.py` | Apple | SSR hydration data parsing from `jobs.apple.com` |
| Google | `google.py` | Google | `AF_initDataCallback` extraction from HTML |

### Database

SQLite at `data/jobtracker.db` with WAL mode. Schema in `src/db.py` with auto-migration support.

**Tables:**
- `jobs` — scraped job listings (company, title, url, location, remote, salary, description, department, seniority, timestamps)
- `matches` — LLM-evaluated matches (relevance_score, match_reason, resume/cover letter paths, suggestions JSON)
- `applications` — tracked applications (status enum: new/applied/interviewing/offer/rejected/withdrawn, follow_up_after, followed_up_at)
- `status_history` — audit log of all application status changes
- `runs` — pipeline execution metadata (job counts, timing, errors)

### Config

`src/config.py` — `Config` dataclass loading `.env` credentials. Defines:
- Keyword patterns and seniority exclusions (`matches_keyword()`, `is_seniority_excluded()`)
- Location acceptors (`is_location_acceptable()`)
- LLM models: Claude Haiku 4.5 (filter), Claude Sonnet 4.6 (tailor/interview prep)
- Company board URLs and Workday tenant configs
- Relevance threshold (0.6)

### Templates (`templates/`)

- `digest.html` — email digest with match cards, relevance scores as percentages, "Follow Up Today" section with overdue badges
- `application.md` — per-job Obsidian note (company, score, requirements, salary, status)
- `dashboard.md` — Obsidian dashboard grouped by application status

## Key Conventions

**Job ID format:** `"{company}:{external_id}"` — used throughout CLI and DB foreign keys.

**LLM calls:** All use Claude `tool_use` with forced tool choice. Tool schemas defined as module-level constants (`EVAL_TOOL`, `ANALYSIS_TOOL`, `PREP_TOOL`). Wrapped with `tenacity` retry (3 attempts, exponential backoff). Different exceptions caught per context: `anthropic.APIError` for LLM, `httpx.HTTPError` for HTTP.

**DB pattern:** `sqlite3.Row` objects (dict-like access). Always `commit()` after writes. Upsert on conflict for `jobs` table. Batch queries use 500-item chunks for large ID lists.

**Resume source:** YAML loaded via the `resumekit` package (`../resumekit`, editable path dependency). `Store.open(...).project(...).version()` resolves the active version by exact id — never glob `{active_version}*`, which matches v1/v10/v11 alike. Contains `summary`, `skills`, `experience[]` (company, title, bullets, achievements).

**PDF generation:** `resumekit.render_resume(yaml, template, out)` compiles data-driven Typst templates (`drew-executive`, `drew-cover`). Templates read the YAML at compile time, so there is no generated `.typ` to keep in sync; `*.build.typ` beside the PDF is a disposable copy of the template. A missing font raises `MissingFontError` rather than silently falling back to a serif face. Do not shell out to `~/.claude/plugins/*/resume-*/scripts/` — that pipeline is retired.

**Output artifacts:** Generated PDFs written to `output/` organized by date/company.

**Obsidian vault path:** `Topics/Job Applications/{company} — {title}.md` for notes, `Topics/Job Applications/Dashboard.md` for dashboard.

**Scraper fragility:** Workday (Capital One, Netflix) and Apple scrapers are brittle — URL formats, auth flows, and path construction break silently. After any scraper change, test against real data (`uv run jobtracker --step scrape`) and verify job counts are plausible. Outline approach and failure points before writing scraper code.

**Testing:** pytest with JSON fixtures in `tests/fixtures/` (Greenhouse, Workday mock responses). 12 test modules covering all components. No CI pipeline configured — tests run locally.

**Scheduling:** macOS launchd runs pipeline every 12 hours via `run.sh` (includes log rotation at 1MB).

## Project Layout

```
src/
├── __init__.py
├── config.py          # Config dataclass, env loading, keyword patterns
├── db.py              # SQLite wrapper, schema, migrations
├── pipeline.py        # CLI entry point, step orchestration, TUI routing
├── tui/
│   ├── app.py         # JobTrackerApp main class, global keybindings
│   ├── styles.tcss    # Textual CSS theme (GitHub dark)
│   ├── screens/       # Dashboard, Matches, JobDetail, Applications, Pipeline
│   └── widgets/       # StatusPopup modal
├── scrapers/
│   ├── base.py        # RawJob dataclass, BaseScraper ABC
│   ├── greenhouse.py  # Greenhouse REST API scraper
│   ├── workday.py     # Workday pagination scraper
│   ├── apple.py       # Apple SSR hydration parser
│   └── google.py      # Google AF_initDataCallback parser
└── steps/
    ├── scrape.py      # Concurrent scraper runner
    ├── dedup.py       # Duplicate job merging
    ├── filter.py      # Keyword + LLM relevance filter
    ├── tailor.py      # Resume analysis + PDF generation
    ├── notify.py      # Email digest sender
    ├── obsidian.py    # Obsidian note generation (MCP)
    └── interview_prep.py  # LLM interview prep generator
templates/             # Jinja2 templates (digest.html, application.md, dashboard.md)
tests/                 # pytest suite with fixtures/
hooks/                 # Git hooks (commit-msg: strip ANSI codes)
launchd/               # macOS scheduling config
```

## Dependencies

Python 3.12+. Key packages: `anthropic`, `httpx`, `jinja2`, `python-dotenv`, `pyyaml`, `tenacity`. Dev: `pytest`. Managed via `uv` (see `pyproject.toml` and `uv.lock`).

# Working Agreements

## Pre-Work

**Step 0 — clear the dead wood.** Before any structural refactor of a file over 300 LOC, first remove dead props, unused exports, unused imports, and debug logs, and commit that cleanup on its own. Reviewing a refactor is far harder when deletions and restructuring land together.

**Phase multi-file refactors.** Break work into explicit phases of no more than 5 files. Complete a phase, run verification, and check in before starting the next.

## Verification

**A task is not done until it is verified.** Before reporting completion:

- `uv run python -m py_compile src/<file>.py` for each changed file
- `uv run pytest` to confirm no regressions
- Fix everything that surfaces

No type-checker (mypy) is configured, so `py_compile` plus the test suite is the whole safety net. Report failures as failures — never describe unverified work as working.

## Renaming

**grep is not an AST.** When renaming a function, type, or variable, search separately for each of:

- Direct calls and references
- Type-level references (interfaces, generics)
- String literals containing the name
- Dynamic imports and `require()` calls
- Re-exports and barrel file entries
- Test files and mocks

One grep does not catch all six.
