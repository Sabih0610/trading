"""Reuse medallion commits and the existing append-only ledger in one SQLite transaction."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from tb.ingest.broker.book import integer
from tb.ingest.broker.models import (
    BrokerContract,
    BrokerIdentity,
    BrokerObservation,
    BrokerQuote,
    BrokerRefused,
    ReferenceQuoteLink,
    Symbol,
)
from tb.ingest.history.core import atomic_write_json, sha256_bytes, sha256_file
from tb.ingest.mt5.cli import collector_lease
from tb.ingest.mt5.models import FeedConfig, Observation
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.rights import SHADOW_USAGES, DataRights
from tb.ingest.rights_review import check_review, require_retention_window
from tb.ledger.store import DecisionLedger, LedgerVersions

VERSION = "broker-quote-evidence-1.0.0"
VERSIONS = LedgerVersions(
    model_version=VERSION,
    prompt_version="none",
    question_set_version="observations-only",
    features_version="none",
)


def canonical_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    )


def source_code_digest() -> str:
    """Pin the broker implementation and shared storage/accounting semantics, never data."""
    base = Path(__file__).resolve().parents[2]
    paths = list((base / "ingest/broker").glob("*.py"))
    paths += [
        base / p
        for p in (
            "core/instruments.py",
            "ingest/rights.py",
            "ingest/rights_review.py",
            "ingest/mt5/models.py",
            "ingest/mt5/storage.py",
            "ledger/store.py",
        )
    ]
    return canonical_hash({p.relative_to(base).as_posix(): sha256_file(p) for p in sorted(paths)})


class BrokerStore:
    """Exact source pin, OS lease, bounded recovery and atomic raw/quote/evidence checkpoints."""

    def __init__(
        self,
        root: Path,
        identity: BrokerIdentity,
        rights: DataRights,
        *,
        started_at: datetime,
        clock: Callable[[], datetime],
        rights_path: Path | None = None,
    ) -> None:
        self.root, self.identity, self.rights, self.clock = root.resolve(), identity, rights, clock
        self.rights_path, self.poisoned, self.closed = rights_path, False, False
        self._rights_pin = rights.digest
        self._permit(next(iter(rights.instruments)))
        if started_at > clock():
            raise BrokerRefused("broker_collection_start_in_future")
        self.folder = self.root / "data/ctrader_demo"
        self._lease = collector_lease(self.folder / "writer.lock")
        self._lease.__enter__()
        try:
            pin: dict[str, object] = {
                "version": VERSION,
                "provider": identity.provider,
                "server": identity.server,
                "identity": identity.account_fingerprint,
                "evidence": identity.evidence,
                "rights_digest": rights.digest,
                "source_code_digest": source_code_digest(),
            }
            path = self.folder / "broker.pin.json"
            exists = (self.folder / "checkpoint.sqlite").exists()
            if path.exists() != exists:
                raise BrokerRefused("broker_store_partial_initialization_refused")
            if path.exists():
                if (
                    path.stat().st_size > 8192
                    or json.loads(path.read_text(encoding="utf-8")) != pin
                ):
                    raise BrokerRefused("broker_store_provider_identity_or_rights_changed")
            self.feed = FeedStore(
                self.root,
                FeedConfig(max_rows=1, max_storage_mb=64),
                code_version=VERSION,
                provider="ctrader_demo",
            )
            self.code_digest = str(pin["source_code_digest"])
            self.feed.db.execute("PRAGMA synchronous=FULL")
            self.ledger = DecisionLedger(self.feed.db_path)
            self.feed.db.executescript("""
                CREATE TABLE IF NOT EXISTS broker_inputs(
                    seq INTEGER PRIMARY KEY,id TEXT UNIQUE NOT NULL,ledger_id TEXT UNIQUE NOT NULL,
                    previous TEXT NOT NULL,digest TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS broker_inputs_no_update BEFORE UPDATE ON broker_inputs
                    BEGIN SELECT RAISE(ABORT,'append-only table'); END;
                CREATE TRIGGER IF NOT EXISTS broker_inputs_no_delete BEFORE DELETE ON broker_inputs
                    BEGIN SELECT RAISE(ABORT,'append-only table'); END;
            """)
            self.feed.db.commit()
            if not exists:
                atomic_write_json(path, pin)
            self._recover()
            self.session, self.started_at = self.feed.session(
                identity.account_fingerprint,
                started_at,
                synthetic=identity.evidence == "owned_fixture",
            )
        except BaseException:
            if hasattr(self, "feed"):
                self.feed.close()
            self._lease.__exit__(None, None, None)
            raise

    def _permit(self, symbol: str) -> None:
        now = self.clock()
        self.identity.require(now)
        if self.poisoned or self.rights.digest != self._rights_pin:
            raise BrokerRefused("broker_store_poisoned_or_rights_changed")
        self.rights.require(
            SHADOW_USAGES,
            provider="owned_fixture"
            if self.identity.evidence == "owned_fixture"
            else "ctrader_demo",
            identity=self.identity.account_fingerprint,
            symbol=symbol,
            now=now,
        )
        if self.identity.evidence == "genuine":
            if (
                self.rights_path is None
                or check_review(self.root, self.rights_path, now, provider="ctrader_demo").digest
                != self._rights_pin
            ):
                raise BrokerRefused("broker_store_documentary_rights_unverified")
            require_retention_window(self.rights, 60)

    def refresh_identity(self, value: BrokerIdentity) -> None:
        """Only a fresh same-account/view identity can renew a running writer."""
        value.require(self.clock())
        fields = {"checked_at"}
        if value.model_dump(exclude=fields) != self.identity.model_dump(exclude=fields):
            self.poisoned = True
            raise BrokerRefused("broker_store_identity_changed")
        self.identity = value

    def _recover(self) -> None:
        """Verify every committed batch and ledger chain; orphan files never count as evidence."""
        db = self.feed.db
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise BrokerRefused("broker_checkpoint_corrupt")
        batches = db.execute("SELECT manifest,digest FROM batches ORDER BY seq").fetchmany(10001)
        if len(batches) > 10000:
            raise BrokerRefused("broker_recovery_bound_exceeded")
        for name, checksum in batches:
            path = (self.root / name).resolve()
            if (
                not path.is_relative_to(self.root)
                or path.stat().st_size > 65536
                or sha256_file(path) != checksum
            ):
                raise BrokerRefused("broker_committed_manifest_corrupt")
            commit = json.loads(path.read_text(encoding="utf-8"))
            for relative, digest in commit["files"].items():
                item = (self.root / relative).resolve()
                if not item.is_relative_to(self.root) or sha256_file(item) != digest:
                    raise BrokerRefused("broker_committed_bytes_corrupt")
        previous = ""
        rows = db.execute(
            "SELECT id,ledger_id,previous,digest FROM broker_inputs ORDER BY seq"
        ).fetchmany(10001)
        if len(rows) > 10000 or len(rows) != len(batches):
            raise BrokerRefused("broker_atomic_checkpoint_count_mismatch")
        for eid, ledger_id, prior, checkpoint in rows:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM decisions WHERE id=?", (ledger_id,)).fetchone()
            db.row_factory = None
            if row is None:
                raise BrokerRefused("broker_atomic_evidence_missing")
            evidence = {
                "id": row["id"],
                "created_at_utc": row["created_at_utc"],
                "decision_id": row["decision_id"],
                "payload": json.loads(row["payload_json"]),
                **{key: row[key] for key in VERSIONS.model_dump()},
            }
            content_hash = canonical_hash(evidence)
            if (
                content_hash != row["content_sha256"]
                or prior != previous
                or checkpoint != canonical_hash([previous, eid, content_hash])
            ):
                raise BrokerRefused("broker_evidence_hash_chain_corrupt")
            previous = checkpoint

    def record(
        self,
        symbol: Symbol,
        raw: dict[str, int | str],
        *,
        quote: BrokerQuote | None = None,
        contract: BrokerContract | None = None,
        link: ReferenceQuoteLink | None = None,
        reason: str = "raw_partial_or_refused_observation",
        fault: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Append one original market update and optional normalized/link evidence atomically."""
        self._permit(symbol)
        if not set(raw) <= {"symbolId", "timestamp", "bid", "ask"} or len(raw) > 4:
            raise BrokerRefused("broker_raw_field_refused")
        normalized = {k: integer(v) for k, v in raw.items()}
        eid = sha256_bytes(
            (self.identity.account_fingerprint + json.dumps(normalized, sort_keys=True)).encode()
        )
        if self.feed.db.execute("SELECT 1 FROM broker_inputs WHERE id=?", (eid,)).fetchone():
            return {"duplicates": 1, "rows": 0}
        if quote is not None:
            BrokerQuote.model_validate(quote.model_dump())
            if contract is not None:
                BrokerContract.model_validate(contract.model_dump())
            if (
                contract is None
                or contract.account_fingerprint != self.identity.account_fingerprint
                or contract.symbol != symbol
                or contract.evidence != self.identity.evidence
                or quote.metadata_digest != contract.digest
                or quote.event_id != eid
                or quote.symbol != symbol
                or quote.symbol_id != integer(raw.get("symbolId"))
                or quote.account_fingerprint != self.identity.account_fingerprint
                or quote.evidence != self.identity.evidence
                or quote.bid % contract.tick_size
                or quote.ask % contract.tick_size
                or quote.rights_digest != self.rights.digest
                or quote.received_at > self.clock()
                or (self.clock() - min(quote.bid_source_at, quote.ask_source_at)).total_seconds()
                > 5
            ):
                raise BrokerRefused("broker_quote_storage_scope_or_freshness_mismatch")
            watermark = self.feed.db.execute(
                "SELECT source_at FROM watermarks WHERE key=?",
                (f"{self.identity.account_fingerprint}:{symbol}:quote:tick",),
            ).fetchone()
            if watermark and quote.source_at < datetime.fromisoformat(watermark[0]):
                raise BrokerRefused("broker_restart_source_regression")
        if link is not None and (
            quote is None
            or link.symbol != symbol
            or (link.status == "observed" and link.quote_id != quote.event_id)
        ):
            raise BrokerRefused("broker_alignment_storage_scope_mismatch")
        now = self.clock()
        rows: list[Observation] = []
        if quote is not None:
            rows.append(
                BrokerObservation(
                    symbol=symbol,
                    broker_symbol=quote.broker_symbol,
                    kind="quote",
                    timeframe="tick",
                    source_at=quote.source_at,
                    received_at=quote.received_at,
                    evidence="synthetic"
                    if quote.evidence == "owned_fixture"
                    else "forward_observed",
                    source_provider="ctrader_demo",
                    source_timezone="UTC",
                    raw_source_time=quote.raw_timestamp,
                    bid=quote.bid,
                    ask=quote.ask,
                    broker_record_id=eid,
                    broker_record_json=quote.model_dump_json(),
                )
            )
        payload = {
            "kind": "broker_quote_observation" if quote else "broker_raw_observation",
            "evidence": self.identity.evidence,
            "symbol": symbol,
            "event_id": eid,
            "raw_event": raw,
            "received_at": now.isoformat(),
            "quote": quote.model_dump(mode="json") if quote else None,
            "contract": contract.model_dump(mode="json") if contract else None,
            "alignment": link.model_dump(mode="json") if link else None,
            "reason": reason,
        }

        def append(db: sqlite3.Connection, _accepted: list[Observation]) -> None:
            identifier = "broker-observation:" + eid
            self.ledger.append_atomic_decision(
                db, payload, VERSIONS, row_id=identifier, created_at=now
            )
            content = db.execute(
                "SELECT content_sha256 FROM decisions WHERE id=?", (identifier,)
            ).fetchone()[0]
            row = db.execute(
                "SELECT digest FROM broker_inputs ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous = row[0] if row else ""
            db.execute(
                "INSERT INTO broker_inputs(id,ledger_id,previous,digest) VALUES(?,?,?,?)",
                (eid, identifier, previous, canonical_hash([previous, eid, content])),
            )
            if fault:
                fault()

        try:
            return self.feed.commit(
                self.session,
                rows,
                [{"market_event": raw}],
                received_at=now,
                warnings=[] if quote else ["partial_or_refused_quote"],
                append_evidence=append,
            )
        except BaseException:
            self.poisoned = True
            raise

    def close(self) -> None:
        if not self.closed:
            self.feed.close()
            self._lease.__exit__(None, None, None)
            self.closed = True
