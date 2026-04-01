import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.db import Database
from src.steps.interview_prep import generate_interview_prep, _patch_obsidian_section


@pytest.fixture
def db(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:1",
        company="Stripe",
        title="EM, Platform",
        url="https://stripe.com/jobs/1",
        description="We need an EM to lead Platform engineering...",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="good match")
    return db


def test_patch_obsidian_section_replaces_with_blank_line_separator():
    """Standard markdown has blank lines between sections."""
    note = "# Title\n\n## Some Section\ncontent\n\n## Interview Prep\nold content\n\n## Notes\nmore"
    result = _patch_obsidian_section(note, "## Interview Prep", "new content")
    assert "old content" not in result
    assert "new content" in result
    assert "## Notes\nmore" in result


def test_patch_obsidian_section_appends_if_missing():
    note = "# Title\n\n## Notes\ncontent"
    result = _patch_obsidian_section(note, "## Interview Prep", "new content")
    assert "## Interview Prep" in result
    assert "new content" in result


def test_generate_interview_prep_calls_llm(db, tmp_path):
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {
        "likely_questions": ["Tell me about a time you dealt with ambiguity"],
        "star_stories": [
            {
                "question": "Tell me about a time you dealt with ambiguity",
                "resume_bullet": "Led platform migration",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            }
        ],
        "talking_points": ["Deep platform experience", "Cross-functional leadership"],
        "red_flags": ["Limited ML experience"],
    }
    mock_response.content = [mock_tool_use]
    mock_response.stop_reason = "tool_use"

    fake_resume = {
        "experience": [
            {"company": "Acme", "title": "EM", "bullets": ["Led platform migration"]}
        ]
    }

    with (
        patch("src.steps.interview_prep.anthropic.Anthropic") as MockAnthropic,
        patch(
            "src.steps.interview_prep.get_active_resume_yaml",
            return_value=(tmp_path / "r.yaml", fake_resume),
        ),
        patch(
            "src.steps.interview_prep._read_obsidian_note",
            return_value="# Stripe — EM, Platform\n\n## Interview Prep\n\n## Notes\n",
        ),
        patch("src.steps.interview_prep._write_obsidian_note") as mock_write,
    ):
        MockAnthropic.return_value.messages.create.return_value = mock_response
        generate_interview_prep(db, "stripe:1")
        assert mock_write.called
        written_content = mock_write.call_args[0][1]
        assert "Tell me about a time" in written_content
        assert "Deep platform experience" in written_content


def test_generate_interview_prep_handles_missing_job(db):
    """Should not raise if job not found."""
    generate_interview_prep(db, "nonexistent:999")  # should not raise


def test_generate_interview_prep_handles_llm_failure(db, tmp_path):
    """Should log error and return cleanly when LLM call fails."""
    fake_resume = {}
    with (
        patch("src.steps.interview_prep.anthropic.Anthropic") as MockAnthropic,
        patch(
            "src.steps.interview_prep.get_active_resume_yaml",
            return_value=(tmp_path / "r.yaml", fake_resume),
        ),
    ):
        # LLM returns no tool_use block → _call_llm raises ValueError
        mock_response = MagicMock()
        mock_response.content = []  # no tool_use block
        MockAnthropic.return_value.messages.create.return_value = mock_response
        # Should not raise
        generate_interview_prep(db, "stripe:1")


def test_status_interviewing_triggers_prep(tmp_path):
    from src.pipeline import parse_args, run_pipeline

    db = Database(tmp_path / "test4.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:20",
        company="Stripe",
        title="EM",
        url="https://x.com",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:20", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:20", "applied")

    prep_calls = []
    with (
        patch("src.pipeline.Database", return_value=db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.steps.obsidian.write_application_note"),
        patch("src.steps.obsidian.write_dashboard"),
        patch(
            "src.pipeline.generate_interview_prep",
            side_effect=lambda *a, **k: prep_calls.append(a),
        ),
    ):
        MockConfig.return_value.db_path = tmp_path / "test4.db"
        args = parse_args(["--status", "stripe:20", "interviewing"])
        run_pipeline(args)

    assert len(prep_calls) == 1


def test_status_interviewing_prep_failure_does_not_block_obsidian(tmp_path):
    """If generate_interview_prep raises, --status handler still completes Obsidian writes."""
    from src.pipeline import parse_args, run_pipeline

    db = Database(tmp_path / "test6.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:22",
        company="Stripe",
        title="EM",
        url="https://x.com",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:22", relevance_score=0.9, match_reason="good")
    db.set_application_status("stripe:22", "applied")

    with (
        patch("src.pipeline.Database", return_value=db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.steps.obsidian.write_application_note") as mock_obsidian,
        patch("src.steps.obsidian.write_dashboard"),
        patch(
            "src.pipeline.generate_interview_prep", side_effect=RuntimeError("LLM down")
        ),
    ):
        MockConfig.return_value.db_path = tmp_path / "test6.db"
        args = parse_args(["--status", "stripe:22", "interviewing"])
        run_pipeline(args)  # should not raise

    # Obsidian write must still have been called despite interview prep failure
    assert mock_obsidian.called


def test_interview_prep_command(tmp_path):
    from src.pipeline import parse_args, run_pipeline

    db = Database(tmp_path / "test5.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:21",
        company="Stripe",
        title="EM",
        url="https://x.com",
        scraped_at=now,
    )
    db.commit()

    prep_calls = []
    with (
        patch("src.pipeline.Database", return_value=db),
        patch("src.pipeline.Config") as MockConfig,
        patch(
            "src.pipeline.generate_interview_prep",
            side_effect=lambda *a, **k: prep_calls.append(a),
        ),
    ):
        MockConfig.return_value.db_path = tmp_path / "test5.db"
        args = parse_args(["--interview-prep", "stripe:21"])
        run_pipeline(args)

    assert len(prep_calls) == 1
