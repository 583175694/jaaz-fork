import sqlite3
import json
import os
import re
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
import aiosqlite
from .config_service import USER_DATA_DIR
from .migrations.manager import MigrationManager, CURRENT_VERSION

DB_PATH = os.path.join(USER_DATA_DIR, "localmanus.db")
CANVAS_FILE_URL_ID_PATTERN = re.compile(r"/api/file/((?:im_|vi_)[^/?#.)]+)")
MARKDOWN_IMAGE_URL_PATTERN = re.compile(r"(!\[[^\]]*]\()([^)]+)(\))")

class DatabaseService:
    def __init__(self):
        self.db_path = DB_PATH
        self._ensure_db_directory()
        self._migration_manager = MigrationManager()
        self._init_db()

    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _init_db(self):
        """Initialize the database with the current schema"""
        with sqlite3.connect(self.db_path) as conn:
            # Create version table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            # Get current version
            cursor = conn.execute("SELECT version FROM db_version")
            current_version = cursor.fetchone()
            print('local db version', current_version, 'latest version', CURRENT_VERSION)
            
            if current_version is None:
                # First time setup - start from version 0
                conn.execute("INSERT INTO db_version (version) VALUES (0)")
                self._migration_manager.migrate(conn, 0, CURRENT_VERSION)
            elif current_version[0] < CURRENT_VERSION:
                print('Migrating database from version', current_version[0], 'to', CURRENT_VERSION)
                # Need to migrate
                self._migration_manager.migrate(conn, current_version[0], CURRENT_VERSION)

    async def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO canvases (id, name)
                VALUES (?, ?)
            """, (id, name))
            await db.commit()

    async def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, name, description, thumbnail, created_at, updated_at
                FROM canvases
                ORDER BY updated_at DESC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO chat_sessions (id, model, provider, canvas_id, title)
                VALUES (?, ?, ?, ?, ?)
            """, (id, model, provider, canvas_id, title))
            await db.commit()

    async def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO chat_messages (session_id, role, message)
                VALUES (?, ?, ?)
            """, (session_id, role, message))
            await db.commit()

    async def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            session_cursor = await db.execute("""
                SELECT canvas_id
                FROM chat_sessions
                WHERE id = ?
            """, (session_id,))
            session_row = await session_cursor.fetchone()
            canvas_data: Dict[str, Any] = {}
            if session_row and session_row["canvas_id"]:
                canvas_cursor = await db.execute("""
                    SELECT data
                    FROM canvases
                    WHERE id = ?
                """, (session_row["canvas_id"],))
                canvas_row = await canvas_cursor.fetchone()
                if canvas_row and canvas_row["data"]:
                    try:
                        canvas_data = json.loads(canvas_row["data"])
                    except Exception:
                        canvas_data = {}

            cursor = await db.execute("""
                SELECT role, message, id
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))
            rows = await cursor.fetchall()
            
            messages = []
            for row in rows:
                row_dict = dict(row)
                if row_dict['message']:
                    try:
                        msg = json.loads(row_dict['message'])
                        msg = self._normalize_message_asset_urls(msg, canvas_data)
                        messages.append(msg)
                    except:
                        pass
                
            return messages

    def _normalize_message_asset_urls(
        self,
        message: Dict[str, Any],
        canvas_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
        if not isinstance(files, dict) or not files:
            return message

        file_url_lookup = self._build_canvas_file_url_lookup(files)
        content = message.get("content")
        if not isinstance(content, list):
            return message

        updated = False
        normalized_content: List[Any] = []
        for item in content:
            if not isinstance(item, dict):
                normalized_content.append(item)
                continue

            if item.get("type") == "image_url":
                image_url = item.get("image_url", {})
                url = image_url.get("url", "") if isinstance(image_url, dict) else ""
                resolved_url = self._resolve_canvas_asset_url(url, file_url_lookup)
                if resolved_url and resolved_url != url:
                    normalized_content.append({
                        **item,
                        "image_url": {
                            **image_url,
                            "url": resolved_url,
                        },
                    })
                    updated = True
                else:
                    normalized_content.append(item)
                continue

            if item.get("type") != "text":
                normalized_content.append(item)
                continue

            text = item.get("text", "")
            if not isinstance(text, str) or "/api/file/" not in text:
                normalized_content.append(item)
                continue

            normalized_text = self._normalize_markdown_asset_urls(text, file_url_lookup)
            if normalized_text == text:
                normalized_content.append(item)
                continue

            normalized_content.append({
                **item,
                "text": normalized_text,
            })
            updated = True

        if not updated:
            return message

        return {
            **message,
            "content": normalized_content,
        }

    def _build_canvas_file_url_lookup(self, files: Dict[str, Any]) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for file_id, file_value in files.items():
            if not isinstance(file_value, dict):
                continue
            resolved_url = file_value.get("dataURL", "")
            if not isinstance(resolved_url, str) or not resolved_url.strip():
                continue
            resolved_url = resolved_url.strip()
            lookup[file_id] = resolved_url
            lookup[f"/api/file/{file_id}"] = resolved_url
            lookup[self._strip_origin(f"/api/file/{file_id}")] = resolved_url
        return lookup

    def _strip_origin(self, url: str) -> str:
        try:
            parsed = urlparse(url)
        except Exception:
            return url.strip()

        if not parsed.scheme or not parsed.netloc:
            return url.strip()

        path = parsed.path or ""
        if parsed.query:
            path = f"{path}?{parsed.query}"
        if parsed.fragment:
            path = f"{path}#{parsed.fragment}"
        return path.strip()

    def _resolve_canvas_asset_url(
        self,
        url: Any,
        file_url_lookup: Dict[str, str],
    ) -> Optional[str]:
        if not isinstance(url, str):
            return None
        normalized_url = url.strip()
        if not normalized_url:
            return None

        direct = file_url_lookup.get(normalized_url)
        if direct:
            return direct

        originless = self._strip_origin(normalized_url)
        direct_originless = file_url_lookup.get(originless)
        if direct_originless:
            return direct_originless

        match = CANVAS_FILE_URL_ID_PATTERN.search(normalized_url)
        if not match:
            return None

        return file_url_lookup.get(match.group(1))

    def _normalize_markdown_asset_urls(
        self,
        text: str,
        file_url_lookup: Dict[str, str],
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            original_url = match.group(2)
            resolved_url = self._resolve_canvas_asset_url(original_url, file_url_lookup)
            if not resolved_url:
                return match.group(0)
            return f"{match.group(1)}{resolved_url}{match.group(3)}"

        return MARKDOWN_IMAGE_URL_PATTERN.sub(replace, text)

    async def list_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """List all chat sessions"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            if canvas_id:
                cursor = await db.execute("""
                    SELECT id, title, model, provider, created_at, updated_at
                    FROM chat_sessions
                    WHERE canvas_id = ?
                    ORDER BY updated_at DESC
                """, (canvas_id,))
            else:
                cursor = await db.execute("""
                    SELECT id, title, model, provider, created_at, updated_at
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a single chat session metadata record"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, title, model, provider, canvas_id, created_at, updated_at
                FROM chat_sessions
                WHERE id = ?
            """, (session_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE canvases 
                SET data = ?, thumbnail = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
            """, (data, thumbnail, id))

            if cursor.rowcount == 0:
                print("⚠️ save_canvas_data missing canvas row, creating fallback canvas record", {
                    "canvas_id": id,
                })
                await db.execute("""
                    INSERT INTO canvases (id, name, data, thumbnail)
                    VALUES (?, ?, ?, ?)
                """, (id, "未命名", data, thumbnail))
            await db.commit()

    async def get_canvas_data(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas data"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT data, name
                FROM canvases
                WHERE id = ?
            """, (id,))
            row = await cursor.fetchone()

            sessions = await self.list_sessions(id)
            
            if row:
                return {
                    'data': json.loads(row['data']) if row['data'] else {},
                    'name': row['name'],
                    'sessions': sessions
                }
            return None

    async def delete_canvas(self, id: str):
        """Delete canvas and related data"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM canvases WHERE id = ?", (id,))
            await db.commit()

    async def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE canvases SET name = ? WHERE id = ?", (name, id))
            await db.commit()

    async def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO comfy_workflows (name, api_json, description, inputs, outputs)
                VALUES (?, ?, ?, ?, ?)
            """, (name, api_json, description, inputs, outputs))
            await db.commit()

    async def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT id, name, description, api_json, inputs, outputs FROM comfy_workflows ORDER BY id DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM comfy_workflows WHERE id = ?", (id,))
            await db.commit()

    async def get_comfy_workflow(self, id: int):
        """Get comfy workflow dict"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT api_json FROM comfy_workflows WHERE id = ?", (id,)
            )
            row = await cursor.fetchone()
        try:
            workflow_json = (
                row["api_json"]
                if isinstance(row["api_json"], dict)
                else json.loads(row["api_json"])
            )
            return workflow_json
        except json.JSONDecodeError as exc:
            raise ValueError(f"Stored workflow api_json is not valid JSON: {exc}")

    async def create_generation_job(
        self,
        *,
        id: str,
        type: str,
        session_id: str,
        canvas_id: str,
        status: str,
        provider: str,
        request_payload: str,
        provider_task_id: Optional[str] = None,
        result_payload: Optional[str] = None,
        error_message: Optional[str] = None,
        progress: Optional[int] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO generation_jobs (
                    id, type, session_id, canvas_id, status, provider,
                    provider_task_id, request_payload, result_payload,
                    error_message, progress, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id,
                    type,
                    session_id,
                    canvas_id,
                    status,
                    provider,
                    provider_task_id,
                    request_payload,
                    result_payload,
                    error_message,
                    progress,
                    started_at,
                    finished_at,
                ),
            )
            await db.commit()

    async def get_generation_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT id, type, session_id, canvas_id, status, provider,
                       provider_task_id, request_payload, result_payload,
                       error_message, progress, created_at, updated_at,
                       started_at, finished_at
                FROM generation_jobs
                WHERE id = ?
                """,
                (job_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_generation_job(
        self,
        job_id: str,
        **fields: Any,
    ) -> None:
        if not fields:
            return

        allowed_fields = {
            "status",
            "provider_task_id",
            "result_payload",
            "error_message",
            "progress",
            "started_at",
            "finished_at",
            "request_payload",
        }
        updates: List[str] = []
        params: List[Any] = []
        for key, value in fields.items():
            if key not in allowed_fields:
                continue
            updates.append(f"{key} = ?")
            params.append(value)

        if not updates:
            return

        updates.append("updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')")
        params.append(job_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"""
                UPDATE generation_jobs
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                tuple(params),
            )
            await db.commit()

    async def list_generation_jobs(
        self,
        *,
        canvas_id: Optional[str] = None,
        session_id: Optional[str] = None,
        type: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT id, type, session_id, canvas_id, status, provider,
                   provider_task_id, request_payload, result_payload,
                   error_message, progress, created_at, updated_at,
                   started_at, finished_at
            FROM generation_jobs
        """
        conditions: List[str] = []
        params: List[Any] = []

        if canvas_id:
            conditions.append("canvas_id = ?")
            params.append(canvas_id)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if type:
            conditions.append("type = ?")
            params.append(type)
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            conditions.append(f"status IN ({placeholders})")
            params.extend(statuses)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def find_active_generation_job(
        self,
        *,
        session_id: str,
        canvas_id: str,
        type: str,
        request_payload: str,
    ) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT id, type, session_id, canvas_id, status, provider,
                       provider_task_id, request_payload, result_payload,
                       error_message, progress, created_at, updated_at,
                       started_at, finished_at
                FROM generation_jobs
                WHERE session_id = ?
                  AND canvas_id = ?
                  AND type = ?
                  AND request_payload = ?
                  AND status IN ('queued', 'running')
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (session_id, canvas_id, type, request_payload),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_recoverable_generation_jobs(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT id, type, session_id, canvas_id, status, provider,
                       provider_task_id, request_payload, result_payload,
                       error_message, progress, created_at, updated_at,
                       started_at, finished_at
                FROM generation_jobs
                WHERE status IN ('queued', 'running')
                ORDER BY created_at ASC, id ASC
                """
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

# Create a singleton instance
db_service = DatabaseService()
