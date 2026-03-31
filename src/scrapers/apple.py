import json
import logging
import re
import time
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

_http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)

BASE_URL = "https://jobs.apple.com/en-us/search"
PAGE_SIZE = 20


class AppleScraper(BaseScraper):
    """Scrapes Apple jobs by parsing server-side rendered hydration data."""

    company_name = "Apple"

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(
                timeout=30, headers={"User-Agent": "Mozilla/5.0"}
            ) as client:
                all_jobs = {}
                # Search 1: remote EM roles (homeOffice=1)
                self._fetch_search(
                    client,
                    {
                        "q": "engineering manager",
                        "homeOffice": "1",
                        "sort": "relevance",
                    },
                    all_jobs,
                )
                # Search 2: NYC area EM roles
                self._fetch_search(
                    client,
                    {
                        "q": "engineering manager",
                        "location": "new-york-city-NEW YORK CITY USA",
                        "sort": "relevance",
                    },
                    all_jobs,
                )
                logger.info(f"Apple: {len(all_jobs)} unique jobs after dedup")
                return list(all_jobs.values())
        except Exception as e:
            logger.error(f"Failed to fetch Apple jobs: {e}")
            return []

    def _fetch_search(self, client: httpx.Client, params: dict, seen: dict) -> None:
        page = 1
        while True:
            p = {**params, "page": str(page)}
            data = self._fetch_page(client, p)
            if not data:
                break
            results = data.get("searchResults", [])
            total = data.get("totalRecords", 0)
            for item in results:
                job = self._parse_job(item)
                if job and job.db_id not in seen:
                    seen[job.db_id] = job
            if page * PAGE_SIZE >= total or not results:
                break
            page += 1
            time.sleep(1.0)

    @_http_retry
    def _fetch_page(self, client: httpx.Client, params: dict) -> dict | None:
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
        m = re.search(
            r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\("(.*?)"\);',
            resp.text,
            re.DOTALL,
        )
        if not m:
            logger.warning("Apple: hydration data not found in page")
            return None
        unescaped = m.group(1).encode().decode("unicode_escape")
        d = json.loads(unescaped)
        return d.get("loaderData", {}).get("search", {})

    def _parse_job(self, item: dict) -> RawJob | None:
        req_id = item.get("reqId") or item.get("positionId") or item.get("id", "")
        if not req_id:
            return None
        title = item.get("postingTitle") or item.get("transformedPostingTitle", "")
        locations = item.get("locations", [])
        location = locations[0].get("name") if locations else None
        is_remote = item.get("homeOffice", False) or False
        url = f"https://jobs.apple.com/en-us/details/{item.get('positionId', req_id)}"
        now = datetime.now(timezone.utc)
        return RawJob(
            external_id=str(req_id),
            company=self.company_name,
            title=title,
            url=url,
            location=location,
            remote=True if is_remote else None,
            salary=None,
            description=item.get("jobSummary"),
            department=item.get("team", {}).get("teamName")
            if item.get("team")
            else None,
            seniority=None,
            scraped_at=now,
        )
