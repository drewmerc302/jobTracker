import subprocess

from textual.app import ComposeResult
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
        Binding("x", "dismiss", "Dismiss", show=True),
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
        table.add_columns(
            "Score", "PDF", "Status", "First Seen", "Company", "Title", "Location"
        )
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
            WHERE j.closed_at IS NULL AND m.dismissed_at IS NULL
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
                r
                for r in filtered
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

    def action_dismiss(self) -> None:
        job_id = self._get_selected_job_id()
        if job_id:
            job = self.app.db.get_job(job_id)
            self.app.db.dismiss_match(job_id)
            self._load_data()
            self._update_filter_bar()
            name = f"{job['company']} — {job['title']}" if job else job_id
            self.notify(f"Dismissed: {name}")


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
