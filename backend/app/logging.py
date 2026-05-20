from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from loguru import logger

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.jsonl"
ROTATION = "10 MB"
RETENTION = "7 days"
DEFAULT_LEVEL = "INFO"


class InterceptHandler(logging.Handler):
    """Redirect stdlib logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        frame = logging.currentframe()
        depth = 0
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            record.levelname, record.getMessage()
        )


def _stderr_format(record: dict) -> str:
    """Human-readable coloured format with optional trace_id."""
    trace_id = record["extra"].get("trace_id", "-")
    return (
        f"<green>{record['time']:HH:mm:ss.SSS}</green> | "
        f"<level>{record['level']: <8}</level> | "
        f"<cyan>{trace_id}</cyan> | "
        f"<level>{record['message']}</level>\n"
    )


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", DEFAULT_LEVEL).upper()

    logger.remove()

    # Sink 1: structured JSON to rotating file
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        LOG_FILE,
        serialize=True,
        level=level,
        rotation=ROTATION,
        retention=RETENTION,
        compression="gz",
        enqueue=True,
    )

    # Sink 2: human-readable coloured output to stderr
    logger.add(
        sys.stderr,
        format=_stderr_format,
        level=level,
        colorize=True,
    )

    # Intercept stdlib logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for _name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy",
        "chromadb",
    ):
        _lib_logger = logging.getLogger(_name)
        _lib_logger.handlers = [InterceptHandler()]
        _lib_logger.propagate = False
