import copy
import json
import logging
import subprocess
from pathlib import Path

import anthropic
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import Config
from src.db import Database

logger = logging.getLogger(__name__)

_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError)),
    reraise=True,
)

ANALYSIS_TOOL = {
    "name": "resume_analysis",
    "description": "Analyze resume against job description and suggest improvements",
    "input_schema": {
        "type": "object",
        "properties": {
            "reordered_bullets": {
                "type": "object",
                "description": "Map of 'Company - Title' to reordered bullet list",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
            },
            "suggested_edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original": {"type": "string"},
                        "suggested": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["original", "suggested", "reason"],
                },
            },
            "keyword_gaps": {
                "type": "array", "items": {"type": "string"},
                "description": "Keywords in the JD missing from the resume",
            },
        },
        "required": ["reordered_bullets", "suggested_edits", "keyword_gaps"],
    },
}


def get_active_resume_yaml(config: Config) -> tuple[Path, dict]:
    project_json = config.resume_versions_path / "projects" / config.resume_project / "project.json"
    with open(project_json) as f:
        project = json.load(f)
    active_version = project["active_version"]
    versions_dir = config.resume_versions_path / "projects" / config.resume_project / "versions"
    candidates = list(versions_dir.glob(f"{active_version}*"))
    if not candidates:
        raise FileNotFoundError(f"No version directory found for {active_version}")
    version_dir = candidates[0]
    yaml_path = version_dir / "resume.yaml"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return yaml_path, data


def reorder_resume_yaml(resume_data: dict, reorder_map: dict) -> dict:
    result = copy.deepcopy(resume_data)
    for exp in result.get("experience", []):
        key = f"{exp.get('company', '')} - {exp.get('title', '')}"
        if key in reorder_map:
            new_order = reorder_map[key]
            existing = exp.get("bullets", [])
            reordered = [b for b in new_order if b in existing]
            remaining = [b for b in existing if b not in reordered]
            exp["bullets"] = reordered + remaining
    return result


@_llm_retry
def llm_resume_analysis(resume_yaml_str: str, job_description: str, config: Config) -> dict:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    response = client.messages.create(
        model=config.llm_tailor_model,
        max_tokens=4096,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "resume_analysis"},
        messages=[{
            "role": "user",
            "content": f"""Analyze this resume against the job description. Reorder bullets to prioritize
relevance to the JD, suggest wording improvements for better keyword alignment,
and identify keyword gaps.

RESUME (YAML):
{resume_yaml_str}

JOB DESCRIPTION:
{job_description}""",
        }],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {"reordered_bullets": {}, "suggested_edits": [], "keyword_gaps": []}


def generate_resume_pdf(resume_data: dict, output_dir: Path, config: Config) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = output_dir / "resume.yaml"
    typ_path = output_dir / "resume.typ"
    pdf_path = output_dir / "resume.pdf"

    with open(yaml_path, "w") as f:
        yaml.dump(resume_data, f, default_flow_style=False, allow_unicode=True)

    try:
        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_formatter_dir),
             "scripts/yaml_to_typst.py", str(yaml_path), config.resume_template,
             "--output", str(typ_path)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_formatter_dir),
             "scripts/compile_typst.py", str(typ_path), "--output", str(pdf_path)],
            check=True, capture_output=True, text=True,
        )
        return pdf_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Resume PDF generation failed: {e.stderr}")
        return None


def _enforce_one_page(typ_path: Path):
    """Patch the generated Typst file to fit on exactly one page."""
    content = typ_path.read_text()
    # Reduce font size from 11pt to 10pt
    content = content.replace("size: 11pt", "size: 10pt")
    # Tighten paragraph leading if present
    content = content.replace("leading: 0.65em", "leading: 0.55em")
    typ_path.write_text(content)


def generate_cover_letter_pdf(resume_yaml_path: Path, job_description: str,
                               company: str, position: str,
                               output_dir: Path, config: Config) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jd_path = output_dir / "job_description.txt"
    typ_path = output_dir / "cover_letter.typ"
    pdf_path = output_dir / "cover_letter.pdf"
    jd_path.write_text(job_description)

    try:
        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_coverletter_dir),
             "scripts/generate_cover_letter.py", str(resume_yaml_path),
             "--template", config.cover_letter_template,
             "--company", company,
             "--position", position,
             "--job-file", str(jd_path),
             "--output", str(typ_path)],
            check=True, capture_output=True, text=True,
        )

        # Enforce 1-page cover letter: reduce font size and tighten spacing
        _enforce_one_page(typ_path)

        subprocess.run(
            ["uv", "run", "--directory", str(config.resume_coverletter_dir),
             "scripts/compile_cover_letter.py", str(typ_path),
             "--output", str(pdf_path)],
            check=True, capture_output=True, text=True,
        )
        return pdf_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Cover letter generation failed: {e.stderr}")
        return None


def run_tailor_for_job(job: dict, evaluation: dict, resume_yaml_path: Path,
                       resume_data: dict, output_dir: Path,
                       config: Config, db: Database) -> dict:
    job_dir = output_dir / f"{job['company']}_{job['id'].replace(':', '_')}"
    resume_yaml_str = yaml.dump(resume_data, default_flow_style=False)
    analysis = llm_resume_analysis(resume_yaml_str, job.get("description", ""), config)
    tailored = reorder_resume_yaml(resume_data, analysis.get("reordered_bullets", {}))
    resume_pdf = generate_resume_pdf(tailored, job_dir, config)
    cover_letter_pdf = generate_cover_letter_pdf(
        resume_yaml_path, job.get("description", ""),
        job["company"], job["title"], job_dir, config,
    )
    suggestions = json.dumps({
        "suggested_edits": analysis.get("suggested_edits", []),
        "keyword_gaps": analysis.get("keyword_gaps", []),
        "key_requirements": evaluation.get("key_requirements", []),
        "interview_talking_points": evaluation.get("interview_talking_points", []),
    })
    db.update_match_paths(
        job["id"],
        resume_path=str(resume_pdf) if resume_pdf else None,
        cover_letter_path=str(cover_letter_pdf) if cover_letter_pdf else None,
    )
    db.update_match_suggestions(job["id"], suggestions)
    return {
        "job_id": job["id"],
        "resume_pdf": resume_pdf,
        "cover_letter_pdf": cover_letter_pdf,
        "analysis": analysis,
    }
