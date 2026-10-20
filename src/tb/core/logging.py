"""Structured logging with defense-in-depth secret redaction."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.logging import RichHandler

from tb.core.config import repo_root

REDACTED = "[REDACTED]"

_SENSITIVE_NAME = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|passwd|authorization|credential)"
)
_KEY_VALUE = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret|token|password|authorization)\b\s*[:=]\s*)"
    r"(?:bearer\s+)?[^\s,;]+"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_PROVIDER_TOKEN = re.compile(r"\b(?:sk|pk|xox[baprs]|gh[pousr])-[A-Za-z0-9_-]{8,}\b")
_OPAQUE_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_+/=-]{32,}(?![A-Za-z0-9])")

_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)


def redact(value: Any, known_secrets: Iterable[str] = ()) -> Any:
    """Return a recursively redacted copy of a log value."""

    secret_values = tuple(secret for secret in known_secrets if secret)
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _SENSITIVE_NAME.search(str(key)) else redact(item, secret_values)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact(item, secret_values) for item in value)
    if isinstance(value, list):
        return [redact(item, secret_values) for item in value]
    if not isinstance(value, str):
        return value

    result = value
    for secret in secret_values:
        result = result.replace(secret, REDACTED)
    result = _KEY_VALUE.sub(lambda match: f"{match.group(1)}{REDACTED}", result)
    result = _BEARER.sub(REDACTED, result)
    result = _PROVIDER_TOKEN.sub(REDACTED, result)
    return _OPAQUE_TOKEN.sub(REDACTED, result)


class RedactingFilter(logging.Filter):
    """Sanitize message arguments and structured extras before any handler emits them."""

    def __init__(self, known_secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._known_secrets = tuple(known_secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record in place and allow it to be emitted."""

        # Interpolate before redaction so replacing a value never changes the number of
        # placeholders in the original logging template.
        record.msg = redact(record.getMessage(), self._known_secrets)
        record.args = ()
        for field_name, value in vars(record).items():
            if field_name in _STANDARD_LOG_RECORD_FIELDS:
                continue
            replacement = (
                REDACTED
                if _SENSITIVE_NAME.search(field_name)
                else redact(value, self._known_secrets)
            )
            setattr(record, field_name, replacement)
        return True


class JsonFormatter(logging.Formatter):
    """Encode each log record as one compact JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record using stable, UTC fields."""

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = {
            key: value
            for key, value in vars(record).items()
            if key not in _STANDARD_LOG_RECORD_FIELDS and not key.startswith("_")
        }
        if extras:
            payload["context"] = extras
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False, separators=(",", ":"))


def configure_logging(
    *,
    log_dir: Path | None = None,
    level: int = logging.INFO,
    known_secrets: Iterable[str] = (),
    console: bool = True,
) -> logging.Logger:
    """Configure root handlers and return the application logger."""

    destination = repo_root() / "logs" if log_dir is None else log_dir
    destination.mkdir(parents=True, exist_ok=True)
    redactor = RedactingFilter(known_secrets)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    file_handler = logging.FileHandler(
        destination / "trading-bot.jsonl", encoding="utf-8", delay=True
    )
    file_handler.setFormatter(JsonFormatter())
    file_handler.addFilter(redactor)
    root_logger.addHandler(file_handler)

    if console:
        console_handler = RichHandler(
            level=level,
            show_path=False,
            rich_tracebacks=True,
            markup=False,
        )
        console_handler.addFilter(redactor)
        root_logger.addHandler(console_handler)

    return logging.getLogger("tb")
