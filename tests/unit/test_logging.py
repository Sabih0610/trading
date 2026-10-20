"""Tests for structured log output and credential redaction."""

import json
import logging
from pathlib import Path

from tb.core.logging import REDACTED, configure_logging, redact


def _flush_handlers() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_redact_handles_nested_values_and_credential_names() -> None:
    value = {
        "api_key": "visible",
        "nested": ["Bearer abcdefghijklmnop", {"safe": "ok"}],
    }

    assert redact(value) == {
        "api_key": REDACTED,
        "nested": [REDACTED, {"safe": "ok"}],
    }


def test_json_log_redacts_known_and_heuristic_secrets(tmp_path: Path) -> None:
    secret = "known-secret-value-123"
    logger = configure_logging(log_dir=tmp_path, known_secrets=(secret,), console=False)

    logger.info(
        "credentials api_key=%s bearer=%s known=%s",
        "abcdefghijklmnopqrstuvwx",
        "Bearer abcdefghijklmnop",
        secret,
        extra={"authorization": "Bearer hidden-hidden-hidden"},
    )
    _flush_handlers()

    output = (tmp_path / "trading-bot.jsonl").read_text(encoding="utf-8")
    payload = json.loads(output)
    assert secret not in output
    assert "abcdefghijklmnopqrstuvwx" not in output
    assert "hidden-hidden-hidden" not in output
    assert REDACTED in payload["message"]
    assert payload["context"]["authorization"] == REDACTED


def test_logging_creates_directory_with_spaces(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs with spaces"
    logger = configure_logging(log_dir=log_dir, console=False)
    logger.info("safe event")
    _flush_handlers()

    assert (log_dir / "trading-bot.jsonl").is_file()
