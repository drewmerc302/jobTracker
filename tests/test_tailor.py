import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.config import Config
from src.steps.tailor import reorder_resume_yaml, llm_resume_analysis


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
