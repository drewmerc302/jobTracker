# JobTracker TUI Design Spec

**Date:** 2026-04-09
**Status:** Draft
**Framework:** Textual (Python TUI framework)

## Overview

Replace the CLI's 15+ argparse flags with a persistent, keyboard-driven terminal UI as the default entry point. The TUI provides a dashboard, navigable job lists, drill-down detail views, application tracking, and pipeline control — all discoverable via footer keybinding hints.

CLI flags are preserved for automation (launchd, scripting). The TUI is a new layer on top of existing pipeline code — it calls into existing step functions and DB queries without modifying them.

## Goals

1. **Discoverability** — features surfaced via menus and footer hints, not memorized flags
2. **No job ID friction** — arrow-key navigation replaces copy-pasting `"Stripe:7609424"`
3. **Seamless workflows** — view a job, select resume edits, generate PDFs, mark as applied — all from one screen
4. **At-a-glance overview** — dashboard answers "anything new?" in seconds

## Entry Point

`uv run jobtracker` with no flags launches the TUI. Any CLI flag triggers the existing `run_pipeline()` path.

```python
def main():
    args = parse_args()
    if has_cli_flags(args):
        run_pipeline(args)
    else:
        from src.tui.app import JobTrackerApp
        JobTrackerApp().run()
```

### Flags That Stay CLI-Only (automation)

- `--step scrape|filter|tailor|notify|dedup`
- `--dry-run`
- `--prune-stale` (also in TUI)
- `--renotify`
- `--tailor-job` + `--adopt` (scripting)

### Flags Absorbed Into TUI

- `--list-matches` → Matches screen
- `--show-job` / `--show-all-jobs` → Job Detail screen
- `--applications` → Applications screen
- `--follow-ups` / `--followed-up` / `--set-followup` → Applications screen
- `--track` / `--status` → Applications & Job Detail screens
- `--interview-prep` / `--gripes` → Job Detail actions
- `--score` / `--markdown` → TUI filters (markdown output not needed)

## Architecture

### File Structure

```
src/
├── tui/
│   ├── __init__.py
│   ├── app.py              # Main Textual App, screen registration, global keybindings
│   ├── screens/
│   │   ├── dashboard.py    # Landing screen with summary cards
│   │   ├── matches.py      # Sortable/filterable job list
│   │   ├── job_detail.py   # Single job view with actions
│   │   ├── applications.py # Application tracking grouped by status
│   │   └── pipeline.py     # Trigger runs with live progress
│   ├── widgets/            # Reusable custom widgets
│   └── styles.tcss         # Textual CSS theme (GitHub dark palette)
├── pipeline.py             # Modified: TUI default, flags bypass to run_pipeline()
├── steps/                  # Unchanged
├── scrapers/               # Unchanged
└── ...
```

### Data Flow

The TUI is a read/write consumer of the existing database and step functions. No new data layer.

- **Reads:** `Database` methods (get_job, get_match, get_all_applications, get_overdue_follow_ups, etc.)
- **Writes:** `Database` methods (set_application_status, set_follow_up_date, mark_followed_up, update_match_paths, etc.)
- **LLM calls:** `ensure_analysis()` for on-demand job analysis, `generate_interview_prep()` for interview prep
- **Pipeline runs:** `run_scrape()`, `run_filter()`, `run_dedup()`, `run_notify()` via Textual Workers (background threads)
- **PDF generation:** `run_tailor_for_job()` via Textual Worker, auto-opens generated PDFs with `subprocess.run(["open", path])`

### Dependency

Add `textual` to `pyproject.toml` dependencies.

## Global Navigation

| Key | Action |
|-----|--------|
| `d` | Go to Dashboard |
| `m` | Go to Matches |
| `a` | Go to Applications |
| `p` | Go to Pipeline |
| `/` | Open search/filter (on list screens) |
| `?` | Show help overlay |
| `q` | Quit |
| `Esc` | Go back / close overlay |

Global keys work from any screen. Footer bar always shows available actions for the current context.

## Screens

### 1. Dashboard

The landing screen. Answers "anything new?" in seconds.

**Layout:**

- **Header bar:** App name, last scrape time, total job/match counts
- **Summary cards (row of 4):**
  - New Matches (since last session) — green
  - Active Applications (applied + interviewing + offer) — blue, with breakdown
  - Overdue Follow-ups — red if any
  - Total Matches — with average score
- **Two-panel body:**
  - Left (wider): Recent Matches table — top 5 by score with status dots. Press `m` for full list.
  - Right: Overdue Follow-ups list with urgency coloring + Pipeline Status (last run, next auto-run, job counts)
- **Footer:** Global keybinding hints

**"New since last session" tracking:** Store a `last_tui_open` timestamp in the DB or a dotfile. Matches with `matched_at` after that timestamp are "new."

### 2. Matches

The main job list. Sortable, filterable DataTable.

**Columns:** Score | PDF | Status | First Seen | Company | Title | Location

**Navigation:**
- Arrow keys move highlight (blue left border on selected row)
- Enter opens Job Detail for highlighted row
- Quick actions on highlighted row without entering detail:
  - `s` — set status (popup)
  - `t` — tailor (generate PDFs)
  - `o` — open job URL in browser

**Sort/filter bar:**
- `S` — cycle sort: Score ▼ (default), Date, Company
- `/` — fuzzy search by company or title
- Filter by status dropdown, minimum score threshold
- Shows "Showing X of Y" count

**Visual indicators:**
- Score color: green ≥85%, blue ≥70%, white ≥60%
- Status dots: orange=new, green=applied, purple=interviewing, grey=rejected
- PDF column: ✓ = tailored PDF exists, — = not yet generated
- Scroll indicator at bottom when more rows below

### 3. Job Detail

Deep dive into a single job. Scrollable content with pinned header and footer.

**Header:** Company — Title, score, status, location, salary, first seen date

**Sections (scrollable):**
1. **Why This Matches** — match_reason text
2. **Key Requirements** — bulleted list from analysis
3. **Interview Talking Points** — bulleted list from analysis
4. **Suggested Resume Edits** — interactive checkboxes (see below)
5. **Keyword Gaps** — colored tag pills

**On-demand analysis:** If the job hasn't been analyzed yet (no `suggested_edits` in suggestions), triggers `ensure_analysis()` on screen load with a loading spinner. Cached results appear instantly.

**Suggested Resume Edits interaction:**
- Each edit shown as a card: original (red strikethrough) → suggested (green) + reason (italic)
- Arrow keys navigate between edit cards
- `Space` toggles checkbox on focused edit (☑/☐)
- Selected edits get blue highlight background
- `e` — adopt selected edits + generate PDFs
- `E` — adopt all edits + generate PDFs

**PDF handling:**
- `t` — generate resume/cover letter PDFs with current resume (no edits adopted)
- `e`/`E` — adopt edits then generate PDFs
- After generation, PDFs auto-open in the system default viewer (`open` on macOS)
- `v` — open existing PDFs (resume + cover letter) in default viewer. Disabled/greyed out if no PDFs exist yet.
- Toast notification confirms "Resume PDF opened" / "Cover letter PDF opened"

**Other actions:**
- `s` — set/change application status (popup selector)
- `i` — generate interview prep (with loading progress)
- `g` — show company gripes (appended below main content)
- `o` — open job listing URL in system browser
- `Esc` — back to Matches list

**Status change side effects** (same as current CLI):
- applied/interviewing → auto-set follow-up date
- interviewing → auto-trigger interview prep generation
- Any status change → update Obsidian application note + dashboard

### 4. Applications

Track active applications grouped by status.

**Groups (in display order):**
1. Interviewing (purple) — expanded
2. Applied (green) — expanded
3. Offer (orange) — expanded
4. New (grey) — expanded
5. Rejected / Withdrawn (grey) — collapsed by default, Enter to expand

**Columns per group:** Score | Company | Title | Applied Date | Follow-up / Notes

**Follow-up urgency indicators:**
- Red `⚠ Xd overdue` — past due
- Orange — approaching (within 2 days)
- Green date — upcoming

**Actions on highlighted row:**
- `Enter` — open Job Detail screen
- `s` — change status (popup)
- `f` — set follow-up date (inline date input)
- `F` — mark followed up (one keystroke, resets +7 days)
- `n` — edit salary notes (inline text input)

**Arrow keys navigate fluidly across groups** — moving from the last row of "Interviewing" lands on the first row of "Applied."

**Group badges** show count per status (e.g., "Applied (3)").

### 5. Pipeline

Trigger pipeline runs and view history.

**Action buttons row:**
- `r` — Run Full Pipeline (scrape → dedup → filter)
- `1` — Scrape Only
- `2` — Filter Only
- `3` — Prune Stale Listings
- `R` — Renotify (resend last failed digest)

**Live progress area (shown during a run):**
- Step-by-step status: ✓ completed, ⟳ in progress (with detail like "7/12"), ○ pending
- Progress bar
- Elapsed time

**Non-blocking execution:** Pipeline steps run in a Textual Worker (background thread). The UI stays responsive — you can navigate to other screens while a run is in progress. A small progress indicator appears in the header bar when a run is active.

**Run history table:** Pulled from the `runs` DB table.
- Columns: When | Source (launchd/manual) | Jobs | New | Matches | Email | Duration | Status
- Failed runs highlighted in red/orange
- Manual runs (triggered from TUI) distinguished from launchd runs

## Theme

GitHub dark palette:
- Background: `#0d1117`
- Surface: `#161b22`
- Border: `#30363d`
- Text primary: `#c9d1d9`
- Text secondary: `#484f58`
- Blue accent: `#58a6ff`
- Green: `#3fb950`
- Orange: `#f0883e`
- Red: `#f85149`
- Purple: `#a371f7`

Defined in `styles.tcss` using Textual's CSS dialect.

## Popups / Overlays

Small modal overlays for inline actions (not full screen changes):

- **Status selector:** List of statuses with current highlighted. Arrow + Enter to select.
- **Follow-up date input:** Text input with date format hint (YYYY-MM-DD).
- **Salary notes input:** Single-line text input.
- **Help overlay (`?`):** Full keybinding reference for current screen.
- **Confirmation toasts:** Brief non-blocking messages ("Status → applied", "PDF opened", "Follow-up set: Apr 16").

## Error Handling

- **Scraper failures:** Show in pipeline progress as "⚠ Workday: timeout" — non-fatal, other scrapers continue
- **LLM failures:** Show error toast, fall back to cached analysis if available
- **PDF generation failures:** Toast with error, job detail screen shows "PDF generation failed" instead of paths
- **DB errors:** Unlikely with SQLite, but catch and display gracefully

## Testing Approach

- **Unit tests:** Test TUI screen widgets in isolation using Textual's `pilot` testing API (simulate keypresses, assert screen content)
- **Integration:** Test that TUI actions (set status, trigger scrape) produce correct DB state via the existing step functions
- **Existing tests:** All current pytest tests continue to pass — TUI is additive, doesn't modify step logic

## Out of Scope

- Web-based UI or desktop app (separate initiative for non-technical users)
- New scrapers or aggregator APIs
- Multi-user support
- Resume import from PDF (existing resume skills handle this separately)
