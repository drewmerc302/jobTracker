from src.pipeline import parse_args, run_pipeline
from src.db import Database


def test_parse_args_defaults():
    args = parse_args([])
    assert args.dry_run is False
    assert args.renotify is False
    assert args.step is None


def test_parse_args_dry_run():
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parse_args_step():
    args = parse_args(["--step", "scrape"])
    assert args.step == "scrape"


def test_parse_args_status():
    args = parse_args(["--status", "Stripe:123", "applied"])
    assert args.status == ["Stripe:123", "applied"]


def test_parse_args_track():
    args = parse_args(["--track", "Stripe:123"])
    assert args.track == "Stripe:123"


def test_parse_args_applications():
    args = parse_args(["--applications"])
    assert args.applications is True


def test_full_pipeline_runs_dedup_after_scrape(tmp_path, monkeypatch):
    """Dedup should run automatically after scraping in the full pipeline."""
    from unittest.mock import MagicMock, patch
    from src.scrapers.base import RawJob
    from datetime import datetime, timezone

    db = Database(tmp_path / "dedup_test.db")
    dedup_calls = []

    def fake_dedup(d):
        dedup_calls.append(True)
        return (0, 0)

    mock_scraper = MagicMock()
    mock_scraper.company_name = "Stripe"
    mock_scraper.fetch_jobs.return_value = [
        RawJob(
            external_id="1",
            company="Stripe",
            title="EM",
            url="https://x.com",
            location=None,
            remote=None,
            salary=None,
            description=None,
            department=None,
            seniority=None,
            scraped_at=datetime.now(timezone.utc),
        )
    ]

    with (
        patch("src.pipeline.Database", return_value=db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.pipeline.build_scrapers", return_value=[mock_scraper]),
        patch("src.pipeline.run_dedup", fake_dedup),
        patch(
            "src.pipeline.get_active_resume_yaml",
            return_value=(tmp_path / "r.yaml", {}),
        ),
        patch("src.pipeline.run_filter", return_value=[]),
        patch("src.pipeline.run_notify", return_value=True),
    ):
        MockConfig.return_value.db_path = tmp_path / "dedup_test.db"
        args = parse_args(["--dry-run"])
        run_pipeline(args)

    assert len(dedup_calls) == 1
