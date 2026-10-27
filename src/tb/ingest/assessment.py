"""P11a.2 finite read-only source assessment; reporting never promotes a clock profile."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from tb.core.config import repo_root
from tb.ingest.clock_profiles import load_profiles
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.mt5.adapter import MT5Feed, PythonReader
from tb.ingest.mt5.cli import collector_lease
from tb.ingest.mt5.diagnostics import diagnostic_session, publish_diagnostic
from tb.ingest.mt5.mcp import ReadOnlyMCP
from tb.ingest.mt5.models import FeedUnavailable, load_feed_config
from tb.ingest.mt5.settings import MT5Settings
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.oanda import OandaSettings


def source_version(root: Path) -> str:
    """Fingerprint public runtime source/config, including uncommitted phase implementation."""
    digest = hashlib.sha256()
    files = [*root.glob("src/**/*.py"), *root.glob("config/**/*.yaml")]
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    commit = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True
    ).strip()
    return commit + "+tree." + digest.hexdigest()


def main() -> None:
    """Produce evidence and a fresh read-only snapshot without starting an extended run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, choices=range(1, 6), default=5)
    args = parser.parse_args()
    root = repo_root()
    profiles = load_profiles(root / "config/source_clocks.yaml")
    settings = MT5Settings.from_root(root)
    alternative = OandaSettings.from_root(root)
    report: dict[str, Any] = {
        "phase": "P11a.2",
        "observed_at": datetime.now(UTC).isoformat(),
        "source_version": source_version(root),
        "profiles": [p.model_dump(mode="json") for p in profiles],
        "external_orders_enabled": False,
        "extended_collection_started": False,
        "p11b": {"EURUSD": "NO-GO", "XAUUSD": "NO-GO"},
        "alternatives": {
            "oanda_practice": {
                "credentials_present": bool(
                    alternative.token.get_secret_value()
                    and alternative.account_id.get_secret_value()
                ),
                "genuine_connection": "not_attempted; region/API/rights approval unverified",
                "pakistan_access": "UNVERIFIED",
                "clock_profile": "not_genuinely_verified",
                "note": "Official v20 excludes Global Markets/TMS; no account created",
            },
            "separate_mt5_demo": {
                "candidate": "Pepperstone",
                "genuine_connection": "not_configured_or_attempted",
                "pakistan_access": "current demo/research access UNVERIFIED; dated official affiliate list includes Pakistan",
                "clock_profile": "no exact server/build/SDK validation; published US-DST +2/+3 not applied to MetaQuotes",
            },
        },
    }
    feed: MT5Feed | None = None
    mcp: ReadOnlyMCP | None = None
    try:
        if settings.terminal_path is None:
            raise FeedUnavailable("MT5 terminal pins unavailable")
        config = load_feed_config(root / "config/mt5_feed.yaml")
        profile = next(
            (p for p in profiles if p.provider == "mt5_demo" and p.server == settings.demo_server),
            None,
        )
        feed = MT5Feed(
            PythonReader(),
            config,
            terminal_path=settings.terminal_path,
            login=settings.demo_login.get_secret_value(),
            server=settings.demo_server,
            clock_profile=profile,
        )
        mcp = ReadOnlyMCP(
            settings.mcp_token.get_secret_value(),
            login=settings.demo_login.get_secret_value(),
            server=settings.demo_server,
            symbols=config.symbols,
        )
        with collector_lease(root / "data/mt5_feed/collector.lock"):
            store = FeedStore(root, config, code_version=report["source_version"])
            try:
                measured = diagnostic_session(feed, mcp, store, samples=args.samples)
            finally:
                store.close()
        report["mt5"] = measured
        diagnostics: list[dict[str, Any]] = []
        for symbol in config.symbols:
            rows = [r for r in measured["samples"] if r["symbol"] == symbol]
            last = rows[-1]
            raw_at = last.get("source_milliseconds_utc")
            native_wall = last.get("mcp_marketwatch", {}).get("symbols", [{}])[0].get("update_time")
            agreement: float | None = None
            if raw_at and native_wall:
                # Compare wall components only; never convert naive native time into UTC.
                agreement = (
                    datetime.fromisoformat(raw_at).replace(tzinfo=None)
                    - datetime.fromisoformat(native_wall).replace(tzinfo=None)
                ).total_seconds()
            diagnostics.append(
                {
                    "Market": symbol,
                    "Raw epoch as UTC (unqualified)": raw_at,
                    "Normalized UTC": None,
                    "Receipt UTC": last.get("received_utc"),
                    "Raw minus receipt seconds": last.get("source_minus_receipt_seconds"),
                    "SDK minus MCP wall seconds (sequential)": agreement,
                    "Native wall text (zone unverified)": native_wall,
                }
            )
            report["p11b"][symbol] = "NO-GO: authoritative source clock profile unavailable"
            facts = measured["readiness"].get(symbol, {}).get("facts", {})
            if facts.get("visible") is False:
                report["p11b"][symbol] += "; exact instrument currently hidden"
        # Reuse the existing safe display publisher; enrich only the new snapshot.
        publish_diagnostic(root, measured)
        folder = root / "reports/market_feed/genuine"
        import json

        pointer = json.loads((folder / "current.json").read_text(encoding="utf-8"))
        snapshot = json.loads((folder / pointer["file"]).read_text(encoding="utf-8"))
        snapshot["clock_profiles"] = {
            s: {
                "profile_id": profile.profile_id if profile else "unavailable",
                "digest": profile.digest if profile else "unavailable",
                "state": profile.effective_state(datetime.now(UTC)).value
                if profile
                else "UNVERIFIED",
            }
            for s in config.symbols
        }
        snapshot["clock_diagnostics"] = diagnostics
        snapshot["readiness"] = {
            s: {
                "p11b": report["p11b"][s],
                "data_qualified": False,
                "strategy_ready": False,
                "sizing_usable": False,
            }
            for s in config.symbols
        }
        # New immutable payload rather than editing the publisher's or any earlier snapshot.
        enriched = folder / f"snapshot-P11a.2-{uuid4().hex}.json"
        atomic_write_json(enriched, snapshot)
        atomic_write_json(
            folder / "current.json", {"file": enriched.name, "sha256": sha256_file(enriched)}
        )
        report["clock_diagnostics"] = diagnostics
    except (FeedUnavailable, ValueError, OSError, KeyError, IndexError):
        report["mt5_status"] = "diagnostic_unavailable_or_refused; no qualification claimed"
    finally:
        if feed:
            feed.close()
        if mcp:
            mcp.close()
    output = (
        root
        / "reports/mt5"
        / (
            "P11a.2-"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid4().hex[:8]
            + ".json"
        )
    )
    atomic_write_json(output, report)
    print(output.relative_to(root).as_posix())
    print(
        "Assessment complete. Profiles are not auto-promoted; inspect per-instrument NO-GO reasons."
    )


if __name__ == "__main__":
    main()
