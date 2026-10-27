"""Default-deny MCP transport tests never contact a terminal or send an external order."""

import json

import httpx
import pytest

from tb.ingest.mt5.mcp import MCP_READ_TOOLS, ReadOnlyMCP
from tb.ingest.mt5.mcp_proxy import dispatch
from tb.ingest.mt5.models import FeedUnavailable, IdentityRefused


@pytest.fixture
def native():
    calls = []
    account = {
        "login": 123,
        "server": "Offline-Demo",
        "type": "demo",
        "broker": "Synthetic",
        "currency": "USD",
        "name": "PRIVATE_NAME",
        "balance": 5000,
    }

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        if body["method"] == "initialize":
            result = {"serverInfo": {"name": "fixture"}}
        elif body["method"] == "tools/list":
            result = {
                "tools": [
                    {"name": n} for n in (*MCP_READ_TOOLS, "shell", "trade_send_market_order")
                ]
            }
        else:
            name = body["params"]["name"]
            if name == "get_trading_account_info":
                value = {"account": account}
            elif name == "terminal_get_info":
                value = {
                    "terminal": {
                        "build": 6060,
                        "mcp_trade_allowed": True,
                        "connection": {"state": "connected"},
                    }
                }
            elif name == "get_time_information":
                value = {"utc_time": "2024-01-01T00:00:00Z", "secret": "PRIVATE_VALUE"}
            else:
                value = {
                    "symbols": [
                        {
                            "symbol": "EURUSD",
                            "bid": 1.1,
                            "ask": 1.2,
                            "api_key": "PRIVATE_VALUE",
                            "name": "Euro",
                        }
                    ]
                }
            result = {"content": [{"type": "text", "text": json.dumps(value)}]}
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": result},
            headers={"mcp-session-id": "fixture"},
        )

    client = ReadOnlyMCP(
        "FAKE_TOKEN",
        login="123",
        server="Offline-Demo",
        symbols={"EURUSD": "EURUSD"},
        transport=httpx.MockTransport(handler),
    )
    yield client, calls, account
    client.close()


@pytest.mark.parametrize(
    "tool",
    [
        "trade_send_market_order",
        "trade_send_pending_order",
        "trade_modify_sl_tp",
        "trade_delete_order",
        "trade_close_single_position",
        "trade_close_by_position",
        "shell",
        "send_web_request",
        "write_file",
        "chart_add_expert",
        "chart_add_script",
        "service_start",
        "profile_apply",
        "login",
        "account_switch",
        "get_chart_history",
        "get_chart_ticks_history",
    ],
)
def test_unsafe_or_historical_tool_cannot_reach_transport(native, tool):
    client, calls, _ = native
    with pytest.raises(FeedUnavailable):
        client.call(tool, {})
    with pytest.raises(FeedUnavailable):
        client._rpc("tools/call", {"name": tool, "arguments": {}})
    assert calls == []
    response = dispatch(
        client,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": {}},
        },
    )
    assert response["result"]["isError"] and calls == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"symbol": "EURUSD", "command": "malicious"},
        {"symbol": "EURUSD", "limit": 1000},
        {"symbol": "EURUSD*"},
        {"symbol": "EURUSD", "include_hidden": True},
    ],
)
def test_argument_smuggling_denied_before_network(native, arguments):
    client, calls, _ = native
    with pytest.raises(ValueError):
        client.call("get_marketwatch_symbols", arguments)
    assert calls == []


@pytest.mark.parametrize("mode", ["real", "contest", "unknown", None])
def test_mcp_demo_gate_refuses_other_account_types(native, mode):
    client, calls, account = native
    account["type"] = mode
    with pytest.raises(IdentityRefused):
        client.call("get_marketwatch_symbols", {"symbol": "EURUSD"})
    assert [c["params"]["name"] for c in calls] == ["get_trading_account_info"]


def test_mcp_read_outputs_mask_identity_and_drop_unknown_fields(native):
    client, calls, _ = native
    identity = client.call("get_trading_account_info", {})
    assert len(identity["fingerprint"]) == 64 and "login" not in identity
    assert "balance" not in identity and "name" not in identity
    result = client.call("get_marketwatch_symbols", {"symbol": "EURUSD"})
    assert result["symbols"][0]["bid"] == 1.1 and "api_key" not in result["symbols"][0]
    assert "PRIVATE" not in json.dumps(result)
    assert set(c["params"]["name"] for c in calls) <= MCP_READ_TOOLS


def test_stdio_exposes_four_reads_only_and_no_generic_methods(native):
    client, calls, _ = native
    response = dispatch(client, {"id": 1, "method": "tools/list"})
    tools = response["result"]["tools"]
    assert {t["name"] for t in tools} == MCP_READ_TOOLS
    assert all(t["annotations"]["readOnlyHint"] for t in tools)
    assert calls == []
    for method in ("resources/read", "prompts/get", "run", "exec", "tools/call/other"):
        assert dispatch(client, {"id": 2, "method": method})["error"]["code"] == -32601
    assert dispatch(client, {"method": "notifications/initialized"}) is None


def test_native_discovery_handshake_and_account_change_after_read(native):
    client, calls, account = native
    assert len(client.discover()) == len(MCP_READ_TOOLS) + 2
    assert [c["method"] for c in calls] == ["initialize", "notifications/initialized", "tools/list"]
    original = client._read

    def switch(name, args):
        value = original(name, args)
        if name == "get_marketwatch_symbols":
            account["login"] = 999
        return value

    from unittest.mock import patch

    with patch.object(client, "_read", side_effect=switch):
        with pytest.raises(IdentityRefused):
            client.call("get_marketwatch_symbols", {"symbol": "EURUSD"})


def test_http_errors_and_oversized_response_never_leak_secrets():
    for response in (
        httpx.Response(401, text="FAKE_TOKEN"),
        httpx.Response(200, content=b"X" * 2_000_001),
    ):
        client = ReadOnlyMCP(
            "FAKE_TOKEN",
            login="123",
            server="Offline-Demo",
            symbols={"EURUSD": "EURUSD"},
            transport=httpx.MockTransport(lambda request, reply=response: reply),
        )
        with pytest.raises(FeedUnavailable) as exc:
            client.discover()
        assert "FAKE_TOKEN" not in str(exc.value)
        client.close()
