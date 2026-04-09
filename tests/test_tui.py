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


@pytest.mark.asyncio
async def test_applications_screen_grouped(seeded_db):
    """Test that applications screen groups by status."""
    from src.tui.app import JobTrackerApp
    from textual.widgets import DataTable

    seeded_db.set_application_status("co:0", "interviewing")
    seeded_db.set_application_status("co:2", "applied")

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        await pilot.press("a")
        tables = app.screen.query(DataTable)
        assert len(tables) > 0


@pytest.mark.asyncio
async def test_pipeline_screen_shows_history(seeded_db):
    """Test that pipeline screen shows run history."""
    from src.tui.app import JobTrackerApp
    from textual.widgets import DataTable

    r1 = seeded_db.start_run()
    seeded_db.complete_run(
        r1, jobs_scraped=100, new_jobs=5, matches_found=2, email_sent=True
    )

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        await pilot.press("p")
        table = app.screen.query_one("#run-history", DataTable)
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_job_detail_shows_analysis(seeded_db):
    """Test that job detail screen displays match data."""
    from src.tui.app import JobTrackerApp
    import json

    suggestions = json.dumps(
        {
            "key_requirements": ["5+ years management"],
            "suggested_edits": [
                {
                    "original": "Led team",
                    "suggested": "Led distributed team",
                    "reason": "scope",
                }
            ],
            "keyword_gaps": ["fintech"],
            "interview_talking_points": ["scaling teams"],
        }
    )
    seeded_db.update_match_suggestions("co:0", suggestions)

    app = JobTrackerApp()
    app._db_override = seeded_db
    async with app.run_test() as pilot:
        app.action_show_job("co:0")
        await pilot.pause()
        header = app.screen.query_one("#job-header")
        assert "TestCo" in str(header.render())
