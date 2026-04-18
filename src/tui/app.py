from pathlib import Path

from textual.app import App

from src.tui.screens.applications import ApplicationsScreen
from src.tui.screens.dashboard import DashboardScreen
from src.tui.screens.job_detail import JobDetailScreen
from src.tui.screens.matches import MatchesScreen
from src.tui.screens.pipeline import PipelineScreen


class JobTrackerApp(App):
    """JobTracker TUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "JobTracker"

    SCREENS = {
        "applications": ApplicationsScreen,
        "dashboard": DashboardScreen,
        "matches": MatchesScreen,
        "pipeline": PipelineScreen,
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
        self.push_screen(JobDetailScreen(job_id))

    def action_set_job_status(self, job_id: str) -> None:
        from src.tui.widgets.status_popup import StatusPopup

        self.push_screen(StatusPopup(job_id), self._on_status_set)

    def _on_status_set(self, result: tuple[str, str] | None) -> None:
        if result:
            job_id, new_status = result
            self.db.set_application_status(job_id, new_status)
            if new_status in ("applied", "interviewing"):
                from src.pipeline import _compute_follow_up_date

                app = self.db.get_application(job_id)
                follow_up = _compute_follow_up_date(
                    app.get("applied_date") if app else None
                )
                self.db.set_follow_up_date(job_id, follow_up)
            self.notify(f"Status → {new_status}")
            # Refresh all screens in the stack (e.g. JobDetail header + Matches/Dashboard below)
            for screen in self.screen_stack:
                if hasattr(screen, "_load_data"):
                    screen._load_data()
            # Run slow operations (LLM, MCP) in a background worker
            self._run_status_side_effects(job_id, new_status)

    def _run_status_side_effects(self, job_id: str, status: str) -> None:
        def do_side_effects():
            if status == "interviewing":
                try:
                    from src.steps.interview_prep import generate_interview_prep

                    generate_interview_prep(self.db, job_id)
                    self.call_from_thread(
                        self.notify, "Interview prep written to Obsidian"
                    )
                except Exception as e:
                    self.call_from_thread(self.notify, f"Interview prep failed: {e}")
            try:
                from src.steps.obsidian import write_application_note, write_dashboard

                write_application_note(job_id, self.db, self.config)
                write_dashboard(self.db, self.config)
            except Exception:
                pass

        self.run_worker(do_side_effects, thread=True)

    def action_tailor_job(self, job_id: str) -> None:
        """Quick tailor from matches list — push to job detail."""
        self.push_screen(JobDetailScreen(job_id))

    def action_help(self) -> None:
        self.notify("Help: d=Dashboard  m=Matches  a=Apps  p=Pipeline  q=Quit")
