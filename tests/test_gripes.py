from datetime import datetime

import pytest
from src.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_get_company_gripes_returns_none_when_missing(db):
    assert db.get_company_gripes("Stripe") is None


def test_upsert_and_get_company_gripes(db):
    gripes = {
        "tldr": ["Slow promo cycles", "High on-call burden"],
        "themes": [{"name": "WLB", "summary": "Bad", "detail": "Very bad."}],
    }
    db.upsert_company_gripes("Stripe", gripes)
    result = db.get_company_gripes("Stripe")
    assert result is not None
    assert result["tldr"][0] == "Slow promo cycles"
    assert result["themes"][0]["name"] == "WLB"


def test_upsert_company_gripes_overwrites_existing(db):
    db.upsert_company_gripes("Stripe", {"tldr": ["v1"], "themes": []})
    db.upsert_company_gripes("Stripe", {"tldr": ["v2"], "themes": []})
    result = db.get_company_gripes("Stripe")
    assert result["tldr"] == ["v2"]


def test_upsert_company_gripes_sets_fetched_at(db):
    db.upsert_company_gripes("Stripe", {"tldr": [], "themes": []})
    row = db._conn.execute(
        "SELECT fetched_at FROM company_gripes WHERE company = ?", ("Stripe",)
    ).fetchone()
    assert row is not None
    dt = datetime.fromisoformat(row["fetched_at"])
    assert dt.tzinfo is not None  # must be timezone-aware UTC string
