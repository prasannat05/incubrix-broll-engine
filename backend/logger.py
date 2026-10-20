import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "job_id"):
            payload["job_id"] = getattr(record, "job_id")
        if hasattr(record, "step"):
            payload["step"] = getattr(record, "step")
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_job_logger(job_id: str, job_dir: Path) -> logging.Logger:
    """Create or retrieve a structured logger that writes to stdout and jobs/{job_id}/logs.txt."""
    logger_name = f"broll_engine.job.{job_id}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        formatter = StructuredFormatter()

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        job_dir.mkdir(parents=True, exist_ok=True)
        log_file = job_dir / "logs.txt"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_step(logger: logging.Logger, job_id: str, step: str, message: str, level: int = logging.INFO) -> None:
    logger.log(level, message, extra={"job_id": job_id, "step": step})
