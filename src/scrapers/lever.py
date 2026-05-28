import logging
from datetime import datetime, timezone

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

LEVER_API = "https://api.lever.co/v0/postings"

_http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


class LeverScraper(BaseScraper):
    source = "lever"

    def __init__(self, slug: str, company_name: str):
        self.slug = slug
        self.company_name = company_name

    def fetch_jobs(self) -> list[RawJob]:
        url = f"{LEVER_API}/{self.slug}?mode=json"
        try:
            resp = self._fetch_with_retry(url)
            return self._parse_response(resp.json())
        except Exception as e:
            logger.error(f"Failed to fetch {self.company_name} jobs: {e}")
            return []

    @_http_retry
    def _fetch_with_retry(self, url: str) -> httpx.Response:
        resp = httpx.get(url, timeout=30, headers={"User-Agent": "JobTracker/1.0"})
        resp.raise_for_status()
        return resp

    def _parse_response(self, data: list[dict]) -> list[RawJob]:
        jobs = []
        now = datetime.now(timezone.utc)
        for item in data:
            jobs.append(
                RawJob(
                    external_id=item["id"],
                    company=self.company_name,
                    title=item.get("text", ""),
                    url=item.get("hostedUrl", ""),
                    location=item.get("categories", {}).get("location"),
                    remote=self._is_remote(item),
                    salary=None,
                    description=self._build_description(item),
                    department=item.get("categories", {}).get("department"),
                    seniority=item.get("categories", {}).get("commitment"),
                    scraped_at=now,
                    source=self.source,
                )
            )
        return jobs

    def _build_description(self, item: dict) -> str:
        """Assemble full posting from description + lists + additional."""
        parts = []
        if desc := item.get("descriptionPlain"):
            parts.append(desc)
        for section in item.get("lists", []):
            if heading := section.get("text"):
                parts.append(heading)
            if content := section.get("content"):
                parts.append(content)
        if additional := item.get("additionalPlain"):
            parts.append(additional)
        return "\n\n".join(parts)

    def _is_remote(self, item: dict) -> bool | None:
        workplace = item.get("workplaceType", "")
        if workplace == "remote":
            return True
        if workplace in ("on-site", "hybrid"):
            return False
        location = item.get("categories", {}).get("location", "")
        if location and "remote" in location.lower():
            return True
        return None

    def is_job_live(self, url: str) -> bool | None:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code in (404, 410):
                return False
            if resp.status_code == 200:
                return True
            return None
        except Exception:
            return None
