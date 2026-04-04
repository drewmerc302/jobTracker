---
name: scan
description: Run the jobTracker scan pipeline (scrape + filter) and report results. Use when the user says /scan, "run the scanner", "check for new jobs", "scan for jobs", or wants to see what's new without full pipeline. Does NOT tailor resumes or send emails.
---

# Job Scan

Runs scrape + filter only. No tailoring, no email.

## Steps

1. Run the scrape step:
   ```bash
   cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --step scrape
   ```

2. Run the filter step:
   ```bash
   uv run jobtracker --step filter
   ```

3. Show current matches:
   ```bash
   uv run jobtracker --list-matches
   ```

4. Report a summary:
   - Total jobs scraped (new vs. existing)
   - Matches found (total, and any new since last run)
   - Any scraper errors or warnings

## What not to do

- Do not run `--step tailor` or the full pipeline — tailoring is expensive and only done intentionally
- Do not run `--step notify` — no emails during a scan
- If a scraper fails, report the error and continue — don't abort the whole scan
