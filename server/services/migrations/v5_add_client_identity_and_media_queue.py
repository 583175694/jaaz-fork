from . import Migration
import sqlite3


class V5AddClientIdentityAndMediaQueue(Migration):
    version = 5
    description = "Add client identity and media queue fields"

    def up(self, conn: sqlite3.Connection) -> None:
        canvas_columns = [row[1] for row in conn.execute("PRAGMA table_info(canvases)").fetchall()]
        if "client_id" not in canvas_columns:
            conn.execute("ALTER TABLE canvases ADD COLUMN client_id TEXT")

        chat_session_columns = [row[1] for row in conn.execute("PRAGMA table_info(chat_sessions)").fetchall()]
        if "client_id" not in chat_session_columns:
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN client_id TEXT")

        generation_job_columns = [
            row[1] for row in conn.execute("PRAGMA table_info(generation_jobs)").fetchall()
        ]
        if "client_id" not in generation_job_columns:
            conn.execute("ALTER TABLE generation_jobs ADD COLUMN client_id TEXT")
        if "summary_text" not in generation_job_columns:
            conn.execute("ALTER TABLE generation_jobs ADD COLUMN summary_text TEXT")

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_canvases_client_updated_at
            ON canvases(client_id, updated_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_client_updated_at
            ON chat_sessions(client_id, updated_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_jobs_client_status_created_at
            ON generation_jobs(client_id, status, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_jobs_client_created_at
            ON generation_jobs(client_id, created_at ASC, id ASC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_jobs_client_canvas_created_at
            ON generation_jobs(client_id, canvas_id, created_at DESC)
            """
        )

    def down(self, conn: sqlite3.Connection) -> None:
        pass
