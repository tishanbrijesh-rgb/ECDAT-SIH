"""Structured JSON logging with request-ID propagation (pure stdlib)."""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from typing import Any


LOG_LEVEL = os.getenv("ECDAT_LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("ECDAT_LOG_DIR", "logs")

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class _JSONFormatter(logging.Formatter):
    """Minimal JSON log formatter — no third-party dependencies."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        request_id = getattr(record, "request_id", "-")
        if request_id:
            data["request_id"] = request_id
        if record.exc_info and record.exc_info[0]:
            data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        if hasattr(record, "extra_data") and record.extra_data:
            data.update(record.extra_data)
        return json.dumps(data, default=str, ensure_ascii=True)


_request_id: ContextVar[str] = ContextVar("ecdat_request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inject the current request ID from thread-local storage."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True

    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        _request_id.set(request_id)

    @classmethod
    def clear_request_id(cls) -> None:
        _request_id.set("-")


def _get_logger(name: str) -> logging.Logger:
    """Return a configured logger that writes JSON to console and rotating file."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        level = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO)
        logger.setLevel(level)

        formatter = _JSONFormatter()
        request_filter = RequestIdFilter()

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        console.setLevel(level)
        console.addFilter(request_filter)
        logger.addHandler(console)

        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            file_handler = RotatingFileHandler(
                os.path.join(LOG_DIR, "ecdat.log"),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            file_handler.addFilter(request_filter)
            logger.addHandler(file_handler)
        except OSError:
            pass  # file logging is best-effort

    logger.propagate = False
    return logger


def get_logger(name: str = "ecdat") -> logging.Logger:
    """Public entry point — returns a structured JSON logger."""
    return _get_logger(name)
