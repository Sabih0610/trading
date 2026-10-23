"""Default-deny native MCP client. Only four fixed read tools can cross this boundary."""

from __future__ import annotations

import json
from typing import Any, Literal

import httpx
from pydantic import Field

from tb.ingest.mt5.adapter import fingerprint
from tb.ingest.mt5.models import FeedUnavailable, IdentityRefused
from tb.risk.config import PolicyModel

MCP_READ_TOOLS = frozenset(
    {
        "terminal_get_info",
        "get_time_information",
        "get_trading_account_info",
        "get_marketwatch_symbols",
    }
)
NATIVE_URL = "http://127.0.0.1:22346/mcp"


class EmptyArguments(PolicyModel):
    """No extra argument, script, path or operation can be smuggled into a read."""


class SymbolArguments(PolicyModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    limit: int = Field(default=1, ge=1, le=1)


class ReadOnlyMCP:
    """No generic forwarding, external URL, dynamic method or credential output."""

    def __init__(
        self,
        token: str,
        *,
        login: str,
        server: str,
        symbols: dict[str, str],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not token or not login or not server:
            raise FeedUnavailable("Native MCP token and demo identity pins required")
        self._login, self._server, self._symbols = login, server, symbols
        self._http = httpx.Client(
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json, text/event-stream",
            },
            timeout=10,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        self._session: str | None = None
        self._id = 0

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method not in {"initialize", "notifications/initialized", "tools/list", "tools/call"}:
            raise FeedUnavailable("MCP method refused")
        if method == "tools/call" and params.get("name") not in MCP_READ_TOOLS:
            raise FeedUnavailable("MCP operation refused before transport")
        self._id += 1
        headers = {"Mcp-Session-Id": self._session} if self._session else {}
        try:
            payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
            if method != "notifications/initialized":
                payload["id"] = self._id
            with self._http.stream(
                "POST",
                NATIVE_URL,
                headers=headers,
                json=payload,
            ) as response:
                if method == "notifications/initialized" and response.status_code in {
                    200,
                    202,
                    204,
                }:
                    return {}
                if response.status_code != 200:
                    raise FeedUnavailable("Native MCP unavailable or authentication refused")
                data = bytearray()
                for chunk in response.iter_bytes(65536):
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise FeedUnavailable("Native MCP response exceeds read limit")
                self._session = response.headers.get("mcp-session-id", self._session)
            value = json.loads(data)
            if "error" in value or not isinstance(value.get("result"), dict):
                raise FeedUnavailable("Native MCP returned an error")
            return dict(value["result"])
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, FeedUnavailable):
                raise
            raise FeedUnavailable("Native MCP read failed") from None

    def discover(self) -> list[dict[str, Any]]:
        """Inspect schemas without exposing the native write-capable tool list to Codex."""
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "p11a-readonly", "version": "1"},
            },
        )
        self._http.headers["MCP-Protocol-Version"] = "2025-03-26"
        self._rpc("notifications/initialized", {})
        return list(self._rpc("tools/list", {}).get("tools", []))

    def _read(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in MCP_READ_TOOLS:
            raise FeedUnavailable("Operation outside the read-only MCP boundary")
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise FeedUnavailable("Native MCP facts unavailable")
        if isinstance(result.get("structuredContent"), dict):
            return dict(result["structuredContent"])
        for block in result.get("content", []):
            if block.get("type") == "text":
                try:
                    value = json.loads(block["text"])
                    if isinstance(value, dict):
                        return value
                except ValueError:
                    pass
        raise FeedUnavailable("Native MCP result shape unavailable")

    def _identity(self) -> dict[str, Any]:
        payload = self._read("get_trading_account_info", {})
        account = payload.get("account", {})
        if (
            account.get("type") != "demo"
            or str(account.get("login")) != self._login
            or account.get("server") != self._server
        ):
            raise IdentityRefused("Native MCP demo identity refused")
        return {
            "environment": "demo",
            "server": self._server,
            "fingerprint": fingerprint(self._login, self._server),
            "broker": account.get("broker"),
            "currency": account.get("currency"),
        }

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate arguments before any network operation and check identity on both sides."""
        if name not in MCP_READ_TOOLS:
            raise FeedUnavailable("Operation outside the read-only MCP boundary")
        if name == "get_marketwatch_symbols":
            args = SymbolArguments.model_validate(arguments)
            if args.symbol not in self._symbols:
                raise FeedUnavailable("Symbol not configured")
            native_args = {"symbol": self._symbols[args.symbol], "limit": 1}
        else:
            EmptyArguments.model_validate(arguments)
            native_args = {}
        identity = self._identity()
        if name == "get_trading_account_info":
            return identity
        result = self._read(name, native_args)
        self._identity()
        if name == "terminal_get_info":
            terminal = result.get("terminal", {})
            return {
                "build": terminal.get("build"),
                "connection": {"state": terminal.get("connection", {}).get("state")},
                "native_mcp_trading_permission": terminal.get("mcp_trade_allowed"),
                "proxy_trading_enabled": False,
            }
        if name == "get_time_information":
            return {
                key: result.get(key)
                for key in (
                    "utc_time",
                    "local_time",
                    "local_utc_offset_minutes",
                    "daylight_saving_time",
                    "trade_server_last_known_time",
                )
            }
        # Native Market Watch is projected later by the inspection CLI; never forward arbitrary text.
        return project_market_symbols(result)

    def close(self) -> None:
        self._http.close()


def project_market_symbols(result: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown fields and free text, including anything credential-shaped."""
    rows = result.get("symbols", result.get("data", []))
    if not isinstance(rows, list):
        return {"symbols": [], "availability": "Native schema unverified"}
    keys = {
        "name",
        "symbol",
        "currency_base",
        "currency_profit",
        "digits",
        "point",
        "bid",
        "ask",
        "time",
        "time_msc",
        "trade_tick_size",
        "trade_contract_size",
        "volume_min",
        "volume_max",
        "volume_step",
        "trade_tick_value",
        "spread",
        "tick_size",
        "tick_value",
        "contract_size",
        "update_time",
    }
    return {
        "symbols": [
            {k: v for k, v in row.items() if k in keys} for row in rows[:1] if isinstance(row, dict)
        ]
    }
