import pytest
from datetime import datetime, timezone

from src.db import Database
from src.steps.dedup import _normalize_title, _score_job, run_dedup


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _make_job(db, job_id, company, title, **kwargs):
    db.upsert_job(
        id=job_id,
        company=company,
        title=title,
        url=f"https://example.com/{job_id}",
        scraped_at=datetime.now(timezone.utc),
        **kwargs,
    )
    db.commit()


# --- normalize_title tests ---


def test_normalize_strips_senior():
    assert _normalize_title("Senior Engineering Manager") == "engineering manager"


def test_normalize_strips_sr():
    assert _normalize_title("Sr. Engineering Manager") == "engineering manager"


def test_normalize_strips_trailing_roman():
    assert _normalize_title("Engineering Manager II") == "engineering manager"


def test_normalize_preserves_department():
    assert (
        _normalize_title("Engineering Manager, Growth") == "engineering manager growth"
    )


def test_normalize_two_different_departments():
    assert _normalize_title("Engineering Manager, Growth") != _normalize_title(
        "Engineering Manager, Platform"
    )


def test_normalize_strips_punctuation():
    assert (
        _normalize_title("Engineering Manager - Platform")
        == "engineering manager platform"
    )


# --- score_job tests ---


def test_score_all_fields():
    job = {
        "salary": "200k",
        "description": "x" * 600,
        "location": "NYC",
        "department": "Eng",
    }
    assert _score_job(job) == 6


def test_score_no_fields():
    job = {"salary": None, "description": None, "location": None, "department": None}
    assert _score_job(job) == 0


def test_score_short_description_no_bonus():
    job = {"salary": None, "description": "short", "location": None, "department": None}
    assert _score_job(job) == 0


# --- run_dedup integration tests ---


def test_dedup_no_duplicates(db):
    _make_job(db, "stripe:1", "Stripe", "Engineering Manager, Growth")
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager, Platform")
    merged, removed = run_dedup(db)
    assert merged == 0
    assert removed == 0


def test_dedup_finds_seniority_duplicate(db):
    _make_job(
        db,
        "stripe:1",
        "Stripe",
        "Senior Engineering Manager",
        description="x" * 600,
        salary="200k",
        location="NYC",
    )
    _make_job(
        db,
        "stripe:2",
        "Stripe",
        "Engineering Manager",
        description=None,
        salary=None,
        location=None,
    )
    merged, removed = run_dedup(db)
    assert merged == 1
    assert removed == 1
    # canonical (stripe:1) survives
    assert db.get_job("stripe:1") is not None
    assert db.get_job("stripe:2") is None


def test_dedup_keeps_canonical_match(db):
    _make_job(
        db,
        "stripe:1",
        "Stripe",
        "Senior Engineering Manager",
        description="x" * 600,
        salary="200k",
    )
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="strong")
    db.insert_match(job_id="stripe:2", relevance_score=0.5, match_reason="weak")
    run_dedup(db)
    match = db.get_match("stripe:1")
    assert match is not None
    assert match["relevance_score"] == 0.9
    assert db.get_match("stripe:2") is None


def test_dedup_migrates_orphan_match_to_canonical(db):
    _make_job(
        db,
        "stripe:1",
        "Stripe",
        "Senior Engineering Manager",
        description="x" * 600,
        salary="200k",
    )
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    # Only duplicate has a match
    db.insert_match(job_id="stripe:2", relevance_score=0.7, match_reason="decent")
    run_dedup(db)
    assert db.get_match("stripe:1") is not None
    assert db.get_match("stripe:2") is None


def test_dedup_migrates_application_to_canonical(db):
    _make_job(
        db,
        "stripe:1",
        "Stripe",
        "Senior Engineering Manager",
        description="x" * 600,
        salary="200k",
    )
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    db.set_application_status("stripe:2", "applied")
    run_dedup(db)
    app = db.get_application("stripe:1")
    assert app is not None
    assert app["status"] == "applied"
    assert db.get_application("stripe:2") is None


def test_dedup_keeps_more_advanced_application_status(db):
    _make_job(
        db,
        "stripe:1",
        "Stripe",
        "Senior Engineering Manager",
        description="x" * 600,
        salary="200k",
    )
    _make_job(db, "stripe:2", "Stripe", "Engineering Manager")
    db.set_application_status("stripe:1", "applied")
    db.set_application_status("stripe:2", "interviewing")
    run_dedup(db)
    app = db.get_application("stripe:1")
    assert app["status"] == "interviewing"


def test_dedup_no_cross_company(db):
    _make_job(db, "stripe:1", "Stripe", "Engineering Manager")
    _make_job(db, "datadog:1", "DataDog", "Engineering Manager")
    merged, removed = run_dedup(db)
    assert merged == 0
