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


class WorkdayScraper(BaseScraper):
    def __init__(
        self,
        company_name: str,
        base_url: str,
        path: str,
        keyword_patterns: list[str] | None = None,
    ):
        self.company_name = company_name
        self.base_url = base_url
        self.path = path
        self.page_size = 20
        self.request_delay = 1.5
        self.keyword_patterns = keyword_patterns or []

    def _title_matches(self, title: str) -> bool:
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.keyword_patterns)

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(
                timeout=30,
                headers={
                    "User-Agent": "JobTracker/1.0",
                    "Content-Type": "application/json",
                },
            ) as client:
                listings = self._fetch_all_listings(client)
                logger.info(f"Found {len(listings)} listings for {self.company_name}")

                # Only fetch detail pages for manager-relevant titles
                relevant = [l for l in listings if self._title_matches(l["title"])]
                logger.info(
                    f"  {len(relevant)} match manager keywords, fetching details"
                )

                jobs = []
                now = datetime.now(timezone.utc)
                # Store non-relevant listings as basic records (for tracking/dedup)
                for listing in listings:
                    if listing in relevant:
                        continue
                    jobs.append(
                        RawJob(
                            external_id=listing["external_id"],
                            company=self.company_name,
                            title=listing["title"],
                            url=f"{self.base_url}{self.path}/{listing.get('external_path', '')}",
                            location=listing.get("location"),
                            remote=None,
                            salary=None,
                            description=None,
                            department=None,
                            seniority=None,
                            scraped_at=now,
                        )
                    )

                # Fetch full details only for relevant titles
                for i, listing in enumerate(relevant):
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
            resp = self._post_listings_page(
                client,
                url,
                {
                    "appliedFacets": {},
                    "limit": self.page_size,
                    "offset": offset,
                    "searchText": "engineering manager",
                },
            )
            data = resp.json()
            listings = self._parse_search_results(data)
            all_listings.extend(listings)
            total = data.get("total", 0)
            offset += self.page_size
            if offset >= total:
                break
            time.sleep(self.request_delay)
        return all_listings

    @_http_retry
    def _post_listings_page(
        self, client: httpx.Client, url: str, payload: dict
    ) -> httpx.Response:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp

    @_http_retry
    def _get_detail_page(self, client: httpx.Client, url: str) -> httpx.Response:
        resp = client.get(url)
        resp.raise_for_status()
        return resp

    def _parse_search_results(self, data: dict) -> list[dict]:
        results = []
        for posting in data.get("jobPostings", []):
            ext_path = posting.get("externalPath", "")
            raw_id = (posting.get("bulletFields") or [""])[0]
            # Fall back to last path segment if bulletFields is empty
            external_id = raw_id or ext_path.split("/")[-1] or ext_path
            results.append(
                {
                    "external_id": external_id,
                    "title": posting.get("title", ""),
                    "external_path": ext_path,
                    "location": posting.get("locationsText"),
                }
            )
        return results

    def _fetch_detail(self, client: httpx.Client, listing: dict) -> RawJob | None:
        path = listing.get("external_path", "")
        if not path:
            return None
        url = f"{self.base_url}{self.path}/{path}"
        try:
            resp = self._get_detail_page(client, url)
            return self._parse_detail(resp.json(), listing["external_id"])
        except Exception as e:
            logger.warning(f"Failed to fetch detail for {listing['external_id']}: {e}")
            now = datetime.now(timezone.utc)
            return RawJob(
                external_id=listing["external_id"],
                company=self.company_name,
                title=listing["title"],
                url=url,
                location=listing.get("location"),
                remote=None,
                salary=None,
                description=None,
                department=None,
                seniority=None,
                scraped_at=now,
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
