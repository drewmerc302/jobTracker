import html
import logging
import re
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

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards"

# Used only for the optional per-job listing-page salary fetch (see
# _fetch_salary_from_page). Some boards render the pay band on their own site
# behind a default-UA check, so present a browser UA there.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


def _slugify(title: str) -> str:
    """Convert a job title to a URL slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug


class GreenhouseScraper(BaseScraper):
    source = "greenhouse"

    def __init__(
        self,
        board_slug: str,
        company_name: str,
        url_template: str | None = None,
        salary_from_page: bool = False,
        keyword_patterns: list[str] | None = None,
    ):
        self.board_slug = board_slug
        self.company_name = company_name
        self.url_template = url_template
        # When the board's API content omits the pay band (e.g. Stripe renders
        # it only on stripe.com), optionally fetch the listing page to recover
        # it — gated to keyword-relevant titles to bound request volume.
        self.salary_from_page = salary_from_page
        self.keyword_patterns = keyword_patterns or []

    def fetch_jobs(self) -> list[RawJob]:
        url = f"{GREENHOUSE_API}/{self.board_slug}/jobs?content=true"
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

    def _parse_response(self, data: dict) -> list[RawJob]:
        jobs = []
        now = datetime.now(timezone.utc)
        for item in data.get("jobs", []):
            url = self._build_url(item)
            salary = self._extract_salary(item.get("content", ""))
            if (
                salary is None
                and self.salary_from_page
                and self._title_relevant(item.get("title", ""))
            ):
                salary = self._fetch_salary_from_page(url)
            seniority = self._extract_metadata(item, "IC or MG")
            jobs.append(
                RawJob(
                    external_id=str(item["id"]),
                    company=self.company_name,
                    title=item["title"],
                    url=url,
                    location=item.get("location", {}).get("name"),
                    remote=self._is_remote(item),
                    salary=salary,
                    description=item.get("content"),
                    department=(item.get("departments") or [{}])[0].get("name")
                    if item.get("departments")
                    else None,
                    seniority=seniority,
                    scraped_at=now,
                    source=self.source,
                )
            )
        return jobs

    def _build_url(self, item: dict) -> str:
        """Build the job listing URL. Uses custom template if configured, else Greenhouse embed."""
        if self.url_template:
            slug = _slugify(item.get("title", ""))
            return self.url_template.format(slug=slug, id=item["id"])
        return f"https://job-boards.greenhouse.io/{self.board_slug}/jobs/{item['id']}"

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

    def _title_relevant(self, title: str) -> bool:
        """Whether a title warrants the extra per-job page fetch for salary.

        Boards return every open req (Stripe ~500+); only manager-track titles
        are worth a second HTTP round-trip. Empty patterns => never fetch.
        """
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.keyword_patterns)

    def _fetch_salary_from_page(self, url: str) -> str | None:
        """Recover a base-salary band from the public listing page.

        Used when the API content omits comp (Stripe renders the pay band on
        stripe.com, not in the Greenhouse payload). Returns None on any failure
        so a single bad fetch never breaks the board parse. The anchored regex
        avoids grabbing unrelated dollar figures elsewhere on the page.
        """
        try:
            resp = httpx.get(
                url,
                timeout=15,
                headers={"User-Agent": _BROWSER_UA},
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return None
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.debug(f"Salary page fetch failed for {url}: {e}")
            return None
        text = html.unescape(resp.text)
        match = re.search(
            r"base salary range[^$]{0,40}"
            r"(\$[\d,]+(?:\.\d+)?\s*[-–]\s*\$[\d,]+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
        return None

    def _is_remote(self, item: dict) -> bool | None:
        location = item.get("location", {}).get("name", "")
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

    def _extract_metadata(self, item: dict, field_name: str) -> str | None:
        for meta in item.get("metadata") or []:
            if meta.get("name") == field_name:
                return meta.get("value")
        return None
