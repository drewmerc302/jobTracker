# Design: Interview Prep, Deduplication, and Follow-up Tracking

**Date:** 2026-03-31
**Project:** jobTracker
**Status:** Approved

---

## Overview

Three independent features added to the jobTracker pipeline:

1. **Interview Prep Auto-generation** — when a job moves to `interviewing` status, generate a structured prep note (STAR stories, predicted questions, talking points, red flags) and write it to the Obsidian application note.
2. **Cross-board Job Deduplication** — detect and merge jobs that appear on multiple scraped boards, keeping the most complete record.
3. **Application Follow-up Tracking** — track follow-up dates per application, surface overdue items in the CLI and email digest.

---

## Feature 1: Interview Prep Auto-generation

### Trigger

In `src/steps/obsidian.py`, the `update_status()` function handles status transitions. When the new status is `interviewing`, call `generate_interview_prep(db, job_id)` before returning. This is synchronous — acceptable latency given LLM calls already occur in the pipeline.

### New File: `src/steps/interview_prep.py`

Single public function: `generate_interview_prep(db, job_id, research=False)`.

**Steps:**
1. Load job record from DB (JD, company, title, URL)
2. Load active resume YAML from `~/.resume_versions/`
3. Call Claude Sonnet with `interview_prep` tool-use schema returning:
   - `likely_questions` — behavioral + technical questions predicted from JD
   - `star_stories` — list of `{question, resume_bullet, situation, task, action, result}` mappings
   - `talking_points` — 3–5 things to emphasize about your background for this role
   - `red_flags` — gaps or weaknesses relative to the JD to prepare for
4. If `research=True`: web search for `"{company} engineering culture {year}"`, summarize top results, pass as additional context to the Claude call
5. Write/patch the `## Interview Prep` section of the Obsidian application note with the generated content

### CLI

- `--interview-prep "Company:id"` — trigger manually (no research)
- `--interview-prep "Company:id" --research` — trigger with web research
- Status change to `interviewing` (via `--status` or `--track`) — auto-triggers without `--research`

### Error Handling

If the Claude call fails, log the error and continue — status transition completes regardless. Prep generation is best-effort.

---

## Feature 2: Cross-board Job Deduplication

### New File: `src/steps/dedup.py`

Single public function: `run_dedup(db)` — returns `(merged_count, removed_count)`.

### Matching Logic

Two jobs are duplicates if they share the same `(company, normalized_title)` after normalization.

**Normalization:**
- Strip seniority prefixes/suffixes: `Sr.`, `Senior`, `Junior`, `Staff`, `Principal`, `Lead`
- Strip roman numerals: `I`, `II`, `III`
- Strip punctuation and extra whitespace
- Lowercase

Example: `"Senior Engineering Manager, Growth"` and `"Engineering Manager - Growth"` → same normalized form.

### Merge Strategy

Score each candidate:
- `+2` — has salary field
- `+2` — description length > 500 chars
- `+1` — has location
- `+1` — has department

Highest score wins. Tie-break: keep earliest `first_seen_at`.

### FK Safety

Before removing a duplicate, re-point all FK references to the canonical job_id:
- `matches` — if both have a match, keep the one with higher `relevance_score`
- `applications` — if both have an application, keep the one with the more advanced status (ordering: `interviewing > offer > applied > new > rejected > withdrawn`)
- `status_history` — re-point all rows to canonical

### Pipeline Integration

Runs automatically after `scrape` step in the full pipeline and when `--step scrape` is used. Also callable standalone:

```
uv run jobtracker --step dedup
```

**Retroactive cleanup:** Running `--step dedup` on the existing DB performs a full cleanup pass. Logs: `"Dedup: N duplicate groups found, M jobs merged, M records removed"`.

---

## Feature 3: Application Follow-up Tracking

### Schema Change

Add two columns to `applications` table:

| Column | Type | Description |
|--------|------|-------------|
| `follow_up_after` | TEXT (nullable) | ISO date; defaults to `applied_date + 7 days` when status → `applied` |
| `followed_up_at` | TEXT (nullable) | ISO timestamp of last follow-up action |

**Migration:** `src/db.py` runs `ALTER TABLE` on startup, guarded by `PRAGMA table_info` check (safe to re-run on existing DB).

### CLI Commands

| Command | Description |
|---------|-------------|
| `--follow-ups` | List applications where `follow_up_after <= today` and `status = applied`, sorted by most overdue |
| `--followed-up "Company:id"` | Mark as followed up; resets `follow_up_after` to today + 7 days |
| `--set-followup "Company:id" 2026-04-10` | Set a specific follow-up date |

**`--follow-ups` output columns:** Company | Title | Applied | Days overdue | Follow-up date

### Interactive `--track` Flow

After setting status to `applied`, prompt:
```
Follow up in how many days? [7]:
```
Accepts a number or Enter for default (7 days).

### Email Digest

`notify.py` queries for overdue follow-ups (same filter as `--follow-ups`) and passes them to the Jinja2 template. A "Follow Up Today" section appears **above new matches** in the digest, rendered only when overdue items exist.

**Section contents:** Company | Title | Days overdue | Link to listing

---

## Implementation Order

1. **Dedup** — no new dependencies, pure DB + scrape pipeline work
2. **Follow-up tracking** — schema migration + CLI + digest template change
3. **Interview prep** — new LLM step, most complex, depends on stable status transition flow

---

## Files Created / Modified

| File | Change |
|------|--------|
| `src/steps/dedup.py` | New — deduplication logic |
| `src/steps/interview_prep.py` | New — prep generation |
| `src/steps/scrape.py` | Modified — call `run_dedup` after scrape |
| `src/steps/obsidian.py` | Modified — trigger `generate_interview_prep` on `interviewing` transition |
| `src/steps/notify.py` | Modified — query and render overdue follow-ups |
| `src/db.py` | Modified — migration for new columns, helper queries |
| `src/pipeline.py` | Modified — add `--step dedup`, `--interview-prep`, `--follow-ups`, `--followed-up`, `--set-followup` CLI args |
| `templates/digest.html` | Modified — follow-up section |

---

## Out of Scope

- Slack/SMS notifications for follow-ups
- Multiple follow-up rounds per application
- Auto-sending follow-up emails
- Deduplication across companies (only within same company)
