"""Generate SVG screenshots of TUI screens for README documentation.

Usage: uv run python scripts/generate_screenshots.py
"""

import json
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.db import Database

SCREENSHOT_DIR = Path(__file__).parent.parent / "docs" / "screenshots"
DB_PATH = Path("/tmp/jobtracker_screenshot.db")


def seed_database() -> Database:
    """Create a realistic demo database for screenshots."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    db = Database(DB_PATH)
    now = datetime.now(timezone.utc)

    companies = [
        (
            "Acme Corp",
            "Engineering Manager, Platform Services",
            "Remote / New York",
            "$123,456",
            0.92,
        ),
        (
            "Acme Corp",
            "AI/ML Engineering Manager, Data Platform",
            "Remote / New York",
            "$123,456",
            0.92,
        ),
        (
            "Acme Corp",
            "Engineering Manager, Developer Experience",
            "Remote / New York",
            "$123,456",
            0.92,
        ),
        (
            "Acme Corp",
            "Engineering Manager, Commerce Platform",
            "Remote / New York",
            "$123,456",
            0.92,
        ),
        ("Initech", "Engineering Manager, AI Governance", "Remote", "$123,456", 0.92),
        (
            "Globex",
            "Senior Engineering Manager, ML Infrastructure",
            "Remote / Bay Area",
            "$123,456",
            0.92,
        ),
        (
            "Hooli",
            "Engineering Manager, Observability",
            "NYC / Remote",
            "$123,456",
            0.88,
        ),
        (
            "Pied Piper",
            "Engineering Manager, Core Infrastructure",
            "Remote / Seattle",
            "$123,456",
            0.85,
        ),
        (
            "Umbrella Co",
            "Sr Manager, Software Engineering",
            "Arlington, VA",
            "$123,456",
            0.82,
        ),
        ("Stark Ind", "Engineering Program Manager, ML", "Cupertino, CA", None, 0.80),
        ("Wayne Ent", "Engineering Manager, Cloud AI", "NYC", "$123,456", 0.78),
        ("Initech", "Manager, Source Code Management", "Remote", "$123,456", 0.76),
        ("Globex", "EM, Studio Technology", "Remote / LA", "$123,456", 0.74),
        ("Acme Corp", "EM, Developer Productivity", "Remote", "$123,456", 0.72),
        ("Hooli", "Engineering Manager, Infrastructure", "NYC", "$123,456", 0.70),
        ("Umbrella Co", "Manager, Cloud Engineering", "Richmond, VA", "$123,456", 0.68),
        ("Pied Piper", "Engineering Manager, Security", "Remote", "$123,456", 0.66),
        ("Stark Ind", "Software Engineering Manager, AI", "Cupertino, CA", None, 0.64),
    ]

    for i, (company, title, location, salary, score) in enumerate(companies):
        ext_id = f"{1000 + i}"
        job_id = f"{company}:{ext_id}"
        seen = now - timedelta(days=i)
        db.upsert_job(
            id=job_id,
            company=company,
            title=title,
            url=f"https://jobs.example.com/{ext_id}",
            scraped_at=seen,
            location=location,
            remote="Remote" in (location or ""),
            salary=salary,
            description=f"We're looking for a {title} to join our team.",
        )
        db.commit()

        suggestions = json.dumps(
            {
                "key_requirements": [
                    "5+ years managing engineering teams",
                    "Experience scaling teams from 5→20+ engineers",
                    "Track record of shipping distributed systems",
                ],
                "suggested_edits": [
                    {
                        "original": "Led platform team",
                        "suggested": f"Led platform team focused on {title.split(',')[-1].strip().lower()}",
                        "reason": "Domain alignment",
                    },
                    {
                        "original": "Managed 12 engineers",
                        "suggested": "Scaled team from 4 to 16 engineers across 3 squads",
                        "reason": "Growth narrative",
                    },
                ],
                "keyword_gaps": ["fintech", "PCI compliance"],
                "interview_talking_points": [
                    "Team scaling experience",
                    "Cross-functional leadership",
                ],
            }
        )
        db.insert_match(
            job_id=job_id,
            relevance_score=score,
            match_reason=f"Strong alignment with {title.lower()} requirements.",
            suggestions=suggestions,
        )

    # Application statuses
    db.set_application_status("Acme Corp:1000", "applied")
    db.set_follow_up_date(
        "Acme Corp:1000", (now - timedelta(days=3)).strftime("%Y-%m-%d")
    )
    db.set_application_status("Globex:1005", "applied")
    db.set_application_status("Umbrella Co:1008", "interviewing")
    db.set_follow_up_date(
        "Umbrella Co:1008", (now - timedelta(days=1)).strftime("%Y-%m-%d")
    )

    # Run history
    for days_ago in [0, 0.5, 1, 1.5, 2]:
        rid = db.start_run()
        db.complete_run(
            rid,
            jobs_scraped=2200 + int(days_ago * 20),
            new_jobs=12 + int(days_ago * 3),
            matches_found=2 if days_ago < 1 else 0,
            email_sent=True,
        )

    return db


async def capture_screen(
    db: Database,
    screen_name: str,
    filename: str,
    press_keys: list[str] | None = None,
    show_job: str | None = None,
):
    """Launch app, navigate to screen, export SVG."""
    from src.tui.app import JobTrackerApp

    app = JobTrackerApp()
    app._db_override = db

    async with app.run_test(size=(120, 35)) as pilot:
        if press_keys:
            for key in press_keys:
                await pilot.press(key)
                await pilot.pause()
        if show_job:
            app.action_show_job(show_job)
            await pilot.pause()
        await pilot.pause()

        svg = app.export_screenshot()
        path = SCREENSHOT_DIR / filename
        path.write_text(svg)
        print(f"  Saved: {path}")


async def main():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    db = seed_database()

    print("Generating screenshots...")
    await capture_screen(db, "dashboard", "dashboard.svg")
    await capture_screen(db, "matches", "matches.svg", press_keys=["m"])
    await capture_screen(db, "job_detail", "job-detail.svg", show_job="Acme Corp:1000")
    await capture_screen(db, "applications", "applications.svg", press_keys=["a"])
    await capture_screen(db, "pipeline", "pipeline.svg", press_keys=["p"])
    print("Done!")

    # Cleanup
    DB_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
