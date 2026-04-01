# jobTracker

Automated job tracker for engineering manager roles. Scrapes multiple job boards twice daily, filters with an LLM, tailors resumes and cover letters per job, and sends an email digest.

## What it does

1. **Scrape** — fetches new postings from Greenhouse (Dropbox, DataDog, Stripe, GitLab), Workday (Capital One, Netflix), Apple Jobs, and Google Careers
2. **Dedup** — merges duplicate listings that appear across multiple boards (same company + normalized title)
3. **Filter** — keyword pre-filter by title + location, then Claude Haiku scores each job for relevance against your resume
4. **Tailor** — Claude Sonnet analyzes the job description and suggests resume edits; generates tailored PDF resume and cover letter
5. **Notify** — sends an HTML email digest with match scores, salary, location, direct links, and overdue follow-up reminders
6. **Follow-up tracking** — automatically sets follow-up dates when you apply or enter interviews; reminds you in each digest
7. **Interview prep** — Claude generates company research, role-specific questions, and talking points; patches your Obsidian note

## Setup

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/drewmerc302/jobTracker
cd jobTracker
uv sync
cp .env.example .env  # fill in credentials
```

**.env** — copy `.env.example` and populate:

```
ANTHROPIC_API_KEY=sk-ant-...
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password   # Gmail App Password, not your account password
```

## Usage

```bash
# Full pipeline (scrape → dedup → filter → tailor → email)
uv run jobtracker

# Dry run — scrape + filter only, no email
uv run jobtracker --dry-run

# Run a single step
uv run jobtracker --step scrape
uv run jobtracker --step filter
uv run jobtracker --step tailor
uv run jobtracker --step notify
uv run jobtracker --step dedup   # merge duplicate listings

# Query tools
uv run jobtracker --list-matches
uv run jobtracker --show-job "Stripe:7609424"
uv run jobtracker --tailor-job "Stripe:7609424"

# Adopt suggested resume edits when generating PDFs
uv run jobtracker --tailor-job "Stripe:7609424" --adopt 1,3,5

# Application tracking
uv run jobtracker --applications
uv run jobtracker --status "Stripe:7609424" applied
uv run jobtracker --track "Stripe:7609424"   # interactive prompt

# Follow-up tracking
uv run jobtracker --follow-ups                          # list overdue follow-ups
uv run jobtracker --followed-up "Stripe:7609424"        # mark as followed up (resets 7-day timer)
uv run jobtracker --set-followup "Stripe:7609424" 2026-04-07  # set explicit follow-up date

# Interview prep
uv run jobtracker --interview-prep "Stripe:7609424"           # generate prep (LLM only)
uv run jobtracker --interview-prep "Stripe:7609424" --research  # include web research
```

## Scheduling (macOS launchd)

A launchd plist is included to run the pipeline every 12 hours:

```bash
cp launchd/com.drewmerc.jobtracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.drewmerc.jobtracker.plist
```

Logs are written to `data/logs/` and automatically truncated at 1MB.

## Architecture

```
scrape.py → dedup.py → filter.py → tailor.py → notify.py
                                              → obsidian.py
```

| Component | File | Description |
|-----------|------|-------------|
| Pipeline / CLI | `src/pipeline.py` | Arg parsing, step sequencing |
| Scrape | `src/steps/scrape.py` | Runs all scrapers concurrently |
| Dedup | `src/steps/dedup.py` | Merges duplicates by normalized title |
| Filter | `src/steps/filter.py` | Keyword filter + LLM scoring |
| Tailor | `src/steps/tailor.py` | Resume analysis + PDF generation |
| Notify | `src/steps/notify.py` | HTML email digest with follow-up reminders |
| Obsidian | `src/steps/obsidian.py` | Markdown notes for job applications |
| Interview Prep | `src/steps/interview_prep.py` | LLM-generated prep patched into Obsidian notes |
| Database | `src/db.py` | SQLite (WAL mode) |
| Config | `src/config.py` | Keywords, locations, company boards |

**Scrapers** (`src/scrapers/`): `greenhouse.py`, `workday.py`, `apple.py`, `google.py`

**Database tables:** `jobs`, `matches`, `applications`, `status_history`, `runs`

**Job ID format:** `"Company:external_id"` — used in CLI commands and as DB primary key

## Configuration

Edit `src/config.py` to tune:

- `keyword_patterns` — job titles to match
- `seniority_exclusions` — titles to exclude (VP, Staff, etc.)
- `acceptable_locations` — commute-range cities for in-office roles
- `greenhouse_boards` / `workday_companies` — which companies to scrape
- `relevance_threshold` — LLM score cutoff (default: 0.6)

## Development

```bash
uv run pytest          # run all tests
uv run pytest -x -q    # fail fast, quiet
```

Tests use fixture JSON files in `tests/fixtures/` — no live HTTP calls required.

## Resume & PDF generation

Tailored PDFs are generated using external formatter scripts (not included in this repo). Resume YAML source files are loaded from `~/.resume_versions/`. Output PDFs are written to `output/<date>/`.
