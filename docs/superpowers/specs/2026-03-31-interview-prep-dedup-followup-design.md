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

In `src/pipeline.py`, the `--status` and `--track` CLI handlers call `db.set_application_status()`. After a successful status transition to `interviewing`, call `generate_interview_prep(db, job_id)`. This is synchronous — acceptable latency given LLM calls already occur in the pipeline.

The `src/steps/obsidian.py` module handles note writing only and is not involved in status logic.

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
5. **Section-level patch of the Obsidian note:** read the existing application note via MCP, locate the `## Interview Prep` section, replace only that section's content with the generated output, write the full note back. This preserves all other manually-edited content (salary notes, contacts, personal notes). If no `## Interview Prep` section exists, append it.

### CLI

- `--interview-prep "Company:id"` — trigger manually (no research). Add `--research` as a standalone boolean flag in argparse.
- `--interview-prep "Company:id" --research` — trigger with web research
- Status change to `interviewing` (via `--status` or `--track`) — auto-triggers without `--research`

### Error Handling

If the Claude call fails, log the error and continue — status transition completes regardless. Prep generation is best-effort. If the Obsidian note does not exist yet, create it before patching.

---

## Feature 2: Cross-board Job Deduplication

### New File: `src/steps/dedup.py`

Single public function: `run_dedup(db)` — returns `(merged_count, removed_count)`.

### Matching Logic

Two jobs are duplicates if they share the same `(company, normalized_title)` after normalization.

**Normalization:**
- Strip seniority prefixes/suffixes: `Sr.`, `Senior`, `Junior`, `Staff`, `Principal`, `Lead`
- Strip roman numerals only when they appear as standalone trailing tokens: ` I`, ` II`, ` III`
- Strip punctuation (commas, hyphens, periods) and extra whitespace
- Lowercase
- **Preserve department/team suffixes** (e.g., `Growth`, `Platform`, `Infrastructure`) — these are part of the match key. `"Engineering Manager, Growth"` and `"Engineering Manager, Platform"` are NOT duplicates.

Example of a true duplicate: `"Senior Engineering Manager"` and `"Engineering Manager"` → both normalize to `"engineering manager"`.

### Merge Strategy

Score each candidate:
- `+2` — has salary field
- `+2` — description length > 500 chars
- `+1` — has location
- `+1` — has department

Highest score wins. Tie-break: keep earliest `first_seen_at`.

### FK Safety

Each merge group is wrapped in a single `BEGIN / COMMIT` transaction. On any error, `ROLLBACK` is issued and the group is skipped with a logged warning.

For each duplicate group, re-point FK references in this order before deleting the duplicate job record:

1. **`matches`** (PK is `job_id`): if both canonical and duplicate have a match row, delete the row with the lower `relevance_score` first, then leave the surviving row in place (no UPDATE needed if canonical row wins; if duplicate row wins, delete canonical row then UPDATE duplicate row's `job_id` to canonical). If only the duplicate has a match row, UPDATE its `job_id` to canonical.
2. **`applications`** (PK is `job_id`): same pattern — delete the losing row first (lower-priority status per ordering: `interviewing > offer > applied > new > rejected > withdrawn`), then UPDATE the winner's `job_id` to canonical if needed.
3. **`status_history`** (no PK conflict): UPDATE all rows `WHERE job_id = duplicate_id` to `job_id = canonical_id`. Drop duplicate history rows that are exact duplicates of canonical history rows (`old_status`, `new_status`, `changed_at` all match) to avoid a misleading audit trail. Do not annotate merged rows — the dedup run log is the audit record.
4. **`jobs`**: DELETE the duplicate job record.

### Pipeline Integration

Runs automatically after `scrape` step in the full pipeline and when `--step scrape` is used. Also callable standalone:

```
uv run jobtracker --step dedup
```

`"dedup"` must be added to the `choices` list in the `--step` argparse declaration in `parse_args()` (alongside `scrape`, `filter`, `tailor`, `notify`).

When `--step scrape` is used, call `run_dedup(db)` after `run_scrape()` completes but **before** `db.complete_run()` and `return`.

**Retroactive cleanup:** Running `--step dedup` on the existing DB performs a full cleanup pass. Logs: `"Dedup: N duplicate groups found, M jobs merged, M records removed"`.

---

## Feature 3: Application Follow-up Tracking

### Schema Change

Add two columns to `applications` table:

| Column | Type | Description |
|--------|------|-------------|
| `follow_up_after` | TEXT (nullable) | ISO date; defaults to `applied_date + 7 days` when status → `applied` or `interviewing` |
| `followed_up_at` | TEXT (nullable) | ISO timestamp of last follow-up action |

**Migration:** `src/db.py` runs `ALTER TABLE` on startup, guarded by `PRAGMA table_info` check (safe to re-run on existing DB).

### CLI Commands

| Command | Description |
|---------|-------------|
| `--follow-ups` | List applications where `follow_up_after <= today` and status is any non-terminal value (`new`, `applied`, `interviewing`), sorted by most overdue |
| `--followed-up "Company:id"` | Mark as followed up: if `follow_up_after` was set, reset it to today + 7 days and record `followed_up_at`. If `follow_up_after` was null, only set `followed_up_at` — do not auto-create a new follow-up date. |
| `--set-followup "Company:id" 2026-04-10` | Set a specific follow-up date |

**`--follow-ups` filter:** `follow_up_after <= today AND status IN ('new', 'applied', 'interviewing')`. Terminal statuses (`offer`, `rejected`, `withdrawn`) are excluded — they don't need follow-up. `follow_up_after` is auto-set on both `applied` and `interviewing` transitions so `interviewing` items will appear here without requiring a manual `--set-followup`.

**`--follow-ups` output columns:** Company | Title | Status | Applied | Days overdue | Follow-up date

### Interactive `--track` Flow

After setting status to `applied`, prompt:
```
Follow up in how many days? [7]:
```
Accepts a number or Enter for default (7 days). Sets `follow_up_after = applied_date + N days`.

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
| `src/steps/notify.py` | Modified — query and render overdue follow-ups |
| `src/db.py` | Modified — migration for new columns, helper queries |
| `src/pipeline.py` | Modified — add `--step dedup`, `--interview-prep`, `--research`, `--follow-ups`, `--followed-up`, `--set-followup` CLI args; trigger `generate_interview_prep` on `interviewing` status transition |
| `templates/digest.html` | Modified — follow-up section |

---

## Out of Scope

- Slack/SMS notifications for follow-ups
- Multiple follow-up rounds per application
- Auto-sending follow-up emails
- Deduplication across companies (only within same company)
