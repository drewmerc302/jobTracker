import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock


from src.scrapers.base import RawJob
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.workday import WorkdayScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_raw_job_db_id():
    job = RawJob(
        external_id="12345",
        company="Dropbox",
        title="EM",
        url="https://example.com",
        location=None,
        remote=None,
        salary=None,
        description=None,
        department=None,
        seniority=None,
        scraped_at=datetime.now(timezone.utc),
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
    assert jobs[0].url == "https://job-boards.greenhouse.io/dropbox/jobs/12345"


def test_greenhouse_custom_url_template():
    with open(FIXTURES / "greenhouse_response.json") as f:
        data = json.load(f)
    scraper = GreenhouseScraper(
        board_slug="stripe",
        company_name="Stripe",
        url_template="https://stripe.com/jobs/listing/{slug}/{id}",
    )
    jobs = scraper._parse_response(data)
    assert (
        jobs[0].url
        == "https://stripe.com/jobs/listing/engineering-manager-platform/12345"
    )
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


def test_workday_parse_search():
    with open(FIXTURES / "workday_search_response.json") as f:
        data = json.load(f)
    scraper = WorkdayScraper(
        company_name="Capital One",
        base_url="https://capitalone.wd12.myworkdayjobs.com",
        path="/wday/cxs/capitalone/Capital_One",
    )
    listings = scraper._parse_search_results(data)
    assert len(listings) == 2
    assert listings[0]["external_id"] == "R239042"
    assert listings[0]["title"] == "Senior Manager, Software Engineering"


def test_workday_parse_detail():
    with open(FIXTURES / "workday_detail_response.json") as f:
        data = json.load(f)
    scraper = WorkdayScraper(
        company_name="Capital One",
        base_url="https://capitalone.wd12.myworkdayjobs.com",
        path="/wday/cxs/capitalone/Capital_One",
    )
    job = scraper._parse_detail(data, "R239042")
    assert job.external_id == "R239042"
    assert job.company == "Capital One"
    assert "Lead multiple engineering teams" in job.description
    assert job.location == "McLean, VA"


@patch("src.scrapers.workday.httpx.Client")
def test_workday_handles_failure(mock_client_class):
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = Exception("Connection refused")
    mock_client_class.return_value = mock_client

    scraper = WorkdayScraper(
        company_name="Capital One",
        base_url="https://capitalone.wd12.myworkdayjobs.com",
        path="/wday/cxs/capitalone/Capital_One",
    )
    jobs = scraper.fetch_jobs()
    assert jobs == []


@patch("src.scrapers.greenhouse.httpx")
def test_greenhouse_is_job_live_returns_true_on_200(mock_httpx):
    from src.scrapers.greenhouse import GreenhouseScraper

    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_httpx.get.return_value = mock_resp
    assert (
        scraper.is_job_live("https://job-boards.greenhouse.io/stripe/jobs/123") is True
    )


@patch("src.scrapers.greenhouse.httpx")
def test_greenhouse_is_job_live_returns_false_on_404(mock_httpx):
    from src.scrapers.greenhouse import GreenhouseScraper

    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_httpx.get.return_value = mock_resp
    assert (
        scraper.is_job_live("https://job-boards.greenhouse.io/stripe/jobs/123") is False
    )


@patch("src.scrapers.greenhouse.httpx")
def test_greenhouse_is_job_live_returns_none_on_error(mock_httpx):
    from src.scrapers.greenhouse import GreenhouseScraper

    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    mock_httpx.get.side_effect = Exception("timeout")
    assert (
        scraper.is_job_live("https://job-boards.greenhouse.io/stripe/jobs/123") is None
    )


@patch("src.scrapers.workday.httpx")
def test_workday_is_job_live_returns_true_on_200_with_content(mock_httpx):
    from src.scrapers.workday import WorkdayScraper

    scraper = WorkdayScraper(
        company_name="Netflix",
        base_url="https://netflix.wd1.myworkdayjobs.com",
        path="/wday/cxs/netflix/netflix",
        keyword_patterns=[],
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Job details here: Engineering Manager</html>"
    mock_httpx.get.return_value = mock_resp
    assert scraper.is_job_live("https://netflix.wd1.myworkdayjobs.com/job/123") is True


@patch("src.scrapers.workday.httpx")
def test_workday_is_job_live_returns_false_on_not_available(mock_httpx):
    from src.scrapers.workday import WorkdayScraper

    scraper = WorkdayScraper(
        company_name="Netflix",
        base_url="https://netflix.wd1.myworkdayjobs.com",
        path="/wday/cxs/netflix/netflix",
        keyword_patterns=[],
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>This page is no longer available</html>"
    mock_httpx.get.return_value = mock_resp
    assert scraper.is_job_live("https://netflix.wd1.myworkdayjobs.com/job/123") is False


@patch("src.scrapers.google.httpx")
def test_google_is_job_live_returns_false_on_no_longer_available(mock_httpx):
    from src.scrapers.google import GoogleScraper

    scraper = GoogleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>This job is no longer available</html>"
    mock_httpx.get.return_value = mock_resp
    assert (
        scraper.is_job_live(
            "https://www.google.com/about/careers/applications/jobs/results/123"
        )
        is False
    )


@patch("src.scrapers.google.httpx")
def test_google_is_job_live_returns_true_on_valid_content(mock_httpx):
    from src.scrapers.google import GoogleScraper

    scraper = GoogleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Engineering Manager - Apply now" + "x" * 500 + "</html>"
    mock_httpx.get.return_value = mock_resp
    assert (
        scraper.is_job_live(
            "https://www.google.com/about/careers/applications/jobs/results/123"
        )
        is True
    )


@patch("src.scrapers.apple.httpx")
def test_apple_is_job_live_returns_false_on_not_available(mock_httpx):
    from src.scrapers.apple import AppleScraper

    scraper = AppleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>This position is no longer available</html>"
    mock_httpx.get.return_value = mock_resp
    assert scraper.is_job_live("https://jobs.apple.com/en-us/details/123") is False


@patch("src.scrapers.apple.httpx")
def test_apple_is_job_live_returns_true_on_valid_content(mock_httpx):
    from src.scrapers.apple import AppleScraper

    scraper = AppleScraper()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Engineering Manager - Apply</html>"
    mock_httpx.get.return_value = mock_resp
    assert scraper.is_job_live("https://jobs.apple.com/en-us/details/123") is True
