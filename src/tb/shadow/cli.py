"""Owned offline replay or explicit supervised shadow processes; never an unattended task."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from tb.core.config import repo_root
from tb.ingest.assessment import source_version
from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.rights import SHADOW_USAGES, load_rights
from tb.risk.config import load_asset_registry
from tb.shadow.fixtures import (
    FIXTURE_START,
    fixture_pin,
    fixture_rights,
    read_replay,
    write_fixture,
)
from tb.shadow.journal import ShadowJournal, ShadowRefused
from tb.shadow.models import ShadowConfig, SourcePin
from tb.shadow.reporting import publish
from tb.shadow.runtime import ShadowRuntime
from tb.shadow.source import read_committed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("replay", "watch"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bars", type=int, default=64)
    parser.add_argument("--source-pin", type=Path)
    parser.add_argument("--seconds", type=int, default=120, choices=range(1, 7201))
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    root = repo_root()
    config = ShadowConfig.model_validate(
        yaml.safe_load((root / "config/shadow.yaml").read_text(encoding="utf-8"))
    )
    code = source_version(root).split("+tree.")[-1]
    rights = (
        fixture_rights() if args.mode == "replay" else load_rights(root / "config/data_rights.yaml")
    )
    new_fixture = False
    if args.mode == "replay":
        pin = fixture_pin(config, code)
        folder = (args.output or root / "reports/shadow/fixture").resolve()
        input_path = folder / "input/input.manifest.json"
        if not input_path.exists():
            write_fixture(input_path.parent, pin, args.bars)
            new_fixture = True
        started = FIXTURE_START
    else:
        # Refuse before opening raw data, creating a genuine journal, or accessing credentials.
        for symbol in ("EURUSD", "XAUUSD"):
            rights.require(
                SHADOW_USAGES,
                provider="twelve_data",
                identity=rights.account_fingerprint or "unconfigured",
                symbol=symbol,
                now=datetime.now(UTC),
            )
        if args.source_pin is None:
            raise ShadowRefused("genuine_shadow_requires_exact_source_pin")
        pin = SourcePin.model_validate_json(args.source_pin.read_text(encoding="utf-8"))
        if pin.mode != "genuine_shadow" or pin.consumer_version != code:
            raise ShadowRefused("genuine_shadow_consumer_version_or_mode_mismatch")
        folder = (args.output or root / "reports/shadow/genuine").resolve()
        started = datetime.now(UTC)
    journal = ShadowJournal(folder / "runtime", pin, config, create=args.initialize or new_fixture)
    try:
        runtime = ShadowRuntime(journal, rights, load_asset_registry(), started_at=started)
        if args.mode == "replay":
            for event in read_replay(input_path, pin):
                runtime.process(event, event.observation.received_at + timedelta(milliseconds=1))
            runtime.stop(datetime.now(UTC))
        else:
            deadline, cursor = time.monotonic() + args.seconds, 0
            checkpoint = root / "data/twelve_data/checkpoint.sqlite"
            while time.monotonic() < deadline:
                journal.require_writer()
                rights = load_rights(root / "config/data_rights.yaml")
                if rights.digest != pin.rights_digest:
                    raise ShadowRefused("shadow_rights_version_changed")
                for symbol in ("EURUSD", "XAUUSD"):
                    rights.require(
                        SHADOW_USAGES,
                        provider=pin.provider,
                        identity=pin.identity,
                        symbol=symbol,
                        now=datetime.now(UTC),
                    )
                with sqlite3.connect(f"{checkpoint.as_uri()}?mode=ro", uri=True) as db:
                    batches = db.execute(
                        "SELECT seq,manifest,digest FROM batches WHERE seq>? ORDER BY seq LIMIT 50",
                        (cursor,),
                    ).fetchall()
                for seq, name, checksum in batches:
                    path = (root / name).resolve()
                    from tb.ingest.history.core import sha256_file

                    if (
                        not path.is_relative_to(root / "data/bronze/twelve_data")
                        or path.stat().st_size > 131072
                        or sha256_file(path) != checksum
                    ):
                        raise ShadowRefused("shadow_discovery_manifest_corrupt")
                    metadata = json.loads(path.read_text(encoding="utf-8"))
                    admitted_count = 0
                    if datetime.fromisoformat(metadata["received_at"]) >= started:
                        for event in read_committed(root, path, pin):
                            admitted_count += 1
                            try:
                                runtime.process(event, datetime.now(UTC))
                            except FeedUnavailable as exc:
                                if (
                                    journal.poisoned
                                    or "changed" in str(exc)
                                    or "rights" in str(exc)
                                ):
                                    raise
                                journal.health(str(exc), datetime.now(UTC), batch=seq)
                        if not admitted_count:
                            journal.health(
                                "skipped_batch_no_admissible_forward_rows",
                                datetime.now(UTC),
                                batch=seq,
                            )
                    cursor = seq
                last = max((v[1] for v in runtime.previous.values()), default=started)
                stale = (datetime.now(UTC) - last).total_seconds() > 600
                journal.health("stale_no_new_signals" if stale else "heartbeat", datetime.now(UTC))
                publish(journal, rights, state="stale" if stale else "running")
                time.sleep(min(10, max(0, deadline - time.monotonic())))
            runtime.stop(datetime.now(UTC))
        value = publish(journal, rights)
        print(
            json.dumps(
                {"mode": value.mode, "counts": value.counts, "orders": False, "consumer": "stopped"}
            )
        )
    except (FeedUnavailable, ValueError, OSError, sqlite3.Error):
        if not journal.poisoned:
            try:
                journal.health("runtime_refused_source_rights_or_state", datetime.now(UTC))
                publish(journal, rights, state="refused")
            except (FeedUnavailable, OSError, sqlite3.Error):
                pass
        raise
    finally:
        journal.close()


if __name__ == "__main__":
    try:
        main()
    except (FeedUnavailable, OSError, sqlite3.Error, ValueError):
        raise SystemExit(
            "Shadow refused: inspect rights, source integrity and journal health; no orders or signals submitted"
        ) from None
