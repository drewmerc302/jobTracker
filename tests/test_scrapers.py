import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.scrapers.base import RawJob, BaseScraper
from src.scrapers.greenhouse import GreenhouseScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_raw_job_db_id():
    job = RawJob(
        external_id="12345", company="Dropbox", title="EM",
        url="https://example.com", location=None, remote=None,
        salary=None, description=None, department=None,
        seniority=None, scraped_at=datetime.now(timezone.utc),
    )
    assert job.db_id == "Dropbox:12345"


def test_greenhouse_parse_jobs():
    with open(FIXTURES / "greenhouse_response.json") as f:
        data = json.load(f)
    scraper = GreenhouseScraper(board_slug="dropbox", company_name="Dropbox")
    jobs = scraper._parse_response(data)
    assert len(jobs) == 2
    assert jobs[0].external_id == "12345"
    assert jobs[0].company == "Dropbox"
    assert jobs[0].title == "Engineering Manager, Platform"
    assert jobs[0].url == "https://jobs.dropbox.com/listing/12345"
    assert jobs[0].location == "Remote - US"
    assert jobs[0].department == "Engineering"
    assert "Lead a team" in jobs[0].description


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_fetch_jobs(mock_get):
    with open(FIXTURES / "greenhouse_response.json") as f:
        data = json.load(f)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = data
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    scraper = GreenhouseScraper(board_slug="dropbox", company_name="Dropbox")
    jobs = scraper.fetch_jobs()
    assert len(jobs) == 2
    mock_get.assert_called_once()
    assert "dropbox" in mock_get.call_args[0][0]


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_handles_failure(mock_get):
    mock_get.side_effect = Exception("Connection refused")
    scraper = GreenhouseScraper(board_slug="dropbox", company_name="Dropbox")
    jobs = scraper.fetch_jobs()
    assert jobs == []
