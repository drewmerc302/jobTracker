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
        yield Static(
            self.card_value,
            classes=f"card-value {self.value_class}",
            id=f"val-{self.card_title.lower().replace(' ', '-')}",
        )
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
        active_count = sum(
            1 for a in apps if a.get("status") in ("applied", "interviewing", "offer")
        )
        active_detail = []
        for s in ("applied", "interviewing", "offer"):
            c = sum(1 for a in apps if a.get("status") == s)
            if c:
                active_detail.append(f"{c} {s}")

        # "New since last session" tracking
        last_open = self.app.get_last_tui_open()
        new_count = (
            db.count_matches_since(last_open) if last_open else stats["total_matches"]
        )

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
                yield Static(
                    " Recent Matches · press [m] for full list ",
                    classes="section-header",
                )
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
                fu_table.add_row(f["company"], f["title"][:35], f"{days}d")
        except Exception:
            pass

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
