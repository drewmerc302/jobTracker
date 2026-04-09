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
