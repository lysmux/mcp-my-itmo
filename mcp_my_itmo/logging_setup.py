from __future__ import annotations

import logging
import sys

import structlog
from structlog.typing import FilteringBoundLogger

_configured = False


def _stderr_logger_factory(*_args: object) -> structlog.PrintLogger:
    return structlog.PrintLogger(file=sys.stderr)


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=_stderr_logger_factory,
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    return structlog.get_logger(name)
