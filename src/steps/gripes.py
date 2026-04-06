import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import Config
from src.db import Database

logger = logging.getLogger(__name__)

_CACHE_TTL_DAYS = 30

_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError)),
    reraise=True,
)

GRIPES_TOOL = {
    "name": "company_gripes",
    "description": "Analyze employee reviews and summarize common complaints for a company",
    "input_schema": {
        "type": "object",
        "properties": {
            "tldr": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5 one-line bullets summarizing the most common employee complaints",
            },
            "themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "summary": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                    "required": ["name", "summary", "detail"],
                },
                "description": "3-5 recurring complaint themes with expanded detail",
            },
        },
        "required": ["tldr", "themes"],
    },
}


def _web_search(company: str) -> str:
    """Fetch employee review content for company via public HTTP APIs."""
    parts = []

    # Query 1: DuckDuckGo Instant Answer API — glassdoor reviews
    try:
        q = urllib.parse.quote(f"{company} glassdoor employee reviews")
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        abstract = data.get("Abstract", "")
        if abstract:
            parts.append(abstract)
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                parts.append(topic["Text"])
    except Exception as e:
        logger.debug(f"DuckDuckGo search failed for {company}: {e}")

    # Query 2: Reddit public JSON search
    try:
        q = urllib.parse.quote(f"{company} employees work culture")
        url = f"https://www.reddit.com/search.json?q={q}&sort=top&limit=5&t=year"
        req = urllib.request.Request(url, headers={"User-Agent": "jobtracker/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        for post in data.get("data", {}).get("children", []):
            pd = post.get("data", {})
            title = pd.get("title", "")
            selftext = pd.get("selftext", "")[:300]
            if title:
                parts.append(f"{title}. {selftext}".strip())
    except Exception as e:
        logger.debug(f"Reddit search failed for {company}: {e}")

    # Query 3: DuckDuckGo — work culture problems (general)
    try:
        q = urllib.parse.quote(f"{company} work culture problems complaints")
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        abstract = data.get("Abstract", "")
        if abstract:
            parts.append(abstract)
        for topic in data.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and topic.get("Text"):
                parts.append(topic["Text"])
    except Exception as e:
        logger.debug(f"DuckDuckGo culture search failed for {company}: {e}")

    result = " ".join(parts)
    return result[:4000]


@_llm_retry
def _call_llm(company: str, search_text: str, config: Config) -> dict | None:
    client = anthropic.Anthropic()

    prompt = f"""You are analyzing employee sentiment about {company}.

Here is content from employee reviews and discussions:
{search_text or "(no search results available — use your training knowledge)"}

Synthesize the most common employee pain points and complaints using the company_gripes tool.
Focus on recurring themes that multiple employees mention, not one-off complaints."""

    response = client.messages.create(
        model=config.llm_filter_model,
        max_tokens=1200,
        tools=[GRIPES_TOOL],
        tool_choice={"type": "tool", "name": "company_gripes"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            return block.input
    logger.error(f"gripes: LLM returned no tool_use block for {company}")
    return None


def get_gripes(db: Database, company: str, config: Config) -> dict | None:
    """Return cached gripes for company, or fetch fresh if stale/missing."""
    cached = db.get_company_gripes(company)
    if cached is not None:
        row = db._conn.execute(
            "SELECT fetched_at FROM company_gripes WHERE company = ?", (company,)
        ).fetchone()
        if row:
            fetched_at = datetime.fromisoformat(row["fetched_at"])
            if fetched_at >= datetime.now(timezone.utc) - timedelta(
                days=_CACHE_TTL_DAYS
            ):
                return cached

    logger.info(f"gripes: fetching reviews for {company}")
    search_text = _web_search(company)
    try:
        gripes = _call_llm(company, search_text, config)
    except (anthropic.APIError, anthropic.APIConnectionError) as e:
        logger.error(f"gripes: LLM call failed after retries for {company}: {e}")
        return None
    if gripes is None:
        return None
    db.upsert_company_gripes(company, gripes)
    return gripes


def _format_gripes_plain(gripes: dict, company: str) -> str:
    lines = [f"\nEmployee Gripes ({company}):"]
    if gripes.get("tldr"):
        lines.append("  TL;DR:")
        for bullet in gripes["tldr"]:
            lines.append(f"  - {bullet}")
    for theme in gripes.get("themes", []):
        lines.append(f"\n  {theme['name']}")
        lines.append(f"  {theme['summary']}")
        lines.append(f"  {theme['detail']}")
    return "\n".join(lines)


def _format_gripes_markdown(gripes: dict, company: str) -> str:
    lines = [f"## Employee Gripes ({company})", ""]
    if gripes.get("tldr"):
        lines.append("**TL;DR**")
        for bullet in gripes["tldr"]:
            lines.append(f"- {bullet}")
        lines.append("")
    for theme in gripes.get("themes", []):
        lines.append(f"### {theme['name']}")
        lines.append(f"*{theme['summary']}*")
        lines.append("")
        lines.append(theme["detail"])
        lines.append("")
    return "\n".join(lines)
