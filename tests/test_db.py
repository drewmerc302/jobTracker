import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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
        id=job_id, company="Dropbox", title="EM", url="https://example.com",
        location="Remote", remote=True, salary="200k", description="desc",
        department="Eng", seniority="Senior", scraped_at=now,
    )
    job = db.get_job(job_id)
    assert job is not None
    assert job["title"] == "EM"
    assert job["first_seen_at"] is not None


def test_upsert_job_updates_last_seen(db):
    job_id = "dropbox:123"
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id=job_id, company="Dropbox", title="EM", url="https://example.com",
        scraped_at=now,
    )
    first = db.get_job(job_id)
    db.upsert_job(
        id=job_id, company="Dropbox", title="EM", url="https://example.com",
        scraped_at=now,
    )
    second = db.get_job(job_id)
    assert second["last_seen_at"] >= first["last_seen_at"]


def test_get_new_job_ids(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    new_ids = db.get_new_job_ids(["dropbox:1", "dropbox:2", "dropbox:3"])
    assert set(new_ids) == {"dropbox:2", "dropbox:3"}


def test_close_missing_jobs(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    db.upsert_job(id="dropbox:2", company="Dropbox", title="EM2", url="u", scraped_at=now)
    db.close_missing_jobs("Dropbox", current_ids=["dropbox:1"])
    job1 = db.get_job("dropbox:1")
    job2 = db.get_job("dropbox:2")
    assert job1["closed_at"] is None
    assert job2["closed_at"] is not None


def test_insert_match(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    db.insert_match(
        job_id="dropbox:1", relevance_score=0.85, match_reason="good fit",
        suggestions='{"edits": []}',
    )
    match = db.get_match("dropbox:1")
    assert match is not None
    assert match["relevance_score"] == 0.85


def test_start_and_complete_run(db):
    run_id = db.start_run()
    assert run_id is not None
    db.complete_run(run_id, jobs_scraped=100, new_jobs=5, matches_found=2, email_sent=True)
    run = db.get_run(run_id)
    assert run["jobs_scraped"] == 100
    assert run["email_sent"] == 1
    assert run["completed_at"] is not None


def test_get_unnotified_matches(db):
    now = datetime.now(timezone.utc)
    db.upsert_job(id="dropbox:1", company="Dropbox", title="EM", url="u", scraped_at=now)
    db.insert_match(job_id="dropbox:1", relevance_score=0.9, match_reason="great")
    unnotified = db.get_unnotified_matches()
    assert len(unnotified) == 1
    assert unnotified[0]["job_id"] == "dropbox:1"
