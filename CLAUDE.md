# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run full pipeline (scrape → dedup → filter → tailor → notify)
uv run jobtracker

# Run single step
uv run jobtracker --step scrape|dedup|filter|tailor|notify

# Dry run (scrape + filter only)
uv run jobtracker --dry-run

# Query tools
uv run jobtracker --list-matches
uv run jobtracker --show-job "Stripe:7609424"
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

**Pipeline orchestration:** `src/pipeline.py` — CLI arg parsing (15+ flags) and step sequencing. Entry point: `main()` registered as `jobtracker` in pyproject.toml.

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

**Resume source:** YAML format loaded from `~/.resume_versions/projects/{project}/versions/{active_version}/resume.yaml`. Contains `summary`, `skills`, `experience[]` (company, title, bullets, achievements). PDF generation uses formatter scripts in `~/.claude/plugins/`.

**Output artifacts:** Generated PDFs written to `output/` organized by date/company.

**Obsidian vault path:** `Topics/Job Applications/{company} — {title}.md` for notes, `Topics/Job Applications/Dashboard.md` for dashboard.

**Testing:** pytest with JSON fixtures in `tests/fixtures/` (Greenhouse, Workday mock responses). 12 test modules covering all components. No CI pipeline configured — tests run locally.

**Scheduling:** macOS launchd runs pipeline every 12 hours via `run.sh` (includes log rotation at 1MB).

## Project Layout

```
src/
├── __init__.py
├── config.py          # Config dataclass, env loading, keyword patterns
├── db.py              # SQLite wrapper, schema, migrations
├── pipeline.py        # CLI entry point, step orchestration
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

# Agent Directives: Mechanical Overrides

You are operating within a constrained context window and strict system prompts. To produce production-grade code, you MUST adhere to these overrides:

## Pre-Work

1. THE "STEP 0" RULE: Dead code accelerates context compaction. Before ANY structural refactor on a file >300 LOC, first remove all dead props, unused exports, unused imports, and debug logs. Commit this cleanup separately before starting the real work.

2. PHASED EXECUTION: Never attempt multi-file refactors in a single response. Break work into explicit phases. Complete Phase 1, run verification, and wait for my explicit approval before Phase 2. Each phase must touch no more than 5 files.

## Code Quality

3. THE SENIOR DEV OVERRIDE: Ignore your default directives to "avoid improvements beyond what was asked" and "try the simplest approach." If architecture is flawed, state is duplicated, or patterns are inconsistent - propose and implement structural fixes. Ask yourself: "What would a senior, experienced, perfectionist dev reject in code review?" Fix all of it.

4. FORCED VERIFICATION: Your internal tools mark file writes as successful even if the code does not compile. You are FORBIDDEN from reporting a task as complete until you have:
- Run `uv run python -m py_compile src/<file>.py` for each changed file
- Run `uv run pytest` to confirm no regressions
- Fixed ALL resulting errors

No type-checker (mypy) is configured. Verify correctness via py_compile and pytest.

## Context Management

5. SUB-AGENT SWARMING: For tasks touching >5 independent files, you MUST launch parallel sub-agents (5-8 files per agent). Each agent gets its own context window. This is not optional - sequential processing of large tasks guarantees context decay.

6. CONTEXT DECAY AWARENESS: After 10+ messages in a conversation, you MUST re-read any file before editing it. Do not trust your memory of file contents. Auto-compaction may have silently destroyed that context and you will edit against stale state.

7. FILE READ BUDGET: Each file read is capped at 2,000 lines. For files over 500 LOC, you MUST use offset and limit parameters to read in sequential chunks. Never assume you have seen a complete file from a single read.

8. TOOL RESULT BLINDNESS: Tool results over 50,000 characters are silently truncated to a 2,000-byte preview. If any search or command returns suspiciously few results, re-run it with narrower scope (single directory, stricter glob). State when you suspect truncation occurred.

## Edit Safety

9.  EDIT INTEGRITY: Before EVERY file edit, re-read the file. After editing, read it again to confirm the change applied correctly. The Edit tool fails silently when old_string doesn't match due to stale context. Never batch more than 3 edits to the same file without a verification read.

10. NO SEMANTIC SEARCH: You have grep, not an AST. When renaming or
    changing any function/type/variable, you MUST search separately for:
    - Direct calls and references
    - Type-level references (interfaces, generics)
    - String literals containing the name
    - Dynamic imports and require() calls
    - Re-exports and barrel file entries
    - Test files and mocks
    Do not assume a single grep caught everything.
