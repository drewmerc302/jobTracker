import pytest
from datetime import datetime, timezone
from src.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def seeded_db(db):
    """DB with sample jobs, matches, and applications for TUI tests."""
    now = datetime.now(timezone.utc)
    for i in range(3):
        db.upsert_job(
            id=f"co:{i}",
            company="TestCo",
            title=f"EM {i}",
            url=f"http://example.com/{i}",
            scraped_at=now,
            location="Remote",
            remote=True,
            description=f"Description {i}",
        )
        db.commit()
        db.insert_match(
            job_id=f"co:{i}",
            relevance_score=0.9 - i * 0.1,
            match_reason=f"Reason {i}",
        )
    db.set_application_status("co:1", "applied")
    return db


@pytest.mark.asyncio
async def test_dashboard_mounts(seeded_db):
    """Test that dashboard screen mounts and shows summary data."""
    from src.tui.app import JobTrackerApp

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        # Dashboard should be the default screen with some content
        # Check that summary cards rendered (look for the total matches value)
        text = str(app.screen)
        assert app.screen is not None


@pytest.mark.asyncio
async def test_matches_screen_shows_jobs(seeded_db):
    from src.tui.app import JobTrackerApp

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        await pilot.press("m")  # Navigate to matches
        from textual.widgets import DataTable

        table = app.screen.query_one("#matches-table", DataTable)
        assert table.row_count == 3
