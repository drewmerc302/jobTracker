import json
import logging

import anthropic
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

EVAL_TOOL = {
    "name": "evaluate_job",
    "description": "Evaluate a job listing for relevance to the candidate",
    "input_schema": {
        "type": "object",
        "properties": {
            "relevant": {"type": "boolean", "description": "Whether this job is relevant"},
            "score": {"type": "number", "description": "Relevance score 0.0-1.0"},
            "reason": {"type": "string", "description": "Why this job matches or doesn't"},
            "key_requirements": {
                "type": "array", "items": {"type": "string"},
                "description": "Top requirements from the job description",
            },
            "interview_talking_points": {
                "type": "array", "items": {"type": "string"},
                "description": "What the candidate should emphasize in interviews",
            },
        },
        "required": ["relevant", "score", "reason", "key_requirements", "interview_talking_points"],
    },
}


def keyword_filter(jobs: list[dict], config: Config) -> list[dict]:
    matches = []
    for job in jobs:
        if not job.get("description"):
            logger.debug(f"Skipping {job['id']}: no description")
            continue
        if not config.matches_keyword(job["title"]):
            continue
        if not config.is_location_acceptable(job.get("location"), job.get("remote")):
            logger.debug(f"Skipping {job['id']}: location '{job.get('location')}' not in commute range")
            continue
        matches.append(job)
    logger.info(f"Keyword filter: {len(jobs)} -> {len(matches)}")
    return matches


@_llm_retry
def llm_evaluate(job: dict, resume_summary: str, config: Config) -> dict:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    response = client.messages.create(
        model=config.llm_filter_model,
        max_tokens=1024,
        tools=[EVAL_TOOL],
        tool_choice={"type": "tool", "name": "evaluate_job"},
        messages=[{
            "role": "user",
            "content": f"""Evaluate this job listing for relevance to the candidate.

CANDIDATE PROFILE:
{resume_summary}

JOB LISTING:
Title: {job['title']}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', 'Unknown')}
Salary: {job.get('salary', 'Not listed')}

Description:
{job.get('description', 'No description available')}""",
        }],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    logger.warning(f"No tool_use in LLM response for {job.get('title')}")
    return {"relevant": False, "score": 0.0, "reason": "Failed to evaluate",
            "key_requirements": [], "interview_talking_points": []}


def run_filter(db: Database, new_job_ids: list[str], resume_summary: str,
               config: Config) -> list[dict]:
    jobs = []
    for job_id in new_job_ids:
        job = db.get_job(job_id)
        if job:
            jobs.append(job)
    candidates = keyword_filter(jobs, config)
    if not candidates:
        logger.info("No jobs passed keyword filter")
        return []
    matches = []
    for job in candidates:
        try:
            result = llm_evaluate(job, resume_summary, config)
            if result.get("relevant") and result.get("score", 0) >= config.relevance_threshold:
                db.insert_match(
                    job_id=job["id"],
                    relevance_score=result["score"],
                    match_reason=result["reason"],
                    suggestions=json.dumps({
                        "key_requirements": result.get("key_requirements", []),
                        "interview_talking_points": result.get("interview_talking_points", []),
                    }),
                )
                matches.append({"job": job, "evaluation": result})
                logger.info(f"Match: {job['title']} @ {job['company']} (score: {result['score']})")
            else:
                logger.debug(f"Rejected: {job['title']} (score: {result.get('score', 0)})")
        except Exception as e:
            logger.error(f"LLM evaluation failed for {job['id']}: {e}")
    logger.info(f"LLM filter: {len(candidates)} -> {len(matches)}")
    return matches
