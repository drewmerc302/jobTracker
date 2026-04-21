from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.db import Database
from src.steps.interview_prep import (
    generate_interview_prep,
    _generate_typst,
    _escape_typst,
)


def _make_db(tmp_path, job_id="stripe:1"):
    db = Database(tmp_path / "test.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id=job_id,
        company="Stripe",
        title="EM, Platform",
        url="https://stripe.com/jobs/1",
        description="We need an EM to lead Platform engineering...",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id=job_id, relevance_score=0.9, match_reason="good match")
    return db


def test_escape_typst_replaces_special_chars():
    assert _escape_typst("hello#world") == "hello\\#world"
    assert _escape_typst("a*b_c") == "a\\*b\\_c"


def test_generate_typst_contains_sections():
    prep = {
        "talking_points": ["Cross-functional leadership"],
        "red_flags": ["Limited ML experience"],
        "likely_questions": ["Tell me about ambiguity"],
        "star_stories": [
            {
                "question": "Ambiguity question",
                "resume_bullet": "Led migration",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            }
        ],
    }
    job = {"company": "Stripe", "title": "EM, Platform"}
    typst = _generate_typst(prep, job)
    assert "Stripe" in typst
    assert "Key Talking Points" in typst
    assert "Gaps to Prepare For" in typst
    assert "STAR Stories" in typst
    assert "Cross-functional leadership" in typst


def test_generate_interview_prep_calls_llm_and_returns_path(tmp_path):
    db = _make_db(tmp_path)
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {
        "likely_questions": ["Tell me about a time you dealt with ambiguity"],
        "star_stories": [
            {
                "question": "Tell me about ambiguity",
                "resume_bullet": "Led platform migration",
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            }
        ],
        "talking_points": ["Deep platform experience"],
        "red_flags": ["Limited ML experience"],
    }
    mock_response.content = [mock_tool_use]

    fake_pdf = tmp_path / "Stripe_stripe_1_interview_prep.pdf"
    fake_pdf.touch()

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
            "src.steps.interview_prep._generate_pdf",
            return_value=fake_pdf,
        ) as mock_gen_pdf,
    ):
        MockAnthropic.return_value.messages.create.return_value = mock_response
        result = generate_interview_prep(db, "stripe:1")

    assert mock_gen_pdf.called
    assert result == fake_pdf


def test_generate_interview_prep_handles_missing_job(tmp_path):
    db = _make_db(tmp_path)
    result = generate_interview_prep(db, "nonexistent:999")
    assert result is None


def test_generate_interview_prep_handles_llm_failure(tmp_path):
    db = _make_db(tmp_path)
    with (
        patch("src.steps.interview_prep.anthropic.Anthropic") as MockAnthropic,
        patch(
            "src.steps.interview_prep.get_active_resume_yaml",
            return_value=(tmp_path / "r.yaml", {}),
        ),
    ):
        mock_response = MagicMock()
        mock_response.content = []
        MockAnthropic.return_value.messages.create.return_value = mock_response
        result = generate_interview_prep(db, "stripe:1")
    assert result is None


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
            side_effect=lambda *a, **k: prep_calls.append(a) or None,
        ),
    ):
        MockConfig.return_value.db_path = tmp_path / "test4.db"
        args = parse_args(["--status", "stripe:20", "interviewing"])
        run_pipeline(args)

    assert len(prep_calls) == 1


def test_status_interviewing_prep_failure_does_not_block_obsidian(tmp_path):
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
        run_pipeline(args)

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
            side_effect=lambda *a, **k: prep_calls.append(a) or None,
        ),
    ):
        MockConfig.return_value.db_path = tmp_path / "test5.db"
        args = parse_args(["--interview-prep", "stripe:21"])
        run_pipeline(args)

    assert len(prep_calls) == 1
