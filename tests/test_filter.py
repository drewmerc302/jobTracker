from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.db import Database
from src.steps.filter import keyword_filter, llm_evaluate, prune_stale_matches


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_keyword_filter_matches():
    config = Config()
    jobs = [
        {"id": "1", "title": "Engineering Manager, Platform", "description": "desc"},
        {"id": "2", "title": "Software Engineer", "description": "desc"},
        {"id": "3", "title": "Director of Engineering", "description": "desc"},
        {"id": "4", "title": "VP of Engineering", "description": "desc"},
    ]
    matches = keyword_filter(jobs, config)
    matched_ids = [j["id"] for j in matches]
    assert "1" in matched_ids
    assert "3" in matched_ids
    assert "2" not in matched_ids
    assert "4" not in matched_ids


def test_keyword_filter_skips_no_description():
    config = Config()
    jobs = [
        {"id": "1", "title": "Engineering Manager", "description": None},
        {"id": "2", "title": "Engineering Manager", "description": "Lead a team"},
    ]
    matches = keyword_filter(jobs, config)
    assert len(matches) == 1
    assert matches[0]["id"] == "2"


def test_llm_evaluate_returns_structured_result():
    mock_client = MagicMock()

    tool_result = {
        "relevant": True,
        "score": 0.85,
        "reason": "Strong EM match",
        "key_requirements": ["team leadership"],
        "interview_talking_points": ["scaling teams"],
    }
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.type = "tool_use"
    mock_content.input = tool_result
    mock_response.content = [mock_content]
    mock_response.stop_reason = "tool_use"
    mock_client.messages.create.return_value = mock_response

    config = Config()
    config.anthropic_api_key = "test-key"
    result = llm_evaluate(
        job={
            "title": "EM",
            "company": "Dropbox",
            "description": "Lead team",
            "location": "Remote",
            "salary": "200k",
        },
        resume_summary="Experienced EM with 10 years...",
        config=config,
        client=mock_client,
    )
    assert result["relevant"] is True
    assert result["score"] == 0.85


def _seed_match(db, job_id, location, remote=False):
    db.upsert_job(
        id=job_id,
        company="Stripe",
        title="Engineering Manager",
        url=f"https://example.com/{job_id}",
        location=location,
        remote=remote,
        scraped_at=datetime.now(timezone.utc),
    )
    db.commit()
    db.insert_match(job_id=job_id, relevance_score=0.9, match_reason="strong")


def test_prune_dismisses_unacceptable_location_match(db):
    config = Config()
    _seed_match(db, "Stripe:nyc", "New York, NY")
    _seed_match(db, "Stripe:blr", "Bengaluru")
    pruned = prune_stale_matches(db, config)
    assert pruned == 1
    active_ids = {m["job_id"] for m in db.get_active_matches()}
    assert "Stripe:nyc" in active_ids  # acceptable match kept
    assert "Stripe:blr" not in active_ids  # offshore match dismissed


def test_prune_keeps_remote_match(db):
    config = Config()
    # Unacceptable city string but flagged remote -> acceptable, must survive.
    _seed_match(db, "Stripe:rem", "Bengaluru", remote=True)
    pruned = prune_stale_matches(db, config)
    assert pruned == 0
    assert "Stripe:rem" in {m["job_id"] for m in db.get_active_matches()}


def test_prune_noop_on_empty_db(db):
    assert prune_stale_matches(db, Config()) == 0
