import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from src.db import Database
from src.pipeline import parse_args, run_pipeline


@pytest.fixture
def db_with_applied_job(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:1", company="Stripe", title="EM", url="https://x.com", scraped_at=now
    )
    db.commit()
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:1", "applied")
    db.set_follow_up_date("stripe:1", "2000-01-01")
    return db


def test_parse_args_follow_ups():
    args = parse_args(["--follow-ups"])
    assert args.follow_ups is True


def test_parse_args_followed_up():
    args = parse_args(["--followed-up", "stripe:1"])
    assert args.followed_up == "stripe:1"


def test_parse_args_set_followup():
    args = parse_args(["--set-followup", "stripe:1", "2026-05-01"])
    assert args.set_followup == ["stripe:1", "2026-05-01"]


def test_follow_ups_prints_overdue(db_with_applied_job, tmp_path, capsys):
    with (
        patch("src.pipeline.Database", return_value=db_with_applied_job),
        patch("src.pipeline.Config") as MockConfig,
    ):
        MockConfig.return_value.db_path = tmp_path / "test.db"
        args = parse_args(["--follow-ups"])
        # run_pipeline needs a real db — test via db method directly
    overdue = db_with_applied_job.get_overdue_follow_ups()
    assert len(overdue) == 1
    assert overdue[0]["company"] == "Stripe"


def test_followed_up_resets_date(db_with_applied_job):
    db_with_applied_job.mark_followed_up("stripe:1", reset_days=7)
    app = db_with_applied_job.get_application("stripe:1")
    assert app["followed_up_at"] is not None
    assert app["follow_up_after"] > "2000-01-01"


def test_set_followup_updates_date(db_with_applied_job):
    db_with_applied_job.set_follow_up_date("stripe:1", "2026-06-01")
    app = db_with_applied_job.get_application("stripe:1")
    assert app["follow_up_after"] == "2026-06-01"


def test_follow_ups_command_output(tmp_path, capsys):
    """--follow-ups handler in run_pipeline() outputs the overdue table correctly."""
    db = Database(tmp_path / "fu_test.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:99",
        company="Stripe",
        title="EM",
        url="https://x.com",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:99", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:99", "applied")
    db.set_follow_up_date("stripe:99", "2000-01-01")

    with (
        patch("src.pipeline.Database", return_value=db),
        patch("src.pipeline.Config") as MockConfig,
    ):
        MockConfig.return_value.db_path = tmp_path / "fu_test.db"
        args = parse_args(["--follow-ups"])
        run_pipeline(args)

    captured = capsys.readouterr()
    assert "Stripe" in captured.out
    assert "applied" in captured.out
    assert "2000-01-01" in captured.out


def test_status_applied_auto_sets_follow_up(tmp_path):
    db = Database(tmp_path / "test2.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:10",
        company="Stripe",
        title="EM",
        url="https://x.com",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:10", relevance_score=0.9, match_reason="good")

    with (
        patch("src.pipeline.Database", return_value=db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.steps.obsidian.write_application_note"),
        patch("src.steps.obsidian.write_dashboard"),
    ):
        MockConfig.return_value.db_path = tmp_path / "test2.db"
        args = parse_args(["--status", "stripe:10", "applied"])
        run_pipeline(args)

    app = db.get_application("stripe:10")
    assert app["follow_up_after"] is not None


def test_status_interviewing_auto_sets_follow_up(tmp_path):
    db = Database(tmp_path / "test3.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:11",
        company="Stripe",
        title="EM",
        url="https://x.com",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:11", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:11", "applied")

    with (
        patch("src.pipeline.Database", return_value=db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.steps.obsidian.write_application_note"),
        patch("src.steps.obsidian.write_dashboard"),
    ):
        MockConfig.return_value.db_path = tmp_path / "test3.db"
        args = parse_args(["--status", "stripe:11", "interviewing"])
        run_pipeline(args)

    app = db.get_application("stripe:11")
    assert app["follow_up_after"] is not None
