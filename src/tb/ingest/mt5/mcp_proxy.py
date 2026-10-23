"""Minimal newline-delimited stdio MCP server with a fixed read-only native client."""

from __future__ import annotations

import json
import sys
from typing import Any

from tb.core.config import repo_root
from tb.ingest.mt5.mcp import MCP_READ_TOOLS, EmptyArguments, ReadOnlyMCP, SymbolArguments
from tb.ingest.mt5.models import FeedUnavailable, load_feed_config
from tb.ingest.mt5.settings import MT5Settings


def dispatch(client: ReadOnlyMCP, message: dict[str, Any]) -> dict[str, Any] | None:
    """Never interpret an unknown tool, resource, prompt, operation or notification as a command."""
    request_id = message.get("id")
    if request_id is None:
        return None
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    method = message.get("method")
    if method == "initialize":
        response["result"] = {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "MT5 read-only P11a proxy", "version": "1"},
        }
    elif method == "ping":
        response["result"] = {}
    elif method == "tools/list":
        response["result"] = {
            "tools": [
                {
                    "name": name,
                    "description": "Pinned demo read; no trading capability.",
                    "inputSchema": (
                        SymbolArguments if name == "get_marketwatch_symbols" else EmptyArguments
                    ).model_json_schema(),
                    "annotations": {"readOnlyHint": True, "destructiveHint": False},
                }
                for name in sorted(MCP_READ_TOOLS)
            ]
        }
    elif method == "tools/call":
        try:
            params = message.get("params", {})
            result = client.call(params.get("name", ""), params.get("arguments", {}))
            response["result"] = {"content": [{"type": "text", "text": json.dumps(result)}]}
        except (ValueError, TypeError, KeyError):
            response["result"] = {
                "isError": True,
                "content": [{"type": "text", "text": "Read refused or unavailable"}],
            }
    else:
        response["error"] = {"code": -32601, "message": "Method outside read-only proxy"}
    return response


def main() -> None:
    """Load credentials privately; stdout carries only protocol messages and sanitized data."""
    root = repo_root()
    settings = MT5Settings.from_root(root)
    config = load_feed_config(root / "config/mt5_feed.yaml")
    try:
        client = ReadOnlyMCP(
            settings.mcp_token.get_secret_value(),
            login=settings.demo_login.get_secret_value(),
            server=settings.demo_server,
            symbols=config.symbols,
        )
        client.discover()
    except FeedUnavailable:
        print("MT5 read-only MCP unavailable; check local demo pins and token", file=sys.stderr)
        return
    try:
        while True:
            line = sys.stdin.buffer.readline(65537)
            if not line:
                break
            if len(line) > 65536:
                break
            try:
                response = dispatch(client, json.loads(line))
                if response is not None:
                    print(json.dumps(response), flush=True)
            except (ValueError, TypeError, AttributeError):
                print(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": "Invalid request"},
                        }
                    ),
                    flush=True,
                )
    finally:
        client.close()


if __name__ == "__main__":
    main()
