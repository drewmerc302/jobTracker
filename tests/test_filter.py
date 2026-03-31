from unittest.mock import MagicMock


from src.config import Config
from src.steps.filter import keyword_filter, llm_evaluate


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
