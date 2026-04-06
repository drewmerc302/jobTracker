import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.db import Database
from src.steps.gripes import _format_gripes_markdown, _format_gripes_plain, get_gripes

SAMPLE_GRIPES = {
    "tldr": [
        "Slow promotion cycles",
        "High on-call burden",
        "Poor work-life balance",
        "Opaque management decisions",
        "Frequent reorgs",
    ],
    "themes": [
        {
            "name": "Work-life balance",
            "summary": "Long hours are normalized.",
            "detail": "Many employees report 60+ hour weeks during launches. On-call rotations are frequent with limited relief.",
        }
    ],
}


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def config():
    cfg = MagicMock(spec=Config)
    cfg.llm_filter_model = "claude-haiku-4-5-20251001"
    return cfg


def test_get_company_gripes_returns_none_when_missing(db):
    assert db.get_company_gripes("Stripe") is None


def test_upsert_and_get_company_gripes(db):
    gripes = {
        "tldr": ["Slow promo cycles", "High on-call burden"],
        "themes": [{"name": "WLB", "summary": "Bad", "detail": "Very bad."}],
    }
    db.upsert_company_gripes("Stripe", gripes)
    result, _ = db.get_company_gripes("Stripe")
    assert result is not None
    assert result["tldr"][0] == "Slow promo cycles"
    assert result["themes"][0]["name"] == "WLB"


def test_upsert_company_gripes_overwrites_existing(db):
    db.upsert_company_gripes("Stripe", {"tldr": ["v1"], "themes": []})
    db.upsert_company_gripes("Stripe", {"tldr": ["v2"], "themes": []})
    result, _ = db.get_company_gripes("Stripe")
    assert result["tldr"] == ["v2"]


def test_upsert_company_gripes_sets_fetched_at(db):
    db.upsert_company_gripes("Stripe", {"tldr": [], "themes": []})
    row = db._conn.execute(
        "SELECT fetched_at FROM company_gripes WHERE company = ?", ("Stripe",)
    ).fetchone()
    assert row is not None
    dt = datetime.fromisoformat(row["fetched_at"])
    assert dt.tzinfo is not None  # must be timezone-aware UTC string


def test_get_gripes_returns_cached_when_fresh(db, config):
    """Cache hit: no web search or LLM called."""
    db.upsert_company_gripes("Stripe", SAMPLE_GRIPES)
    with (
        patch("src.steps.gripes._web_search") as mock_search,
        patch("src.steps.gripes._call_llm") as mock_llm,
    ):
        result = get_gripes(db, "Stripe", config)
    mock_search.assert_not_called()
    mock_llm.assert_not_called()
    assert result["tldr"][0] == "Slow promotion cycles"


def test_get_gripes_fetches_when_cache_missing(db, config):
    """Cache miss: web search + LLM called, result cached."""
    with (
        patch("src.steps.gripes._web_search", return_value="some review text"),
        patch("src.steps.gripes._call_llm", return_value=SAMPLE_GRIPES),
    ):
        result = get_gripes(db, "Stripe", config)
    assert result["tldr"][0] == "Slow promotion cycles"
    # Verify it was cached
    cached, _ = db.get_company_gripes("Stripe")
    assert cached["tldr"][0] == "Slow promotion cycles"


def test_get_gripes_fetches_when_cache_expired(db, config):
    """Stale cache (>30 days): re-fetch."""
    old_date = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    db._conn.execute(
        "INSERT INTO company_gripes (company, gripes_json, fetched_at) VALUES (?, ?, ?)",
        ("Stripe", json.dumps({"tldr": ["old"], "themes": []}), old_date),
    )
    db._conn.commit()
    with (
        patch("src.steps.gripes._web_search", return_value="fresh text"),
        patch("src.steps.gripes._call_llm", return_value=SAMPLE_GRIPES),
    ):
        result = get_gripes(db, "Stripe", config)
    assert result["tldr"][0] == "Slow promotion cycles"


def test_get_gripes_returns_none_on_llm_failure(db, config):
    """LLM failure: return None, do not cache."""
    with (
        patch("src.steps.gripes._web_search", return_value="text"),
        patch("src.steps.gripes._call_llm", return_value=None),
    ):
        result = get_gripes(db, "Stripe", config)
    assert result is None
    assert db.get_company_gripes("Stripe") is None


def test_get_gripes_handles_naive_fetched_at(db, config):
    """Naive datetime in DB (no tzinfo) should not crash the TTL check."""
    import json

    naive_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")  # no timezone info
    db._conn.execute(
        "INSERT INTO company_gripes (company, gripes_json, fetched_at) VALUES (?, ?, ?)",
        ("Stripe", json.dumps(SAMPLE_GRIPES), naive_ts),
    )
    db._conn.commit()
    with (
        patch("src.steps.gripes._web_search") as mock_search,
        patch("src.steps.gripes._call_llm") as mock_llm,
    ):
        result = get_gripes(db, "Stripe", config)
    assert result is not None
    mock_search.assert_not_called()


def test_format_gripes_plain_includes_tldr_and_themes():
    output = _format_gripes_plain(SAMPLE_GRIPES, "Stripe")
    assert "Stripe" in output
    assert "Slow promotion cycles" in output
    assert "Work-life balance" in output
    assert "Long hours are normalized" in output


def test_format_gripes_markdown_structure():
    output = _format_gripes_markdown(SAMPLE_GRIPES, "Stripe")
    assert "## Employee Gripes" in output
    assert "**TL;DR**" in output
    assert "### Work-life balance" in output
    assert "*Long hours are normalized.*" in output


from src.pipeline import parse_args, run_pipeline


@pytest.fixture
def pipeline_db(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now(timezone.utc)
    db.upsert_job(
        id="stripe:1",
        company="Stripe",
        title="EM, Platform",
        url="https://stripe.com/jobs/1",
        description="Lead Platform engineering",
        scraped_at=now,
    )
    db.commit()
    db.insert_match(job_id="stripe:1", relevance_score=0.9, match_reason="good match")
    return db


def test_gripes_flag_parses():
    args = parse_args(["--show-job", "stripe:1", "--gripes"])
    assert args.gripes is True


def test_show_job_without_gripes_does_not_call_get_gripes(
    pipeline_db, capsys, tmp_path
):
    with (
        patch("src.pipeline.Database", return_value=pipeline_db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.pipeline.get_gripes") as mock_gripes,
    ):
        MockConfig.return_value.db_path = tmp_path / "test.db"
        args = parse_args(["--show-job", "stripe:1"])
        run_pipeline(args)
    mock_gripes.assert_not_called()


def test_show_job_with_gripes_prints_gripes(pipeline_db, capsys, tmp_path):
    with (
        patch("src.pipeline.Database", return_value=pipeline_db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.pipeline.get_gripes", return_value=SAMPLE_GRIPES),
    ):
        MockConfig.return_value.db_path = tmp_path / "test.db"
        args = parse_args(["--show-job", "stripe:1", "--gripes"])
        run_pipeline(args)
    out = capsys.readouterr().out
    assert "Slow promotion cycles" in out
    assert "Work-life balance" in out


def test_show_job_with_gripes_none_prints_fallback(pipeline_db, capsys, tmp_path):
    with (
        patch("src.pipeline.Database", return_value=pipeline_db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.pipeline.get_gripes", return_value=None),
    ):
        MockConfig.return_value.db_path = tmp_path / "test.db"
        args = parse_args(["--show-job", "stripe:1", "--gripes"])
        run_pipeline(args)
    out = capsys.readouterr().out
    assert "Could not fetch gripes" in out


def test_show_job_with_gripes_markdown(pipeline_db, capsys, tmp_path):
    with (
        patch("src.pipeline.Database", return_value=pipeline_db),
        patch("src.pipeline.Config") as MockConfig,
        patch("src.pipeline.get_gripes", return_value=SAMPLE_GRIPES),
    ):
        MockConfig.return_value.db_path = tmp_path / "test.db"
        args = parse_args(["--show-job", "stripe:1", "--gripes", "--markdown"])
        run_pipeline(args)
    out = capsys.readouterr().out
    assert "## Employee Gripes (Stripe)" in out
    assert "**TL;DR**" in out
