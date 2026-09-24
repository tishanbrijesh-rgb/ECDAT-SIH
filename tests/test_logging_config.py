"""Regression tests for process-wide logging handler ownership."""
import logging
from logging.handlers import RotatingFileHandler

from backend.logging_config import _TextFormatter, get_logger


def test_named_loggers_share_one_rotating_file_handler() -> None:
    first = get_logger("ecdat.test.first")
    second = get_logger("ecdat.test.second")

    first_file_handlers = [h for h in first.handlers if isinstance(h, RotatingFileHandler)]
    second_file_handlers = [h for h in second.handlers if isinstance(h, RotatingFileHandler)]

    assert len(first_file_handlers) == 1
    assert len(second_file_handlers) == 1
    assert first_file_handlers[0] is second_file_handlers[0]


def test_text_formatter_renders_exception_once() -> None:
    try:
        raise ValueError("formatter canary")
    except ValueError:
        record = logging.LogRecord(
            name="ecdat.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    record.request_id = "request-1"
    rendered = _TextFormatter().format(record)

    assert rendered.count("Traceback (most recent call last)") == 1
