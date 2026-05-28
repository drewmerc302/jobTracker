import json
import logging
import re
import time
from datetime import datetime, timezone

from curl_cffi import requests as cffi_requests
from curl_cffi.requests.exceptions import RequestException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

_http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RequestException),
    reraise=True,
)

BASE_URL = "https://jobs.fidelity.com"
LISTING_PATH = "/en/jobs/"
PAGE_SIZE = 20
IMPERSONATE = "chrome124"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _is_remote(location: str | None, description: str | None) -> bool | None:
    loc_str = (location or "").lower()
    desc_preview = (description or "")[:200].lower()
    if "remote" in loc_str or "remote" in desc_preview:
        return True
    return None


class FidelityScraper(BaseScraper):
    """Scrapes Fidelity jobs from jobs.fidelity.com using Chrome TLS impersonation."""

    company_name = "Fidelity"
    source = "fidelity"

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with cffi_requests.Session(impersonate=IMPERSONATE) as session:
                job_urls = self._collect_job_urls(session)
                logger.info(f"Fidelity: found {len(job_urls)} job URLs to fetch")
                results: list[RawJob] = []
                for job_id, url in job_urls.items():
                    job = self._fetch_detail(session, job_id, url)
                    if job:
                        results.append(job)
                    time.sleep(0.5)
                logger.info(f"Fidelity: returning {len(results)} jobs")
                return results
        except Exception as e:
            logger.error(f"Failed to fetch Fidelity jobs: {e}")
            return []

    def _collect_job_urls(self, session: cffi_requests.Session) -> dict[str, str]:
        job_urls: dict[str, str] = {}
        page = 1
        total: int | None = None

        while True:
            html = self._fetch_listing_page(session, page)
            if not html:
                break

            if total is None:
                m = re.search(r"([\d,]+)\s+open roles", html, re.IGNORECASE)
                if m:
                    total = int(m.group(1).replace(",", ""))
                    logger.info(f"Fidelity: {total} total open roles")
                else:
                    total = 0

            found = re.findall(r'href="(/en/jobs/(\d+)/[^"]+/)"', html)
            if not found:
                logger.debug(f"Fidelity: no job links found on page {page}")
                break

            for path, job_id in found:
                if job_id not in job_urls:
                    job_urls[job_id] = f"{BASE_URL}{path}"

            if total and len(job_urls) >= total:
                break
            if len(found) < PAGE_SIZE:
                break

            page += 1
            time.sleep(1.0)

        return job_urls

    @_http_retry
    def _fetch_listing_page(
        self, session: cffi_requests.Session, page: int
    ) -> str | None:
        params = {
            "team": "Technology",
            "search": "engineering manager",
            "pagesize": str(PAGE_SIZE),
            "origin": "filtered",
            "page": str(page),
        }
        resp = session.get(BASE_URL + LISTING_PATH, params=params)
        resp.raise_for_status()
        return resp.text

    @_http_retry
    def _fetch_detail_page(
        self, session: cffi_requests.Session, url: str
    ) -> str | None:
        resp = session.get(url)
        resp.raise_for_status()
        return resp.text

    def _fetch_detail(
        self, session: cffi_requests.Session, job_id: str, url: str
    ) -> RawJob | None:
        try:
            html = self._fetch_detail_page(session, url)
        except RequestException as e:
            logger.warning(f"Fidelity: request error fetching {url}: {e}")
            return None
        except Exception as e:
            if "404" in str(e):
                logger.debug(f"Fidelity: 404 for job {job_id}")
                return None
            logger.warning(f"Fidelity: error fetching {url}: {e}")
            return None

        if not html:
            return None

        return self._parse_detail(job_id, url, html)

    def _parse_detail(self, job_id: str, url: str, html: str) -> RawJob:
        now = datetime.now(timezone.utc)

        # Match by id="js-job-posting" — type attr is HTML-entity encoded
        m = re.search(
            r'<script[^>]*\bid="js-job-posting"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )

        if m:
            try:
                data = json.loads(m.group(1))
                title = data.get("title", "")
                raw_desc = data.get("description", "")
                description = _strip_html(raw_desc) if raw_desc else None

                location_obj = (
                    data.get("jobLocation", {}).get("address", {})
                    if isinstance(data.get("jobLocation"), dict)
                    else {}
                )
                city = location_obj.get("addressLocality", "")
                region = location_obj.get("addressRegion", "")
                location = ", ".join(filter(None, [city, region])) or None

                employment_type = data.get("employmentType")

                return RawJob(
                    external_id=job_id,
                    company=self.company_name,
                    title=title,
                    url=url,
                    location=location,
                    remote=_is_remote(location, description),
                    salary=None,
                    description=description,
                    department=None,
                    seniority=employment_type,
                    scraped_at=now,
                    source=self.source,
                )
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Fidelity: failed to parse ld+json for {job_id}: {e}")

        # Fallback: parse <h1> for title, nulls for everything else
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
        title = _strip_html(h1_match.group(1)) if h1_match else job_id

        logger.warning(f"Fidelity: using fallback parse for job {job_id}")
        return RawJob(
            external_id=job_id,
            company=self.company_name,
            title=title,
            url=url,
            location=None,
            remote=None,
            salary=None,
            description=None,
            department=None,
            seniority=None,
            scraped_at=now,
            source=self.source,
        )

    def is_job_live(self, url: str) -> bool | None:
        try:
            resp = cffi_requests.get(url, impersonate=IMPERSONATE, timeout=10)
            if resp.status_code == 404:
                return False
            if resp.status_code == 200:
                return "js-job-posting" in resp.text
            return None
        except Exception:
            return None
