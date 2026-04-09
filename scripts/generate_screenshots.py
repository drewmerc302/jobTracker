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
            "Stripe",
            "Engineering Manager, Payments Platform",
            "Remote / San Francisco",
            "$220k–$280k",
            0.92,
        ),
        (
            "Stripe",
            "AI/ML Engineering Manager, Payment Intelligence",
            "Remote / San Francisco",
            "$230k–$290k",
            0.92,
        ),
        (
            "Stripe",
            "Engineering Manager, Agent Experiences",
            "Remote / San Francisco",
            "$220k–$280k",
            0.92,
        ),
        (
            "Stripe",
            "Engineering Manager, Agentic Commerce",
            "Remote / San Francisco",
            "$225k–$285k",
            0.92,
        ),
        (
            "GitLab",
            "Engineering Manager, SSCS: AI Governance",
            "Remote",
            "$185k–$230k",
            0.92,
        ),
        (
            "Netflix",
            "Senior Engineering Manager, Model Inference",
            "Remote / Los Gatos",
            "$250k–$350k",
            0.92,
        ),
        ("DataDog", "Engineering Manager, APM", "NYC / Remote", "$210k–$260k", 0.88),
        (
            "Dropbox",
            "Engineering Manager, Core Infrastructure",
            "Remote / Seattle",
            "$200k–$250k",
            0.85,
        ),
        (
            "Capital One",
            "Sr Manager, Software Engineering",
            "McLean, VA",
            "$195k–$240k",
            0.82,
        ),
        (
            "Apple",
            "Engineering Program Manager, Machine Learning",
            "Cupertino, CA",
            None,
            0.80,
        ),
        ("Google", "Engineering Manager, Cloud AI", "NYC", "$220k–$280k", 0.78),
        ("GitLab", "Manager, Create:Source Code", "Remote", "$180k–$220k", 0.76),
        ("Netflix", "EM, Studio Technology", "Remote / LA", "$240k–$320k", 0.74),
        ("Stripe", "EM, Developer Productivity", "Remote", "$215k–$275k", 0.72),
        ("DataDog", "Engineering Manager, Infrastructure", "NYC", "$205k–$255k", 0.70),
        (
            "Capital One",
            "Manager, Cloud Engineering",
            "Richmond, VA",
            "$180k–$230k",
            0.68,
        ),
        ("Dropbox", "Engineering Manager, Security", "Remote", "$195k–$245k", 0.66),
        ("Apple", "Software Engineering Manager, Siri", "Cupertino, CA", None, 0.64),
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
    db.set_application_status("Stripe:1000", "applied")
    db.set_follow_up_date("Stripe:1000", (now - timedelta(days=3)).strftime("%Y-%m-%d"))
    db.set_application_status("Netflix:1005", "applied")
    db.set_application_status("Capital One:1008", "interviewing")
    db.set_follow_up_date(
        "Capital One:1008", (now - timedelta(days=1)).strftime("%Y-%m-%d")
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
    await capture_screen(db, "job_detail", "job-detail.svg", show_job="Stripe:1000")
    await capture_screen(db, "applications", "applications.svg", press_keys=["a"])
    await capture_screen(db, "pipeline", "pipeline.svg", press_keys=["p"])
    print("Done!")

    # Cleanup
    DB_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
