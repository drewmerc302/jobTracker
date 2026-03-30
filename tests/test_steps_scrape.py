from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.db import Database
from src.scrapers.base import RawJob
from src.steps.scrape import run_scrape


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _make_job(external_id="123", company="Dropbox", title="EM"):
    return RawJob(
        external_id=external_id, company=company, title=title,
        url="https://example.com", location="Remote", remote=True,
        salary="200k", description="Lead a team", department="Eng",
        seniority=None, scraped_at=datetime.now(timezone.utc),
    )


def test_scrape_stores_new_jobs(db):
    mock_scraper = MagicMock()
    mock_scraper.company_name = "Dropbox"
    mock_scraper.fetch_jobs.return_value = [_make_job("1"), _make_job("2")]

    result = run_scrape(db, scrapers=[mock_scraper])
    assert result["jobs_scraped"] == 2
    assert result["new_jobs"] == 2
    assert len(result["new_job_ids"]) == 2
    assert db.get_job("Dropbox:1") is not None


def test_scrape_deduplicates(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="Dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)

    mock_scraper = MagicMock()
    mock_scraper.company_name = "Dropbox"
    mock_scraper.fetch_jobs.return_value = [_make_job("1"), _make_job("2")]

    result = run_scrape(db, scrapers=[mock_scraper])
    assert result["jobs_scraped"] == 2
    assert result["new_jobs"] == 1


def test_scrape_handles_scraper_failure(db):
    good_scraper = MagicMock()
    good_scraper.company_name = "Dropbox"
    good_scraper.fetch_jobs.return_value = [_make_job("1")]

    bad_scraper = MagicMock()
    bad_scraper.company_name = "Stripe"
    bad_scraper.fetch_jobs.side_effect = Exception("Connection failed")

    result = run_scrape(db, scrapers=[good_scraper, bad_scraper])
    assert result["jobs_scraped"] == 1
    assert "Stripe" in result["failed_companies"]
