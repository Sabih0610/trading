"""Local credential boundary; imported only by collector/proxy entrypoints, never the dashboard."""

from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MT5Settings(BaseSettings):
    """Ignored root .env is the sole persisted credential/pinning store."""

    model_config = SettingsConfigDict(env_prefix="MT5_", extra="ignore")
    terminal_path: Path | None = None
    demo_login: SecretStr = SecretStr("")
    demo_server: str = ""
    mcp_token: SecretStr = SecretStr("")

    @classmethod
    def from_root(cls, root: Path) -> "MT5Settings":
        arguments: dict[str, Any] = {"_env_file": root / ".env"}
        return cls(**arguments)
