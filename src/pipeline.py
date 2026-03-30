import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.config import Config
from src.db import Database
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.workday import WorkdayScraper
from src.steps.scrape import run_scrape
from src.steps.filter import run_filter
from src.steps.tailor import get_active_resume_yaml, run_tailor_for_job
from src.steps.notify import run_notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Job Tracker Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run scrape + filter only, skip tailor + notify")
    parser.add_argument("--renotify", action="store_true",
                        help="Re-send last failed email digest")
    parser.add_argument("--step", choices=["scrape", "filter", "tailor", "notify"],
                        help="Run a single step")
    parser.add_argument("--tailor-job", metavar="JOB_ID",
                        help="Generate resume + cover letter for a specific job (e.g. 'Stripe:7609424')")
    parser.add_argument("--list-matches", action="store_true",
                        help="List all matched jobs with their IDs and scores")
    return parser.parse_args(argv)


def build_scrapers(config: Config) -> list:
    scrapers = []
    for slug, name in config.greenhouse_boards.items():
        scrapers.append(GreenhouseScraper(board_slug=slug, company_name=name))
    for key, info in config.workday_companies.items():
        scrapers.append(WorkdayScraper(
            company_name=info["display_name"],
            base_url=info["base_url"],
            path=info["path"],
        ))
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

    if args.list_matches:
        rows = db._conn.execute("""
            SELECT m.job_id, j.company, j.title, m.relevance_score,
                   CASE WHEN m.resume_path IS NOT NULL THEN 'yes' ELSE 'no' END as has_pdf
            FROM matches m JOIN jobs j ON m.job_id = j.id
            ORDER BY m.relevance_score DESC
        """).fetchall()
        if not rows:
            print("No matches found.")
            return
        print(f"{'ID':<25} {'Company':<15} {'Title':<45} {'Score':>5} {'PDF':>3}")
        print("-" * 97)
        for r in rows:
            print(f"{r[0]:<25} {r[1]:<15} {r[2]:<45} {r[3]:>5.0%} {r[4]:>3}")
        return

    if args.tailor_job:
        job_id = args.tailor_job
        job = db.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}. Use --list-matches to see available IDs.")
            return
        match = db.get_match(job_id)
        if not match:
            logger.error(f"No match record for {job_id}. Run the filter step first.")
            return
        resume_yaml_path, resume_data = get_active_resume_yaml(config)
        evaluation = json.loads(match.get("suggestions") or "{}")
        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        output_dir = config.output_dir / run_date
        result = run_tailor_for_job(
            job=dict(job), evaluation=evaluation,
            resume_yaml_path=resume_yaml_path, resume_data=resume_data,
            output_dir=output_dir, config=config, db=db,
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
        run_stats = {"jobs_scraped": 0, "new_jobs": 0, "matches_found": 0,
                     "duration": "renotify"}
        success = run_notify(db, run_stats, config)
        logger.info(f"Renotify {'succeeded' if success else 'failed'}")
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
            logger.info(f"Scrape complete: {scrape_result['jobs_scraped']} jobs, {scrape_result['new_jobs']} new")
            if args.step == "scrape":
                db.complete_run(run_id, jobs_scraped=scrape_result["jobs_scraped"],
                               new_jobs=scrape_result["new_jobs"], matches_found=0, email_sent=False)
                return
        else:
            scrape_result = {"jobs_scraped": 0, "new_jobs": 0, "new_job_ids": [], "failed_companies": []}

        # Step 2: Filter
        if not args.step or args.step == "filter":
            new_job_ids = scrape_result["new_job_ids"]
            if args.step == "filter" and not new_job_ids:
                rows = db._conn.execute(
                    "SELECT id FROM jobs WHERE id NOT IN (SELECT job_id FROM matches) AND closed_at IS NULL"
                ).fetchall()
                new_job_ids = [r["id"] for r in rows]
                logger.info(f"Filter standalone: found {len(new_job_ids)} unfiltered jobs in DB")
            matches = run_filter(db, new_job_ids, resume_summary, config)
            logger.info(f"Filter complete: {len(matches)} matches")
            if args.step == "filter":
                db.complete_run(run_id, jobs_scraped=0, new_jobs=0,
                               matches_found=len(matches), email_sent=False)
                return
        else:
            matches = []

        if args.dry_run:
            logger.info("Dry run -- skipping tailor and notify")
            db.complete_run(run_id, jobs_scraped=scrape_result["jobs_scraped"],
                           new_jobs=scrape_result["new_jobs"],
                           matches_found=len(matches), email_sent=False)
            return

        # Step 3: Tailor
        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        output_dir = config.output_dir / run_date
        if not args.step or args.step == "tailor":
            if args.step == "tailor" and not matches:
                unnotified = db.get_unnotified_matches()
                matches = [{"job": dict(m), "evaluation": json.loads(m.get("suggestions") or "{}")}
                           for m in unnotified if not m.get("resume_path")]
                logger.info(f"Tailor standalone: found {len(matches)} untailored matches")
            for match in matches:
                try:
                    run_tailor_for_job(
                        job=match["job"], evaluation=match["evaluation"],
                        resume_yaml_path=resume_yaml_path, resume_data=resume_data,
                        output_dir=output_dir, config=config, db=db,
                    )
                except Exception as e:
                    logger.error(f"Tailor failed for {match['job']['id']}: {e}")
            if args.step == "tailor":
                db.complete_run(run_id, jobs_scraped=0, new_jobs=0,
                               matches_found=len(matches), email_sent=False)
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

        db.complete_run(run_id, jobs_scraped=scrape_result["jobs_scraped"],
                       new_jobs=scrape_result["new_jobs"],
                       matches_found=len(matches), email_sent=email_sent)
        logger.info(f"Pipeline complete in {duration}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        db.complete_run(run_id, jobs_scraped=0, new_jobs=0,
                       matches_found=0, email_sent=False, error=str(e))
        raise


def main():
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
