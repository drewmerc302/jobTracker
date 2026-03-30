# Application Status Tracker — Design Specification

**Date**: 2026-03-30
**Status**: Approved
**Author**: Drew Mercurio + Claude
**Parent**: jobTracker

## Overview

Adds job application status tracking to the existing jobTracker. Tracks progression (new → applied → interviewing → offer → rejected/withdrawn) in SQLite with auto-generated Obsidian notes per application and a dashboard.

## Database

New `applications` table in `data/jobtracker.db`:

| Column | Type | Notes |
|--------|------|-------|
| job_id | TEXT PK FK | references jobs(id) |
| status | TEXT NOT NULL | new, applied, interviewing, offer, rejected, withdrawn |
| applied_date | TEXT | set when status becomes "applied" |
| salary_notes | TEXT | free-form compensation notes |
| status_updated_at | TEXT NOT NULL | set to current UTC timestamp on every change |
| created_at | TEXT NOT NULL | set to current UTC timestamp on creation |

New `status_history` table (append-only audit log):

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | autoincrement |
| job_id | TEXT FK | references jobs(id) |
| old_status | TEXT | null on first entry |
| new_status | TEXT NOT NULL | |
| changed_at | TEXT NOT NULL | UTC timestamp |

No status transition enforcement — any status can move to any other. Closed jobs (closed_at set) can still be tracked — you may have applied before the listing was removed.

Valid statuses: `new`, `applied`, `interviewing`, `offer`, `rejected`, `withdrawn`.

## CLI Commands

### Quick status update
```
uv run jobtracker --status "Stripe:7334661" applied
```
Argparse: `--status` takes exactly 2 arguments via `nargs=2, metavar=("JOB_ID", "STATUS")`.
- Validates STATUS is one of: new, applied, interviewing, offer, rejected, withdrawn (error if not)
- Updates status in DB
- Sets `applied_date` if transitioning to "applied" and not already set
- Logs to `status_history` table
- Creates Obsidian application note if it doesn't exist
- Updates Obsidian dashboard note
- Prints confirmation with new status

### Interactive tracking
```
uv run jobtracker --track "Stripe:7334661"
```
- Shows current job info (company, title, score, current status)
- Presents numbered menu of statuses (1-6) with current status marked
- User enters number or presses Enter to keep current
- Prompts for salary notes (optional, Enter to skip)
- Creates/updates Obsidian note
- Updates dashboard
- Prints the Obsidian note path so user can open and add details

### Application dashboard (terminal)
```
uv run jobtracker --applications
```
- Groups all applications by status
- "New" = matches with no `applications` record (implicit, via LEFT JOIN)
- All other statuses come from the `applications` table
- Shows: company, title, score, applied date, last updated
- Example output:
```
APPLIED (3)
  92%  Stripe    Engineering Manager, Agentic Commerce     applied 2026-03-31
  88%  Stripe    Engineering Manager, Connect               applied 2026-03-31
  95%  Stripe    Engineering Manager, User Billing          applied 2026-04-01

INTERVIEWING (1)
  92%  Stripe    Engineering Manager, Agentic Commerce     updated 2026-04-05

NEW (14)
  91%  Stripe    Engineering Manager, Developer Product..  matched 2026-03-30
  ...
```

## Obsidian Integration

### Per-application note

**Path**: `Topics/Job Applications/Company — Title.md`

Filename sanitization: strip characters invalid in filenames (`:`, `/`, `\`, `?`, `*`, `"`, `<`, `>`, `|`), collapse multiple spaces, truncate to 80 chars.

Created via `mcp__obsidian__write_note` when status is first set.

**Template**:
```markdown
---
company: Stripe
title: Engineering Manager, Agentic Commerce
status: interviewing
score: 92%
applied_date: 2026-03-31
url: https://stripe.com/jobs/search?gh_jid=7334661
job_id: Stripe:7334661
tags: [job-application, stripe]
---

# Stripe — Engineering Manager, Agentic Commerce

## Status: Interviewing
- **Applied:** 2026-03-31
- **Status updated:** 2026-04-05

## Contacts

## Salary & Compensation

## Interview Prep

## Notes

## Match Analysis
Score: 92% | [View Listing](url)

Key requirements:
- (auto-populated from DB)

Why this matches:
(auto-populated from DB)
```

**On creation**: Full note rendered from Jinja2 template and written via `mcp__obsidian__write_note`.

**On status updates**: Use `mcp__obsidian__update_frontmatter` to update the `status` and `applied_date` fields. Then use `mcp__obsidian__patch_note` to replace only the `## Status` section content (everything between `## Status` and the next `##` heading). All other sections (Contacts, Salary, Interview Prep, Notes) are preserved — user-edited content is never overwritten.

**For jobs with no match record** (status set on a job that wasn't LLM-filtered): the Match Analysis section shows "No match analysis available — job was tracked directly" and score shows "N/A" in frontmatter.

### Dashboard note

**Path**: `Topics/Job Applications/Dashboard.md`

Auto-regenerated on every status change via `mcp__obsidian__write_note`.

**Template**:
```markdown
---
tags: [job-application, dashboard]
updated: 2026-03-31
---

# Job Application Dashboard

*Auto-generated by jobTracker. Last updated: 2026-03-31 14:30 UTC*

## Interviewing (1)
| Company | Title | Score | Applied | Updated |
|---------|-------|-------|---------|---------|
| Stripe | [[Stripe — Engineering Manager, Agentic Commerce]] | 92% | 2026-03-31 | 2026-04-05 |

## Applied (2)
| Company | Title | Score | Applied | Updated |
|---------|-------|-------|---------|---------|
| Stripe | [[Stripe — Engineering Manager, Connect]] | 88% | 2026-03-31 | 2026-03-31 |
| Stripe | [[Stripe — Engineering Manager, User Billing]] | 95% | 2026-04-01 | 2026-04-01 |

## Offer (0)

## Rejected (0)

## Withdrawn (0)

## New (14)
| Company | Title | Score | Matched |
|---------|-------|-------|---------|
| Stripe | Engineering Manager, Developer Productivity AI | 91% | 2026-03-30 |
| ... | | | |
```

Dashboard uses Obsidian wikilinks to the per-application notes for easy navigation.

## Changes to Existing Commands

### `--show-job`
Add a line after Score showing application status:
```
Status:   applied (2026-03-31)
```
Or `Status:   not tracked` if no application record exists.

### `--list-matches`
Add a `Status` column:
```
Score  PDF  Status       Company      Title                                    Tailor Command
  95%   no  applied      Stripe       Engineering Manager, User Billing        uv run jobtracker --tailor-job "Stripe:7609424"
  92%   no  new          Stripe       Engineering Manager, Agent Experiences   uv run jobtracker --tailor-job "Stripe:7657999"
```

### Email digest
The email digest only contains newly matched jobs (first-time notifications). If a job was already matched and tracked in a previous run, it won't appear in the digest again. No changes needed to the email for this feature — the existing `notified_at` dedup handles it.

## Implementation Files

| File | Change |
|------|--------|
| `src/db.py` | Add `applications` table, CRUD methods |
| `src/pipeline.py` | Add `--status`, `--track`, `--applications`, `--show-job` args and handlers |
| `src/steps/notify.py` | Add status badge to email for tracked jobs |
| `src/steps/obsidian.py` | New: generate/update application notes and dashboard via MCP |
| `templates/digest.html` | Add status indicator for tracked jobs |
| `templates/application.md` | Jinja2 template rendered to string, then passed to `mcp__obsidian__write_note` |
| `templates/dashboard.md` | Jinja2 template rendered to string, then passed to `mcp__obsidian__write_note` |

## Dependencies

No new dependencies. Uses existing:
- SQLite (DB)
- Jinja2 (templates)
- Obsidian MCP tools (already configured)

## Error Handling

- `--status` on a job_id that doesn't exist in the DB: error with "Job not found" message
- `--status` on a job_id that has no match record: works anyway (creates application record from job data)
- Obsidian MCP tool failure: log warning, don't fail the status update (DB is source of truth)
- Dashboard regeneration failure: log warning, stale dashboard is acceptable
