"""Bounded reference acquisition using the existing store, manifests and forward classifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from tb.ingest.assessment import source_version
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.mt5.cli import collector_lease
from tb.ingest.mt5.collector import classify_forward
from tb.ingest.mt5.models import FeedConfig, FeedUnavailable, InstrumentCounts, Observation
from tb.ingest.mt5.qualification import clock_reference_passes, independent_utc
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.retention import lifetime, require_lifetime, require_projection
from tb.ingest.rights_review import check_review
from tb.ingest.twelve_data.adapter import TwelveDataFeed
from tb.ingest.twelve_data.client import (
    CreditBudget,
    EntitlementRefused,
    QuotaRefused,
    TwelveDataClient,
    TwelveDataSettings,
)
from tb.ingest.twelve_data.models import ReferenceExport, ReferenceIdentity


def publish(root: Path, value: ReferenceExport) -> Path:
    """Reuse atomic immutable snapshot + hash pointer; raw market data stays Git-ignored."""
    if value.source == "twelve_data":
        rights = check_review(root, root / "config/data_rights.yaml", datetime.now(UTC))
        retained = require_projection(rights, value.authorization, datetime.now(UTC))
        if any(
            row.received_at < retained.acquired_at for row in [*value.references, *value.candles]
        ):
            raise FeedUnavailable("reference_publication_acquisition_changed")
    folder = (
        root
        / "reports/market_feed"
        / ("twelve_data_synthetic" if value.source == "synthetic" else "twelve_data")
    )
    path = folder / f"snapshot-{uuid4().hex}.json"
    atomic_write_json(path, value.model_dump(mode="json"))
    atomic_write_json(
        folder / "current.json",
        {"file": path.name, "sha256": sha256_file(path), "authorization": value.authorization},
    )
    return path


def run(
    root: Path,
    feed: TwelveDataFeed,
    store: FeedStore,
    *,
    polls: int = 5,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
    utc_probe: Callable[[], list[dict[str, Any]]] = independent_utc,
    probe_reference: bool = False,
) -> ReferenceExport:
    """Finite 1-12 polls, at most four market requests/minute, with independent instruments.

    A restart resumes dedup/checkpoint identity but starts NEW coverage. It cannot bridge a
    downtime gap into continuous or prospective candle evidence. No scheduler is installed.
    """
    if not 1 <= polls <= 12 or store.provider != "twelve_data":
        raise FeedUnavailable("twelve_data_bounded_run_or_storage_refused")
    started = clock()
    feed.client.get("api_usage")
    identity = ReferenceIdentity(
        fingerprint=hashlib.sha256(
            ("twelve_data:" + feed.client.credential_scope).encode()
        ).hexdigest()
    )
    if not feed.synthetic:
        if feed.client.rights is None:
            raise FeedUnavailable("current_reference_rights_required")
        store.require_retained(feed.client.rights, started)
    store.last_commit()  # Verify prior committed bytes before accepting a restart.
    session, session_started = store.session(
        identity.fingerprint, started, synthetic=feed.synthetic
    )
    counts = {s: InstrumentCounts() for s in ("EURUSD", "XAUUSD")}
    references: dict[str, Observation] = {}
    bars: dict[tuple[str, datetime], Observation] = {}
    updates: dict[str, set[datetime]] = {s: set() for s in counts}
    qualified_bars: dict[str, set[datetime]] = {s: set() for s in counts}
    disabled: set[str] = set()
    warnings: set[str] = set()
    last_reasons: dict[str, str] = {}
    utc_references: list[dict[str, Any]] = []
    coverage = {s: started for s in counts}
    last_poll = started
    final: ReferenceExport | None = None
    try:
        for poll in range(polls):
            if poll:
                sleep(60)
            now = clock()
            if (now - last_poll).total_seconds() > 90 or now < last_poll:
                coverage = {s: now for s in counts}
                warnings.add("collection_gap_coverage_reset")
            last_poll = now
            passed_this_poll = {s: 0 for s in counts}
            utc_references = utc_probe()
            host_ok = clock_reference_passes(utc_references, clock())
            # This diagnostic does not equate Forex v2's 24/7 composites with an open
            # broker market. Qualify the bounded sample only in a conservative weekday window.
            active_session = now.weekday() < 5 and not (now.weekday() == 4 and now.hour >= 21)
            if not host_ok:
                warnings.add("independent_host_UTC_not_verified")
            for symbol in counts:
                if symbol in disabled:
                    continue
                endpoints = (
                    ("reference", "candle") if probe_reference and poll == 0 else ("candle",)
                )
                for endpoint in endpoints:
                    previous = counts[symbol]
                    counts[symbol] = previous.model_copy(update={"attempts": previous.attempts + 1})
                    raw: list[dict[str, Any]] = []
                    feed.latest_raw = {}
                    try:
                        if endpoint == "reference":
                            row, value = feed.reference(symbol)
                            rows, raw = [row], [value]
                        else:
                            rows, raw = feed.candles(symbol)
                        classified = [
                            classify_forward(
                                r, started, coverage_start=coverage[symbol], maximum_lag=120
                            )
                            for r in rows
                        ]
                        if not host_ok and not feed.synthetic:
                            classified = [
                                r.model_copy(
                                    update={
                                        "evidence": "historical_backfill",
                                        "coverage_started_at": None,
                                    }
                                )
                                for r in classified
                            ]
                        result = store.commit(
                            session,
                            classified,
                            raw,
                            received_at=clock(),
                            warnings=[],
                            retention=require_lifetime(
                                feed.client.rights, raw[0].get("retention"), clock()
                            )
                            if not feed.synthetic and feed.client.rights is not None
                            else None,
                        )
                        accepted = result["_accepted_rows"]
                        passed_this_poll[symbol] += 1
                        count = counts[symbol]
                        forward = [r for r in accepted if r.evidence == "forward_observed"]
                        counts[symbol] = count.model_copy(
                            update={
                                "received": count.received + len(rows),
                                "valid": count.valid + len(rows),
                                "duplicates": count.duplicates + result["duplicates"],
                                "qualified_forward": count.qualified_forward + len(forward),
                                "quote_updates": count.quote_updates
                                + sum(r.kind == "reference" for r in forward),
                            }
                        )
                        for row in accepted:
                            if row.evidence not in {"forward_observed", "synthetic"}:
                                continue
                            if row.kind == "reference":
                                references[symbol] = row
                                updates[symbol].add(row.source_at)
                            elif row.interval_complete and row.source_at >= coverage[symbol]:
                                if feed.synthetic and row.coverage_started_at is None:
                                    row = row.model_copy(
                                        update={"coverage_started_at": coverage[symbol]}
                                    )
                                bars[(symbol, row.source_at)] = row
                                qualified_bars[symbol].add(row.source_at)
                        last_reasons[symbol] = "reference_endpoint_and_UTC_response_validated"
                    except (FeedUnavailable, ValueError, KeyError, ArithmeticError) as exc:
                        # Never expose third-party payloads or exception text. Typed classes
                        # select sanitized outcomes; raw invalid observations stay internal.
                        if isinstance(exc, QuotaRefused):
                            reason = "quota_or_retry_after_refused"
                            disabled.update(counts)
                        elif isinstance(exc, EntitlementRefused):
                            reason = "instrument_endpoint_entitlement_denied"
                            if endpoint == "candle":
                                disabled.add(symbol)
                        else:
                            reason = "invalid_or_unavailable_source_response"
                        last_reasons[symbol] = reason
                        count = counts[symbol]
                        reasons = dict(count.rejected_by_reason)
                        reasons[reason] = reasons.get(reason, 0) + 1
                        counts[symbol] = count.model_copy(
                            update={"rejected": count.rejected + 1, "rejected_by_reason": reasons}
                        )
                        coverage[symbol] = clock()
                        if feed.latest_raw:
                            store.commit(
                                session,
                                [],
                                [feed.latest_raw],
                                received_at=clock(),
                                warnings=[reason],
                                retention=require_lifetime(
                                    feed.client.rights, feed.latest_raw.get("retention"), clock()
                                )
                                if not feed.synthetic and feed.client.rights is not None
                                else None,
                            )
                        if symbol in disabled:
                            break
            readiness: dict[str, dict[str, Any]] = {}
            for symbol in counts:
                times = updates[symbol]
                span = (max(times) - min(times)).total_seconds() if times else 0
                candle_times = qualified_bars[symbol]
                candle_span = (
                    (max(candle_times) - min(candle_times)).total_seconds() if candle_times else 0
                )
                ready = (
                    not feed.synthetic
                    and host_ok
                    and active_session
                    and symbol not in disabled
                    and passed_this_poll[symbol] >= 1
                    and len(candle_times) >= 3
                    and candle_span >= 120
                )
                readiness[symbol] = {
                    "source_data": "QUALIFIED_BOUNDED_M1_REFERENCE" if ready else "NO-GO",
                    "reference_updates": len(times),
                    "source_span_seconds": span,
                    "completed_forward_M1": len(qualified_bars[symbol]),
                    "completed_M1_span_seconds": candle_span,
                    "qualification_scope": "completed_M1_midpoint_OHLC_only; no_point_quote_claim",
                    "reason": last_reasons.get(symbol, "not_observed"),
                    "executable_bid_ask": False,
                    "realistic_paper_fills": False,
                    "p11b": "not_started; reference research only",
                    "candle_completion": "elapsed_UTC_interval; provider_finality_unverified",
                    "continuous_24h_reliability": "unverified",
                }
            final = ReferenceExport(
                authorization={
                    "provider": "twelve_data",
                    "identity": identity.fingerprint,
                    "rights_digest": feed.client.rights.digest,
                    "instruments": list(feed.client.rights.instruments),
                    "retention": lifetime(feed.client.rights, started).model_dump(mode="json"),
                }
                if not feed.synthetic and feed.client.rights is not None
                else None,
                source="synthetic" if feed.synthetic else "twelve_data",
                identity=identity,
                session_id=session,
                session_started=session_started,
                collection_started_at=started,
                generated_at=clock(),
                collector_running=True,
                counts=counts,
                references=list(references.values()),
                candles=list(bars.values())[-20:],
                readiness=readiness,
                incomplete_intervals=dict(feed.incomplete_intervals),
                warnings=sorted(warnings),
                plan_usage=feed.client.budget._limits(),
                utc_references=utc_references,
            )
            publish(root, final)
            store.health(
                {
                    "provider": "twelve_data",
                    "poll": poll + 1,
                    "at": clock().isoformat(),
                    "counts": {s: c.model_dump(mode="json") for s, c in counts.items()},
                }
            )
            print(
                json.dumps(
                    {
                        "poll": poll + 1,
                        "source": final.source,
                        "readiness": readiness,
                        "network_requests": feed.client.network_requests,
                    }
                ),
                flush=True,
            )
            if disabled == set(counts):
                break
    finally:
        if final:
            final = final.model_copy(update={"generated_at": clock(), "collector_running": False})
            publish(root, final)
    if final is None:
        raise FeedUnavailable("twelve_data_no_snapshot_available")
    return final


def main() -> None:
    """Opt-in bounded genuine run; missing credentials cleanly disable the component."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polls", type=int, choices=range(1, 13), default=5)
    parser.add_argument(
        "--probe-reference",
        action="store_true",
        help="One optional reference-rate probe per instrument at startup",
    )
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if not (root / "pyproject.toml").is_file():
        raise SystemExit("Run from the repository root")
    rights = check_review(root, root / "config/data_rights.yaml", datetime.now(UTC))
    settings = TwelveDataSettings.from_root(root)
    if not settings.api_key.get_secret_value().strip():
        print("Twelve Data disabled: TWELVE_DATA_API_KEY missing")
        return
    scope = hashlib.sha256(settings.api_key.get_secret_value().encode()).hexdigest()
    budget = CreditBudget(root / "data/twelve_data/credits.sqlite", scope)
    client = TwelveDataClient(settings, budget, rights=rights, rights_root=root)
    feed = TwelveDataFeed(client)
    store = FeedStore(
        root,
        FeedConfig(poll_seconds=60, max_rows=10),
        code_version=source_version(root),
        provider="twelve_data",
    )
    try:
        with collector_lease(root / "data/twelve_data/collector.lock"):
            run(root, feed, store, polls=args.polls, probe_reference=args.probe_reference)
    except FeedUnavailable as exc:
        print(str(exc))  # Only project-owned sanitized messages can cross this boundary.
        raise SystemExit(2) from None
    finally:
        feed.close()
        budget.close()
        store.close()


if __name__ == "__main__":
    main()
