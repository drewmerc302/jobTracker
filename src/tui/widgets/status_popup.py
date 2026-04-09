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
