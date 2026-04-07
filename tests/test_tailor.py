import json
from pathlib import Path
from unittest.mock import MagicMock, patch


from src.config import Config
from src.steps.tailor import ensure_analysis, llm_resume_analysis, reorder_resume_yaml


def test_reorder_resume_yaml():
    resume_data = {
        "experience": [
            {
                "company": "Acme Corp",
                "title": "Engineering Manager",
                "bullets": ["bullet_a", "bullet_b", "bullet_c"],
            }
        ]
    }
    reorder_map = {
        "Acme Corp - Engineering Manager": ["bullet_c", "bullet_a", "bullet_b"]
    }
    result = reorder_resume_yaml(resume_data, reorder_map)
    assert result["experience"][0]["bullets"] == ["bullet_c", "bullet_a", "bullet_b"]


def test_reorder_resume_yaml_missing_key():
    resume_data = {
        "experience": [
            {
                "company": "Acme Corp",
                "title": "EM",
                "bullets": ["a", "b"],
            }
        ]
    }
    reorder_map = {"Nonexistent - Role": ["x", "y"]}
    result = reorder_resume_yaml(resume_data, reorder_map)
    assert result["experience"][0]["bullets"] == ["a", "b"]


@patch("src.steps.tailor.anthropic")
def test_llm_analysis_returns_structured_output(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    analysis = {
        "reordered_bullets": {"Acme - EM": ["c", "a", "b"]},
        "suggested_edits": [{"original": "a", "suggested": "a+", "reason": "kw"}],
        "keyword_gaps": ["agile"],
    }
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.type = "tool_use"
    mock_content.input = analysis
    mock_response.content = [mock_content]
    mock_client.messages.create.return_value = mock_response

    config = Config()
    config.anthropic_api_key = "test-key"
    result = llm_resume_analysis("yaml content", "job description", config)
    assert "reordered_bullets" in result
    assert "suggested_edits" in result


def test_ensure_analysis_returns_cached_when_edits_exist():
    """When suggested_edits already exist in DB, return them without LLM call."""
    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    cached_suggestions = {
        "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
        "keyword_gaps": ["agile"],
        "key_requirements": ["Python"],
        "interview_talking_points": ["Led teams"],
    }
    db.get_match.return_value = {"suggestions": json.dumps(cached_suggestions)}

    with patch("src.steps.tailor.llm_resume_analysis") as mock_llm:
        result = ensure_analysis(job, db, config)

    assert result["suggested_edits"] == cached_suggestions["suggested_edits"]
    assert result.get("reordered_bullets") == {}
    mock_llm.assert_not_called()


@patch("src.steps.tailor.llm_resume_analysis")
@patch("src.steps.tailor.get_active_resume_yaml")
def test_ensure_analysis_calls_llm_when_no_edits_cached(mock_get_yaml, mock_llm):
    """When no suggested_edits in DB, call LLM and write results."""
    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    haiku_suggestions = {
        "key_requirements": ["Python"],
        "interview_talking_points": ["Led teams"],
    }
    db.get_match.return_value = {"suggestions": json.dumps(haiku_suggestions)}

    mock_get_yaml.return_value = (Path("/fake/resume.yaml"), {"name": "Drew"})
    mock_llm.return_value = {
        "reordered_bullets": {"Acme - EM": ["c", "a"]},
        "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
        "keyword_gaps": ["agile"],
        "key_requirements": ["React"],
        "interview_talking_points": [],
    }

    result = ensure_analysis(job, db, config)

    mock_llm.assert_called_once()
    db.update_match_suggestions.assert_called_once()
    written = json.loads(db.update_match_suggestions.call_args[0][1])
    assert written["suggested_edits"] == [
        {"original": "a", "suggested": "b", "reason": "kw"}
    ]
    assert written["keyword_gaps"] == ["agile"]
    assert written["interview_talking_points"] == ["Led teams"]  # Haiku fallback
    assert written["key_requirements"] == ["React"]  # Sonnet had value
    assert result["reordered_bullets"] == {"Acme - EM": ["c", "a"]}


@patch("src.steps.tailor.llm_resume_analysis")
@patch("src.steps.tailor.get_active_resume_yaml")
def test_ensure_analysis_force_reruns_even_with_cache(mock_get_yaml, mock_llm):
    """force=True should call LLM even when cached edits exist."""
    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    cached = {
        "suggested_edits": [{"original": "old", "suggested": "old+", "reason": "old"}],
        "key_requirements": ["Python"],
        "interview_talking_points": ["Led teams"],
    }
    db.get_match.return_value = {"suggestions": json.dumps(cached)}

    mock_get_yaml.return_value = (Path("/fake/resume.yaml"), {"name": "Drew"})
    mock_llm.return_value = {
        "reordered_bullets": {},
        "suggested_edits": [{"original": "new", "suggested": "new+", "reason": "new"}],
        "keyword_gaps": [],
        "key_requirements": ["Go"],
        "interview_talking_points": ["Scaled systems"],
    }

    result = ensure_analysis(job, db, config, force=True)

    mock_llm.assert_called_once()
    db.update_match_suggestions.assert_called_once()
    assert result["suggested_edits"] == [
        {"original": "new", "suggested": "new+", "reason": "new"}
    ]


def test_ensure_analysis_skips_llm_when_no_description():
    """Jobs with empty description should not trigger LLM call."""
    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": ""}

    haiku = {"key_requirements": ["Python"], "interview_talking_points": ["Led teams"]}
    db.get_match.return_value = {"suggestions": json.dumps(haiku)}

    result = ensure_analysis(job, db, config)

    assert result["key_requirements"] == ["Python"]
    assert result.get("reordered_bullets") == {}


@patch("src.steps.tailor.llm_resume_analysis")
@patch("src.steps.tailor.get_active_resume_yaml")
def test_ensure_analysis_catches_llm_error(mock_get_yaml, mock_llm):
    """LLM errors should be caught, returning cached suggestions."""
    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    haiku = {"key_requirements": ["Python"], "interview_talking_points": ["Led teams"]}
    db.get_match.return_value = {"suggestions": json.dumps(haiku)}

    mock_get_yaml.return_value = (Path("/fake/resume.yaml"), {"name": "Drew"})
    mock_llm.side_effect = Exception("API timeout")

    result = ensure_analysis(job, db, config)

    assert result["key_requirements"] == ["Python"]
    db.update_match_suggestions.assert_not_called()


@patch("src.steps.tailor.generate_cover_letter_pdf")
@patch("src.steps.tailor.generate_resume_pdf")
@patch("src.steps.tailor.apply_suggested_edits")
@patch("src.steps.tailor.reorder_resume_yaml")
def test_run_tailor_uses_passed_analysis(
    mock_reorder, mock_apply, mock_resume, mock_cover
):
    """run_tailor_for_job should use the analysis dict passed to it, not call LLM."""
    from src.steps.tailor import run_tailor_for_job

    config = MagicMock()
    job = {
        "id": "Stripe:123",
        "company": "Stripe",
        "description": "Build stuff",
        "title": "EM",
    }
    analysis = {
        "reordered_bullets": {"Acme - EM": ["c", "a"]},
        "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
    }

    mock_reorder.return_value = {"experience": []}
    mock_resume.return_value = Path("/out/resume.pdf")
    mock_cover.return_value = Path("/out/cover.pdf")

    result = run_tailor_for_job(
        job=job,
        analysis=analysis,
        resume_yaml_path=Path("/fake/resume.yaml"),
        resume_data={"name": "Drew"},
        output_dir=Path("/tmp/out"),
        config=config,
    )

    mock_reorder.assert_called_once_with({"name": "Drew"}, {"Acme - EM": ["c", "a"]})
    assert result["resume_pdf"] == Path("/out/resume.pdf")
    assert result["analysis"] == analysis
