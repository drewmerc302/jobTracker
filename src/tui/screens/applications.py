from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, DataTable, Footer, Input
from textual.binding import Binding


STATUS_ORDER = [
    "interviewing",
    "applied",
    "offer",
    "interested",
    "new",
    "closed",
    "rejected",
    "withdrawn",
]
COLLAPSED_DEFAULT = {"closed", "rejected", "withdrawn"}


class ApplicationsScreen(Screen):
    """Application tracking grouped by status."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("space", "open_detail", "Open", show=False),
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
        overdue = {
            f["job_id"]: int(f.get("days_overdue") or 0)
            for f in db.get_overdue_follow_ups()
        }

        groups: dict = {}
        for app in apps:
            status = app.get("status", "new")
            groups.setdefault(status, []).append(app)

        for status in STATUS_ORDER:
            items = groups.get(status, [])
            if not items:
                continue

            collapsed = status in COLLAPSED_DEFAULT

            if collapsed:
                content.mount(
                    Static(
                        f"  ▶ {status.title()} ({len(items)}) — press Enter to expand",
                        id=f"group-{status}",
                    )
                )
                continue

            content.mount(
                Static(
                    f"  ● {status.upper()} ({len(items)})",
                    id=f"group-{status}",
                )
            )

            table = DataTable(id=f"table-{status}", cursor_type="row")
            table.add_columns("Score", "Company", "Title", "Applied", "Follow-up")
            for app_item in items:
                score = (
                    f"{app_item['relevance_score']:.0%}"
                    if app_item.get("relevance_score")
                    else "N/A"
                )
                applied = (app_item.get("applied_date") or "")[:10]
                job_id = app_item["job_id"]

                if job_id in overdue:
                    days = overdue[job_id]
                    followup = f"⚠ {days}d overdue"
                elif app_item.get("salary_notes"):
                    followup = app_item["salary_notes"][:20]
                else:
                    followup = ""

                table.add_row(
                    score,
                    app_item["company"][:15],
                    app_item["title"][:35],
                    applied,
                    followup,
                    key=job_id,
                )
            content.mount(table)

    def _get_active_table(self) -> DataTable | None:
        for table in self.query(DataTable):
            if table.has_focus:
                return table
        return None

    def _get_selected_job_id(self) -> str | None:
        table = self._get_active_table()
        if not table or table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return str(row_key.value)

    def action_cursor_down(self) -> None:
        table = self._get_active_table()
        if table:
            table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self._get_active_table()
        if table:
            table.action_cursor_up()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        job_id = str(event.row_key.value)
        if job_id:
            self.app.action_show_job(job_id)

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
