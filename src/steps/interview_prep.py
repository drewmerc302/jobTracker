import logging
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

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


def _escape_typst(text: str) -> str:
    """Escape characters that have special meaning in Typst."""
    for ch in ("\\", "@", "#", "<", ">", "=", "_", "*", "`", "~", "$"):
        text = text.replace(ch, "\\" + ch)
    return text


def _generate_typst(prep: dict, job: dict) -> str:
    e = _escape_typst
    company = e(job.get("company", ""))
    title = e(job.get("title", ""))

    lines = [
        '#set page(margin: 2cm, paper: "us-letter")',
        "#set text(size: 11pt)",
        "#set heading(numbering: none)",
        "#set list(indent: 1em)",
        "",
        f"= {company} — {title}",
        "",
        "#text(size: 9pt, fill: gray)[Interview Preparation]",
        "#line(length: 100%)",
        "#v(0.5em)",
        "",
    ]

    if prep.get("talking_points"):
        lines.append("== Key Talking Points")
        lines.append("")
        for tp in prep["talking_points"]:
            lines.append(f"- {e(tp)}")
        lines.append("")

    if prep.get("red_flags"):
        lines.append("== Gaps to Prepare For")
        lines.append("")
        for rf in prep["red_flags"]:
            lines.append(f"- {e(rf)}")
        lines.append("")

    if prep.get("likely_questions"):
        lines.append("== Likely Interview Questions")
        lines.append("")
        for q in prep["likely_questions"]:
            lines.append(f"- {e(q)}")
        lines.append("")

    if prep.get("star_stories"):
        lines.append("== STAR Stories")
        lines.append("")
        for story in prep["star_stories"]:
            lines.append(f"*Q: {e(story['question'])}*")
            lines.append("")
            lines.append(f"_From: {e(story['resume_bullet'])}_")
            lines.append("")
            lines.append(f"- *S:* {e(story['situation'])}")
            lines.append(f"- *T:* {e(story['task'])}")
            lines.append(f"- *A:* {e(story['action'])}")
            lines.append(f"- *R:* {e(story['result'])}")
            lines.append("")

    return "\n".join(lines)


def _generate_pdf(
    prep: dict, job: dict, output_dir: Path, config: Config
) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    company_clean = (job.get("company") or "company").replace(" ", "_")
    job_id_safe = (job.get("id") or "job").replace(":", "_")
    typ_path = output_dir / f"{company_clean}_{job_id_safe}_interview_prep.typ"
    pdf_path = output_dir / f"{company_clean}_{job_id_safe}_interview_prep.pdf"

    typ_path.write_text(_generate_typst(prep, job))

    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(config.resume_formatter_dir),
                "scripts/compile_typst.py",
                str(typ_path),
                "--output",
                str(pdf_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(
                f"interview_prep: typst compile failed: {result.stderr.strip()}"
            )
            return None
        return pdf_path
    except Exception as e:
        logger.warning(f"interview_prep: PDF generation failed: {e}")
        return None


@_llm_retry
def _call_llm(
    job: dict, resume_data: dict, config: Config, extra_context: str = ""
) -> dict:
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
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(company)}"
        with urllib.request.urlopen(url, timeout=5) as r:
            import json

            data = json.loads(r.read())
            return data.get("extract", "")[:500]
    except Exception:
        return ""


def generate_interview_prep(
    db: Database, job_id: str, research: bool = False, config: "Config | None" = None
) -> "Path | None":
    """Generate interview prep PDF for a job. Returns the PDF path or None on failure."""
    job = db.get_job(job_id)
    if not job:
        logger.warning(f"interview_prep: job {job_id} not found")
        return None

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
        prep = _call_llm(job, resume_data, config, extra_context)
    except Exception as e:
        logger.error(f"interview_prep: LLM call failed for {job_id}: {e}")
        return None

    pdf_path = _generate_pdf(prep, dict(job), config.output_dir, config)
    if pdf_path:
        logger.info(f"interview_prep: generated PDF at {pdf_path}")
    else:
        logger.warning(f"interview_prep: PDF generation failed for {job_id}")

    return pdf_path
