import json
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

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

CAREERS_URL = "https://www.shopify.com/careers"
_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
# brotli MUST be excluded — httpx brotli decoder crashes on Shopify's payload
_HEADERS = {
    "User-Agent": _CHROME_UA,
    "Accept-Encoding": "gzip, deflate",
}

# React Router 7 turbo-stream special index sentinels
_SPECIAL: dict[int, object] = {
    -1: None,
    -2: False,
    -3: True,
    -4: float("inf"),
    -5: None,
}


def _decode(arr: list, idx: int, cache: dict | None = None) -> object:
    """Recursively resolve a React Router turbo-stream flat JSON array."""
    if cache is None:
        cache = {}
    if idx in _SPECIAL:
        return _SPECIAL[idx]
    if idx < 0 or idx >= len(arr):
        return None
    if idx in cache:
        return cache[idx]
    val = arr[idx]
    if isinstance(val, dict):
        result: dict = {}
        for k, v in val.items():
            key = arr[int(k[1:])] if k.startswith("_") else k
            result[key] = _decode(arr, v, cache)
        cache[idx] = result
        return result
    elif isinstance(val, list):
        result_list = [_decode(arr, i, cache) for i in val]
        cache[idx] = result_list
        return result_list
    else:
        cache[idx] = val
        return val


def _extract_array(html: str) -> list | None:
    """Extract and decode the turbo-stream JSON array from the page HTML."""
    m = re.search(
        r'streamController\.enqueue\("(.*?)"(?:\);|\))',
        html,
        re.DOTALL,
    )
    if not m:
        return None
    raw = m.group(1).encode().decode("unicode_escape")
    return json.loads(raw)


def _find_route_data(
    arr: list, name_fragment: str, exclude: list[str] | None = None
) -> dict | None:
    """
    arr[2] is a dict mapping index refs to route value indices.
    Walk it to find a route whose resolved name contains `name_fragment`
    and does NOT contain any string in `exclude`.
    """
    if len(arr) < 3 or not isinstance(arr[2], dict):
        return None
    exclude = exclude or []
    route_map = arr[2]
    for k, route_val_idx in route_map.items():
        # Resolve the key to a route name string
        try:
            key_idx = int(k[1:]) if k.startswith("_") else None
        except (ValueError, TypeError):
            key_idx = None
        route_name = arr[key_idx] if key_idx is not None and key_idx < len(arr) else k
        if not isinstance(route_name, str):
            continue
        if name_fragment not in route_name:
            continue
        if any(exc in route_name for exc in exclude):
            continue
        decoded = _decode(arr, route_val_idx)
        if isinstance(decoded, dict):
            return decoded
    return None


class ShopifyScraper(BaseScraper):
    """Scrapes Shopify jobs from the Ashby-backed careers page."""

    company_name = "Shopify"

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(timeout=30, headers=_HEADERS) as client:
                listing_data = self._fetch_listing(client)
                if not listing_data:
                    logger.warning("Shopify: could not extract listing data")
                    return []

                postings = listing_data.get("jobPostingsWithJobs")
                if not isinstance(postings, list):
                    logger.warning(
                        "Shopify: jobPostingsWithJobs not found or not a list"
                    )
                    return []

                logger.info(f"Shopify: found {len(postings)} job postings")
                jobs: list[RawJob] = []
                for i, entry in enumerate(postings):
                    job = self._parse_entry(entry, client)
                    if job:
                        jobs.append(job)
                    if i < len(postings) - 1:
                        time.sleep(0.3)

                logger.info(f"Shopify: returning {len(jobs)} jobs")
                return jobs
        except Exception as e:
            logger.error(f"Shopify: failed to fetch jobs: {e}")
            return []

    @_http_retry
    def _fetch_listing(self, client: httpx.Client) -> dict | None:
        resp = client.get(CAREERS_URL)
        resp.raise_for_status()
        arr = _extract_array(resp.text)
        if arr is None:
            logger.warning("Shopify: turbo-stream array not found on listing page")
            return None
        return _find_route_data(arr, "careers", exclude=["~~", "posting"])

    @_http_retry
    def _fetch_description(self, client: httpx.Client, uuid: str) -> str | None:
        resp = client.get(CAREERS_URL, params={"ashby_jid": uuid})
        resp.raise_for_status()
        arr = _extract_array(resp.text)
        if arr is None:
            return None
        route_data = _find_route_data(arr, "posting")
        if not isinstance(route_data, dict):
            return None
        posting = route_data.get("jobPosting")
        if not isinstance(posting, dict):
            return None
        return posting.get("descriptionPlain")

    def _parse_entry(self, entry: object, client: httpx.Client) -> RawJob | None:
        if not isinstance(entry, dict):
            return None
        posting = entry.get("jobPosting")
        if not isinstance(posting, dict):
            return None

        uuid = posting.get("id")
        if not uuid:
            return None

        title = posting.get("title") or ""
        department = posting.get("teamName")
        location = posting.get("locationName")
        workplace_type = posting.get("workplaceType", "")
        apply_link = posting.get("applyLink") or f"{CAREERS_URL}?ashby_jid={uuid}"

        # Only flag explicitly Remote; Hybrid/OnSite left as None (may still be acceptable)
        remote: bool | None = True if workplace_type == "Remote" else None

        description: str | None = None
        try:
            description = self._fetch_description(client, uuid)
        except Exception as e:
            logger.debug(f"Shopify: could not fetch description for {uuid}: {e}")

        now = datetime.now(timezone.utc)
        return RawJob(
            external_id=str(uuid),
            company=self.company_name,
            title=title,
            url=apply_link,
            location=location,
            remote=remote,
            salary=None,
            description=description,
            department=department,
            seniority=None,
            scraped_at=now,
        )

    def is_job_live(self, url: str) -> bool | None:
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            jid_list = qs.get("ashby_jid")
            if not jid_list:
                return None
            uuid = jid_list[0]
            resp = httpx.get(
                CAREERS_URL,
                params={"ashby_jid": uuid},
                headers=_HEADERS,
                timeout=15,
                follow_redirects=True,
            )
            if resp.status_code == 404:
                return False
            if resp.status_code != 200:
                return None
            arr = _extract_array(resp.text)
            if arr is None:
                return None
            route_data = _find_route_data(arr, "posting")
            if not isinstance(route_data, dict):
                return False
            posting = route_data.get("jobPosting")
            return isinstance(posting, dict) and bool(posting.get("id"))
        except Exception:
            return None
