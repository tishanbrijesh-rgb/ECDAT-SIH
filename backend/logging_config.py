"""Structured JSON logging with request-ID propagation (pure stdlib)."""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import traceback
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

LOG_LEVEL = os.getenv("ECDAT_LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("ECDAT_LOG_DIR", "logs")
LOG_FORMAT = os.getenv("ECDAT_LOG_FORMAT", "text").lower()  # "json" or "text"
SLOW_REQUEST_THRESHOLD_S = float(os.getenv("ECDAT_SLOW_REQUEST_THRESHOLD", "5.0"))

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_handler_lock = threading.Lock()
_shared_handlers: tuple[logging.Handler, ...] | None = None


class _TextFormatter(logging.Formatter):
    """Human-readable formatter with request-id context."""

    _BASE_FMT = "%(request_prefix)s%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
    _DATE_FMT = "%Y-%m-%d %H:%M:%S%z"

    def __init__(self) -> None:
        super().__init__(self._BASE_FMT, datefmt=self._DATE_FMT)

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", "-")
        record.request_prefix = f"[req:{request_id[:12]}] " if request_id and request_id != "-" else ""
        return super().format(record)


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


def _build_shared_handlers() -> tuple[logging.Handler, ...]:
    """Create the process-wide console and file handlers once."""
    global _shared_handlers
    if _shared_handlers is not None:
        return _shared_handlers

    with _handler_lock:
        if _shared_handlers is not None:
            return _shared_handlers

        level = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO)
        if LOG_FORMAT == "json":
            formatter: logging.Formatter = _JSONFormatter()
        else:
            formatter = _TextFormatter()
        request_filter = RequestIdFilter()
        handlers: list[logging.Handler] = []

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        console.setLevel(level)
        console.addFilter(request_filter)
        handlers.append(console)

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
            handlers.append(file_handler)
        except OSError:
            pass  # file logging is best-effort

        _shared_handlers = tuple(handlers)
        return _shared_handlers


def _get_logger(name: str) -> logging.Logger:
    """Return a logger backed by process-wide structured-output handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO))
    for handler in _build_shared_handlers():
        if handler not in logger.handlers:
            logger.addHandler(handler)

    logger.propagate = False
    return logger


def get_logger(name: str = "ecdat") -> logging.Logger:
    """Public entry point — returns a structured logger."""
    return _get_logger(name)


# ── Slow-request middleware helpers ────────────────────────────────────────────


class SlowRequestMiddleware(BaseHTTPMiddleware):
    """Log a warning when a request exceeds ECDAT_SLOW_REQUEST_THRESHOLD seconds.

    Place this **before** any body-reading middleware (e.g. streaming / SSRF wrappers)
    so the timing wraps the full dispatch cycle.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = time.time() - start
            if elapsed > SLOW_REQUEST_THRESHOLD_S:
                _get_logger("ecdat.slow").warning(
                    "Slow request: %.2fs — %s %s",
                    elapsed, request.method, request.url.path,
                    extra={"extra_data": {"duration_s": round(elapsed, 3), "method": request.method, "path": str(request.url.path)}},
                )
