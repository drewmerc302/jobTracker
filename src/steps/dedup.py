import logging
import re
from datetime import datetime

from src.db import Database

logger = logging.getLogger(__name__)

_SENIORITY_WORDS = {
    "senior",
    "sr",
    "junior",
    "jr",
    "staff",
    "principal",
    "lead",
    "associate",
}
_ROMAN = re.compile(r"\s+\b(i{1,3}|iv|vi{0,3}|ix)\b$", re.IGNORECASE)
_PUNCT = re.compile(r"[,\-./\\()\[\]]")
_WHITESPACE = re.compile(r"\s+")

_STATUS_RANK = {
    "interviewing": 5,
    "offer": 4,
    "applied": 3,
    "new": 2,
    "rejected": 1,
    "withdrawn": 0,
}


def _normalize_title(title: str) -> str:
    title = _ROMAN.sub("", title)
    title = _PUNCT.sub(" ", title)
    words = title.lower().split()
    words = [w for w in words if w.rstrip(".") not in _SENIORITY_WORDS]
    return _WHITESPACE.sub(" ", " ".join(words)).strip()


def _score_job(job: dict) -> int:
    score = 0
    if job.get("salary"):
        score += 2
    desc = job.get("description") or ""
    if len(desc) > 500:
        score += 2
    if job.get("location"):
        score += 1
    if job.get("department"):
        score += 1
    return score


def _pick_canonical(jobs: list[dict]) -> tuple[dict, list[dict]]:
    ranked = sorted(
        jobs,
        key=lambda j: (_score_job(j), -_parse_ts(j["first_seen_at"])),
        reverse=True,
    )
    return ranked[0], ranked[1:]


def _parse_ts(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _merge_group(db: Database, canonical: dict, duplicates: list[dict]) -> int:
    """Merge duplicate jobs into canonical. Returns number removed."""
    removed = 0
    for dup in duplicates:
        cid = canonical["id"]
        did = dup["id"]
        try:
            with db._conn:  # transaction per group
                _merge_matches(db, cid, did)
                _merge_applications(db, cid, did)
                _merge_status_history(db, cid, did)
                db._conn.execute("DELETE FROM jobs WHERE id = ?", (did,))
            removed += 1
            logger.info(f"Dedup: merged {did} -> {cid}")
        except Exception as e:
            logger.warning(f"Dedup: failed to merge {did} -> {cid}: {e}")
    return removed


def _merge_matches(db: Database, canonical_id: str, dup_id: str):
    canonical_match = db.get_match(canonical_id)
    dup_match = db.get_match(dup_id)
    if canonical_match and dup_match:
        # Keep higher score; delete loser first to avoid PK conflict
        if dup_match["relevance_score"] > canonical_match["relevance_score"]:
            db._conn.execute("DELETE FROM matches WHERE job_id = ?", (canonical_id,))
            db._conn.execute(
                "UPDATE matches SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id)
            )
        else:
            db._conn.execute("DELETE FROM matches WHERE job_id = ?", (dup_id,))
    elif dup_match:
        db._conn.execute(
            "UPDATE matches SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id)
        )


def _merge_applications(db: Database, canonical_id: str, dup_id: str):
    canonical_app = db.get_application(canonical_id)
    dup_app = db.get_application(dup_id)
    if canonical_app and dup_app:
        c_rank = _STATUS_RANK.get(canonical_app["status"], 0)
        d_rank = _STATUS_RANK.get(dup_app["status"], 0)
        if d_rank > c_rank:
            # dup has better status — delete canonical, re-point dup
            db._conn.execute(
                "DELETE FROM applications WHERE job_id = ?", (canonical_id,)
            )
            db._conn.execute(
                "UPDATE applications SET job_id = ? WHERE job_id = ?",
                (canonical_id, dup_id),
            )
        else:
            db._conn.execute("DELETE FROM applications WHERE job_id = ?", (dup_id,))
    elif dup_app:
        db._conn.execute(
            "UPDATE applications SET job_id = ? WHERE job_id = ?",
            (canonical_id, dup_id),
        )


def _merge_status_history(db: Database, canonical_id: str, dup_id: str):
    db._conn.execute(
        "UPDATE status_history SET job_id = ? WHERE job_id = ?", (canonical_id, dup_id)
    )
    # Drop exact duplicate history rows (same old_status + new_status + changed_at)
    db._conn.execute(
        """
        DELETE FROM status_history
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM status_history
            WHERE job_id = ?
            GROUP BY old_status, new_status, changed_at
        )
        AND job_id = ?
    """,
        (canonical_id, canonical_id),
    )


def run_dedup(db: Database) -> tuple[int, int]:
    """Find and merge duplicate jobs. Returns (groups_merged, records_removed)."""
    rows = db._conn.execute(
        "SELECT id, company, title, description, salary, location, department, first_seen_at FROM jobs"
    ).fetchall()

    # Group by (company, normalized_title)
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        job = dict(row)
        key = (job["company"], _normalize_title(job["title"]))
        groups.setdefault(key, []).append(job)

    total_merged = 0
    total_removed = 0
    for key, jobs in groups.items():
        if len(jobs) < 2:
            continue
        canonical, duplicates = _pick_canonical(jobs)
        removed = _merge_group(db, canonical, duplicates)
        if removed:
            total_merged += 1
            total_removed += removed

    if total_merged:
        logger.info(
            f"Dedup: {total_merged} duplicate groups found, {total_removed} records removed"
        )
    return total_merged, total_removed
