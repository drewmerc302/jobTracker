import json
import logging
import re
import subprocess

import anthropic
import yaml
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import Config
from src.db import Database
from src.steps.tailor import get_active_resume_yaml

logger = logging.getLogger(__name__)

_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError)),
    reraise=True,
)

PREP_TOOL = {
    "name": "interview_prep",
    "description": "Generate structured interview preparation content for a job",
    "input_schema": {
        "type": "object",
        "properties": {
            "likely_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Predicted behavioral and technical interview questions based on the JD",
            },
            "star_stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "resume_bullet": {"type": "string"},
                        "situation": {"type": "string"},
                        "task": {"type": "string"},
                        "action": {"type": "string"},
                        "result": {"type": "string"},
                    },
                    "required": [
                        "question",
                        "resume_bullet",
                        "situation",
                        "task",
                        "action",
                        "result",
                    ],
                },
                "description": "STAR story mappings from resume experience to interview questions",
            },
            "talking_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-5 key things to emphasize about your background for this specific role",
            },
            "red_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Gaps or weaknesses relative to the JD to prepare for",
            },
        },
        "required": ["likely_questions", "star_stories", "talking_points", "red_flags"],
    },
}


def _read_obsidian_note(path: str) -> str:
    """Read a note from Obsidian vault via CLI. Returns empty string if not found."""
    try:
        result = subprocess.run(
            [
                "claude",
                "mcp",
                "call",
                "obsidian",
                "read_note",
                "--",
                json.dumps({"path": path}),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, list) and data:
                return data[0].get("text", "")
            return result.stdout
    except Exception as e:
        logger.debug(f"Could not read Obsidian note {path}: {e}")
    return ""


def _write_obsidian_note(path: str, content: str):
    try:
        result = subprocess.run(
            [
                "claude",
                "mcp",
                "call",
                "obsidian",
                "write_note",
                "--",
                json.dumps({"path": path, "content": content}),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning(
                f"Failed to write Obsidian note {path}: {result.stderr.strip()}"
            )
    except Exception as e:
        logger.warning(f"Failed to write Obsidian note {path}: {e}")


def _patch_obsidian_section(note: str, section_header: str, new_content: str) -> str:
    """Replace section_header block in note with new_content, or append if missing."""
    pattern = re.compile(
        rf"({re.escape(section_header)})\n.*?(?=\n\n## |\n## |\Z)", re.DOTALL
    )
    replacement = f"{section_header}\n{new_content}"
    if pattern.search(note):
        return pattern.sub(replacement, note)
    return note.rstrip() + f"\n\n{section_header}\n{new_content}\n"


def _format_prep_content(prep: dict) -> str:
    lines = []

    if prep.get("talking_points"):
        lines.append("### Key Talking Points")
        for tp in prep["talking_points"]:
            lines.append(f"- {tp}")
        lines.append("")

    if prep.get("red_flags"):
        lines.append("### Gaps to Prepare For")
        for rf in prep["red_flags"]:
            lines.append(f"- {rf}")
        lines.append("")

    if prep.get("likely_questions"):
        lines.append("### Likely Questions")
        for q in prep["likely_questions"]:
            lines.append(f"- {q}")
        lines.append("")

    if prep.get("star_stories"):
        lines.append("### STAR Stories")
        for story in prep["star_stories"]:
            lines.append(f"\n**Q: {story['question']}**")
            lines.append(f"*From: {story['resume_bullet']}*")
            lines.append(f"- **S:** {story['situation']}")
            lines.append(f"- **T:** {story['task']}")
            lines.append(f"- **A:** {story['action']}")
            lines.append(f"- **R:** {story['result']}")

    return "\n".join(lines)


@_llm_retry
def _call_llm(job: dict, resume_data: dict, extra_context: str = "") -> dict:
    client = anthropic.Anthropic()

    resume_text = yaml.dump(resume_data, default_flow_style=False)[:4000]

    prompt = f"""You are preparing an engineering manager candidate for an interview.

Job: {job["company"]} — {job["title"]}
Description:
{(job.get("description") or "")[:3000]}

Candidate's resume (YAML):
{resume_text}
"""
    if extra_context:
        prompt += f"\nAdditional company context:\n{extra_context}\n"

    prompt += (
        "\nGenerate structured interview prep content using the interview_prep tool."
    )

    response = client.messages.create(
        model=config.llm_tailor_model,
        max_tokens=2000,
        tools=[PREP_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            return block.input

    raise ValueError("LLM did not return tool_use block")


def _web_research(company: str) -> str:
    """Basic web research for company context. Returns summary string."""
    import urllib.request
    import urllib.parse

    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(company)}"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
            return data.get("extract", "")[:500]
    except Exception:
        return ""


def generate_interview_prep(
    db: Database, job_id: str, research: bool = False, config: "Config | None" = None
):
    """Generate and write interview prep content for a job to its Obsidian note."""
    job = db.get_job(job_id)
    if not job:
        logger.warning(f"interview_prep: job {job_id} not found")
        return

    try:
        if config is None:
            config = Config()
        _, resume_data = get_active_resume_yaml(config)
    except Exception as e:
        logger.warning(f"interview_prep: could not load resume: {e}")
        resume_data = {}

    extra_context = ""
    if research:
        logger.info(f"interview_prep: fetching company research for {job['company']}")
        extra_context = _web_research(job["company"])

    try:
        prep = _call_llm(job, resume_data, extra_context)
    except Exception as e:
        logger.error(f"interview_prep: LLM call failed for {job_id}: {e}")
        return

    from src.steps.obsidian import sanitize_filename, VAULT_PATH

    note_name = sanitize_filename(f"{job['company']} — {job['title']}")
    note_path = f"{VAULT_PATH}/{note_name}"

    existing = _read_obsidian_note(note_path)
    if not existing:
        existing = (
            f"# {job['company']} — {job['title']}\n\n## Interview Prep\n\n## Notes\n"
        )

    new_content = _format_prep_content(prep)
    patched = _patch_obsidian_section(existing, "## Interview Prep", new_content)
    _write_obsidian_note(note_path, patched)

    logger.info(f"interview_prep: wrote prep note for {job_id}")
