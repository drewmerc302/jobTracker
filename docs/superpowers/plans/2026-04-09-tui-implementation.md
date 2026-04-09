# JobTracker TUI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Textual-based TUI as the default entry point for jobtracker, replacing interactive CLI flags with keyboard-driven screens.

**Architecture:** New `src/tui/` package with a main App class and 5 screen modules (dashboard, matches, job_detail, applications, pipeline). The TUI calls existing DB and step functions — no changes to core logic. Entry point in `pipeline.py` routes to TUI when no CLI flags are set.

**Tech Stack:** Python 3.12+, Textual (TUI framework), existing SQLite DB + step functions

**Spec:** `docs/superpowers/specs/2026-04-09-tui-design.md`

---

## File Structure

```
src/tui/
├── __init__.py              # Empty
├── app.py                   # JobTrackerApp(App), screen registration, global keybindings
├── screens/
│   ├── __init__.py          # Empty
│   ├── dashboard.py         # DashboardScreen — summary cards, recent matches, follow-ups
│   ├── matches.py           # MatchesScreen — sortable DataTable of matched jobs
│   ├── job_detail.py        # JobDetailScreen — full job view with edit selection + actions
│   ├── applications.py      # ApplicationsScreen — grouped by status with follow-up mgmt
│   └── pipeline.py          # PipelineScreen — trigger runs, live progress, run history
├── widgets/
│   ├── __init__.py          # Empty
│   └── status_popup.py      # StatusPopup — modal for selecting application status
└── styles.tcss              # Textual CSS theme (GitHub dark palette)

tests/
└── test_tui.py              # TUI tests using Textual pilot API

src/db.py                    # Modified: add get_recent_runs(), get_match_stats()
src/pipeline.py              # Modified: TUI default entry point
pyproject.toml               # Modified: add textual dependency
```

---

### Task 0: Add Textual dependency and scaffold TUI package

**Files:**
- Modify: `pyproject.toml`
- Create: `src/tui/__init__.py`
- Create: `src/tui/app.py`
- Create: `src/tui/screens/__init__.py`
- Create: `src/tui/styles.tcss`

- [ ] **Step 1: Add textual to pyproject.toml**

In `pyproject.toml`, add `"textual>=1.0.0"` to the `dependencies` list.

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: textual installs successfully

- [ ] **Step 3: Create empty package files**

Create `src/tui/__init__.py` (empty), `src/tui/screens/__init__.py` (empty).

- [ ] **Step 4: Create styles.tcss**

```css
/* GitHub dark theme */
Screen {
    background: #0d1117;
}

Header {
    background: #161b22;
    color: #58a6ff;
    dock: top;
    height: 1;
}

Footer {
    background: #161b22;
}

DataTable {
    background: #0d1117;
}

DataTable > .datatable--header {
    background: #0d1117;
    color: #484f58;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #1f3a5f;
    color: #ffffff;
}

#summary-cards {
    layout: horizontal;
    height: auto;
    padding: 1;
}

.summary-card {
    background: #161b22;
    border: solid #30363d;
    padding: 1 2;
    width: 1fr;
    margin: 0 1;
    height: auto;
}

.summary-card .card-value {
    text-style: bold;
    color: #c9d1d9;
}

.card-value.green { color: #3fb950; }
.card-value.blue { color: #58a6ff; }
.card-value.red { color: #f85149; }

.section-header {
    background: #161b22;
    color: #58a6ff;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid #30363d;
    height: 1;
}

.status-new { color: #f0883e; }
.status-applied { color: #3fb950; }
.status-interviewing { color: #a371f7; }
.status-offer { color: #f0883e; }
.status-rejected { color: #8b949e; }
.status-withdrawn { color: #8b949e; }
.status-closed { color: #8b949e; }

.score-high { color: #3fb950; }
.score-mid { color: #58a6ff; }
.score-low { color: #c9d1d9; }

#dashboard-body {
    layout: horizontal;
    height: 1fr;
}

#left-panel {
    width: 3fr;
}

#right-panel {
    width: 2fr;
}
```

- [ ] **Step 5: Create minimal app.py skeleton**

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer


class JobTrackerApp(App):
    """JobTracker TUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "JobTracker"

    BINDINGS = [
        ("d", "switch_screen('dashboard')", "Dashboard"),
        ("m", "switch_screen('matches')", "Matches"),
        ("a", "switch_screen('applications')", "Applications"),
        ("p", "switch_screen('pipeline')", "Pipeline"),
        ("q", "quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]

    def on_mount(self) -> None:
        from src.config import Config
        from src.db import Database
        self.config = Config()
        self.db = Database(self.config.db_path)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def action_switch_screen(self, screen_name: str) -> None:
        # Screens will be registered in later tasks
        pass

    def action_help(self) -> None:
        self.notify("Help: d=Dashboard  m=Matches  a=Apps  p=Pipeline  q=Quit")
```

- [ ] **Step 6: Verify app launches**

Run: `uv run python -c "from src.tui.app import JobTrackerApp; print('import ok')"`
Expected: "import ok"

- [ ] **Step 7: Commit**

```
git add src/tui/ pyproject.toml uv.lock
git commit -m "feat: scaffold TUI package with Textual app skeleton and theme"
```

---

### Task 1: Add DB helper methods for TUI

**Files:**
- Modify: `src/db.py` (add 2 methods)
- Modify: `tests/test_db.py` (add tests)

- [ ] **Step 1: Write failing tests for get_recent_runs**

Add to `tests/test_db.py`:

```python
def test_get_recent_runs(db):
    # Create some runs
    r1 = db.start_run()
    db.complete_run(r1, jobs_scraped=100, new_jobs=5, matches_found=2, email_sent=True)
    r2 = db.start_run()
    db.complete_run(r2, jobs_scraped=110, new_jobs=8, matches_found=1, email_sent=False, error="SMTP fail")

    runs = db.get_recent_runs(limit=10)
    assert len(runs) == 2
    assert runs[0]["id"] == r2  # Most recent first
    assert runs[0]["error"] == "SMTP fail"
    assert runs[1]["jobs_scraped"] == 100
```

- [ ] **Step 2: Write failing test for get_match_stats**

```python
def test_get_match_stats(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="co:1", company="Co", title="EM", url="http://x", scraped_at=now)
    db.upsert_job(id="co:2", company="Co", title="EM2", url="http://y", scraped_at=now)
    db.commit()
    db.insert_match(job_id="co:1", relevance_score=0.85, match_reason="good")
    db.insert_match(job_id="co:2", relevance_score=0.72, match_reason="ok")

    stats = db.get_match_stats()
    assert stats["total_matches"] == 2
    assert stats["avg_score"] == pytest.approx(0.785, abs=0.01)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py::test_get_recent_runs tests/test_db.py::test_get_match_stats -v`
Expected: FAIL — methods don't exist

- [ ] **Step 4: Implement get_recent_runs and get_match_stats in db.py**

Add to `Database` class in `src/db.py`:

```python
def get_recent_runs(self, limit: int = 10) -> list[dict]:
    rows = self._conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]

def get_match_stats(self) -> dict:
    row = self._conn.execute("""
        SELECT COUNT(*) as total_matches,
               AVG(m.relevance_score) as avg_score
        FROM matches m
        JOIN jobs j ON m.job_id = j.id
        WHERE j.closed_at IS NULL
    """).fetchone()
    return {
        "total_matches": row["total_matches"] or 0,
        "avg_score": row["avg_score"] or 0.0,
    }

def count_matches_since(self, since_iso: str) -> int:
    """Count matches added after a given ISO timestamp."""
    row = self._conn.execute(
        "SELECT COUNT(*) as cnt FROM matches WHERE matched_at > ?", (since_iso,)
    ).fetchone()
    return row["cnt"] or 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py::test_get_recent_runs tests/test_db.py::test_get_match_stats -v`
Expected: PASS

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `uv run pytest`
Expected: All tests pass

- [ ] **Step 7: Commit**

```
git add src/db.py tests/test_db.py
git commit -m "feat: add get_recent_runs and get_match_stats DB methods for TUI"
```

---

### Task 2: Implement Dashboard screen

**Files:**
- Create: `src/tui/screens/dashboard.py`
- Modify: `src/tui/app.py` (register screen)
- Create: `tests/test_tui.py`

- [ ] **Step 1: Write Dashboard screen test**

Create `tests/test_tui.py`:

```python
import pytest
from datetime import datetime, timezone
from src.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def seeded_db(db):
    """DB with sample jobs, matches, and applications for TUI tests."""
    now = datetime.now(timezone.utc)
    for i in range(3):
        db.upsert_job(
            id=f"co:{i}", company="TestCo", title=f"EM {i}",
            url=f"http://example.com/{i}", scraped_at=now,
            location="Remote", remote=True, description=f"Description {i}",
        )
        db.commit()
        db.insert_match(
            job_id=f"co:{i}", relevance_score=0.9 - i * 0.1,
            match_reason=f"Reason {i}",
        )
    db.set_application_status("co:1", "applied")
    return db


async def test_dashboard_mounts(seeded_db):
    """Test that dashboard screen mounts and shows summary data."""
    from src.tui.app import JobTrackerApp

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        # Should show match count somewhere
        assert app.query_one("#total-matches").renderable is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui.py::test_dashboard_mounts -v`
Expected: FAIL — DashboardScreen doesn't exist

- [ ] **Step 3: Create dashboard.py**

```python
import json
from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static, DataTable, Footer


class SummaryCard(Static):
    """A summary statistic card."""

    def __init__(self, title: str, value: str, detail: str = "", css_class: str = ""):
        super().__init__()
        self.card_title = title
        self.card_value = value
        self.card_detail = detail
        self.value_class = css_class

    def compose(self) -> ComposeResult:
        yield Static(self.card_title.upper(), classes="card-label")
        yield Static(self.card_value, classes=f"card-value {self.value_class}", id=f"val-{self.card_title.lower().replace(' ', '-')}")
        yield Static(self.card_detail, classes="card-detail")

    DEFAULT_CSS = """
    SummaryCard {
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
        width: 1fr;
        margin: 0 1;
        height: auto;
    }
    .card-label { color: #484f58; text-style: bold; }
    .card-detail { color: #484f58; }
    """


class DashboardScreen(Screen):
    """Landing screen with summary cards and recent data."""

    BINDINGS = [
        ("m", "app.switch_screen('matches')", "Matches"),
        ("a", "app.switch_screen('applications')", "Applications"),
        ("p", "app.switch_screen('pipeline')", "Pipeline"),
    ]

    def compose(self) -> ComposeResult:
        db = self.app.db

        # Stats
        stats = db.get_match_stats()
        overdue = db.get_overdue_follow_ups()
        apps = db.get_all_applications()
        active_count = sum(1 for a in apps if a.get("status") in ("applied", "interviewing", "offer"))
        active_detail = []
        for s in ("applied", "interviewing", "offer"):
            c = sum(1 for a in apps if a.get("status") == s)
            if c:
                active_detail.append(f"{c} {s}")

        # "New since last session" tracking
        last_open = self.app.get_last_tui_open()
        new_count = db.count_matches_since(last_open) if last_open else stats["total_matches"]

        with Horizontal(id="summary-cards"):
            yield SummaryCard(
                "New Matches",
                str(new_count),
                "since last session",
                css_class="green" if new_count else "blue",
            )
            yield SummaryCard(
                "Active Apps",
                str(active_count),
                " · ".join(active_detail) if active_detail else "none",
                css_class="blue",
            )
            yield SummaryCard(
                "Overdue Follow-ups",
                str(len(overdue)),
                f"oldest: {overdue[0]['follow_up_after']}" if overdue else "all clear",
                css_class="red" if overdue else "green",
            )
            yield SummaryCard(
                "Total Matches",
                str(stats["total_matches"]),
                f"avg score: {stats['avg_score']:.0%}",
                css_class="blue",
            )

        # Two-panel body
        with Horizontal(id="dashboard-body"):
            # Left panel: Recent matches
            with Vertical(id="left-panel"):
                yield Static(" Recent Matches · press [m] for full list ", classes="section-header")
                table = DataTable(id="recent-matches")
                table.add_columns("Score", "Company", "Title", "Status")
                yield table

            # Right panel: Overdue follow-ups + pipeline status
            with Vertical(id="right-panel"):
                yield Static(" ⚠ Overdue Follow-ups ", classes="section-header")
                fu_table = DataTable(id="overdue-followups")
                fu_table.add_columns("Company", "Title", "Overdue")
                yield fu_table

                yield Static(" Pipeline Status ", classes="section-header")
                yield Static("", id="pipeline-status")

        yield Footer()

    def on_mount(self) -> None:
        db = self.app.db

        # Populate recent matches
        rows = db._conn.execute("""
            SELECT m.job_id, j.company, j.title, m.relevance_score,
                   COALESCE(a.status, 'new') as status
            FROM matches m JOIN jobs j ON m.job_id = j.id
            LEFT JOIN applications a ON m.job_id = a.job_id
            WHERE j.closed_at IS NULL
            ORDER BY m.relevance_score DESC LIMIT 5
        """).fetchall()
        table = self.query_one("#recent-matches", DataTable)
        for r in rows:
            table.add_row(
                f"{r['relevance_score']:.0%}",
                r["company"],
                r["title"][:45],
                r["status"],
                key=r["job_id"],
            )

        # Populate overdue follow-ups
        overdue = db.get_overdue_follow_ups()
        try:
            fu_table = self.query_one("#overdue-followups", DataTable)
            for f in overdue:
                days = int(f.get("days_overdue") or 0)
                fu_table.add_row(
                    f["company"], f["title"][:35], f["status"], f"{days}d"
                )
        except Exception:
            pass  # No overdue section if none exist

        # Pipeline status
        runs = db.get_recent_runs(limit=1)
        if runs:
            last = runs[0]
            completed = last.get("completed_at", "unknown")
            if completed and completed != "unknown":
                completed = completed[:16].replace("T", " ")
            status_text = (
                f"Last run: {completed}  ·  "
                f"Jobs: {last.get('jobs_scraped', 0)}  ·  "
                f"New: {last.get('new_jobs', 0)}  ·  "
                f"Matches: {last.get('matches_found', 0)}"
            )
        else:
            status_text = "No runs recorded"
        self.query_one("#pipeline-status", Static).update(f"  {status_text}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "recent-matches":
            job_id = str(event.row_key.value)
            self.app.action_show_job(job_id)
```

- [ ] **Step 4: Update app.py to register Dashboard and set as default**

```python
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from src.tui.screens.dashboard import DashboardScreen


class JobTrackerApp(App):
    """JobTracker TUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "JobTracker"

    SCREENS = {
        "dashboard": DashboardScreen,
    }

    BINDINGS = [
        ("d", "switch_screen('dashboard')", "Dashboard"),
        ("m", "switch_screen('matches')", "Matches"),
        ("a", "switch_screen('applications')", "Applications"),
        ("p", "switch_screen('pipeline')", "Pipeline"),
        ("q", "quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]

    _LAST_OPEN_FILE = Path.home() / ".jobtracker_last_tui_open"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._db_override = None

    def get_last_tui_open(self) -> str | None:
        """Read the last TUI open timestamp from dotfile."""
        try:
            return self._LAST_OPEN_FILE.read_text().strip() or None
        except FileNotFoundError:
            return None

    def _save_last_tui_open(self) -> None:
        """Write current timestamp to dotfile."""
        from datetime import datetime, timezone
        self._LAST_OPEN_FILE.write_text(datetime.now(timezone.utc).isoformat())

    def on_mount(self) -> None:
        from src.config import Config
        from src.db import Database

        self.config = Config()
        if self._db_override:
            self.db = self._db_override
        else:
            self.db = Database(self.config.db_path)
        self.push_screen("dashboard")
        self._save_last_tui_open()

    def action_switch_screen(self, screen_name: str) -> None:
        if screen_name in self.SCREENS:
            self.switch_screen(screen_name)
        else:
            self.notify(f"Screen '{screen_name}' not yet implemented")

    def action_show_job(self, job_id: str) -> None:
        self.notify(f"Job detail for {job_id} — not yet implemented")

    def action_help(self) -> None:
        self.notify("Help: d=Dashboard  m=Matches  a=Apps  p=Pipeline  q=Quit")
```

- [ ] **Step 5: Run dashboard test**

Run: `uv run pytest tests/test_tui.py -v`
Expected: PASS

- [ ] **Step 6: Manual smoke test**

Run: `uv run python -c "from src.tui.app import JobTrackerApp; JobTrackerApp().run()"` 
Verify: app launches, shows dashboard with data from your DB. Press `q` to quit.

- [ ] **Step 7: Commit**

```
git add src/tui/ tests/test_tui.py
git commit -m "feat: implement Dashboard screen with summary cards and recent matches"
```

---

### Task 3: Implement Matches screen

**Files:**
- Create: `src/tui/screens/matches.py`
- Modify: `src/tui/app.py` (register screen)
- Modify: `tests/test_tui.py` (add tests)

- [ ] **Step 1: Write Matches screen test**

Add to `tests/test_tui.py`:

```python
async def test_matches_screen_shows_jobs(seeded_db):
    from src.tui.app import JobTrackerApp

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        await pilot.press("m")  # Navigate to matches
        table = app.screen.query_one("#matches-table", DataTable)
        assert table.row_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui.py::test_matches_screen_shows_jobs -v`
Expected: FAIL

- [ ] **Step 3: Create matches.py**

```python
import subprocess
import sys

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Static, DataTable, Footer, Input
from textual.binding import Binding


class MatchesScreen(Screen):
    """Sortable, filterable list of matched jobs."""

    BINDINGS = [
        Binding("enter", "open_detail", "Open", show=True),
        Binding("s", "set_status", "Set status", show=True),
        Binding("t", "tailor", "Tailor", show=True),
        Binding("o", "open_url", "Open URL", show=True),
        Binding("slash", "filter", "Filter", show=True),
        Binding("S", "cycle_sort", "Sort", show=True, key_display="⇧S"),
        Binding("escape", "app.switch_screen('dashboard')", "Back"),
    ]

    SORT_MODES = ["score", "date", "company"]

    def __init__(self):
        super().__init__()
        self._sort_index = 0
        self._filter_text = ""
        self._all_rows = []

    def compose(self) -> ComposeResult:
        yield Static("", id="matches-filter-bar")
        yield DataTable(id="matches-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#matches-table", DataTable)
        table.add_columns("Score", "PDF", "Status", "First Seen", "Company", "Title", "Location")
        self._load_data()
        self._update_filter_bar()

    def _load_data(self) -> None:
        db = self.app.db
        rows = db._conn.execute("""
            SELECT m.job_id, j.company, j.title, j.location, m.relevance_score,
                   CASE WHEN m.resume_path IS NOT NULL THEN '✓' ELSE '—' END as has_pdf,
                   COALESCE(a.status, 'new') as status,
                   j.first_seen_at
            FROM matches m JOIN jobs j ON m.job_id = j.id
            LEFT JOIN applications a ON m.job_id = a.job_id
            WHERE j.closed_at IS NULL
            ORDER BY m.relevance_score DESC
        """).fetchall()
        self._all_rows = [dict(r) for r in rows]
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#matches-table", DataTable)
        table.clear()

        filtered = self._all_rows
        if self._filter_text:
            ft = self._filter_text.lower()
            filtered = [
                r for r in filtered
                if ft in r["company"].lower() or ft in r["title"].lower()
            ]

        sort_key = self.SORT_MODES[self._sort_index]
        if sort_key == "score":
            filtered.sort(key=lambda r: r["relevance_score"], reverse=True)
        elif sort_key == "date":
            filtered.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)
        elif sort_key == "company":
            filtered.sort(key=lambda r: r["company"].lower())

        for r in filtered:
            seen = (r.get("first_seen_at") or "")[:10]
            table.add_row(
                f"{r['relevance_score']:.0%}",
                r["has_pdf"],
                r["status"],
                seen,
                r["company"],
                r["title"][:40],
                (r.get("location") or "")[:20],
                key=r["job_id"],
            )

    def _update_filter_bar(self) -> None:
        sort_name = self.SORT_MODES[self._sort_index].title()
        filter_info = f" Filter: '{self._filter_text}'" if self._filter_text else ""
        total = len(self._all_rows)
        table = self.query_one("#matches-table", DataTable)
        shown = table.row_count
        text = f"  Sort: {sort_name} ▼  ·  Showing {shown} of {total}{filter_info}"
        self.query_one("#matches-filter-bar", Static).update(text)

    def action_cycle_sort(self) -> None:
        self._sort_index = (self._sort_index + 1) % len(self.SORT_MODES)
        self._refresh_table()
        self._update_filter_bar()

    def action_filter(self) -> None:
        self.app.push_screen(FilterInput(self._filter_text), self._apply_filter)

    def _apply_filter(self, text: str) -> None:
        self._filter_text = text
        self._refresh_table()
        self._update_filter_bar()

    def _get_selected_job_id(self) -> str | None:
        table = self.query_one("#matches-table", DataTable)
        if table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return str(row_key.value)

    def action_open_detail(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            self.app.action_show_job(job_id)

    def action_set_status(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            self.app.action_set_job_status(job_id)

    def action_tailor(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            self.app.action_tailor_job(job_id)

    def action_open_url(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            job = self.app.db.get_job(job_id)
            if job and job.get("url"):
                subprocess.Popen(["open", job["url"]])
                self.notify(f"Opened {job['url']}")


class FilterInput(Screen):
    """Modal screen for entering filter text."""

    def __init__(self, current: str = ""):
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        yield Static("  Filter by company or title (Enter to apply, Esc to cancel):")
        yield Input(value=self._current, placeholder="Type to filter...")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def key_escape(self) -> None:
        self.dismiss(self._current)
```

- [ ] **Step 4: Register Matches screen in app.py**

Add import and register in `SCREENS` dict:

```python
from src.tui.screens.matches import MatchesScreen

# In SCREENS dict:
"matches": MatchesScreen,
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_tui.py -v`
Expected: All pass

- [ ] **Step 6: Manual smoke test**

Launch TUI, press `m`, verify matches table shows, arrow keys navigate, `S` changes sort, `/` opens filter, `Esc` goes back.

- [ ] **Step 7: Commit**

```
git add src/tui/screens/matches.py src/tui/app.py tests/test_tui.py
git commit -m "feat: implement Matches screen with sort, filter, and row actions"
```

---

### Task 4: Implement Job Detail screen

**Files:**
- Create: `src/tui/screens/job_detail.py`
- Modify: `src/tui/app.py` (register screen, implement `action_show_job`)
- Modify: `tests/test_tui.py` (add tests)

This is the most complex screen. Key features: scrollable content, on-demand analysis loading, checkbox edit selection, PDF auto-open.

- [ ] **Step 1: Write Job Detail test**

Add to `tests/test_tui.py`:

```python
async def test_job_detail_shows_analysis(seeded_db):
    """Test that job detail screen displays match data."""
    from src.tui.app import JobTrackerApp

    # Add suggestions to a match for testing
    import json
    suggestions = json.dumps({
        "key_requirements": ["5+ years management"],
        "suggested_edits": [
            {"original": "Led team", "suggested": "Led distributed team", "reason": "scope"}
        ],
        "keyword_gaps": ["fintech"],
        "interview_talking_points": ["scaling teams"],
    })
    seeded_db.update_match_suggestions("co:0", suggestions)

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        app.action_show_job("co:0")
        await pilot.pause()
        # Should show the job title somewhere on screen
        text = app.screen.query_one("#job-header").renderable
        assert text is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui.py::test_job_detail_shows_analysis -v`
Expected: FAIL

- [ ] **Step 3: Create job_detail.py**

```python
import json
import subprocess
import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, Footer, Checkbox
from textual.binding import Binding
from textual.worker import Worker


class EditCheckbox(Checkbox):
    """A checkbox for a suggested resume edit."""

    def __init__(self, index: int, edit: dict):
        label = f"[{index}] {edit['original'][:60]} → {edit['suggested'][:60]}"
        super().__init__(label, id=f"edit-{index}")
        self.edit_index = index


class JobDetailScreen(Screen):
    """Full job analysis with interactive edit selection."""

    BINDINGS = [
        Binding("t", "tailor", "Tailor PDF", show=True),
        Binding("e", "adopt_selected", "Adopt selected", show=True),
        Binding("E", "adopt_all", "Adopt all", show=True, key_display="⇧E"),
        Binding("v", "view_pdfs", "View PDFs", show=True),
        Binding("s", "set_status", "Set status", show=True),
        Binding("i", "interview_prep", "Interview prep", show=True),
        Binding("g", "gripes", "Gripes", show=True),
        Binding("o", "open_url", "Open URL", show=True),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="job-header")
        yield VerticalScroll(id="job-content")
        yield Footer()

    def on_mount(self) -> None:
        db = self.app.db
        job = db.get_job(self.job_id)
        match = db.get_match(self.job_id)
        if not job or not match:
            self.query_one("#job-header").update(f"Job not found: {self.job_id}")
            return

        app_row = db.get_application(self.job_id)
        status = app_row["status"] if app_row else "new"

        # Header
        score = f"{match['relevance_score']:.0%}"
        salary = f" · {job['salary']}" if job.get("salary") else ""
        location = job.get("location") or "N/A"
        header = (
            f"{job['company']} — {job['title']}\n"
            f"{score} match · {status} · {location}{salary}"
        )
        self.query_one("#job-header").update(header)

        # Build content
        content = self.query_one("#job-content", VerticalScroll)
        suggestions = json.loads(match.get("suggestions") or "{}")

        # Check if analysis exists, trigger on-demand if not
        if not suggestions.get("suggested_edits"):
            content.mount(Static("  Analyzing job... (this may take a moment)"))
            self._run_analysis()
            return

        self._render_analysis(suggestions, match)

    def _run_analysis(self) -> None:
        """Run LLM analysis in background worker."""
        self.run_worker(self._do_analysis, thread=True)

    async def _do_analysis(self) -> dict:
        from src.steps.tailor import ensure_analysis
        job = self.app.db.get_job(self.job_id)
        return ensure_analysis(dict(job), self.app.db, self.app.config, force=False)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "SUCCESS":
            match = self.app.db.get_match(self.job_id)
            suggestions = json.loads(match.get("suggestions") or "{}")
            content = self.query_one("#job-content", VerticalScroll)
            content.remove_children()
            self._render_analysis(suggestions, match)

    def _render_analysis(self, suggestions: dict, match: dict) -> None:
        content = self.query_one("#job-content", VerticalScroll)

        # Why this matches
        content.mount(Static("  WHY THIS MATCHES", classes="section-header"))
        content.mount(Static(f"  {match['match_reason']}"))

        # Key requirements
        if suggestions.get("key_requirements"):
            content.mount(Static("  KEY REQUIREMENTS", classes="section-header"))
            for req in suggestions["key_requirements"]:
                content.mount(Static(f"  • {req}"))

        # Interview talking points
        if suggestions.get("interview_talking_points"):
            content.mount(Static("  INTERVIEW TALKING POINTS", classes="section-header"))
            for tp in suggestions["interview_talking_points"]:
                content.mount(Static(f"  • {tp}"))

        # Suggested edits (interactive)
        edits = suggestions.get("suggested_edits", [])
        if edits:
            content.mount(Static("  SUGGESTED RESUME EDITS  (Space=toggle, e=adopt selected, E=adopt all)", classes="section-header"))
            for i, edit in enumerate(edits, 1):
                content.mount(EditCheckbox(i, edit))
                content.mount(Static(f"    Current:   {edit['original']}"))
                content.mount(Static(f"    Suggested: {edit['suggested']}"))
                content.mount(Static(f"    Why: {edit['reason']}"))
                content.mount(Static(""))

        # Keyword gaps
        if suggestions.get("keyword_gaps"):
            gaps = ", ".join(suggestions["keyword_gaps"])
            content.mount(Static("  KEYWORD GAPS", classes="section-header"))
            content.mount(Static(f"  {gaps}"))

        # PDF paths
        if match.get("resume_path") or match.get("cover_letter_path"):
            content.mount(Static("  GENERATED PDFs", classes="section-header"))
            if match.get("resume_path"):
                content.mount(Static(f"  Resume: {match['resume_path']}"))
            if match.get("cover_letter_path"):
                content.mount(Static(f"  Cover letter: {match['cover_letter_path']}"))

    def _get_selected_edit_indices(self) -> set[int]:
        indices = set()
        for cb in self.query(EditCheckbox):
            if cb.value:
                indices.add(cb.edit_index)
        return indices

    def action_tailor(self) -> None:
        self.notify("Generating PDFs...")
        self.run_worker(self._do_tailor, thread=True)

    async def _do_tailor(self, adopt: set[int] | None = None) -> None:
        from datetime import datetime, timezone
        from src.steps.tailor import get_active_resume_yaml, run_tailor_for_job, ensure_analysis

        db = self.app.db
        config = self.app.config
        job = db.get_job(self.job_id)
        analysis = ensure_analysis(dict(job), db, config, force=True)
        resume_yaml_path, resume_data = get_active_resume_yaml(config)
        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        output_dir = config.output_dir / run_date
        result = run_tailor_for_job(
            job=dict(job),
            analysis=analysis,
            resume_yaml_path=resume_yaml_path,
            resume_data=resume_data,
            output_dir=output_dir,
            config=config,
            adopt_edits=adopt or set(),
        )
        db.update_match_paths(
            self.job_id,
            resume_path=str(result["resume_pdf"]) if result.get("resume_pdf") else None,
            cover_letter_path=str(result["cover_letter_pdf"]) if result.get("cover_letter_pdf") else None,
        )
        # Auto-open PDFs
        for key in ("resume_pdf", "cover_letter_pdf"):
            path = result.get(key)
            if path and Path(path).exists():
                subprocess.Popen(["open", str(path)])
        self.app.call_from_thread(self.notify, "PDFs generated and opened")

    def action_adopt_selected(self) -> None:
        indices = self._get_selected_edit_indices()
        if not indices:
            self.notify("No edits selected")
            return
        self.notify(f"Adopting edits {sorted(indices)} and generating PDFs...")
        self.run_worker(lambda: self._do_tailor(adopt=indices), thread=True)

    def action_adopt_all(self) -> None:
        all_indices = {cb.edit_index for cb in self.query(EditCheckbox)}
        if not all_indices:
            self.notify("No edits available")
            return
        self.notify(f"Adopting all {len(all_indices)} edits and generating PDFs...")
        self.run_worker(lambda: self._do_tailor(adopt=all_indices), thread=True)

    def action_view_pdfs(self) -> None:
        match = self.app.db.get_match(self.job_id)
        if not match:
            return
        opened = False
        for key in ("resume_path", "cover_letter_path"):
            path = match.get(key)
            if path and Path(path).exists():
                subprocess.Popen(["open", path])
                opened = True
        if opened:
            self.notify("PDFs opened")
        else:
            self.notify("No PDFs generated yet — press [t] to generate")

    def action_set_status(self) -> None:
        self.app.action_set_job_status(self.job_id)

    def action_interview_prep(self) -> None:
        self.notify("Generating interview prep...")
        self.run_worker(self._do_interview_prep, thread=True)

    async def _do_interview_prep(self) -> None:
        from src.steps.interview_prep import generate_interview_prep
        generate_interview_prep(self.app.db, self.job_id)
        self.app.call_from_thread(self.notify, "Interview prep written to Obsidian")

    def action_gripes(self) -> None:
        self.notify("Fetching company gripes...")
        self.run_worker(self._do_gripes, thread=True)

    async def _do_gripes(self) -> None:
        from src.steps.gripes import get_gripes
        job = self.app.db.get_job(self.job_id)
        gripes = get_gripes(self.app.db, job["company"], self.app.config)
        if gripes:
            content = self.query_one("#job-content", VerticalScroll)

            def mount_gripes():
                content.mount(Static("  COMPANY GRIPES", classes="section-header"))
                for category, items in gripes.items():
                    content.mount(Static(f"  {category}:"))
                    if isinstance(items, list):
                        for item in items:
                            content.mount(Static(f"    • {item}"))

            self.app.call_from_thread(mount_gripes)
        else:
            self.app.call_from_thread(self.notify, "Could not fetch gripes")

    def action_open_url(self) -> None:
        job = self.app.db.get_job(self.job_id)
        if job and job.get("url"):
            subprocess.Popen(["open", job["url"]])
            self.notify(f"Opened {job['url']}")

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

- [ ] **Step 4: Update app.py with show_job action and status popup**

Add to `app.py`:

```python
from src.tui.screens.job_detail import JobDetailScreen

# Update action_show_job:
def action_show_job(self, job_id: str) -> None:
    self.push_screen(JobDetailScreen(job_id))

def action_set_job_status(self, job_id: str) -> None:
    from src.tui.widgets.status_popup import StatusPopup
    self.push_screen(StatusPopup(job_id), self._on_status_set)

def _on_status_set(self, result: tuple[str, str] | None) -> None:
    if result:
        job_id, new_status = result
        self.db.set_application_status(job_id, new_status)
        # Side effects
        if new_status in ("applied", "interviewing"):
            from src.pipeline import _compute_follow_up_date
            app = self.db.get_application(job_id)
            follow_up = _compute_follow_up_date(app.get("applied_date") if app else None)
            self.db.set_follow_up_date(job_id, follow_up)
        if new_status == "interviewing":
            try:
                from src.steps.interview_prep import generate_interview_prep
                generate_interview_prep(self.db, job_id)
            except Exception:
                pass
        try:
            from src.steps.obsidian import write_application_note, write_dashboard
            write_application_note(job_id, self.db, self.config)
            write_dashboard(self.db, self.config)
        except Exception:
            pass
        self.notify(f"Status → {new_status}")

def action_tailor_job(self, job_id: str) -> None:
    """Quick tailor from matches list — push to job detail."""
    self.push_screen(JobDetailScreen(job_id))
```

- [ ] **Step 5: Create status_popup.py widget**

Create `src/tui/widgets/__init__.py` (empty) and `src/tui/widgets/status_popup.py`:

```python
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option


STATUSES = ["new", "applied", "interviewing", "offer", "rejected", "withdrawn"]


class StatusPopup(ModalScreen):
    """Modal popup for selecting application status."""

    DEFAULT_CSS = """
    StatusPopup {
        align: center middle;
    }
    #status-dialog {
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
        width: 40;
        height: auto;
        max-height: 14;
    }
    """

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def compose(self) -> ComposeResult:
        with Vertical(id="status-dialog"):
            yield Static("  Set application status:")
            yield OptionList(
                *[Option(s, id=s) for s in STATUSES],
                id="status-list",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss((self.job_id, event.option.id))

    def key_escape(self) -> None:
        self.dismiss(None)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_tui.py -v`
Expected: All pass

- [ ] **Step 7: py_compile all new files**

Run: `uv run python -m py_compile src/tui/screens/job_detail.py && uv run python -m py_compile src/tui/widgets/status_popup.py`
Expected: No errors

- [ ] **Step 8: Commit**

```
git add src/tui/screens/job_detail.py src/tui/widgets/ src/tui/app.py tests/test_tui.py
git commit -m "feat: implement Job Detail screen with edit selection, PDF auto-open, and status popup"
```

---

### Task 5: Implement Applications screen

**Files:**
- Create: `src/tui/screens/applications.py`
- Modify: `src/tui/app.py` (register screen)
- Modify: `tests/test_tui.py` (add tests)

- [ ] **Step 1: Write Applications screen test**

Add to `tests/test_tui.py`:

```python
async def test_applications_screen_grouped(seeded_db):
    """Test that applications screen groups by status."""
    from src.tui.app import JobTrackerApp

    seeded_db.set_application_status("co:0", "interviewing")
    seeded_db.set_application_status("co:2", "applied")

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        await pilot.press("a")
        # Should have application data rendered
        tables = app.screen.query(DataTable)
        assert len(tables) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui.py::test_applications_screen_grouped -v`
Expected: FAIL

- [ ] **Step 3: Create applications.py**

```python
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, DataTable, Footer, Input
from textual.binding import Binding


STATUS_ORDER = ["interviewing", "applied", "offer", "new", "closed", "rejected", "withdrawn"]
STATUS_COLORS = {
    "interviewing": "#a371f7",
    "applied": "#3fb950",
    "offer": "#f0883e",
    "new": "#8b949e",
    "closed": "#8b949e",
    "rejected": "#484f58",
    "withdrawn": "#484f58",
}
COLLAPSED_DEFAULT = {"closed", "rejected", "withdrawn"}


class ApplicationsScreen(Screen):
    """Application tracking grouped by status."""

    BINDINGS = [
        Binding("enter", "open_detail", "Open", show=True),
        Binding("s", "set_status", "Change status", show=True),
        Binding("f", "set_followup", "Set follow-up", show=True),
        Binding("F", "mark_followed_up", "Followed up", show=True, key_display="⇧F"),
        Binding("n", "salary_notes", "Salary notes", show=True),
        Binding("escape", "app.switch_screen('dashboard')", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="apps-content")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        content = self.query_one("#apps-content", VerticalScroll)
        content.remove_children()

        db = self.app.db
        apps = db.get_all_applications()
        overdue = {f["job_id"]: int(f.get("days_overdue") or 0) for f in db.get_overdue_follow_ups()}

        # Group by status
        groups = {}
        for app in apps:
            status = app.get("status", "new")
            groups.setdefault(status, []).append(app)

        for status in STATUS_ORDER:
            items = groups.get(status, [])
            if not items:
                continue

            color = STATUS_COLORS.get(status, "#484f58")
            collapsed = status in COLLAPSED_DEFAULT

            if collapsed:
                content.mount(Static(
                    f"  ▶ {status.title()} ({len(items)}) — press Enter to expand",
                    id=f"group-{status}",
                ))
                continue

            content.mount(Static(
                f"  ● {status.upper()} ({len(items)})",
                id=f"group-{status}",
            ))

            table = DataTable(id=f"table-{status}", cursor_type="row")
            table.add_columns("Score", "Company", "Title", "Applied", "Follow-up")
            for app in items:
                score = f"{app['relevance_score']:.0%}" if app.get("relevance_score") else "N/A"
                applied = (app.get("applied_date") or "")[:10]
                job_id = app["job_id"]

                # Follow-up display
                if job_id in overdue:
                    days = overdue[job_id]
                    followup = f"⚠ {days}d overdue"
                elif app.get("salary_notes"):
                    followup = app["salary_notes"][:20]
                else:
                    followup = ""

                table.add_row(
                    score,
                    app["company"][:15],
                    app["title"][:35],
                    applied,
                    followup,
                    key=job_id,
                )
            content.mount(table)

    def _get_active_table(self) -> DataTable | None:
        for table in self.query(DataTable):
            if table.has_focus:
                return table
        tables = list(self.query(DataTable))
        return tables[0] if tables else None

    def _get_selected_job_id(self) -> str | None:
        table = self._get_active_table()
        if not table or table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return str(row_key.value)

    def action_open_detail(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            self.app.action_show_job(job_id)

    def action_set_status(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            self.app.action_set_job_status(job_id)

    def action_set_followup(self) -> None:
        job_id = self._get_selected_job_id()
        if not job_id:
            return

        def on_date(date_str: str) -> None:
            if date_str:
                self.app.db.set_follow_up_date(job_id, date_str)
                self.notify(f"Follow-up set: {date_str}")
                self._load_data()

        self.app.push_screen(DateInput(), on_date)

    def action_mark_followed_up(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            self.app.db.mark_followed_up(job_id)
            self.notify("Marked as followed up, reset +7 days")
            self._load_data()

    def action_salary_notes(self) -> None:
        job_id = self._get_selected_job_id()
        if not job_id:
            return

        def on_notes(notes: str) -> None:
            if notes:
                app = self.app.db.get_application(job_id)
                if not app:
                    self.app.db.set_application_status(job_id, "new")
                self.app.db.update_salary_notes(job_id, notes)
                self.notify("Salary notes saved")
                self._load_data()

        self.app.push_screen(TextInput("Salary notes:"), on_notes)


class DateInput(Screen):
    """Modal for entering a date."""

    DEFAULT_CSS = """
    DateInput { align: center middle; }
    #date-dialog { background: #161b22; border: solid #30363d; padding: 1 2; width: 40; height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="date-dialog"):
            yield Static("  Follow-up date (YYYY-MM-DD):")
            yield Input(placeholder="2026-04-16")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def key_escape(self) -> None:
        self.dismiss("")


class TextInput(Screen):
    """Generic modal text input."""

    DEFAULT_CSS = """
    TextInput { align: center middle; }
    #text-dialog { background: #161b22; border: solid #30363d; padding: 1 2; width: 50; height: auto; }
    """

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="text-dialog"):
            yield Static(f"  {self.prompt}")
            yield Input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def key_escape(self) -> None:
        self.dismiss("")
```

- [ ] **Step 4: Register Applications screen in app.py**

Add import and register:

```python
from src.tui.screens.applications import ApplicationsScreen

# In SCREENS:
"applications": ApplicationsScreen,
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_tui.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```
git add src/tui/screens/applications.py src/tui/app.py tests/test_tui.py
git commit -m "feat: implement Applications screen with status groups and follow-up management"
```

---

### Task 6: Implement Pipeline screen

**Files:**
- Create: `src/tui/screens/pipeline.py`
- Modify: `src/tui/app.py` (register screen)
- Modify: `tests/test_tui.py` (add tests)

- [ ] **Step 1: Write Pipeline screen test**

Add to `tests/test_tui.py`:

```python
async def test_pipeline_screen_shows_history(seeded_db):
    """Test that pipeline screen shows run history."""
    from src.tui.app import JobTrackerApp

    r1 = seeded_db.start_run()
    seeded_db.complete_run(r1, jobs_scraped=100, new_jobs=5, matches_found=2, email_sent=True)

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        await pilot.press("p")
        table = app.screen.query_one("#run-history", DataTable)
        assert table.row_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui.py::test_pipeline_screen_shows_history -v`
Expected: FAIL

- [ ] **Step 3: Create pipeline.py**

```python
import logging
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, DataTable, Footer, Button
from textual.binding import Binding
from textual.worker import Worker

logger = logging.getLogger(__name__)


class PipelineScreen(Screen):
    """Trigger pipeline runs and view history."""

    BINDINGS = [
        Binding("r", "run_full", "Full pipeline", show=True),
        Binding("1", "run_scrape", "Scrape", show=True),
        Binding("2", "run_filter", "Filter", show=True),
        Binding("3", "run_prune", "Prune", show=True),
        Binding("R", "renotify", "Renotify", show=True, key_display="⇧R"),
        Binding("escape", "app.switch_screen('dashboard')", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("  Pipeline Control", classes="section-header")
        with Horizontal(id="pipeline-buttons"):
            yield Static("  [r] Full Pipeline  ·  [1] Scrape  ·  [2] Filter  ·  [3] Prune  ·  [R] Renotify")
        yield Static("", id="pipeline-progress")
        yield Static("  Run History", classes="section-header")
        yield DataTable(id="run-history")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#run-history", DataTable)
        table.add_columns("When", "Jobs", "New", "Matches", "Email", "Duration", "Status")
        self._load_history()

    def _load_history(self) -> None:
        table = self.query_one("#run-history", DataTable)
        table.clear()
        runs = self.app.db.get_recent_runs(limit=15)
        for run in runs:
            completed = run.get("completed_at")
            started = run.get("started_at", "")

            # When
            when = completed[:16].replace("T", " ") if completed else started[:16].replace("T", " ")

            # Duration
            duration = ""
            if completed and started:
                try:
                    s = datetime.fromisoformat(started)
                    e = datetime.fromisoformat(completed)
                    dur = (e - s).total_seconds()
                    duration = f"{dur:.0f}s"
                except (ValueError, TypeError):
                    pass

            # Status
            error = run.get("error")
            status = "error" if error else ("success" if completed else "running")

            email = "✓" if run.get("email_sent") else ("✗" if completed else "—")

            table.add_row(
                when,
                str(run.get("jobs_scraped", 0)),
                str(run.get("new_jobs", 0)),
                str(run.get("matches_found", 0)),
                email,
                duration,
                status,
            )

    def _update_progress(self, text: str) -> None:
        self.query_one("#pipeline-progress", Static).update(f"  {text}")

    def _run_pipeline_step(self, step_name: str, fn) -> None:
        self._update_progress(f"⟳ Running {step_name}...")

        def do_run():
            try:
                result = fn()
                self.app.call_from_thread(self._update_progress, f"✓ {step_name} complete: {result}")
                self.app.call_from_thread(self._load_history)
            except Exception as e:
                self.app.call_from_thread(self._update_progress, f"✗ {step_name} failed: {e}")

        self.run_worker(do_run, thread=True)

    def action_run_full(self) -> None:
        from src.pipeline import build_scrapers
        config = self.app.config
        db = self.app.db

        def do_full():
            from src.steps.scrape import run_scrape
            from src.steps.dedup import run_dedup
            from src.steps.filter import run_filter
            from src.pipeline import get_resume_summary
            from src.steps.tailor import get_active_resume_yaml

            self.app.call_from_thread(self._update_progress, "⟳ Scraping...")
            scrapers = build_scrapers(config)
            scrape_result = run_scrape(db, scrapers)
            self.app.call_from_thread(
                self._update_progress,
                f"✓ Scrape: {scrape_result['jobs_scraped']} jobs, {scrape_result['new_jobs']} new\n  ⟳ Deduplicating..."
            )

            run_dedup(db)
            self.app.call_from_thread(self._update_progress,
                "✓ Scrape + Dedup done\n  ⟳ Filtering...")

            _, resume_data = get_active_resume_yaml(config)
            resume_summary = get_resume_summary(resume_data)
            new_ids = scrape_result["new_job_ids"]
            matches = run_filter(db, new_ids, resume_summary, config)
            self.app.call_from_thread(
                self._update_progress,
                f"✓ Pipeline complete: {scrape_result['new_jobs']} new jobs, {len(matches)} matches"
            )
            self.app.call_from_thread(self._load_history)
            return f"{scrape_result['new_jobs']} new, {len(matches)} matches"

        self.run_worker(do_full, thread=True)

    def action_run_scrape(self) -> None:
        from src.pipeline import build_scrapers
        config = self.app.config
        db = self.app.db

        def do_scrape():
            from src.steps.scrape import run_scrape
            from src.steps.dedup import run_dedup
            scrapers = build_scrapers(config)
            result = run_scrape(db, scrapers)
            run_dedup(db)
            return f"{result['jobs_scraped']} jobs, {result['new_jobs']} new"

        self._run_pipeline_step("Scrape", do_scrape)

    def action_run_filter(self) -> None:
        config = self.app.config
        db = self.app.db

        def do_filter():
            from src.steps.filter import run_filter
            from src.steps.tailor import get_active_resume_yaml
            from src.pipeline import get_resume_summary
            rows = db._conn.execute(
                "SELECT id FROM jobs WHERE id NOT IN (SELECT job_id FROM matches) AND closed_at IS NULL"
            ).fetchall()
            new_ids = [r["id"] for r in rows]
            _, resume_data = get_active_resume_yaml(config)
            resume_summary = get_resume_summary(resume_data)
            matches = run_filter(db, new_ids, resume_summary, config)
            return f"{len(new_ids)} evaluated, {len(matches)} matches"

        self._run_pipeline_step("Filter", do_filter)

    def action_run_prune(self) -> None:
        from src.pipeline import build_scrapers
        config = self.app.config
        db = self.app.db

        def do_prune():
            import time as _time
            scrapers = build_scrapers(config)
            scraper_map = {s.company_name: s for s in scrapers}
            rows = db._conn.execute("""
                SELECT m.job_id, j.company, j.title, j.url,
                       COALESCE(a.status, 'new') as app_status
                FROM matches m JOIN jobs j ON m.job_id = j.id
                LEFT JOIN applications a ON m.job_id = a.job_id
                WHERE j.closed_at IS NULL
                ORDER BY j.company
            """).fetchall()
            pruned = 0
            current_company = None
            for row in rows:
                scraper = scraper_map.get(row["company"])
                if not scraper:
                    continue
                if row["company"] == current_company:
                    _time.sleep(0.5)
                current_company = row["company"]
                result = scraper.is_job_live(row["url"])
                if result is False:
                    db.close_job(row["job_id"])
                    if row["app_status"] in ("applied", "interviewing"):
                        db.set_application_status(row["job_id"], "closed")
                    pruned += 1
            return f"{pruned} stale jobs pruned"

        self._run_pipeline_step("Prune", do_prune)

    def action_renotify(self) -> None:
        db = self.app.db
        config = self.app.config

        def do_renotify():
            from src.steps.notify import run_notify
            run_stats = {"jobs_scraped": 0, "new_jobs": 0, "matches_found": 0, "duration": "renotify"}
            success = run_notify(db, run_stats, config)
            return "sent" if success else "failed"

        self._run_pipeline_step("Renotify", do_renotify)
```

- [ ] **Step 4: Register Pipeline screen in app.py**

```python
from src.tui.screens.pipeline import PipelineScreen

# In SCREENS:
"pipeline": PipelineScreen,
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_tui.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```
git add src/tui/screens/pipeline.py src/tui/app.py tests/test_tui.py
git commit -m "feat: implement Pipeline screen with run triggers, live progress, and history"
```

---

### Task 7: Wire entry point and final integration

**Files:**
- Modify: `src/pipeline.py` (add TUI default routing)
- Modify: `tests/test_pipeline.py` (add entry point test)

- [ ] **Step 1: Write entry point test**

Add to `tests/test_pipeline.py`:

```python
def test_has_cli_flags_detects_flags():
    from src.pipeline import parse_args, has_cli_flags
    # No flags = TUI
    args = parse_args([])
    assert not has_cli_flags(args)
    # With flag = CLI
    args = parse_args(["--list-matches"])
    assert has_cli_flags(args)
    args = parse_args(["--step", "scrape"])
    assert has_cli_flags(args)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py::test_has_cli_flags_detects_flags -v`
Expected: FAIL — `has_cli_flags` doesn't exist

- [ ] **Step 3: Implement has_cli_flags and update main()**

Add to `src/pipeline.py`:

```python
def has_cli_flags(args) -> bool:
    """Return True if any CLI flag is set (non-default value)."""
    for key, value in vars(args).items():
        if value is not None and value is not False:
            return True
    return False
```

Update `main()`:

```python
def main():
    args = parse_args()
    if has_cli_flags(args):
        run_pipeline(args)
    else:
        from src.tui.app import JobTrackerApp
        JobTrackerApp().run()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_pipeline.py::test_has_cli_flags_detects_flags -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest`
Expected: All tests pass (existing + new)

- [ ] **Step 6: Manual end-to-end test**

Run: `uv run jobtracker`
Expected: TUI launches with dashboard. Navigate all screens: `d`, `m`, `a`, `p`. Open a job detail with Enter. Press `q` to quit.

Run: `uv run jobtracker --list-matches`
Expected: Old CLI output (not TUI)

- [ ] **Step 7: Commit**

```
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: route default entry point to TUI, CLI flags preserved for automation"
```

---

### Task 8: Polish and cleanup

**Files:**
- Modify: `src/tui/styles.tcss` (refine as needed)
- Modify: `CLAUDE.md` (document TUI)
- Modify: `.gitignore` (add .superpowers/)

- [ ] **Step 1: Add .superpowers/ to .gitignore**

Append `.superpowers/` to `.gitignore`.

- [ ] **Step 2: Update CLAUDE.md Commands section**

Add to the Commands section:

```markdown
# Launch TUI (default)
uv run jobtracker

# CLI flags still work for automation
uv run jobtracker --step scrape
uv run jobtracker --dry-run
```

Update the description to note: "Running `uv run jobtracker` with no flags launches the Textual TUI. All existing CLI flags continue to work for scripting and launchd automation."

- [ ] **Step 3: Run full test suite one final time**

Run: `uv run pytest`
Expected: All tests pass

- [ ] **Step 4: Commit**

```
git add .gitignore CLAUDE.md src/tui/styles.tcss
git commit -m "chore: add .superpowers to gitignore, document TUI in CLAUDE.md"
```
