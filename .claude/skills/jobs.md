---
name: jobs
description: Interact with the job tracker — list matches, show analysis, generate tailored resumes/cover letters, run the pipeline, or manage companies. Use when the user mentions job matches, resume tailoring, cover letters, or running the job tracker.
---

# Job Tracker

All commands run from `/Users/drewmerc/workspace/jobTracker`.

## Commands

### List all matches
```bash
uv run jobtracker --list-matches
```
Shows all matched jobs with scores, PDF status, and copy-pasteable tailor commands.

### Show match analysis
```bash
uv run jobtracker --show-job "COMPANY:ID"
```
Shows full analysis: match reason, key requirements, interview talking points, suggested resume edits, keyword gaps, and PDF paths.

### Generate tailored resume + cover letter
```bash
uv run jobtracker --tailor-job "COMPANY:ID"
```
Runs LLM analysis against the job description, reorders resume bullets, generates a tailored resume PDF and cover letter PDF. Prints file paths when done.

### Run the full pipeline
```bash
uv run jobtracker
```
Scrapes all 4 career sites, filters for EM roles, tailors resumes for matches, and emails a digest.

### Dry run (scrape + filter only, no email)
```bash
uv run jobtracker --dry-run
```

### Re-send the last email digest
```bash
uv run jobtracker --renotify
```

### Run a single step
```bash
uv run jobtracker --step scrape|filter|tailor|notify
```

## Adding a new company

### Greenhouse (most tech companies)
Edit `src/config.py`, add to `greenhouse_boards`:
```python
"boardslug": "Display Name",
```
Verify the slug works: `curl -s https://boards-api.greenhouse.io/v1/boards/SLUG/jobs | python -m json.tool | head`

### Workday
Edit `src/config.py`, add to `workday_companies`:
```python
"key": {
    "display_name": "Company Name",
    "base_url": "https://company.wd{N}.myworkdayjobs.com",
    "path": "/wday/cxs/company/External",
},
```

### Other ATS
Create a new scraper in `src/scrapers/` implementing `BaseScraper`, then register it in `pipeline.py:build_scrapers()`.

## Typical workflow

1. **See what matched:** `uv run jobtracker --list-matches`
2. **Read the analysis:** `uv run jobtracker --show-job "Stripe:7609424"`
3. **Generate PDFs:** `uv run jobtracker --tailor-job "Stripe:7609424"`
4. **Open the PDFs**, review, and apply
