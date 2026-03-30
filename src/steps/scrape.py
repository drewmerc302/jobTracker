import logging

from src.db import Database
from src.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)


def run_scrape(db: Database, scrapers: list[BaseScraper]) -> dict:
    total_scraped = 0
    all_new_ids = []
    failed_companies = []

    for scraper in scrapers:
        company = scraper.company_name
        logger.info(f"Scraping {company}...")

        try:
            jobs = scraper.fetch_jobs()
        except Exception as e:
            logger.error(f"Failed to scrape {company}: {e}")
            failed_companies.append(company)
            continue

        if not jobs:
            logger.warning(f"No jobs returned from {company}")
            failed_companies.append(company)
            continue

        # Check which jobs are new BEFORE upserting
        candidate_ids = [job.db_id for job in jobs]
        new_ids = db.get_new_job_ids(candidate_ids)

        # Upsert all jobs (updates last_seen_at for existing)
        for job in jobs:
            db.upsert_job(
                id=job.db_id, company=job.company, title=job.title, url=job.url,
                location=job.location, remote=job.remote, salary=job.salary,
                description=job.description, department=job.department,
                seniority=job.seniority, scraped_at=job.scraped_at,
            )

        # Close jobs that disappeared (only for successful scrapers)
        db.close_missing_jobs(company, current_ids=candidate_ids)

        all_new_ids.extend(new_ids)
        total_scraped += len(jobs)
        logger.info(f"{company}: {len(jobs)} total, {len(new_ids)} new")

    return {
        "jobs_scraped": total_scraped,
        "new_jobs": len(all_new_ids),
        "new_job_ids": all_new_ids,
        "failed_companies": failed_companies,
    }
