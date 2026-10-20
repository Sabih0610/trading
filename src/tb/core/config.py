"""Typed settings and YAML configuration loading.

Secrets remain wrapped in :class:`pydantic.SecretStr` and feature reporting exposes only
enabled/disabled booleans. External integrations are optional by design.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigLoadError(ValueError):
    """Raised when a YAML configuration file cannot be safely loaded or validated."""


class Settings(BaseSettings):
    """Optional external-service settings read from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    binance_testnet_api_key: SecretStr | None = None
    binance_testnet_api_secret: SecretStr | None = None
    binance_api_key: SecretStr | None = None
    binance_api_secret: SecretStr | None = None
    fred_api_key: SecretStr | None = None
    finnhub_api_key: SecretStr | None = None
    cryptopanic_api_key: SecretStr | None = None
    newsdata_api_key: SecretStr | None = None
    xai_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    qwen_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    jev_api_key: SecretStr | None = None
    ollama_host: str | None = "http://127.0.0.1:11434"
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: SecretStr | None = None

    @field_validator("*", mode="before")
    @classmethod
    def blank_values_are_missing(cls, value: object) -> object:
        """Treat blank dotenv values as absent integrations, not configured secrets."""

        if isinstance(value, str) and not value.strip():
            return None
        return value

    def known_secret_values(self) -> tuple[str, ...]:
        """Return configured secret values for registration with the log redactor."""

        values: list[str] = []
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            if isinstance(value, SecretStr):
                secret = value.get_secret_value()
                if secret:
                    values.append(secret)
        return tuple(values)


def repo_root() -> Path:
    """Return the repository root without relying on the process working directory."""

    return Path(__file__).resolve().parents[3]


def load_settings(env_file: Path | None = None) -> Settings:
    """Load optional settings, defaulting to the repository `.env` file if it exists."""

    selected = repo_root() / ".env" if env_file is None else env_file
    # BaseSettings supports private source-selection kwargs at runtime, but its generated
    # constructor signature intentionally exposes only declared environment fields.
    return Settings(_env_file=selected)  # type: ignore[call-arg]


def features_enabled(settings: Settings) -> dict[str, bool]:
    """Report integration availability without exposing credential values."""

    return {
        "binance_testnet": bool(
            settings.binance_testnet_api_key and settings.binance_testnet_api_secret
        ),
        "binance_live": bool(settings.binance_api_key and settings.binance_api_secret),
        "fred": settings.fred_api_key is not None,
        "finnhub": settings.finnhub_api_key is not None,
        "cryptopanic": settings.cryptopanic_api_key is not None,
        "newsdata": settings.newsdata_api_key is not None,
        "xai": settings.xai_api_key is not None,
        "openai": settings.openai_api_key is not None,
        "deepseek": settings.deepseek_api_key is not None,
        "qwen": settings.qwen_api_key is not None,
        "anthropic": settings.anthropic_api_key is not None,
        "jev": settings.jev_api_key is not None,
        "ollama": bool(settings.ollama_host),
        "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }


class LooseYamlConfig(BaseModel):
    """Validated mapping used when a phase has not yet introduced a stricter schema."""

    model_config = ConfigDict(extra="allow")


def load_yaml[YamlModelT: BaseModel](path: Path, model: type[YamlModelT]) -> YamlModelT:
    """Safely parse a YAML mapping and validate it against `model`."""

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigLoadError(f"Unable to read YAML configuration {path}: {exc}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ConfigLoadError(f"YAML configuration {path} must contain a mapping at its root")

    try:
        return model.model_validate(dict(raw))
    except ValidationError as exc:
        raise ConfigLoadError(f"Invalid YAML configuration {path}: {exc}") from exc


def load_config[YamlModelT: BaseModel](
    name: str,
    model: type[YamlModelT],
    *,
    config_dir: Path | None = None,
) -> YamlModelT:
    """Load a named file from the repository config directory with traversal protection."""

    base = (repo_root() / "config" if config_dir is None else config_dir).resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base):
        raise ConfigLoadError("Configuration path must stay inside the config directory")
    return load_yaml(candidate, model)
