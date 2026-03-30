import pytest

from src.config import Config
from src.db import Database
from src.steps.obsidian import (
    render_application_note,
    render_dashboard,
    sanitize_filename,
)


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_sanitize_filename():
    assert (
        sanitize_filename("Stripe — Engineering Manager: Payments/Billing")
        == "Stripe — Engineering Manager Payments Billing"
    )
    assert len(sanitize_filename("A" * 100)) <= 80


def test_render_application_note():
    html = render_application_note(
        company="Stripe",
        title="Engineering Manager, Agentic Commerce",
        status="applied",
        score="92%",
        url="https://stripe.com/jobs/search?gh_jid=7334661",
        job_id="Stripe:7334661",
        applied_date="2026-03-31",
        status_updated_at="2026-03-31",
        salary_notes="",
        match_reason="Strong match",
        key_requirements=["team leadership", "payments"],
        config=Config(),
    )
    assert "Stripe" in html
    assert "applied" in html.lower()
    assert "team leadership" in html


def test_render_application_note_no_match():
    html = render_application_note(
        company="Stripe",
        title="EM",
        status="applied",
        score="N/A",
        url="https://example.com",
        job_id="Stripe:999",
        applied_date="2026-03-31",
        status_updated_at="2026-03-31",
        salary_notes="",
        match_reason=None,
        key_requirements=[],
        config=Config(),
    )
    assert "tracked directly" in html


def test_render_dashboard():
    apps = [
        {
            "company": "Stripe",
            "title": "EM1",
            "relevance_score": 0.92,
            "status": "applied",
            "applied_date": "2026-03-31",
            "status_updated_at": "2026-03-31",
            "job_id": "Stripe:1",
        },
        {
            "company": "DataDog",
            "title": "EM2",
            "relevance_score": 0.62,
            "status": "new",
            "applied_date": None,
            "status_updated_at": None,
            "matched_at": "2026-03-30",
            "job_id": "DataDog:2",
        },
    ]
    html = render_dashboard(apps, Config())
    assert "Applied" in html
    assert "New" in html
    assert "Stripe" in html
