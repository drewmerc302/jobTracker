import sqlite3
from datetime import datetime, timezone

import pytest

from src.db import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    return Database(db_path)


def test_creates_tables(db):
    conn = sqlite3.connect(db.path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert "jobs" in table_names
    assert "matches" in table_names
    assert "runs" in table_names


def test_upsert_job_new(db):
    job_id = "dropbox:123"
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id=job_id,
        company="Dropbox",
        title="EM",
        url="https://example.com",
        location="Remote",
        remote=True,
        salary="200k",
        description="desc",
        department="Eng",
        seniority="Senior",
        scraped_at=now,
    )
    job = db.get_job(job_id)
    assert job is not None
    assert job["title"] == "EM"
    assert job["first_seen_at"] is not None


def test_upsert_job_updates_last_seen(db):
    job_id = "dropbox:123"
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id=job_id,
        company="Dropbox",
        title="EM",
        url="https://example.com",
        scraped_at=now,
    )
    first = db.get_job(job_id)
    db.upsert_job(
        id=job_id,
        company="Dropbox",
        title="EM",
        url="https://example.com",
        scraped_at=now,
    )
    second = db.get_job(job_id)
    assert second["last_seen_at"] >= first["last_seen_at"]


def test_get_new_job_ids(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now
    )
    new_ids = db.get_new_job_ids(["dropbox:1", "dropbox:2", "dropbox:3"])
    assert set(new_ids) == {"dropbox:2", "dropbox:3"}


def test_close_missing_jobs(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now
    )
    db.upsert_job(
        id="dropbox:2", company="Dropbox", title="EM2", url="u", scraped_at=now
    )
    db.close_missing_jobs("Dropbox", current_ids=["dropbox:1"])
    job1 = db.get_job("dropbox:1")
    job2 = db.get_job("dropbox:2")
    assert job1["closed_at"] is None
    assert job2["closed_at"] is not None


def test_insert_match(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now
    )
    db.insert_match(
        job_id="dropbox:1",
        relevance_score=0.85,
        match_reason="good fit",
        suggestions='{"edits": []}',
    )
    match = db.get_match("dropbox:1")
    assert match is not None
    assert match["relevance_score"] == 0.85


def test_start_and_complete_run(db):
    run_id = db.start_run()
    assert run_id is not None
    db.complete_run(
        run_id, jobs_scraped=100, new_jobs=5, matches_found=2, email_sent=True
    )
    run = db.get_run(run_id)
    assert run["jobs_scraped"] == 100
    assert run["email_sent"] == 1
    assert run["completed_at"] is not None


def test_get_unnotified_matches(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now
    )
    db.insert_match(job_id="dropbox:1", relevance_score=0.9, match_reason="great")
    unnotified = db.get_unnotified_matches()
    assert len(unnotified) == 1
    assert unnotified[0]["job_id"] == "dropbox:1"


def test_set_application_status(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    app = db.get_application("stripe:1")
    assert app is not None
    assert app["status"] == "applied"
    assert app["applied_date"] is not None


def test_set_application_status_updates(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    db.set_application_status("stripe:1", "interviewing")
    app = db.get_application("stripe:1")
    assert app["status"] == "interviewing"
    assert app["applied_date"] is not None


def test_status_history_logged(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    db.set_application_status("stripe:1", "interviewing")
    history = db.get_status_history("stripe:1")
    assert len(history) == 2
    assert history[0]["new_status"] == "applied"
    assert history[1]["old_status"] == "applied"
    assert history[1]["new_status"] == "interviewing"


def test_get_all_applications(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM1", url="u", scraped_at=now)
    db.upsert_job(id="stripe:2", company="Stripe", title="EM2", url="u", scraped_at=now)
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="great")
    db.insert_match(job_id="stripe:2", relevance_score=0.8, match_reason="good")
    db.set_application_status("stripe:1", "applied")
    apps = db.get_all_applications()
    assert len(apps) == 2
    statuses = {a["job_id"]: a["status"] for a in apps}
    assert statuses["stripe:1"] == "applied"
    assert statuses["stripe:2"] == "new"


def test_update_salary_notes(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="stripe:1", company="Stripe", title="EM", url="u", scraped_at=now)
    db.set_application_status("stripe:1", "applied")
    db.update_salary_notes("stripe:1", "$200-250k base + equity")
    app = db.get_application("stripe:1")
    assert app["salary_notes"] == "$200-250k base + equity"


def test_follow_up_columns_exist(db):
    cols = {
        row[1] for row in db._conn.execute("PRAGMA table_info(applications)").fetchall()
    }
    assert "follow_up_after" in cols
    assert "followed_up_at" in cols


def test_get_overdue_follow_ups_empty(db):
    assert db.get_overdue_follow_ups() == []


def test_get_overdue_follow_ups_returns_overdue(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:1", company="Stripe", title="EM", url="https://x.com", scraped_at=now
    )
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:1", "applied")
    db.set_follow_up_date("stripe:1", "2000-01-01")  # far in the past

    overdue = db.get_overdue_follow_ups()
    assert len(overdue) == 1
    assert overdue[0]["job_id"] == "stripe:1"


def test_get_overdue_follow_ups_excludes_terminal_statuses(db):
    now = datetime.now(timezone.utc)
    for jid, status in [
        ("stripe:2", "rejected"),
        ("stripe:3", "withdrawn"),
        ("stripe:4", "offer"),
    ]:
        db.upsert_job(
            id=jid, company="Stripe", title="EM", url="https://x.com", scraped_at=now
        )
        db.insert_match(job_id=jid, relevance_score=0.9, match_reason="good")
        db.set_application_status(jid, status)
        db.set_follow_up_date(jid, "2000-01-01")

    assert db.get_overdue_follow_ups() == []


def test_mark_followed_up_resets_date(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:5", company="Stripe", title="EM", url="https://x.com", scraped_at=now
    )
    db.insert_match(job_id="stripe:5", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:5", "applied")
    db.set_follow_up_date("stripe:5", "2000-01-01")

    db.mark_followed_up("stripe:5", reset_days=7)
    app = db.get_application("stripe:5")
    assert app["followed_up_at"] is not None
    assert app["follow_up_after"] > "2000-01-01"  # reset to future


def test_mark_followed_up_no_reset_when_no_date(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:6", company="Stripe", title="EM", url="https://x.com", scraped_at=now
    )
    db.insert_match(job_id="stripe:6", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:6", "applied")
    # do NOT set follow_up_after

    db.mark_followed_up("stripe:6", reset_days=7)
    app = db.get_application("stripe:6")
    assert app["followed_up_at"] is not None
    assert app["follow_up_after"] is None  # was null, stays null
