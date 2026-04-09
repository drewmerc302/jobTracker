from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.binding import Binding
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
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("space", "open_detail", "Open", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="summary-cards"):
            yield SummaryCard("New Matches", "—", "loading...", css_class="blue")
            yield SummaryCard("Active Apps", "—", "loading...", css_class="blue")
            yield SummaryCard("Overdue Follow-ups", "—", "loading...", css_class="blue")
            yield SummaryCard("Total Matches", "—", "loading...", css_class="blue")

        with Horizontal(id="dashboard-body"):
            with Vertical(id="left-panel"):
                yield Static(
                    " Top Matches · press \\[m] for full list ",
                    classes="section-header",
                    id="recent-matches-header",
                )
                table = DataTable(id="recent-matches", cursor_type="row")
                table.add_columns("Score", "Company", "Title", "Status")
                yield table

            with Vertical(id="right-panel"):
                yield Static(" ⚠ Overdue Follow-ups ", classes="section-header")
                fu_table = DataTable(id="overdue-followups", cursor_type="row")
                fu_table.add_columns("Company", "Title", "Overdue")
                yield fu_table

                yield Static(" Pipeline Status ", classes="section-header")
                yield Static("", id="pipeline-status")

        yield Footer()

    def on_mount(self) -> None:
        db = self.app.db

        # Populate summary cards (moved from compose to avoid blocking first frame)
        stats = db.get_match_stats()
        overdue_list = db.get_overdue_follow_ups()
        apps = db.get_all_applications()
        active_count = sum(
            1 for a in apps if a.get("status") in ("applied", "interviewing", "offer")
        )
        active_detail = []
        for s in ("applied", "interviewing", "offer"):
            c = sum(1 for a in apps if a.get("status") == s)
            if c:
                active_detail.append(f"{c} {s}")
        last_open = self.app.get_last_tui_open()
        new_count = (
            db.count_matches_since(last_open) if last_open else stats["total_matches"]
        )

        cards = list(self.query(SummaryCard))
        if len(cards) >= 4:
            cards[0].query_one(".card-value").update(str(new_count))
            cards[0].query_one(".card-detail").update("since last session")
            cards[1].query_one(".card-value").update(str(active_count))
            cards[1].query_one(".card-detail").update(
                " · ".join(active_detail) if active_detail else "none"
            )
            cards[2].query_one(".card-value").update(str(len(overdue_list)))
            cards[2].query_one(".card-detail").update(
                f"oldest: {overdue_list[0]['follow_up_after']}"
                if overdue_list
                else "all clear"
            )
            cards[3].query_one(".card-value").update(str(stats["total_matches"]))
            cards[3].query_one(".card-detail").update(
                f"avg score: {stats['avg_score']:.0%}"
            )

        # Populate recent matches
        rows = db.get_top_matches(limit=15)
        total = stats["total_matches"]
        header_text = (
            f" Top Matches ({len(rows)} of {total}) · press \\[m] for full list "
        )
        self.query_one("#recent-matches-header").update(header_text)
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

    def action_cursor_down(self) -> None:
        table = self.query_one("#recent-matches", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.query_one("#recent-matches", DataTable)
        table.action_cursor_up()

    def action_open_detail(self) -> None:
        table = self.query_one("#recent-matches", DataTable)
        if table.row_count == 0:
            return
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        job_id = str(row_key.value)
        if job_id:
            self.app.action_show_job(job_id)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "recent-matches":
            job_id = str(event.row_key.value)
            self.app.action_show_job(job_id)
