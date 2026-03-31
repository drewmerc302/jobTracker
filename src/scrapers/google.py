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

BASE_URL = "https://www.google.com/about/careers/applications/jobs/results"
PAGE_SIZE = 20

# Job array indices in AF_initDataCallback ds:1 data
IDX_ID = 0
IDX_TITLE = 1
IDX_URL = 2
IDX_DESCRIPTION = 10
IDX_LOCATIONS = 9


class GoogleScraper(BaseScraper):
    """Scrapes Google Careers by parsing AF_initDataCallback data from HTML pages."""

    company_name = "Google"

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
                follow_redirects=True,
            ) as client:
                all_jobs = {}
                # Search NYC area
                self._fetch_search(
                    client,
                    {
                        "q": "engineering manager",
                        "location": "New York City, NY, USA",
                        "distance": "50mi",
                    },
                    all_jobs,
                )
                # Search Philadelphia area
                self._fetch_search(
                    client,
                    {
                        "q": "engineering manager",
                        "location": "Philadelphia, PA, USA",
                        "distance": "50mi",
                    },
                    all_jobs,
                )
                logger.info(f"Google: {len(all_jobs)} unique jobs after dedup")
                return list(all_jobs.values())
        except Exception as e:
            logger.error(f"Failed to fetch Google jobs: {e}")
            return []

    def _fetch_search(self, client: httpx.Client, params: dict, seen: dict) -> None:
        page = 1
        total = None
        while True:
            p = {**params, "page": str(page)}
            jobs, page_total = self._fetch_page(client, p)
            if total is None:
                total = page_total
            for job in jobs:
                if job.db_id not in seen:
                    seen[job.db_id] = job
            fetched = page * PAGE_SIZE
            if not jobs or (total is not None and fetched >= total):
                break
            page += 1
            time.sleep(1.5)

    @_http_retry
    def _fetch_page(
        self, client: httpx.Client, params: dict
    ) -> tuple[list[RawJob], int]:
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
        return self._parse_response(resp.text)

    def _parse_response(self, html: str) -> tuple[list[RawJob], int]:
        idx = html.find("key: 'ds:1'")
        if idx < 0:
            logger.warning("Google: ds:1 callback not found")
            return [], 0

        # Find the closing ); for this callback
        end = html.find(");\n", idx)
        chunk = html[idx : end + 1] if end > 0 else html[idx : idx + 200_000]
        data_start = chunk.find("data:[[")
        if data_start < 0:
            return [], 0

        raw = chunk[data_start + 5 :]
        depth = 0
        end_idx = -1
        for i, c in enumerate(raw):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx < 0:
            return [], 0

        try:
            parsed = json.loads(raw[: end_idx + 1])
        except json.JSONDecodeError as e:
            logger.warning(f"Google: JSON parse error: {e}")
            return [], 0

        jobs_raw = parsed[0] if parsed else []
        total = parsed[2] if len(parsed) > 2 and isinstance(parsed[2], int) else 0

        now = datetime.now(timezone.utc)
        jobs = []
        for item in jobs_raw:
            job = self._parse_job(item, now)
            if job:
                jobs.append(job)
        return jobs, total

    def _parse_job(self, item: list, now: datetime) -> RawJob | None:
        if not item or len(item) <= IDX_LOCATIONS:
            return None
        job_id = str(item[IDX_ID]) if item[IDX_ID] else None
        if not job_id:
            return None
        title = item[IDX_TITLE] if len(item) > IDX_TITLE else ""
        url = item[IDX_URL] if len(item) > IDX_URL else ""
        # Fix signin URL to direct job URL
        if "signin?jobId=" in url:
            url = re.sub(r"/signin\?jobId=.*", "", url) or url

        locations_raw = item[IDX_LOCATIONS] if len(item) > IDX_LOCATIONS else []
        location = locations_raw[0][0] if locations_raw and locations_raw[0] else None
        is_remote = location and "remote" in location.lower() if location else False

        description_raw = item[IDX_DESCRIPTION] if len(item) > IDX_DESCRIPTION else None
        description = (
            description_raw[1]
            if isinstance(description_raw, list) and len(description_raw) > 1
            else None
        )

        return RawJob(
            external_id=job_id,
            company=self.company_name,
            title=title,
            url=url,
            location=location,
            remote=True if is_remote else None,
            salary=None,
            description=description,
            department=None,
            seniority=None,
            scraped_at=now,
        )
