import subprocess

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, DataTable, Footer, Input
from textual.binding import Binding


class MatchesScreen(Screen):
    """Sortable, filterable list of matched jobs."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("space", "open_detail", "Open", show=False),
        Binding("s", "set_status", "Set status", show=True),
        Binding("t", "tailor", "Tailor", show=True),
        Binding("o", "open_url", "Open URL", show=True),
        Binding("slash", "filter", "Filter", show=True),
        Binding("S", "cycle_sort", "Sort", show=True, key_display="⇧S"),
        Binding("x", "dismiss", "Dismiss", show=True),
        Binding("escape", "app.switch_screen('dashboard')", "Back"),
    ]

    SORT_MODES = ["score", "date", "company", "source"]

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
            "Score",
            "PDF",
            "Status",
            "First Seen",
            "Source",
            "Company",
            "Title",
            "Location",
        )
        self._load_data()
        self._update_filter_bar()

    def _load_data(self) -> None:
        self._all_rows = self.app.db.get_active_matches()
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
                if ft in r["company"].lower()
                or ft in r["title"].lower()
                or ft in (r.get("source") or "").lower()
            ]

        sort_key = self.SORT_MODES[self._sort_index]
        if sort_key == "score":
            filtered.sort(
                key=lambda r: (bool(r.get("closed_at")), -r["relevance_score"])
            )
        elif sort_key == "date":
            filtered.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)
            filtered.sort(key=lambda r: bool(r.get("closed_at")))
        elif sort_key == "company":
            filtered.sort(key=lambda r: r["company"].lower())
            filtered.sort(key=lambda r: bool(r.get("closed_at")))
        elif sort_key == "source":
            filtered.sort(key=lambda r: r["company"].lower())
            filtered.sort(key=lambda r: (r.get("source") or "zzz").lower())
            filtered.sort(key=lambda r: bool(r.get("closed_at")))

        for r in filtered:
            seen = (r.get("first_seen_at") or "")[:10]
            is_closed = bool(r.get("closed_at"))
            title = r["title"][:57]
            if is_closed:
                title = f"[strike]{title}[/strike]"
            company = r["company"]
            if is_closed:
                company = f"[dim]{company}[/dim]"
            score_str = f"{r['relevance_score']:.0%}"
            if is_closed:
                score_str = f"[dim]{score_str}[/dim]"
            status_str = r["status"]
            if is_closed:
                status_str = f"[red]✕[/red] {status_str}"
            source_str = r.get("source") or "—"
            if is_closed:
                source_str = f"[dim]{source_str}[/dim]"
            table.add_row(
                score_str,
                r["has_pdf"],
                status_str,
                seen,
                source_str,
                company,
                title,
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        job_id = str(event.row_key.value)
        if job_id:
            self.app.action_show_job(job_id)

    def action_cursor_down(self) -> None:
        table = self.query_one("#matches-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.query_one("#matches-table", DataTable)
        table.action_cursor_up()

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
            table = self.query_one("#matches-table", DataTable)
            cursor_row = table.cursor_coordinate.row
            job = self.app.db.get_job(job_id)
            self.app.db.dismiss_match(job_id)
            self._load_data()
            self._update_filter_bar()
            # Restore cursor near previous position
            if table.row_count > 0:
                new_row = min(cursor_row, table.row_count - 1)
                table.move_cursor(row=new_row)
            name = f"{job['company']} — {job['title']}" if job else job_id
            self.notify(f"Dismissed: {name}")


class FilterInput(Screen):
    """Modal screen for entering filter text."""

    DEFAULT_CSS = """
    FilterInput { align: center middle; }
    #filter-dialog { background: #161b22; border: solid #30363d; padding: 1 2; width: 60; height: auto; }
    """

    def __init__(self, current: str = ""):
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-dialog"):
            yield Static(
                "  Filter by company or title (Enter to apply, Esc to cancel):"
            )
            yield Input(value=self._current, placeholder="Type to filter...")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def key_escape(self) -> None:
        self.dismiss(self._current)
