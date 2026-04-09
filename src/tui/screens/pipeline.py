import logging
from datetime import datetime

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, DataTable, Footer
from textual.binding import Binding

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
        yield Static(
            "  [r] Full Pipeline  ·  [1] Scrape  ·  [2] Filter  ·  [3] Prune  ·  [R] Renotify"
        )
        yield Static("", id="pipeline-progress")
        yield Static("  Run History", classes="section-header")
        yield DataTable(id="run-history")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#run-history", DataTable)
        table.add_columns(
            "When", "Jobs", "New", "Matches", "Email", "Duration", "Status"
        )
        self._load_history()

    def _load_history(self) -> None:
        table = self.query_one("#run-history", DataTable)
        table.clear()
        runs = self.app.db.get_recent_runs(limit=15)
        for run in runs:
            completed = run.get("completed_at")
            started = run.get("started_at", "")

            when = (
                completed[:16].replace("T", " ")
                if completed
                else started[:16].replace("T", " ")
            )

            duration = ""
            if completed and started:
                try:
                    s = datetime.fromisoformat(started)
                    e = datetime.fromisoformat(completed)
                    dur = (e - s).total_seconds()
                    duration = f"{dur:.0f}s"
                except (ValueError, TypeError):
                    pass

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
                self.app.call_from_thread(
                    self._update_progress, f"✓ {step_name} complete: {result}"
                )
                self.app.call_from_thread(self._load_history)
            except Exception as e:
                self.app.call_from_thread(
                    self._update_progress, f"✗ {step_name} failed: {e}"
                )

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
                f"✓ Scrape: {scrape_result['jobs_scraped']} jobs, {scrape_result['new_jobs']} new\n  ⟳ Deduplicating...",
            )

            run_dedup(db)
            self.app.call_from_thread(
                self._update_progress, "✓ Scrape + Dedup done\n  ⟳ Filtering..."
            )

            _, resume_data = get_active_resume_yaml(config)
            resume_summary = get_resume_summary(resume_data)
            new_ids = scrape_result["new_job_ids"]
            matches = run_filter(db, new_ids, resume_summary, config)
            self.app.call_from_thread(
                self._update_progress,
                f"✓ Pipeline complete: {scrape_result['new_jobs']} new jobs, {len(matches)} matches",
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

            run_stats = {
                "jobs_scraped": 0,
                "new_jobs": 0,
                "matches_found": 0,
                "duration": "renotify",
            }
            success = run_notify(db, run_stats, config)
            return "sent" if success else "failed"

        self._run_pipeline_step("Renotify", do_renotify)
