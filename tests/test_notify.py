import json
from unittest.mock import patch, MagicMock

import pytest

from src.config import Config
from src.steps.notify import build_digest_html, build_no_match_html


def test_build_no_match_html():
    html = build_no_match_html(
        run_stats={"jobs_scraped": 100, "new_jobs": 5, "matches_found": 0, "duration": "45s"},
        config=Config(),
    )
    assert "No new matches" in html
    assert "100" in html


def test_build_digest_html():
    matches = [
        {
            "job_id": "Dropbox:123",
            "company": "Dropbox",
            "title": "Engineering Manager",
            "url": "https://example.com",
            "location": "Remote",
            "salary": "$200k",
            "relevance_score": 0.9,
            "match_reason": "Strong EM fit",
            "suggestions": json.dumps({
                "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
                "keyword_gaps": ["agile"],
                "key_requirements": ["team leadership"],
                "interview_talking_points": ["scaling teams"],
            }),
            "resume_path": "/tmp/resume.pdf",
            "cover_letter_path": "/tmp/cover.pdf",
        }
    ]
    run_stats = {"jobs_scraped": 100, "new_jobs": 5, "matches_found": 1, "duration": "45s"}
    html = build_digest_html(matches, run_stats, Config())
    assert "Engineering Manager" in html
    assert "Dropbox" in html
    assert "Strong EM fit" in html
    assert "team leadership" in html


@patch("src.steps.notify.smtplib.SMTP_SSL")
def test_send_email(mock_smtp_class):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    from src.steps.notify import send_email
    config = Config()
    config.smtp_user = "test@gmail.com"
    config.smtp_password = "testpass"

    send_email(
        subject="Test",
        html_body="<p>Hello</p>",
        attachments=[],
        config=config,
    )
    mock_smtp.send_message.assert_called_once()
