import logging
import re
import time
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

_http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


class WorkdayScraper(BaseScraper):
    def __init__(self, company_name: str, base_url: str, path: str):
        self.company_name = company_name
        self.base_url = base_url
        self.path = path
        self.page_size = 20
        self.request_delay = 1.5

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(
                timeout=30,
                headers={"User-Agent": "JobTracker/1.0", "Content-Type": "application/json"},
            ) as client:
                listings = self._fetch_all_listings(client)
                logger.info(f"Found {len(listings)} listings for {self.company_name}")
                jobs = []
                for i, listing in enumerate(listings):
                    if i > 0:
                        time.sleep(self.request_delay)
                    job = self._fetch_detail(client, listing)
                    if job:
                        jobs.append(job)
                return jobs
        except Exception as e:
            logger.error(f"Failed to fetch {self.company_name} jobs: {e}")
            return []

    def _fetch_all_listings(self, client: httpx.Client) -> list[dict]:
        all_listings = []
        offset = 0
        while True:
            url = f"{self.base_url}{self.path}/jobs"
            resp = client.post(url, json={
                "appliedFacets": {},
                "limit": self.page_size,
                "offset": offset,
                "searchText": "manager",
            })
            resp.raise_for_status()
            data = resp.json()
            listings = self._parse_search_results(data)
            all_listings.extend(listings)
            total = data.get("total", 0)
            offset += self.page_size
            if offset >= total:
                break
            time.sleep(self.request_delay)
        return all_listings

    def _parse_search_results(self, data: dict) -> list[dict]:
        results = []
        for posting in data.get("jobPostings", []):
            results.append({
                "external_id": (posting.get("bulletFields") or [""])[0],
                "title": posting.get("title", ""),
                "external_path": posting.get("externalPath", ""),
                "location": posting.get("locationsText"),
            })
        return results

    def _fetch_detail(self, client: httpx.Client, listing: dict) -> RawJob | None:
        path = listing.get("external_path", "")
        if not path:
            return None
        try:
            url = f"{self.base_url}{self.path}/job/{path}"
            resp = client.get(url)
            resp.raise_for_status()
            return self._parse_detail(resp.json(), listing["external_id"])
        except Exception as e:
            logger.warning(f"Failed to fetch detail for {listing['external_id']}: {e}")
            now = datetime.now(timezone.utc)
            return RawJob(
                external_id=listing["external_id"],
                company=self.company_name,
                title=listing["title"],
                url=f"{self.base_url}{self.path}/job/{path}",
                location=listing.get("location"),
                remote=None, salary=None, description=None,
                department=None, seniority=None, scraped_at=now,
            )

    def _parse_detail(self, data: dict, external_id: str) -> RawJob:
        info = data.get("jobPostingInfo", {})
        now = datetime.now(timezone.utc)
        description = info.get("jobDescription", "")
        salary = self._extract_salary(description)
        location = info.get("location", "")
        additional = info.get("additionalLocations", [])
        remote = any("remote" in (loc or "").lower() for loc in [location] + additional)

        return RawJob(
            external_id=external_id,
            company=self.company_name,
            title=info.get("title", ""),
            url=info.get("externalUrl", ""),
            location=location,
            remote=remote or None,
            salary=salary,
            description=description,
            department=None,
            seniority=None,
            scraped_at=now,
        )

    def _extract_salary(self, html_content: str) -> str | None:
        patterns = [
            r"\$[\d,]+\s*[-–]\s*\$[\d,]+",
            r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:to|[-–])\s*\$[\d,]+(?:\.\d{2})?)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(0)
        return None
