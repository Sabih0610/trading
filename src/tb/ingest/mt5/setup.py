"""Install a project-local, credential-free Codex MCP configuration for the constrained proxy."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path

from tb.core.config import repo_root
from tb.ingest.mt5.mcp import MCP_READ_TOOLS
from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.mt5.settings import MT5Settings


def configure(root: Path) -> Path:
    """Preserve unrelated settings; refuse any direct native endpoint in this project's config."""
    settings = MT5Settings.from_root(root)
    if (
        not settings.mcp_token.get_secret_value()
        or not settings.demo_login.get_secret_value()
        or not settings.demo_server
    ):
        raise FeedUnavailable("Configure the ignored root .env token and verified demo pins first")
    for name in (".env", ".codex/config.toml"):
        if subprocess.run(["git", "check-ignore", "-q", name], cwd=root).returncode:
            raise FeedUnavailable("Local secrets/config paths must be Git-ignored")
    target = root / ".codex/config.toml"
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    parsed = tomllib.loads(text)
    for name, server in parsed.get("mcp_servers", {}).items():
        if (
            name != "mt5_readonly_p11a"
            and any(
                part in server.get("url", "")
                for part in (":22346/", ":22345/", "metatrader.com/mcp")
            )
            and server.get("enabled", True)
        ):
            raise FeedUnavailable(
                "Direct native MT5 MCP must be disabled before installing the restricted proxy"
            )
    section = "[mcp_servers.mt5_readonly_p11a]\n"
    section += "command = " + json.dumps(str(root / ".venv/Scripts/python.exe")) + "\n"
    section += 'args = ["-m", "tb.ingest.mt5.mcp_proxy"]\n'
    section += "cwd = " + json.dumps(str(root)) + "\n"
    section += "enabled = true\nstartup_timeout_sec = 20\ntool_timeout_sec = 30\n"
    section += "enabled_tools = " + json.dumps(sorted(MCP_READ_TOOLS)) + "\n"
    section += 'default_tools_approval_mode = "auto"\n'
    text = (
        re.sub(r"(?ms)^\[mcp_servers\.mt5_readonly_p11a\]\n.*?(?=^\[|\Z)", "", text).rstrip()
        + "\n\n"
        + section
    )
    tomllib.loads(text)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def main() -> None:
    try:
        configure(repo_root())
        print(
            "Installed ignored .codex/config.toml: four read-only MT5 tools; restart Codex to discover them."
        )
    except (FeedUnavailable, OSError, ValueError):
        print("MT5 MCP configuration refused; check the local setup guide. No token was displayed.")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
