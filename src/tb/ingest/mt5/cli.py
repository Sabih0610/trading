"""Explicit finite read-only collection and synthetic fixture entrypoints."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tb.core.config import repo_root
from tb.ingest.clock_profiles import load_profiles
from tb.ingest.mt5.adapter import MT5Feed, PythonReader
from tb.ingest.mt5.collector import Collector
from tb.ingest.mt5.fake import FakeReader
from tb.ingest.mt5.mcp import ReadOnlyMCP
from tb.ingest.mt5.models import FeedUnavailable, load_feed_config
from tb.ingest.mt5.qualification import AdmissionMonitor
from tb.ingest.mt5.settings import MT5Settings
from tb.ingest.mt5.storage import FeedStore


@contextmanager
def collector_lease(path: Path) -> Iterator[None]:
    """OS-held process lock releases on interruption; no stale PID file bypass."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl = importlib.import_module("fcntl")
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise FeedUnavailable("Another market-data collector holds this workspace") from None
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def main() -> None:
    """No-key offline path is explicit and cannot write the genuine monitoring namespace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--polls", type=int, default=2)
    parser.add_argument("--tick-history", action="store_true")
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    mcp = None
    project = repo_root()
    root = (args.root or project).resolve()
    config = load_feed_config(project / "config/mt5_feed.yaml")
    clock_value = [datetime.now(UTC) - timedelta(seconds=args.polls * config.poll_seconds + 1)]

    def fake_clock() -> datetime:
        return clock_value[0]

    def fake_sleep(seconds: float) -> None:
        clock_value[0] += timedelta(seconds=seconds)

    try:
        if args.offline:
            client = FakeReader(root / "synthetic-terminal/terminal64.exe", fake_clock)
            feed = MT5Feed(
                client,
                config,
                terminal_path=client.path,
                login=str(client.login),
                server=client.server,
                clock=fake_clock,
            )
        else:
            settings = MT5Settings.from_root(project)
            if settings.terminal_path is None:
                raise FeedUnavailable("Explicit terminal path and demo identity pins unavailable")
            feed = MT5Feed(
                PythonReader(),
                config,
                terminal_path=settings.terminal_path,
                login=settings.demo_login.get_secret_value(),
                server=settings.demo_server,
                clock_profile=next(
                    (
                        p
                        for p in load_profiles(project / "config/source_clocks.yaml")
                        if p.provider == "mt5_demo" and p.server == settings.demo_server
                    ),
                    None,
                ),
            )
            mcp = ReadOnlyMCP(
                settings.mcp_token.get_secret_value(),
                login=settings.demo_login.get_secret_value(),
                server=settings.demo_server,
                symbols=config.symbols,
            )
        version = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=project, text=True
        ).strip()
        with collector_lease(root / "data/mt5_feed/collector.lock"):
            store = FeedStore(root, config, code_version=version)
            try:
                export = root / "reports/market_feed" / ("synthetic" if args.offline else "genuine")
                collector = Collector(
                    feed,
                    store,
                    export,
                    clock=fake_clock if args.offline else None,
                    admission=AdmissionMonitor(feed, mcp) if mcp else None,
                    **({"sleep": fake_sleep} if args.offline else {}),
                )
                result = collector.run(max_polls=args.polls, tick_history=args.tick_history)
                print(
                    json.dumps(
                        {
                            "source": result["source"],
                            "polls": args.polls,
                            "health": result["health"],
                            "warnings": result["warnings"],
                            "external_orders_enabled": False,
                            "qualified_forward_quotes": sum(
                                r["evidence"] == "forward_observed" for r in result["quotes"]
                            ),
                            "collector_running": False,
                        },
                        indent=2,
                    )
                )
            finally:
                store.close()
    except (FeedUnavailable, ValueError, OSError):
        print(
            "Market feed unavailable/refused; no collection success claimed. Check the local setup guide."
        )
        raise SystemExit(2) from None
    finally:
        if mcp:
            mcp.close()


if __name__ == "__main__":
    main()
