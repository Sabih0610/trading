"""Opt-in genuine read-only diagnostics; failed quote validation is never reported as success."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from tb.core.config import repo_root
from tb.ingest.history.core import atomic_write_json
from tb.ingest.mt5.adapter import MT5Feed, PythonReader
from tb.ingest.mt5.mcp import ReadOnlyMCP
from tb.ingest.mt5.models import FeedUnavailable, load_feed_config
from tb.ingest.mt5.settings import MT5Settings


def main() -> None:
    """Attach to the pinned demo; no account login, Market Watch change or execution API."""
    root = repo_root()
    settings = MT5Settings.from_root(root)
    config = load_feed_config(root / "config/mt5_feed.yaml")
    result: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "diagnostic_only": True,
        "external_orders_enabled": False,
        "genuine_terminal_verified": False,
        "qualified_forward_quotes": 0,
        "python_instruments": {},
        "native_mcp_verified": False,
    }
    try:
        if settings.terminal_path is None:
            raise FeedUnavailable("Explicit terminal path unavailable")
        feed = MT5Feed(
            PythonReader(),
            config,
            terminal_path=settings.terminal_path,
            login=settings.demo_login.get_secret_value(),
            server=settings.demo_server,
        )
        try:
            result["identity"] = feed.connect().model_dump(mode="json")
            result["genuine_terminal_verified"] = True
            for symbol in config.symbols:
                item: dict[str, Any] = {
                    "metadata_verified": False,
                    "quote_validation_passed": False,
                }
                try:
                    item["facts"] = feed.metadata(symbol).model_dump(mode="json")
                    item["metadata_verified"] = True
                    feed.latest_raw = {}
                    quote, _ = feed.quote(symbol)
                    item["quote_validation_passed"] = True
                    item["source_at"] = quote.source_at.isoformat()
                except FeedUnavailable as error:
                    item["reason"] = str(error)
                    if feed.latest_raw.get("time_msc"):
                        source = datetime.fromtimestamp(
                            int(feed.latest_raw["time_msc"]) / 1000, UTC
                        )
                        received = datetime.now(UTC)
                        item["source_epoch_as_utc"] = source.isoformat()
                        item["received_utc"] = received.isoformat()
                        item["source_minus_receipt_seconds"] = round(
                            (source - received).total_seconds(), 3
                        )
                result["python_instruments"][symbol] = item
        finally:
            feed.close()
        client = ReadOnlyMCP(
            settings.mcp_token.get_secret_value(),
            login=settings.demo_login.get_secret_value(),
            server=settings.demo_server,
            symbols=config.symbols,
        )
        try:
            result["native_tool_count"] = len(client.discover())
            result["native_terminal"] = client.call("terminal_get_info", {})
            result["native_time"] = client.call("get_time_information", {})
            result["native_marketwatch"] = client.call(
                "get_marketwatch_symbols", {"symbol": "EURUSD"}
            )
            result["native_mcp_verified"] = True
        finally:
            client.close()
    except (FeedUnavailable, ValueError, OSError):
        result["status"] = "unavailable_or_partial; no genuine market-data success inferred"
    else:
        result["status"] = (
            "identity_and_native_reads_verified; per-instrument validation recorded separately"
        )
    path = root / "reports/mt5/P11a-connectivity.json"
    atomic_write_json(path, result)
    print(
        json.dumps(
            {
                "report": str(path.relative_to(root)),
                "genuine_terminal_verified": result["genuine_terminal_verified"],
                "native_mcp_verified": result["native_mcp_verified"],
                "qualified_forward_quotes": result["qualified_forward_quotes"],
                "external_orders_enabled": False,
            }
        )
    )


if __name__ == "__main__":
    main()
