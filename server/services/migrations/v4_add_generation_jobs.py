from . import Migration
import sqlite3


class V4AddGenerationJobs(Migration):
    version = 4
    description = "Add generation jobs"

    def up(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                session_id TEXT NOT NULL,
                canvas_id TEXT NOT NULL,
                status TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_task_id TEXT,
                request_payload TEXT NOT NULL,
                result_payload TEXT,
                error_message TEXT,
                progress INTEGER,
                created_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                started_at TEXT,
                finished_at TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_generation_jobs_canvas_created_at
            ON generation_jobs(canvas_id, created_at DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_generation_jobs_session_created_at
            ON generation_jobs(session_id, created_at DESC)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_generation_jobs_status_updated_at
            ON generation_jobs(status, updated_at DESC)
        """)

    def down(self, conn: sqlite3.Connection) -> None:
        pass
