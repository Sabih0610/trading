"""Coordinated, finite diagnostic. Raw disagreement is quarantined, never time-shifted."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from tb.core.config import repo_root
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.mt5.adapter import MT5Feed, PythonReader, as_dict
from tb.ingest.mt5.cli import collector_lease
from tb.ingest.mt5.collector import Collector
from tb.ingest.mt5.mcp import MCP_READ_TOOLS, ReadOnlyMCP
from tb.ingest.mt5.models import FeedUnavailable, InstrumentFacts, load_feed_config
from tb.ingest.mt5.qualification import AdmissionMonitor, seconds_interpretation
from tb.ingest.mt5.settings import MT5Settings
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.mt5.timestamps import parse_tick_epoch


def windows_clock_status() -> dict[str, Any]:
    """Fixed read-only diagnostics; no time edits, sync commands or configurable shell input."""
    result: dict[str, Any] = {"python_utc": datetime.now(UTC).isoformat()}
    try:
        output = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", "[DateTime]::UtcNow.ToString('o')"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        result["windows_utc"] = output.stdout.strip() if output.returncode == 0 else None
        status = subprocess.run(
            ["w32tm", "/query", "/status"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        # Do not persist machine names, peer addresses or arbitrary subprocess text.
        result.update(
            w32time_query_exit_code=status.returncode,
            w32time_status="query_succeeded"
            if status.returncode == 0
            else "unverified_service_or_sync_unavailable",
        )
    except (OSError, subprocess.TimeoutExpired):
        result["w32time_status"] = "unavailable"
    return result


def readiness(facts: InstrumentFacts, raw: dict[str, Any]) -> dict[str, Any]:
    """Describe observed constraints; indicative rejected prices cannot authorize sizing."""
    indicative: Decimal | None = None
    try:
        ask = Decimal(str(raw.get("ask")))
        if ask.is_finite() and ask > 0 and facts.contract_size and facts.volume_min:
            indicative = ask * facts.contract_size * facts.volume_min
    except ArithmeticError:
        pass
    return {
        "facts": facts.model_dump(mode="json"),
        "pip_size": None,
        "commission": None,
        "financing": None,
        "session_and_holiday_calendar": None,
        "currency_conversion": "USD/USD identity 1"
        if facts.account_currency == "USD"
        else "unverified",
        "validated_minimum_notional_usd": None,
        "diagnostic_only_minimum_notional_usd": str(indicative) if indicative is not None else None,
        "diagnostic_price_validated": False,
        "affordability_100_usd": "indicatively_exceeds_100; sizing_blocked"
        if indicative and indicative > 100
        else "unverified; sizing_blocked",
        "spread_history": "bounded rejected raw diagnostic samples only; no validated spread history",
        "missing_for_sizing": [
            "UTC-valid price",
            "pip policy",
            "commission provenance",
            "session/holiday calendar",
            "cost/slippage policy",
            "minimum stop/freeze constraints",
        ],
        "eligibility": "research/local funded simulation only; external execution disabled",
    }


def diagnostic_session(
    feed: MT5Feed, mcp: ReadOnlyMCP, store: FeedStore, *, samples: int = 3
) -> dict[str, Any]:
    """Capture at most five coordinated SDK/MCP samples and ten unqualified M1 bars per symbol."""
    if not 1 <= samples <= 5:
        raise FeedUnavailable("Diagnostic sample bound refused")
    identity = feed.connect()
    started = feed.clock()
    session, session_started = store.session(identity.fingerprint, started, synthetic=False)
    clock_status = windows_clock_status()
    monitor = AdmissionMonitor(feed, mcp)
    admission = monitor()
    observations: list[dict[str, Any]] = []
    facts_by_symbol: dict[str, InstrumentFacts] = {}
    latest: dict[str, dict[str, Any]] = {}
    counts: dict[str, dict[str, Any]] = {
        s: {
            "attempts": 0,
            "received": 0,
            "valid": 0,
            "rejected": 0,
            "missing": 0,
            "duplicates": 0,
            "qualified_forward": 0,
            "quote_updates": 0,
            "rejected_by_reason": {},
        }
        for s in feed.config.symbols
    }
    seen: dict[str, set[str]] = {s: set() for s in feed.config.symbols}
    for index in range(samples):
        clocks = mcp.call("get_time_information", {})
        for symbol, broker_symbol in feed.config.symbols.items():
            count = counts[symbol]
            count["attempts"] += 1
            before, mono = feed.clock(), time.monotonic()
            item: dict[str, Any] = {
                "sample": index + 1,
                "symbol": symbol,
                "before_utc": before.isoformat(),
                "mcp_clock": clocks,
            }
            raw: dict[str, Any] = {}
            try:
                facts = feed.metadata(symbol)
                facts_by_symbol[symbol] = facts
                raw = as_dict(feed._read("symbol_info_tick", broker_symbol))
                # Only fixed tick fields cross the native boundary into public evidence.
                raw = {
                    k: raw[k]
                    for k in ("time", "time_msc", "bid", "ask", "volume", "volume_real", "flags")
                    if k in raw
                }
                latest[symbol] = raw
                count["received"] += 1
                received = feed.last_read_received_at or feed.clock()
                at = parse_tick_epoch(raw)
                delta = (at - received).total_seconds()
                key = json.dumps(raw, sort_keys=True)
                count["duplicates"] += int(key in seen[symbol])
                count["quote_updates"] += int(key not in seen[symbol])
                seen[symbol].add(key)
                item.update(
                    raw=raw,
                    received_utc=received.isoformat(),
                    source_seconds_utc=seconds_interpretation(raw["time"]),
                    source_milliseconds_utc=at.isoformat(),
                    source_minus_receipt_seconds=delta,
                    native_read_elapsed_seconds=feed.last_read_elapsed_seconds,
                    mcp_marketwatch=mcp.call("get_marketwatch_symbols", {"symbol": symbol}),
                )
                valid_prices = Decimal(str(raw["ask"])) >= Decimal(str(raw["bid"])) > 0
                if delta > feed.config.future_tolerance_seconds:
                    reason = "future_timestamp"
                elif delta < -feed.config.max_tick_age_seconds:
                    reason = "stale_source"
                elif not valid_prices:
                    reason = "invalid_price"
                elif facts.visible is not True or facts.selected is not True:
                    reason = "visibility_unverified"
                else:
                    reason = "diagnostic_only_no_forward_session"
                    count["valid"] += 1
                item["qualification"] = reason
                if reason != "diagnostic_only_no_forward_session":
                    count["rejected"] += 1
                    count["rejected_by_reason"][reason] = (
                        count["rejected_by_reason"].get(reason, 0) + 1
                    )
            except (FeedUnavailable, ValueError, ArithmeticError, KeyError):
                count["rejected"] += 1
                count["missing"] += int(not raw)
                reason = "native_or_metadata_unavailable"
                count["rejected_by_reason"][reason] = count["rejected_by_reason"].get(reason, 0) + 1
                item["qualification"] = reason
            item["elapsed_seconds"] = time.monotonic() - mono
            observations.append(item)
            # Every diagnostic sample remains raw-only, even if its time looks plausible.
            receipt = store.commit(
                session,
                [],
                [{"symbol": symbol, "diagnostic": item}],
                received_at=feed.clock(),
                warnings=["diagnostic_only_not_forward_evidence"],
            )
            item["quarantine_commit"] = {k: receipt[k] for k in ("rows", "raw_rows", "files")}
        if index + 1 < samples:
            time.sleep(2)
    bars: dict[str, list[dict[str, Any]]] = {}
    for symbol, alias in feed.config.symbols.items():
        tail = feed._read("copy_rates_from_pos", alias, 1, 1, 10)
        bars[symbol] = []
        if tail is None:
            continue
        for value in tail[:10]:
            raw_bar = as_dict(value)
            at = parse_tick_epoch({"time": raw_bar.get("time")})
            bars[symbol].append(
                {
                    "raw": raw_bar,
                    "epoch_utc_interpretation": at.isoformat(),
                    "completed_under_host_utc": at + timedelta(minutes=1) <= feed.clock(),
                    "broker_position_excludes_current_bar": True,
                    "qualified_forward": False,
                }
            )
        store.commit(
            session,
            [],
            [{"symbol": symbol, **b} for b in bars[symbol]],
            received_at=feed.clock(),
            warnings=["diagnostic_m1_backfill_not_forward_evidence"],
        )
    terminal = mcp.call("terminal_get_info", {})
    report: dict[str, Any] = {
        "phase": "P11a.1",
        "started_at": started.isoformat(),
        "ended_at": feed.clock().isoformat(),
        "identity": identity.model_dump(mode="json"),
        "sdk_version": importlib.metadata.version("MetaTrader5"),
        "windows_clock": clock_status,
        "independent_utc": monitor.references,
        "terminal": terminal,
        "native_tool_count": len(mcp.discover()),
        "proxy_tools": sorted(MCP_READ_TOOLS),
        "admission": admission.model_dump(mode="json"),
        "samples": observations,
        "counts": counts,
        "m1_tail": bars,
        "readiness": {s: readiness(f, latest.get(s, {})) for s, f in facts_by_symbol.items()},
        "extended_collection_started": False,
        "qualified_m5_intervals": 0,
        "complete_tick_coverage_verified": False,
        "p11b_go": False,
        "external_orders_enabled": False,
        "quarantine_last_commit_verified": store.last_commit() is not None,
        "session_started": session_started.isoformat(),
    }
    return report


def publish_diagnostic(root: Path, report: dict[str, Any]) -> None:
    """Publish a small read-only monitoring snapshot with zero unqualified price rows."""
    now = report["ended_at"]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source": "mt5_demo",
        "session_id": "diagnostic-" + uuid4().hex,
        "session_started": report["session_started"],
        "generated_at": now,
        "identity": report["identity"],
        "facts": [v["facts"] for v in report["readiness"].values()],
        "health": [
            {
                "symbol": s,
                "state": "INSTRUMENT_UNAVAILABLE"
                if report["counts"][s].get("missing", 0)
                else "UNKNOWN",
                "checked_at": now,
                "reason": "Instrument or quote unavailable; verify exact mapping and visibility"
                if report["counts"][s].get("missing", 0)
                else "Source qualification failed; inspect diagnostic report",
            }
            for s in report["counts"]
        ],
        "quotes": [],
        "candles": [],
        "warnings": list(report["admission"]["reasons"]),
        "historical_backfill_displayed": False,
        "external_orders_enabled": False,
        "poll_seconds": 5,
        "collector_running": False,
        "collection_started_at": report["started_at"],
        "collection_ended_at": now,
        "counts": report["counts"],
        "admission": report["admission"],
        "connection_status": "pinned_demo_connected_at_diagnostic; current_liveness_unverified",
        "coverage_kind": "bounded_diagnostic_only; complete_tick_coverage_unverified",
    }
    folder = root / "reports/market_feed/genuine"
    path = folder / f"snapshot-{payload['session_id']}.json"
    atomic_write_json(path, payload)
    atomic_write_json(folder / "current.json", {"file": path.name, "sha256": sha256_file(path)})


def main() -> None:
    """Diagnose by default; --collect admits a finite run only after all fresh checks pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, choices=range(1, 6), default=3)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--duration-seconds", type=int, default=1800)
    args = parser.parse_args()
    if not 60 <= args.duration_seconds <= 2700:
        parser.error("Duration must be 60..2700 seconds (default 1800)")
    root = repo_root()
    settings = MT5Settings.from_root(root)
    if settings.terminal_path is None:
        print("Diagnostic disabled: explicit terminal/demo pins unavailable; use offline collector")
        raise SystemExit(2)
    feed: MT5Feed | None = None
    mcp: ReadOnlyMCP | None = None
    try:
        config = load_feed_config(root / "config/mt5_feed.yaml")
        config = config.model_copy(
            update={"max_polls": args.duration_seconds // int(config.poll_seconds) + 1}
        )
        feed = MT5Feed(
            PythonReader(),
            config,
            terminal_path=settings.terminal_path,
            login=settings.demo_login.get_secret_value(),
            server=settings.demo_server,
        )
        mcp = ReadOnlyMCP(
            settings.mcp_token.get_secret_value(),
            login=settings.demo_login.get_secret_value(),
            server=settings.demo_server,
            symbols=config.symbols,
        )
        version = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True
        ).strip()
        with collector_lease(root / "data/mt5_feed/collector.lock"):
            store = FeedStore(root, config, code_version=version)
            try:
                report = diagnostic_session(feed, mcp, store, samples=args.samples)
                publish_diagnostic(root, report)
                path = (
                    root
                    / "reports/mt5"
                    / (
                        "P11a.1-"
                        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                        + "-"
                        + uuid4().hex[:8]
                        + ".json"
                    )
                )
                atomic_write_json(path, report)
                print(
                    json.dumps(
                        {
                            "report": path.relative_to(root).as_posix(),
                            "admission": report["admission"],
                            "counts": report["counts"],
                            "p11b_go": False,
                        },
                        indent=2,
                    )
                )
                if args.collect:
                    if (
                        not report["admission"]["security_passed"]
                        or not report["admission"]["clock_passed"]
                        or report["admission"]["reasons"]
                    ):
                        raise FeedUnavailable("Extended collection blocked by diagnostic admission")
                    monitor = AdmissionMonitor(feed, mcp)
                    result = Collector(
                        feed, store, root / "reports/market_feed/genuine", admission=monitor
                    ).run(max_polls=config.max_polls, duration_seconds=args.duration_seconds)
                    print(json.dumps({"bounded_run_counts": result["counts"]}))
            finally:
                store.close()
    except (FeedUnavailable, ValueError, OSError):
        print(
            "Genuine acquisition refused/unavailable. No data qualification claimed; inspect the diagnostic and local guide."
        )
        raise SystemExit(2) from None
    finally:
        if feed:
            feed.close()
        if mcp:
            mcp.close()


if __name__ == "__main__":
    main()
