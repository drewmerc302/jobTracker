import argparse
import json
import logging
import time
from datetime import datetime, timedelta, timezone


from src.config import Config
from src.db import Database
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.workday import WorkdayScraper
from src.steps.scrape import run_scrape
from src.steps.filter import run_filter
from src.steps.tailor import get_active_resume_yaml, run_tailor_for_job
from src.steps.notify import run_notify
from src.steps.dedup import run_dedup
from src.steps.interview_prep import generate_interview_prep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _compute_follow_up_date(applied_date_str: str | None, days: int = 7) -> str:
    """Compute a follow-up date string (YYYY-MM-DD) from an applied_date and offset."""
    base = applied_date_str or datetime.now(timezone.utc).isoformat()
    try:
        base_dt = datetime.fromisoformat(base.replace("Z", "+00:00"))
    except ValueError:
        base_dt = datetime.now(timezone.utc)
    return (base_dt + timedelta(days=days)).strftime("%Y-%m-%d")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Job Tracker Pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run scrape + filter only, skip notify",
    )
    parser.add_argument(
        "--renotify", action="store_true", help="Re-send last failed email digest"
    )
    parser.add_argument(
        "--step",
        choices=["scrape", "filter", "tailor", "notify", "dedup"],
        help="Run a single step",
    )
    parser.add_argument(
        "--tailor-job",
        metavar="JOB_ID",
        help="Generate resume + cover letter for a specific job (e.g. 'Stripe:7609424')",
    )
    parser.add_argument(
        "--adopt",
        metavar="NUMS",
        help="Comma-separated edit numbers to apply to the resume (e.g. '1,3,5'). Use with --tailor-job.",
    )
    parser.add_argument(
        "--list-matches",
        action="store_true",
        help="List all matched jobs with their IDs and scores",
    )
    parser.add_argument(
        "--show-job",
        metavar="JOB_ID",
        help="Show match analysis, suggested edits, and keyword gaps for a job",
    )
    parser.add_argument(
        "--status",
        nargs=2,
        metavar=("JOB_ID", "STATUS"),
        help='Set application status (e.g. --status "Stripe:123" applied)',
    )
    parser.add_argument(
        "--track", metavar="JOB_ID", help="Interactive status update with prompts"
    )
    parser.add_argument(
        "--applications", action="store_true", help="Show application status dashboard"
    )
    parser.add_argument(
        "--follow-ups",
        action="store_true",
        help="List applications with overdue follow-up dates",
    )
    parser.add_argument(
        "--followed-up",
        metavar="JOB_ID",
        help="Mark a job as followed up and reset follow-up date",
    )
    parser.add_argument(
        "--set-followup",
        nargs=2,
        metavar=("JOB_ID", "DATE"),
        help='Set follow-up date for a job (e.g. --set-followup "Stripe:123" 2026-05-01)',
    )
    parser.add_argument(
        "--interview-prep",
        metavar="JOB_ID",
        help="Generate interview prep note for a job",
    )
    parser.add_argument(
        "--research",
        action="store_true",
        help="Add web research when generating interview prep (use with --interview-prep)",
    )
    return parser.parse_args(argv)


def build_scrapers(config: Config) -> list:
    from src.scrapers.apple import AppleScraper
    from src.scrapers.google import GoogleScraper

    scrapers = []
    for slug, info in config.greenhouse_boards.items():
        scrapers.append(
            GreenhouseScraper(
                board_slug=slug,
                company_name=info["display_name"],
                url_template=info.get("url_template"),
            )
        )
    for key, info in config.workday_companies.items():
        scrapers.append(
            WorkdayScraper(
                company_name=info["display_name"],
                base_url=info["base_url"],
                path=info["path"],
                keyword_patterns=config.keyword_patterns,
            )
        )
    scrapers.append(AppleScraper())
    scrapers.append(GoogleScraper())
    return scrapers


def get_resume_summary(resume_data: dict) -> str:
    parts = []
    if summary := resume_data.get("summary"):
        parts.append(summary)
    if skills := resume_data.get("skills"):
        if isinstance(skills, list):
            parts.append("Skills: " + ", ".join(str(s) for s in skills[:15]))
        elif isinstance(skills, dict):
            for cat, items in skills.items():
                if isinstance(items, list):
                    parts.append(f"{cat}: {', '.join(str(i) for i in items[:10])}")
    if experience := resume_data.get("experience"):
        for exp in experience[:3]:
            parts.append(f"{exp.get('title', '')} at {exp.get('company', '')}")
    return "\n".join(parts)


def run_pipeline(args):
    start_time = time.time()
    config = Config()
    db = Database(config.db_path)

    if args.status:
        job_id, new_status = args.status
        valid_statuses = [
            "new",
            "applied",
            "interviewing",
            "offer",
            "rejected",
            "withdrawn",
        ]
        if new_status not in valid_statuses:
            logger.error(
                f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}"
            )
            return
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        db.set_application_status(job_id, new_status)
        print(f"Status updated: {job['company']} — {job['title']} → {new_status}")
        # Auto-set follow-up date for active statuses
        if new_status in ("applied", "interviewing"):
            app = db.get_application(job_id)
            follow_up = _compute_follow_up_date(
                app.get("applied_date") if app else None
            )
            db.set_follow_up_date(job_id, follow_up)
        # Trigger interview prep on interviewing transition
        if new_status == "interviewing":
            try:
                logger.info(f"Generating interview prep for {job_id}...")
                generate_interview_prep(db, job_id)
            except Exception as e:
                logger.warning(f"Interview prep generation failed (non-fatal): {e}")
        from src.steps.obsidian import write_application_note, write_dashboard

        write_application_note(job_id, db, config)
        write_dashboard(db, config)
        return

    if args.track:
        job_id = args.track
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        app = db.get_application(job_id)
        current = app["status"] if app else "new"
        print(f"\n{job['company']} — {job['title']}")
        print(f"Current status: {current}\n")

        valid_statuses = [
            "new",
            "applied",
            "interviewing",
            "offer",
            "rejected",
            "withdrawn",
        ]
        for i, s in enumerate(valid_statuses, 1):
            marker = " ←" if s == current else ""
            print(f"  {i}. {s}{marker}")
        print()

        choice = input("Enter number (or Enter to keep current): ").strip()
        if choice and choice.isdigit() and 1 <= int(choice) <= len(valid_statuses):
            new_status = valid_statuses[int(choice) - 1]
            db.set_application_status(job_id, new_status)
            print(f"Status → {new_status}")
        else:
            new_status = current

        if new_status in ("applied", "interviewing"):
            days_input = input("Follow up in how many days? [7]: ").strip()
            follow_up_days = int(days_input) if days_input.isdigit() else 7
            track_app = db.get_application(job_id)
            follow_up = _compute_follow_up_date(
                track_app.get("applied_date") if track_app else None,
                days=follow_up_days,
            )
            db.set_follow_up_date(job_id, follow_up)
            print(f"Follow-up date set: {follow_up}")

        # Trigger interview prep on interviewing transition
        if new_status == "interviewing":
            try:
                logger.info(f"Generating interview prep for {job_id}...")
                generate_interview_prep(db, job_id)
            except Exception as e:
                logger.warning(f"Interview prep generation failed (non-fatal): {e}")

        salary = input("Salary notes (Enter to skip): ").strip()
        if salary:
            if not app:
                db.set_application_status(job_id, new_status)
            db.update_salary_notes(job_id, salary)
            print("Salary notes saved")

        from src.steps.obsidian import write_application_note, write_dashboard

        write_application_note(job_id, db, config)
        write_dashboard(db, config)

        from src.steps.obsidian import sanitize_filename

        note_name = sanitize_filename(f"{job['company']} — {job['title']}")
        print(f"\nObsidian note: Topics/Job Applications/{note_name}.md")
        return

    if args.applications:
        apps = db.get_all_applications()
        if not apps:
            print("No tracked applications.")
            return
        current_status = None
        for a in apps:
            status = a.get("status", "new")
            if status != current_status:
                count = sum(1 for x in apps if x.get("status", "new") == status)
                print(f"\n{status.upper()} ({count})")
                current_status = status
            score = f"{a['relevance_score']:.0%}" if a.get("relevance_score") else "N/A"
            company = a["company"][:12]
            title = a["title"][:40]
            if a.get("applied_date"):
                date_info = f"applied {a['applied_date'][:10]}"
            elif a.get("matched_at"):
                date_info = f"matched {a['matched_at'][:10]}"
            else:
                date_info = ""
            print(f"  {score:>5}  {company:<12} {title:<40} {date_info}")
        return

    if args.follow_ups:
        overdue = db.get_overdue_follow_ups()
        if not overdue:
            print("No overdue follow-ups.")
            return
        print(
            f"\n{'Company':<14} {'Title':<38} {'Status':<14} {'Applied':<12} {'Overdue':>8}  Follow-up date"
        )
        print("-" * 100)
        for f in overdue:
            applied = (f.get("applied_date") or "")[:10]
            days = int(f.get("days_overdue") or 0)
            print(
                f"  {f['company']:<12} {f['title'][:36]:<38} {f['status']:<14} {applied:<12} {days:>6}d  {f['follow_up_after']}"
            )
        return

    if args.followed_up:
        job_id = args.followed_up
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        db.mark_followed_up(job_id)
        print(
            f"Followed up: {job['company']} — {job['title']}. Next follow-up reset to +7 days if date was set."
        )
        return

    if args.set_followup:
        job_id, date_str = args.set_followup
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        db.set_follow_up_date(job_id, date_str)
        print(f"Follow-up date set: {job['company']} — {job['title']} → {date_str}")
        return

    if args.interview_prep:
        job_id = args.interview_prep
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        research = getattr(args, "research", False)
        logger.info(f"Generating interview prep for {job_id} (research={research})...")
        generate_interview_prep(db, job_id, research=research)
        print(f"Interview prep written to Obsidian: {job['company']} — {job['title']}")
        return

    if args.list_matches:
        rows = db._conn.execute("""
            SELECT m.job_id, j.company, j.title, j.location, m.relevance_score,
                   CASE WHEN m.resume_path IS NOT NULL THEN 'yes' ELSE 'no' END as has_pdf,
                   COALESCE(a.status, 'new') as status
            FROM matches m JOIN jobs j ON m.job_id = j.id
            LEFT JOIN applications a ON m.job_id = a.job_id
            ORDER BY m.relevance_score DESC
        """).fetchall()
        if not rows:
            print("No matches found.")
            return
        print(
            f"{'Score':>5}  {'PDF':>3}  {'Status':<12} {'Company':<12} {'Title':<35} {'Show Command'}"
        )
        print("-" * 115)
        for r in rows:
            job_id, company, title, location, score, has_pdf, status = r
            title_display = title[:33] + ".." if len(title) > 35 else title
            print(
                f'{score:>5.0%}  {has_pdf:>3}  {status:<12} {company:<12} {title_display:<35} uv run jobtracker --show-job "{job_id}"'
            )
        return

    if args.show_job:
        job_id = args.show_job
        job = db.get_job(job_id)
        if not job:
            print(f"Job not found: {job_id}")
            return
        match = db.get_match(job_id)
        if not match:
            print(f"No match record for {job_id}")
            return
        suggestions = json.loads(match.get("suggestions") or "{}")

        print(f"\n{'=' * 70}")
        print(f"{job['company']} — {job['title']}")
        print(f"{'=' * 70}")
        print(f"Location: {job.get('location', 'N/A')}")
        print(f"Salary:   {job.get('salary', 'N/A')}")
        print(f"Score:    {match['relevance_score']:.0%}")
        app = db.get_application(job_id)
        app_status = app["status"] if app else "not tracked"
        app_date = (
            f" ({app['applied_date'][:10]})" if app and app.get("applied_date") else ""
        )
        print(f"Status:   {app_status}{app_date}")
        print(f"URL:      {job.get('url', 'N/A')}")
        print(f"\nWhy this matches:\n  {match['match_reason']}")

        if suggestions.get("key_requirements"):
            print("\nKey requirements:")
            for req in suggestions["key_requirements"]:
                print(f"  - {req}")

        if suggestions.get("interview_talking_points"):
            print("\nInterview talking points:")
            for tp in suggestions["interview_talking_points"]:
                print(f"  - {tp}")

        edits = suggestions.get("suggested_edits", [])
        if edits:
            print("\nSuggested resume edits:")
            for i, edit in enumerate(edits, 1):
                print(f"\n  [{i}] CURRENT:")
                print(f"      {edit['original']}")
                print(f"  [{i}] SUGGESTED:")
                print(f"      {edit['suggested']}")
                print(f"  [{i}] WHY: {edit['reason']}")

        if suggestions.get("keyword_gaps"):
            print(f"\nKeyword gaps: {', '.join(suggestions['keyword_gaps'])}")

        if match.get("resume_path"):
            print(f"\nResume PDF:       {match['resume_path']}")
        if match.get("cover_letter_path"):
            print(f"Cover letter PDF: {match['cover_letter_path']}")

        print("\nGenerate/regenerate PDFs:")
        print(f'  uv run jobtracker --tailor-job "{job_id}"')
        if edits:
            all_nums = ",".join(str(i) for i in range(1, len(edits) + 1))
            print("\nAdopt all suggested edits:")
            print(f'  uv run jobtracker --tailor-job "{job_id}" --adopt {all_nums}')
            print("\nAdopt specific edits (e.g. 1,3,5):")
            print(f'  uv run jobtracker --tailor-job "{job_id}" --adopt 1,3,5')
        return

    if args.tailor_job:
        job_id = args.tailor_job
        job = db.get_job(job_id)
        if not job:
            logger.error(
                f"Job not found: {job_id}. Use --list-matches to see available IDs."
            )
            return
        match = db.get_match(job_id)
        if not match:
            logger.error(f"No match record for {job_id}. Run the filter step first.")
            return
        resume_yaml_path, resume_data = get_active_resume_yaml(config)
        evaluation = json.loads(match.get("suggestions") or "{}")

        # Parse --adopt flag
        adopt_indices = set()
        if args.adopt:
            try:
                adopt_indices = {int(n.strip()) for n in args.adopt.split(",")}
            except ValueError:
                logger.error("--adopt must be comma-separated numbers (e.g. '1,3,5')")
                return

        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        output_dir = config.output_dir / run_date
        result = run_tailor_for_job(
            job=dict(job),
            evaluation=evaluation,
            resume_yaml_path=resume_yaml_path,
            resume_data=resume_data,
            output_dir=output_dir,
            config=config,
            db=db,
            adopt_edits=adopt_indices,
        )
        if result.get("resume_pdf"):
            print(f"Resume PDF:       {result['resume_pdf']}")
        if result.get("cover_letter_pdf"):
            print(f"Cover letter PDF: {result['cover_letter_pdf']}")
        if not result.get("resume_pdf") and not result.get("cover_letter_pdf"):
            print("PDF generation failed. Check logs.")
        return

    if args.renotify:
        logger.info("Re-notify mode: resending last failed digest")
        run_stats = {
            "jobs_scraped": 0,
            "new_jobs": 0,
            "matches_found": 0,
            "duration": "renotify",
        }
        success = run_notify(db, run_stats, config)
        logger.info(f"Renotify {'succeeded' if success else 'failed'}")
        return

    if args.step == "dedup":
        merged, removed = run_dedup(db)
        print(
            f"Dedup complete: {merged} duplicate groups merged, {removed} records removed"
        )
        return

    run_id = db.start_run()

    try:
        # Load resume
        resume_yaml_path, resume_data = get_active_resume_yaml(config)
        resume_summary = get_resume_summary(resume_data)

        # Step 1: Scrape
        if not args.step or args.step == "scrape":
            scrapers = build_scrapers(config)
            scrape_result = run_scrape(db, scrapers)
            logger.info(
                f"Scrape complete: {scrape_result['jobs_scraped']} jobs, {scrape_result['new_jobs']} new"
            )
            run_dedup(db)  # deduplicate after each scrape
            if args.step == "scrape":
                db.complete_run(
                    run_id,
                    jobs_scraped=scrape_result["jobs_scraped"],
                    new_jobs=scrape_result["new_jobs"],
                    matches_found=0,
                    email_sent=False,
                )
                return
        else:
            scrape_result = {
                "jobs_scraped": 0,
                "new_jobs": 0,
                "new_job_ids": [],
                "failed_companies": [],
            }

        # Step 2: Filter
        if not args.step or args.step == "filter":
            new_job_ids = scrape_result["new_job_ids"]
            if args.step == "filter" and not new_job_ids:
                rows = db._conn.execute(
                    "SELECT id FROM jobs WHERE id NOT IN (SELECT job_id FROM matches) AND closed_at IS NULL"
                ).fetchall()
                new_job_ids = [r["id"] for r in rows]
                logger.info(
                    f"Filter standalone: found {len(new_job_ids)} unfiltered jobs in DB"
                )
            matches = run_filter(db, new_job_ids, resume_summary, config)
            logger.info(f"Filter complete: {len(matches)} matches")
            if args.step == "filter":
                db.complete_run(
                    run_id,
                    jobs_scraped=0,
                    new_jobs=0,
                    matches_found=len(matches),
                    email_sent=False,
                )
                return
        else:
            matches = []

        if args.dry_run:
            logger.info("Dry run -- skipping notify")
            db.complete_run(
                run_id,
                jobs_scraped=scrape_result["jobs_scraped"],
                new_jobs=scrape_result["new_jobs"],
                matches_found=len(matches),
                email_sent=False,
            )
            return

        # Step 3: Tailor (standalone only — not run automatically)
        if args.step == "tailor":
            run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
            output_dir = config.output_dir / run_date
            unnotified = db.get_unnotified_matches()
            tailor_matches = [
                {
                    "job": dict(m),
                    "evaluation": json.loads(m.get("suggestions") or "{}"),
                }
                for m in unnotified
                if not m.get("resume_path")
            ]
            logger.info(
                f"Tailor standalone: found {len(tailor_matches)} untailored matches"
            )
            for match in tailor_matches:
                try:
                    run_tailor_for_job(
                        job=match["job"],
                        evaluation=match["evaluation"],
                        resume_yaml_path=resume_yaml_path,
                        resume_data=resume_data,
                        output_dir=output_dir,
                        config=config,
                        db=db,
                    )
                except Exception as e:
                    logger.error(f"Tailor failed for {match['job']['id']}: {e}")
            db.complete_run(
                run_id,
                jobs_scraped=0,
                new_jobs=0,
                matches_found=len(tailor_matches),
                email_sent=False,
            )
            return

        # Step 4: Notify
        duration = f"{time.time() - start_time:.1f}s"
        run_stats = {
            "jobs_scraped": scrape_result["jobs_scraped"],
            "new_jobs": scrape_result["new_jobs"],
            "matches_found": len(matches),
            "duration": duration,
        }
        email_sent = run_notify(db, run_stats, config)

        db.complete_run(
            run_id,
            jobs_scraped=scrape_result["jobs_scraped"],
            new_jobs=scrape_result["new_jobs"],
            matches_found=len(matches),
            email_sent=email_sent,
        )
        logger.info(f"Pipeline complete in {duration}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        db.complete_run(
            run_id,
            jobs_scraped=0,
            new_jobs=0,
            matches_found=0,
            email_sent=False,
            error=str(e),
        )
        raise


def main():
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
