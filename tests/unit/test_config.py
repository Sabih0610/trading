"""Tests for safe, optional configuration loading."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from tb.core.config import ConfigLoadError, features_enabled, load_config, load_settings, load_yaml


class ExampleConfig(BaseModel):
    count: int


def test_missing_env_disables_keyed_integrations(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.env")

    status = features_enabled(settings)

    assert status["binance_testnet"] is False
    assert status["binance_live"] is False
    assert status["fred"] is False
    assert status["openai"] is False


def test_blank_env_values_disable_keyed_integrations(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FRED_API_KEY=\nOPENAI_API_KEY=   \nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n",
        encoding="utf-8",
    )

    status = features_enabled(load_settings(env_file))

    assert status["fred"] is False
    assert status["openai"] is False
    assert status["telegram"] is False


def test_garbage_env_lines_do_not_prevent_known_values(tmp_path: Path) -> None:
    env_file = tmp_path / "garbage.env"
    env_file.write_text("this is not valid\nFRED_API_KEY=test-fred-key\n", encoding="utf-8")

    settings = load_settings(env_file)

    assert features_enabled(settings)["fred"] is True
    assert settings.fred_api_key is not None
    assert settings.fred_api_key.get_secret_value() == "test-fred-key"


def test_features_require_both_members_of_credential_pair(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BINANCE_TESTNET_API_KEY=only-one-value\n", encoding="utf-8")

    assert features_enabled(load_settings(env_file))["binance_testnet"] is False


def test_yaml_loads_from_path_with_spaces(tmp_path: Path) -> None:
    config_dir = tmp_path / "path with spaces"
    config_dir.mkdir()
    path = config_dir / "example.yaml"
    path.write_text("count: 3\n", encoding="utf-8")

    assert load_yaml(path, ExampleConfig).count == 3


@pytest.mark.parametrize("content", ["- item\n", "count: nope\n", "count: [unterminated\n"])
def test_yaml_rejects_wrong_root_invalid_values_and_syntax(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigLoadError):
        load_yaml(path, ExampleConfig)


def test_config_loader_blocks_path_traversal(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    with pytest.raises(ConfigLoadError, match="inside the config directory"):
        load_config("../outside.yaml", ExampleConfig, config_dir=config_dir)
