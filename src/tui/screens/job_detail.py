import json
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, Footer, Checkbox
from textual.binding import Binding
from textual.worker import Worker


class EditCheckbox(Checkbox):
    """A checkbox for a suggested resume edit."""

    DEFAULT_CSS = """
    EditCheckbox {
        background: #161b22;
        padding: 0 1;
        border: none;
        height: auto;
    }
    EditCheckbox:focus {
        background: #1f3a5f;
    }
    EditCheckbox > .toggle--button {
        color: #484f58;
    }
    EditCheckbox.-on > .toggle--button {
        color: #3fb950;
    }
    """

    def __init__(self, index: int, edit: dict):
        label = f"[{index}] {edit['original'][:60]} → {edit['suggested'][:60]}"
        super().__init__(label, id=f"edit-{index}")
        self.edit_index = index


class JobDetailScreen(Screen):
    """Full job analysis with interactive edit selection."""

    BINDINGS = [
        Binding("j", "next_edit", "Next edit", show=False),
        Binding("k", "prev_edit", "Prev edit", show=False),
        Binding("down", "next_edit", "Next edit", show=False),
        Binding("up", "prev_edit", "Prev edit", show=False),
        Binding("t", "tailor", "Tailor PDF", show=True),
        Binding("e", "adopt_selected", "Adopt selected", show=True),
        Binding("E", "adopt_all", "Adopt all", show=True, key_display="⇧E"),
        Binding("v", "view_pdfs", "View PDFs", show=True),
        Binding("s", "set_status", "Set status", show=True),
        Binding("i", "interview_prep", "Interview prep", show=True),
        Binding("g", "gripes", "Gripes", show=True),
        Binding("o", "open_url", "Open URL", show=True),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="job-header")
        yield VerticalScroll(id="job-content")
        yield Footer()

    def on_mount(self) -> None:
        db = self.app.db
        job = db.get_job(self.job_id)
        match = db.get_match(self.job_id)
        if not job or not match:
            self.query_one("#job-header").update(f"Job not found: {self.job_id}")
            return

        app_row = db.get_application(self.job_id)
        status = app_row["status"] if app_row else "new"

        score = f"{match['relevance_score']:.0%}"
        salary = f" · {job['salary']}" if job.get("salary") else ""
        location = job.get("location") or "N/A"
        header = (
            f"{job['company']} — {job['title']}\n"
            f"{score} match · {status} · {location}{salary}"
        )
        self.query_one("#job-header").update(header)

        content = self.query_one("#job-content", VerticalScroll)
        suggestions = json.loads(match.get("suggestions") or "{}")

        if not suggestions.get("suggested_edits"):
            content.mount(Static("  Analyzing job... (this may take a moment)"))
            self._run_analysis()
            return

        self._render_analysis(suggestions, match)

    def _run_analysis(self) -> None:
        self.run_worker(self._do_analysis, thread=True)

    def _do_analysis(self) -> dict:
        from src.steps.tailor import ensure_analysis

        job = self.app.db.get_job(self.job_id)
        return ensure_analysis(dict(job), self.app.db, self.app.config, force=False)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "SUCCESS":
            match = self.app.db.get_match(self.job_id)
            suggestions = json.loads(match.get("suggestions") or "{}")
            content = self.query_one("#job-content", VerticalScroll)
            content.remove_children()
            self._render_analysis(suggestions, match)

    def _render_analysis(self, suggestions: dict, match: dict) -> None:
        content = self.query_one("#job-content", VerticalScroll)

        content.mount(Static("  WHY THIS MATCHES", classes="section-header"))
        content.mount(Static(f"  [#c9d1d9]{match['match_reason']}[/]"))

        if suggestions.get("key_requirements"):
            content.mount(Static("  KEY REQUIREMENTS", classes="section-header"))
            for req in suggestions["key_requirements"]:
                content.mount(Static(f"  [#8b949e]•[/] [#c9d1d9]{req}[/]"))

        if suggestions.get("interview_talking_points"):
            content.mount(
                Static("  INTERVIEW TALKING POINTS", classes="section-header")
            )
            for tp in suggestions["interview_talking_points"]:
                content.mount(Static(f"  [#8b949e]•[/] [#c9d1d9]{tp}[/]"))

        edits = suggestions.get("suggested_edits", [])
        if edits:
            content.mount(
                Static(
                    "  SUGGESTED RESUME EDITS  [#8b949e](↑↓/jk=navigate, Space=toggle, e=adopt selected, E=adopt all)[/]",
                    classes="section-header",
                )
            )
            for i, edit in enumerate(edits, 1):
                content.mount(EditCheckbox(i, edit))
                content.mount(
                    Static(f"    [#f85149]Current:[/]   [#8b949e]{edit['original']}[/]")
                )
                content.mount(
                    Static(
                        f"    [#3fb950]Suggested:[/] [#c9d1d9]{edit['suggested']}[/]"
                    )
                )
                content.mount(
                    Static(f"    [#58a6ff]Why:[/] [#8b949e]{edit['reason']}[/]")
                )
                content.mount(Static(""))
            # Focus first checkbox so space/enter can toggle
            self.set_timer(0.1, self._focus_first_checkbox)

        if suggestions.get("keyword_gaps"):
            gaps = ", ".join(suggestions["keyword_gaps"])
            content.mount(Static("  KEYWORD GAPS", classes="section-header"))
            content.mount(Static(f"  [#f0883e]{gaps}[/]"))

        if match.get("resume_path") or match.get("cover_letter_path"):
            content.mount(Static("  GENERATED PDFs", classes="section-header"))
            if match.get("resume_path"):
                content.mount(Static(f"  [#3fb950]Resume:[/] {match['resume_path']}"))
            if match.get("cover_letter_path"):
                content.mount(
                    Static(f"  [#3fb950]Cover letter:[/] {match['cover_letter_path']}")
                )

    def _focus_first_checkbox(self) -> None:
        checkboxes = list(self.query(EditCheckbox))
        if checkboxes:
            checkboxes[0].focus()
            checkboxes[0].scroll_visible()

    def action_next_edit(self) -> None:
        checkboxes = list(self.query(EditCheckbox))
        if not checkboxes:
            return
        focused = self.focused
        if isinstance(focused, EditCheckbox):
            idx = checkboxes.index(focused)
            nxt = checkboxes[(idx + 1) % len(checkboxes)]
        else:
            nxt = checkboxes[0]
        nxt.focus()
        nxt.scroll_visible()

    def action_prev_edit(self) -> None:
        checkboxes = list(self.query(EditCheckbox))
        if not checkboxes:
            return
        focused = self.focused
        if isinstance(focused, EditCheckbox):
            idx = checkboxes.index(focused)
            nxt = checkboxes[(idx - 1) % len(checkboxes)]
        else:
            nxt = checkboxes[-1]
        nxt.focus()
        nxt.scroll_visible()

    def _get_selected_edit_indices(self) -> set[int]:
        indices = set()
        for cb in self.query(EditCheckbox):
            if cb.value:
                indices.add(cb.edit_index)
        return indices

    def action_tailor(self) -> None:
        self.notify("Generating PDFs...")
        self.run_worker(self._do_tailor, thread=True)

    def _do_tailor(self, adopt: set[int] | None = None) -> None:
        from datetime import datetime, timezone

        from src.steps.tailor import (
            ensure_analysis,
            get_active_resume_yaml,
            run_tailor_for_job,
        )

        db = self.app.db
        config = self.app.config
        job = db.get_job(self.job_id)
        analysis = ensure_analysis(dict(job), db, config, force=True)
        resume_yaml_path, resume_data = get_active_resume_yaml(config)
        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        output_dir = config.output_dir / run_date
        result = run_tailor_for_job(
            job=dict(job),
            analysis=analysis,
            resume_yaml_path=resume_yaml_path,
            resume_data=resume_data,
            output_dir=output_dir,
            config=config,
            adopt_edits=adopt or set(),
        )
        db.update_match_paths(
            self.job_id,
            resume_path=str(result["resume_pdf"]) if result.get("resume_pdf") else None,
            cover_letter_path=(
                str(result["cover_letter_pdf"])
                if result.get("cover_letter_pdf")
                else None
            ),
        )
        for key in ("resume_pdf", "cover_letter_pdf"):
            path = result.get(key)
            if path and Path(path).exists():
                subprocess.Popen(["open", str(path)])
        self.app.call_from_thread(self.notify, "PDFs generated and opened")

    def action_adopt_selected(self) -> None:
        indices = self._get_selected_edit_indices()
        if not indices:
            self.notify("No edits selected")
            return
        self.notify(f"Adopting edits {sorted(indices)} and generating PDFs...")
        self.run_worker(lambda: self._do_tailor(adopt=indices), thread=True)

    def action_adopt_all(self) -> None:
        all_indices = {cb.edit_index for cb in self.query(EditCheckbox)}
        if not all_indices:
            self.notify("No edits available")
            return
        self.notify(f"Adopting all {len(all_indices)} edits and generating PDFs...")
        self.run_worker(lambda: self._do_tailor(adopt=all_indices), thread=True)

    def action_view_pdfs(self) -> None:
        match = self.app.db.get_match(self.job_id)
        if not match:
            return
        opened = False
        for key in ("resume_path", "cover_letter_path"):
            path = match.get(key)
            if path and Path(path).exists():
                subprocess.Popen(["open", path])
                opened = True
        if opened:
            self.notify("PDFs opened")
        else:
            self.notify("No PDFs generated yet — press [t] to generate")

    def action_set_status(self) -> None:
        self.app.action_set_job_status(self.job_id)

    def action_interview_prep(self) -> None:
        self.notify("Generating interview prep...")
        self.run_worker(self._do_interview_prep, thread=True)

    def _do_interview_prep(self) -> None:
        from src.steps.interview_prep import generate_interview_prep

        generate_interview_prep(self.app.db, self.job_id)
        self.app.call_from_thread(self.notify, "Interview prep written to Obsidian")

    def action_gripes(self) -> None:
        self.notify("Fetching company gripes...")
        self.run_worker(self._do_gripes, thread=True)

    def _do_gripes(self) -> None:
        from src.steps.gripes import get_gripes

        job = self.app.db.get_job(self.job_id)
        gripes = get_gripes(self.app.db, job["company"], self.app.config)
        if gripes:
            content = self.query_one("#job-content", VerticalScroll)

            def mount_gripes():
                content.mount(Static("  COMPANY GRIPES", classes="section-header"))
                for category, items in gripes.items():
                    content.mount(Static(f"  {category}:"))
                    if isinstance(items, list):
                        for item in items:
                            content.mount(Static(f"    • {item}"))

            self.app.call_from_thread(mount_gripes)
        else:
            self.app.call_from_thread(self.notify, "Could not fetch gripes")

    def action_open_url(self) -> None:
        job = self.app.db.get_job(self.job_id)
        if job and job.get("url"):
            subprocess.Popen(["open", job["url"]])
            self.notify(f"Opened {job['url']}")

    def action_go_back(self) -> None:
        self.app.pop_screen()
