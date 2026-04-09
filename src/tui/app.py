from pathlib import Path

from textual.app import App

from src.tui.screens.dashboard import DashboardScreen
from src.tui.screens.matches import MatchesScreen


class JobTrackerApp(App):
    """JobTracker TUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "JobTracker"

    SCREENS = {
        "dashboard": DashboardScreen,
        "matches": MatchesScreen,
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
