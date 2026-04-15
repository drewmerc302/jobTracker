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
        Binding("j", "next_edit", "Next ↓", show=True),
        Binding("k", "prev_edit", "Prev ↑", show=True),
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

    _SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
        self._tailoring = False

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="job-header")
        yield VerticalScroll(id="job-content")
        yield Static("", id="pdf-progress")
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
        self.run_worker(self._do_analysis, thread=True, name="analysis")

    def _do_analysis(self) -> dict | None:
        from src.steps.tailor import ensure_analysis

        job = self.app.db.get_job(self.job_id)
        if not job:
            return None
        return ensure_analysis(dict(job), self.app.db, self.app.config, force=False)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state.name == "ERROR":
            error = event.worker.error
            name = event.worker.name or "operation"
            if name == "tailor":
                self._stop_pdf_spinner()
            self.notify(f"{name} failed: {error}", severity="error")
            return
        if event.state.name != "SUCCESS":
            return
        if event.worker.name == "analysis":
            match = self.app.db.get_match(self.job_id)
            suggestions = json.loads(match.get("suggestions") or "{}")
            content = self.query_one("#job-content", VerticalScroll)
            content.remove_children()
            self._render_analysis(suggestions, match)
        elif event.worker.name == "tailor":
            self._stop_pdf_spinner("PDFs generated and opened")
            # Refresh to show PDF paths in the analysis section
            match = self.app.db.get_match(self.job_id)
            suggestions = json.loads(match.get("suggestions") or "{}")
            content = self.query_one("#job-content", VerticalScroll)
            content.remove_children()
            self._render_analysis(suggestions, match)
        elif event.worker.name == "gripes":
            gripes = event.worker.result
            if gripes:
                self._mount_gripes(gripes)
            else:
                self.notify("Could not fetch gripes")

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
                    "  SUGGESTED RESUME EDITS  [#8b949e](j/k=navigate, Space=toggle, e=adopt, E=all)[/]",
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

        if suggestions.get("keyword_gaps"):
            content.mount(Static("  KEYWORD GAPS", classes="section-header"))
            content.mount(
                Static(
                    "  [#8b949e]Keywords from the job posting missing from your resume:[/]"
                )
            )
            for gap in suggestions["keyword_gaps"]:
                content.mount(Static(f"  [#f0883e]• {gap}[/]"))

        if match.get("resume_path") or match.get("cover_letter_path"):
            content.mount(Static("  GENERATED PDFs", classes="section-header"))
            if match.get("resume_path"):
                content.mount(Static(f"  [#3fb950]Resume:[/] {match['resume_path']}"))
            if match.get("cover_letter_path"):
                content.mount(
                    Static(f"  [#3fb950]Cover letter:[/] {match['cover_letter_path']}")
                )

    def action_next_edit(self) -> None:
        checkboxes = list(self.query(EditCheckbox))
        if not checkboxes:
            self.query_one("#job-content", VerticalScroll).action_scroll_down()
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
            self.query_one("#job-content", VerticalScroll).action_scroll_up()
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

    def _start_pdf_spinner(self, label: str) -> None:
        self._tailoring = True
        self._spinner_label = label
        self._spinner_idx = 0
        self._spinner_timer = self.set_interval(0.1, self._tick_pdf_spinner)

    def _tick_pdf_spinner(self) -> None:
        frame = self._SPINNER[self._spinner_idx % len(self._SPINNER)]
        self.query_one("#pdf-progress", Static).update(
            f"  [#f0883e]{frame}[/] [#c9d1d9]{self._spinner_label}[/]"
        )
        self._spinner_idx += 1

    def _stop_pdf_spinner(self, message: str = "") -> None:
        self._tailoring = False
        if hasattr(self, "_spinner_timer") and self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        widget = self.query_one("#pdf-progress", Static)
        if message:
            widget.update(f"  [#3fb950]✓[/] [#c9d1d9]{message}[/]")
        else:
            widget.update("")

    def action_tailor(self) -> None:
        self._start_pdf_spinner("Generating PDFs — this takes about a minute...")
        self.run_worker(self._do_tailor, thread=True, name="tailor")

    def _do_tailor(self, adopt: set[int] | None = None) -> str:
        from datetime import datetime, timezone

        from src.steps.tailor import (
            ensure_analysis,
            get_active_resume_yaml,
            run_tailor_for_job,
        )

        db = self.app.db
        config = self.app.config
        job = db.get_job(self.job_id)
        if not job:
            self.app.call_from_thread(self.notify, "Job no longer in database")
            return "failed"
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
        return "done"

    def action_adopt_selected(self) -> None:
        indices = self._get_selected_edit_indices()
        if not indices:
            self.notify("No edits selected")
            return
        self._start_pdf_spinner(
            f"Adopting edits {sorted(indices)} and generating PDFs..."
        )
        self.run_worker(
            lambda: self._do_tailor(adopt=indices), thread=True, name="tailor"
        )

    def action_adopt_all(self) -> None:
        all_indices = {cb.edit_index for cb in self.query(EditCheckbox)}
        if not all_indices:
            self.notify("No edits available")
            return
        self._start_pdf_spinner(
            f"Adopting all {len(all_indices)} edits and generating PDFs..."
        )
        self.run_worker(
            lambda: self._do_tailor(adopt=all_indices), thread=True, name="tailor"
        )

    def action_view_pdfs(self) -> None:
        if self._tailoring:
            self.notify("PDFs are still being generated — please wait")
            return
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
            self.notify("No PDFs generated yet — press \\[t] to generate")

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
        from datetime import datetime, timedelta, timezone

        job = self.app.db.get_job(self.job_id)
        if not job:
            return
        # Check cache on main thread — instant if cached
        cached = self.app.db.get_company_gripes(job["company"])
        if cached is not None:
            gripes_dict, fetched_at_str = cached
            fetched_at = datetime.fromisoformat(fetched_at_str)
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if fetched_at >= datetime.now(timezone.utc) - timedelta(days=30):
                self._mount_gripes(gripes_dict)
                return
        # Cache miss — fetch in background
        self.notify("Fetching company gripes...")
        self.run_worker(self._do_gripes, thread=True, name="gripes")

    def _do_gripes(self) -> dict | None:
        from src.steps.gripes import get_gripes

        job = self.app.db.get_job(self.job_id)
        if not job:
            return None
        return get_gripes(self.app.db, job["company"], self.app.config)

    def _mount_gripes(self, gripes: dict) -> None:
        """Mount gripes content — must be called on the main thread."""
        content = self.query_one("#job-content", VerticalScroll)
        content.mount(Static(""))
        content.mount(Static("  COMPANY GRIPES", classes="section-header"))
        if gripes.get("tldr"):
            for bullet in gripes["tldr"]:
                content.mount(Static(f"  [#8b949e]•[/] [#c9d1d9]{bullet}[/]"))
        for theme in gripes.get("themes", []):
            content.mount(Static(f"  [#58a6ff]{theme['name']}[/]"))
            content.mount(Static(f"  [#f0883e]{theme['summary']}[/]"))
            content.mount(Static(f"  [#8b949e]{theme['detail']}[/]"))
            content.mount(Static(""))
        # Scroll to bottom where gripes were appended
        self.set_timer(0.2, lambda: content.scroll_end(animate=False))

    def action_open_url(self) -> None:
        job = self.app.db.get_job(self.job_id)
        if job and job.get("url"):
            subprocess.Popen(["open", job["url"]])
            self.notify(f"Opened {job['url']}")

    def action_go_back(self) -> None:
        self.app.pop_screen()
