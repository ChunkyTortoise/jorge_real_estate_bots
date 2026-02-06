"""
Logging utility for Jorge's Real Estate AI Bots with Correlation ID support.

Provides structured logging with correlation tracking for distributed tracing.
Adapted from EnterpriseHub.
"""
import logging
import sys
import re
from typing import Optional
from contextvars import ContextVar
import uuid

from bots.shared.config import settings

# Context variable to store correlation ID for the current task/request
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="system")


class CorrelationFilter(logging.Filter):
    """Logging filter that injects the current correlation_id into the log record."""

    def filter(self, record):
        record.correlation_id = correlation_id.get()
        return True


class RedactionFilter(logging.Filter):
    """Redact common PII patterns from log messages."""

    EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    PHONE_RE = re.compile(r"(\+?\d{1,2}[\s.-]?)?(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})")

    def filter(self, record):
        try:
            message = record.getMessage()
            message = self.EMAIL_RE.sub("[REDACTED_EMAIL]", message)
            message = self.PHONE_RE.sub("[REDACTED_PHONE]", message)
            record.msg = message
            record.args = ()
        except Exception:
            pass
        return True


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance with structured formatting and correlation tracking.

    Args:
        name: Logger name (typically __name__)
        level: Optional log level override

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        # Set level from settings
        log_level = level or settings.log_level
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # Console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logger.level)

        # Structured Format including Correlation ID
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | [%(correlation_id)s] | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

        # Add Filter
        handler.addFilter(CorrelationFilter())
        handler.addFilter(RedactionFilter())

        logger.addHandler(handler)
        logger.propagate = False

    return logger


def set_correlation_id(cid: Optional[str] = None) -> str:
    """
    Set the correlation ID for the current context.

    Args:
        cid: Optional correlation ID. If not provided, generates a UUID.

    Returns:
        The correlation ID that was set
    """
    cid = cid or str(uuid.uuid4())
    correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return correlation_id.get()
