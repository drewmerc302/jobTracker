import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx

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


def test_greenhouse_title_relevant_gates_fetch():
    scraper = GreenhouseScraper(
        board_slug="stripe",
        company_name="Stripe",
        keyword_patterns=["engineering manager", "director of engineering"],
    )
    assert scraper._title_relevant("Engineering Manager, Payments") is True
    assert scraper._title_relevant("Senior Software Engineer") is False
    # No patterns configured => never worth a per-job page fetch.
    bare = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    assert bare._title_relevant("Engineering Manager, Payments") is False


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_fetch_salary_from_page_parses_band(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = (
        "<p>The annual US base salary range for this role is "
        "$236,000 - $354,000. Additional benefits may include equity...</p>"
    )
    mock_get.return_value = mock_resp
    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    assert (
        scraper._fetch_salary_from_page("https://stripe.com/x") == "$236,000 - $354,000"
    )


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_fetch_salary_from_page_handles_non_200(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp
    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    assert scraper._fetch_salary_from_page("https://stripe.com/x") is None


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_fetch_salary_from_page_handles_error(mock_get):
    mock_get.side_effect = httpx.ConnectError("boom")
    scraper = GreenhouseScraper(board_slug="stripe", company_name="Stripe")
    assert scraper._fetch_salary_from_page("https://stripe.com/x") is None


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_salary_from_page_integration(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = (
        "The annual US base salary range for this role is $200,000 - $300,000."
    )
    mock_get.return_value = mock_resp
    data = {
        "jobs": [
            {
                "id": 999,
                "title": "Engineering Manager, Payments",
                "content": "<p>No comp listed in the body.</p>",
                "location": {"name": "New York"},
                "departments": [{"name": "Engineering"}],
            }
        ]
    }
    scraper = GreenhouseScraper(
        board_slug="stripe",
        company_name="Stripe",
        url_template="https://stripe.com/jobs/listing/{slug}/{id}",
        salary_from_page=True,
        keyword_patterns=["engineering manager"],
    )
    jobs = scraper._parse_response(data)
    assert jobs[0].salary == "$200,000 - $300,000"
    mock_get.assert_called_once()


@patch("src.scrapers.greenhouse.httpx.get")
def test_greenhouse_salary_from_page_skips_irrelevant_titles(mock_get):
    data = {
        "jobs": [
            {
                "id": 1000,
                "title": "Senior Software Engineer",
                "content": "<p>No comp listed in the body.</p>",
                "location": {"name": "New York"},
                "departments": [{"name": "Engineering"}],
            }
        ]
    }
    scraper = GreenhouseScraper(
        board_slug="stripe",
        company_name="Stripe",
        url_template="https://stripe.com/jobs/listing/{slug}/{id}",
        salary_from_page=True,
        keyword_patterns=["engineering manager"],
    )
    jobs = scraper._parse_response(data)
    assert jobs[0].salary is None
    mock_get.assert_not_called()


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


def test_oracle_parse_and_filter():
    from src.scrapers.oracle import OracleScraper

    with open(FIXTURES / "oracle_search_response.json") as f:
        data = json.load(f)
    scraper = OracleScraper(
        company_name="JPMorganChase",
        tenant="jpmc",
        site_number="CX_1001",
        keyword_patterns=["engineering manager", "manager of software engineering"],
        countries=["US"],
    )
    reqs = data["items"][0]["requisitionList"]
    now = datetime.now(timezone.utc)
    kept = []
    for r in reqs:
        if r.get("PrimaryLocationCountry") not in scraper.countries:
            continue
        if not scraper._title_matches(r.get("Title", "")):
            continue
        kept.append(scraper._parse_req(r, now))

    assert len(kept) == 1, "should keep only US mgr-titled req"
    job = kept[0]
    assert job.company == "JPMorganChase"
    assert "Manager of Software Engineering" in job.title
    assert job.external_id == "210749559"
    assert job.url.startswith("https://jpmc.fa.oraclecloud.com/hcmUI/")
    assert "210749559" in job.url
    assert job.location == "New York, NY, United States"
    assert job.db_id == "JPMorganChase:210749559"


def test_oracle_title_matches():
    from src.scrapers.oracle import OracleScraper

    s = OracleScraper(
        company_name="JPMorganChase",
        tenant="jpmc",
        keyword_patterns=["engineering manager", "manager of software engineering"],
    )
    assert s._title_matches("Manager of Software Engineering - Java")
    assert s._title_matches("Senior Engineering Manager, Payments")
    assert not s._title_matches("Marketing Manager, Loyalty")


def test_oracle_remote_extraction():
    from src.scrapers.oracle import OracleScraper

    s = OracleScraper(company_name="X", tenant="x")
    assert s._extract_remote({"WorkplaceTypeCode": "REMOTE"}) is True
    assert s._extract_remote({"WorkplaceTypeCode": "ONSITE"}) is False
    assert s._extract_remote({"WorkplaceTypeCode": "HYBRID"}) is False
    assert (
        s._extract_remote({"WorkplaceTypeCode": None, "PrimaryLocation": "Remote - US"})
        is True
    )
    assert (
        s._extract_remote({"WorkplaceTypeCode": None, "PrimaryLocation": "NY"}) is None
    )


@patch("src.scrapers.oracle.httpx.Client")
def test_oracle_handles_failure(mock_client_class):
    from src.scrapers.oracle import OracleScraper

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.side_effect = Exception("Connection refused")
    mock_client_class.return_value = mock_client

    s = OracleScraper(company_name="JPMorganChase", tenant="jpmc")
    assert s.fetch_jobs() == []


def test_lever_parse_jobs():
    from src.scrapers.lever import LeverScraper

    with open(FIXTURES / "lever_spotify.json") as f:
        data = json.load(f)
    scraper = LeverScraper(slug="spotify", company_name="Spotify")
    jobs = scraper._parse_response(data)
    assert len(jobs) == 2
    assert jobs[0].external_id == "abc-123-def"
    assert jobs[0].company == "Spotify"
    assert jobs[0].title == "Engineering Manager - Advertising"
    assert jobs[0].url == "https://jobs.lever.co/spotify/abc-123-def"
    assert jobs[0].location == "New York"
    assert jobs[0].department == "Engineering"
    assert jobs[0].remote is False  # hybrid
    assert jobs[0].seniority == "Permanent"
    assert "Lead our advertising engineering team." in jobs[0].description
    assert "What You'll Do" in jobs[0].description
    assert "Who You Are" in jobs[0].description
    assert "equal opportunity employer" in jobs[0].description


def test_lever_parse_remote_job():
    from src.scrapers.lever import LeverScraper

    with open(FIXTURES / "lever_spotify.json") as f:
        data = json.load(f)
    scraper = LeverScraper(slug="spotify", company_name="Spotify")
    jobs = scraper._parse_response(data)
    assert jobs[1].remote is True  # workplaceType: remote
    assert jobs[1].title == "Senior Data Scientist - Music Recs"


def test_lever_description_assembly():
    from src.scrapers.lever import LeverScraper

    scraper = LeverScraper(slug="test", company_name="Test")
    item = {
        "descriptionPlain": "Intro paragraph.",
        "lists": [
            {"text": "Requirements", "content": "<li>Skill A</li>"},
            {"text": "Nice to Have", "content": "<li>Skill B</li>"},
        ],
        "additionalPlain": "EEO statement.",
    }
    desc = scraper._build_description(item)
    assert "Intro paragraph." in desc
    assert "Requirements" in desc
    assert "Nice to Have" in desc
    assert "EEO statement." in desc


@patch("src.scrapers.lever.httpx.get")
def test_lever_fetch_jobs(mock_get):
    from src.scrapers.lever import LeverScraper

    with open(FIXTURES / "lever_spotify.json") as f:
        data = json.load(f)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = data
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    scraper = LeverScraper(slug="spotify", company_name="Spotify")
    jobs = scraper.fetch_jobs()
    assert len(jobs) == 2
    mock_get.assert_called_once()
    assert "spotify" in mock_get.call_args[0][0]


@patch("src.scrapers.lever.httpx.get")
def test_lever_handles_failure(mock_get):
    from src.scrapers.lever import LeverScraper

    mock_get.side_effect = Exception("Connection refused")
    scraper = LeverScraper(slug="spotify", company_name="Spotify")
    jobs = scraper.fetch_jobs()
    assert jobs == []


@patch("src.scrapers.lever.httpx")
def test_lever_is_job_live_returns_true_on_200(mock_httpx):
    from src.scrapers.lever import LeverScraper

    scraper = LeverScraper(slug="spotify", company_name="Spotify")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_httpx.get.return_value = mock_resp
    assert scraper.is_job_live("https://jobs.lever.co/spotify/abc-123") is True


@patch("src.scrapers.lever.httpx")
def test_lever_is_job_live_returns_false_on_404(mock_httpx):
    from src.scrapers.lever import LeverScraper

    scraper = LeverScraper(slug="spotify", company_name="Spotify")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_httpx.get.return_value = mock_resp
    assert scraper.is_job_live("https://jobs.lever.co/spotify/abc-123") is False


@patch("src.scrapers.lever.httpx")
def test_lever_is_job_live_returns_none_on_error(mock_httpx):
    from src.scrapers.lever import LeverScraper

    scraper = LeverScraper(slug="spotify", company_name="Spotify")
    mock_httpx.get.side_effect = Exception("timeout")
    assert scraper.is_job_live("https://jobs.lever.co/spotify/abc-123") is None
