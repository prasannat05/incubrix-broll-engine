import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from backend.config import settings
from backend.models import InputType, JobStatus


class JobRepository:
    """Thread-safe SQLite repository for tracking video generation jobs."""

    def __init__(self, db_path: Path = settings.database_path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    current_step TEXT NOT NULL,
                    input_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT
                )
                """
            )
            conn.commit()

    def create_job(self, job_id: str, input_type: InputType) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, status, progress, current_step, input_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, JobStatus.QUEUED.value, 0, "Job queued", input_type.value, now, now),
            )
            conn.commit()
        return self.get_job(job_id)  # type: ignore[return-value]

    def update_job(
        self,
        job_id: str,
        *,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [datetime.now(timezone.utc).isoformat()]

        if status is not None:
            fields.append("status = ?")
            values.append(status.value)
        if progress is not None:
            fields.append("progress = ?")
            values.append(progress)
        if current_step is not None:
            fields.append("current_step = ?")
            values.append(current_step)
        if error_code is not None:
            fields.append("error_code = ?")
            values.append(error_code)
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)

        values.append(job_id)
        query = f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?"
        with self._lock, self._get_conn() as conn:
            conn.execute(query, tuple(values))
            conn.commit()

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._get_conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return dict(row) if row else None


job_repo = JobRepository()
