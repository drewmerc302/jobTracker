import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                location TEXT,
                remote BOOLEAN,
                salary TEXT,
                description TEXT,
                department TEXT,
                seniority TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                closed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS matches (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id),
                relevance_score REAL NOT NULL,
                match_reason TEXT NOT NULL,
                resume_path TEXT,
                cover_letter_path TEXT,
                suggestions TEXT,
                matched_at TEXT NOT NULL,
                notified_at TEXT
            );
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                jobs_scraped INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                matches_found INTEGER DEFAULT 0,
                email_sent BOOLEAN DEFAULT 0,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS applications (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id),
                status TEXT NOT NULL,
                applied_date TEXT,
                salary_notes TEXT,
                status_updated_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                old_status TEXT,
                new_status TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );
        """)

    def upsert_job(
        self,
        *,
        id: str,
        company: str,
        title: str,
        url: str,
        scraped_at: datetime,
        location: str = None,
        remote: bool = None,
        salary: str = None,
        description: str = None,
        department: str = None,
        seniority: str = None,
    ):
        now = scraped_at.isoformat()
        self._conn.execute(
            """
            INSERT INTO jobs (id, company, title, url, location, remote, salary,
                            description, department, seniority, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                description = COALESCE(excluded.description, jobs.description),
                salary = COALESCE(excluded.salary, jobs.salary),
                location = COALESCE(excluded.location, jobs.location),
                closed_at = NULL
        """,
            (
                id,
                company,
                title,
                url,
                location,
                remote,
                salary,
                description,
                department,
                seniority,
                now,
                now,
            ),
        )
        self._conn.commit()

    def get_job(self, job_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_new_job_ids(self, candidate_ids: list[str]) -> list[str]:
        existing = set()
        for i in range(0, len(candidate_ids), 500):
            batch = candidate_ids[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            rows = self._conn.execute(
                f"SELECT id FROM jobs WHERE id IN ({placeholders})", batch
            ).fetchall()
            existing.update(r["id"] for r in rows)
        return [cid for cid in candidate_ids if cid not in existing]

    def close_missing_jobs(self, company: str, current_ids: list[str]):
        now = datetime.now(timezone.utc).isoformat()
        if not current_ids:
            self._conn.execute(
                "UPDATE jobs SET closed_at = ? WHERE company = ? AND closed_at IS NULL",
                (now, company),
            )
        else:
            placeholders = ",".join("?" * len(current_ids))
            self._conn.execute(
                f"""UPDATE jobs SET closed_at = ?
                    WHERE company = ? AND closed_at IS NULL
                    AND id NOT IN ({placeholders})""",
                [now, company] + current_ids,
            )
        self._conn.commit()

    def insert_match(
        self,
        *,
        job_id: str,
        relevance_score: float,
        match_reason: str,
        suggestions: str = None,
        resume_path: str = None,
        cover_letter_path: str = None,
    ):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO matches
            (job_id, relevance_score, match_reason, suggestions, resume_path,
             cover_letter_path, matched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                job_id,
                relevance_score,
                match_reason,
                suggestions,
                resume_path,
                cover_letter_path,
                now,
            ),
        )
        self._conn.commit()

    def update_match_paths(
        self, job_id: str, *, resume_path: str = None, cover_letter_path: str = None
    ):
        updates = []
        params = []
        if resume_path:
            updates.append("resume_path = ?")
            params.append(resume_path)
        if cover_letter_path:
            updates.append("cover_letter_path = ?")
            params.append(cover_letter_path)
        if updates:
            params.append(job_id)
            self._conn.execute(
                f"UPDATE matches SET {', '.join(updates)} WHERE job_id = ?", params
            )
            self._conn.commit()

    def update_match_suggestions(self, job_id: str, suggestions: str):
        self._conn.execute(
            "UPDATE matches SET suggestions = ? WHERE job_id = ?", (suggestions, job_id)
        )
        self._conn.commit()

    def get_match(self, job_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM matches WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_unnotified_matches(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT m.*, j.company, j.title, j.url, j.location, j.salary, j.description
            FROM matches m JOIN jobs j ON m.job_id = j.id
            WHERE m.notified_at IS NULL
            ORDER BY m.relevance_score DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def mark_notified(self, job_ids: list[str]):
        now = datetime.now(timezone.utc).isoformat()
        for job_id in job_ids:
            self._conn.execute(
                "UPDATE matches SET notified_at = ? WHERE job_id = ?", (now, job_id)
            )
        self._conn.commit()

    def start_run(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute("INSERT INTO runs (started_at) VALUES (?)", (now,))
        self._conn.commit()
        return cursor.lastrowid

    def complete_run(
        self,
        run_id: int,
        *,
        jobs_scraped: int,
        new_jobs: int,
        matches_found: int,
        email_sent: bool,
        error: str = None,
    ):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            UPDATE runs SET completed_at = ?, jobs_scraped = ?, new_jobs = ?,
                           matches_found = ?, email_sent = ?, error = ?
            WHERE id = ?
        """,
            (now, jobs_scraped, new_jobs, matches_found, email_sent, error, run_id),
        )
        self._conn.commit()

    def get_run(self, run_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_last_failed_run_with_matches(self) -> dict | None:
        row = self._conn.execute("""
            SELECT * FROM runs
            WHERE matches_found > 0 AND email_sent = 0
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        return dict(row) if row else None

    def set_application_status(self, job_id: str, status: str):
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_application(job_id)
        old_status = existing["status"] if existing else None

        if existing:
            updates = {"status": status, "status_updated_at": now}
            if status == "applied" and not existing.get("applied_date"):
                updates["applied_date"] = now
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            self._conn.execute(
                f"UPDATE applications SET {set_clause} WHERE job_id = ?",
                list(updates.values()) + [job_id],
            )
        else:
            applied_date = now if status == "applied" else None
            self._conn.execute(
                "INSERT INTO applications (job_id, status, applied_date, status_updated_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, status, applied_date, now, now),
            )

        self._conn.execute(
            "INSERT INTO status_history (job_id, old_status, new_status, changed_at) VALUES (?, ?, ?, ?)",
            (job_id, old_status, status, now),
        )
        self._conn.commit()

    def get_application(self, job_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_status_history(self, job_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM status_history WHERE job_id = ? ORDER BY id", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_applications(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT m.job_id, j.company, j.title, j.url, j.location, m.relevance_score,
                   COALESCE(a.status, 'new') as status,
                   a.applied_date, a.status_updated_at, a.salary_notes,
                   m.matched_at, m.resume_path, m.cover_letter_path
            FROM matches m
            JOIN jobs j ON m.job_id = j.id
            LEFT JOIN applications a ON m.job_id = a.job_id
            ORDER BY
                CASE COALESCE(a.status, 'new')
                    WHEN 'interviewing' THEN 1
                    WHEN 'offer' THEN 2
                    WHEN 'applied' THEN 3
                    WHEN 'new' THEN 4
                    WHEN 'rejected' THEN 5
                    WHEN 'withdrawn' THEN 6
                END,
                m.relevance_score DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def update_salary_notes(self, job_id: str, notes: str):
        self._conn.execute(
            "UPDATE applications SET salary_notes = ? WHERE job_id = ?", (notes, job_id)
        )
        self._conn.commit()
