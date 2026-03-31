# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run full pipeline
uv run jobtracker

# Run single step
uv run jobtracker --step scrape|filter|tailor|notify

# Dry run (scrape + filter only)
uv run jobtracker --dry-run

# Query tools
uv run jobtracker --list-matches
uv run jobtracker --show-job "Stripe:7609424"
uv run jobtracker --tailor-job "Stripe:7609424"

# Application tracking
uv run jobtracker --applications
uv run jobtracker --status "Stripe:123" applied
uv run jobtracker --track "Stripe:123"

# Tests
uv run pytest
uv run pytest tests/test_filter.py::test_name
```

## Architecture

Automated job tracker for engineering manager roles. Scrapes job boards → filters via LLM → tailors resumes/cover letters → sends email digest with PDFs.

**Data flow:** `scrape.py` → `filter.py` → `tailor.py` → `notify.py` + `obsidian.py`

**Pipeline orchestration:** `src/pipeline.py` — CLI arg parsing and step sequencing.

**Steps** (`src/steps/`):
- `scrape.py` — fetches jobs from all configured boards, upserts to DB
- `filter.py` — keyword pre-filter + Claude Haiku LLM evaluation (threshold: 0.6), writes to `matches` table
- `tailor.py` — Claude Sonnet analysis, bullet reordering, PDF generation via external formatter scripts
- `notify.py` — renders `templates/digest.html` Jinja2 template, sends via Gmail SMTP
- `obsidian.py` — generates Markdown notes from `templates/application.md` and `dashboard.md`

**Scrapers** (`src/scrapers/`): Greenhouse and Workday implementations extending `base.py`.

**Database:** SQLite at `data/jobtracker.db` with WAL mode. Tables: `jobs`, `matches`, `applications`, `runs`, `status_history`. See `src/db.py` for schema.

**Config:** `src/config.py` loads `.env` credentials and defines keyword patterns, location filters, LLM models, company/board configs. Central place for tuning filter behavior.

## Key Conventions

**Job ID format:** `"{company}:{external_id}"` — used throughout CLI and DB foreign keys.

**LLM calls:** All use Claude tool_use (`evaluate_job` tool for filter, `resume_analysis` for tailor). Wrapped with `tenacity` retry (3 attempts, exponential backoff).

**DB pattern:** `sqlite3.Row` objects (dict-like access). Always commit after writes. Upsert on conflict for jobs.

**Resume source:** Loaded from `~/.resume_versions/` (external). PDF generation uses formatter scripts in `~/.claude/plugins/`.

**Output artifacts:** Generated PDFs written to `output/` organized by date/company.
