"""Isolated DecisionLedger with atomic processed events and append-only hash checkpoints."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from tb.core.leases import WriterBusy
from tb.core.leases import writer_lease as collector_lease
from tb.ingest.history.core import atomic_write_json, sha256_bytes
from tb.ingest.mt5.models import FeedUnavailable
from tb.ledger.store import DecisionLedger, LedgerVersions
from tb.shadow.models import (
    ResearchDecision,
    ShadowConfig,
    ShadowEvent,
    SourcePin,
)


class ShadowRefused(FeedUnavailable):
    """Fail-closed reference consumer state; never repairs or clears evidence automatically."""


def digest(value: object) -> str:
    return sha256_bytes(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    )


def schema_digest(db: sqlite3.Connection) -> str:
    """Pin every table, index and append-only trigger, including unexpected additions."""
    return digest(
        [
            tuple(row)
            for row in db.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )
        ]
    )


class ShadowJournal:
    """One OS-held writer with FULL-sync transactions and validated recovery."""

    def __init__(
        self, folder: Path, pin: SourcePin, config: ShadowConfig, *, create: bool = False
    ) -> None:
        self.folder, self.pin, self.config = folder.resolve(), pin, config
        SourcePin.model_validate(pin.model_dump())
        ShadowConfig.model_validate(config.model_dump())
        if pin.config_digest != digest(config.model_dump(mode="json")):
            raise ShadowRefused("shadow_configuration_version_changed")
        self.path = self.folder / "journal.sqlite"
        self.meta = self.folder / "journal.meta.json"
        self._lease = collector_lease(self.folder / "consumer.lock")
        try:
            self.handle = self._lease.__enter__()
        except WriterBusy:
            raise ShadowRefused("Another market-data collector holds this workspace") from None
        self.closed = False
        self.poisoned = False
        try:
            exists = self.path.exists()
            if exists != self.meta.exists() or (not exists and not create):
                raise ShadowRefused(
                    "shadow_journal_or_metadata_missing; explicit initialization required"
                )
            expected: dict[str, Any] = {
                "schema": "shadow-v1",
                "pin": pin.model_dump(mode="json"),
                "pin_sha256": pin.digest,
            }
            if config.reference_strategies is not None:
                expected["evaluation_protocol"] = config.evaluation.model_dump(mode="json")
            if exists:
                if self.meta.stat().st_size > 32768:
                    raise ShadowRefused("shadow_manifest_size_refused")
                saved = json.loads(self.meta.read_text(encoding="utf-8"))
                if not isinstance(saved, dict):
                    raise ShadowRefused("shadow_manifest_object_required")
                saved_schema = saved.pop("schema_sha256", None)
                if saved != expected:
                    raise ShadowRefused("shadow_manifest_or_source_version_mismatch")
                with closing(sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)) as check:
                    if check.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ShadowRefused("shadow_journal_corrupt")
                    if saved_schema != schema_digest(check):
                        raise ShadowRefused("shadow_schema_mismatch_no_repair")
            self.ledger = DecisionLedger(self.path, initialize=not exists)
            self.db = self.ledger.connect()
            self.db.execute("PRAGMA synchronous=FULL")
            if not exists:
                self._initialize()
                expected["schema_sha256"] = schema_digest(self.db)
                atomic_write_json(self.meta, expected)
            self.verify()
        except (ValueError, OSError, sqlite3.Error) as exc:
            if hasattr(self, "db"):
                self.db.close()
            self._lease.__exit__(None, None, None)
            self.closed = True
            if isinstance(exc, ShadowRefused):
                raise
            if isinstance(exc, FeedUnavailable):
                raise ShadowRefused("shadow_retention_or_current_rights_refused") from None
            raise ShadowRefused("shadow_startup_integrity_or_identity_refused") from None

    def _initialize(self) -> None:
        """Create a new journal only; existing schemas never pass through this path."""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS shadow_events(seq INTEGER PRIMARY KEY, id TEXT UNIQUE,
                evidence TEXT, symbol TEXT, opening TEXT, payload TEXT, digest TEXT);
            CREATE TABLE IF NOT EXISTS shadow_checkpoints(seq INTEGER PRIMARY KEY,
                event_id TEXT UNIQUE, previous TEXT, digest TEXT, decisions_digest TEXT);
            CREATE TABLE IF NOT EXISTS shadow_health(seq INTEGER PRIMARY KEY, payload TEXT);
            CREATE TABLE IF NOT EXISTS shadow_labels(id TEXT PRIMARY KEY, payload TEXT, digest TEXT);
            CREATE TABLE IF NOT EXISTS shadow_retention(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        """)
        if self.config.reference_strategies is not None:
            self.db.executescript("""
                CREATE INDEX IF NOT EXISTS shadow_event_symbol_time ON shadow_events(symbol, opening);
                CREATE INDEX IF NOT EXISTS shadow_decision_symbol_time ON decisions(json_extract(payload_json,'$.symbol'), json_extract(payload_json,'$.decision_at'));
                CREATE INDEX IF NOT EXISTS shadow_label_decision_horizon ON shadow_labels(json_extract(payload,'$.decision_id'), json_extract(payload,'$.horizon_m5'));
            """)
        for table in (
            "shadow_events",
            "shadow_checkpoints",
            "shadow_health",
            "shadow_labels",
            "shadow_retention",
        ):
            for action in ("UPDATE", "DELETE"):
                self.db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only shadow'); END"
                )
        self.db.commit()

    def require_writer(self) -> None:
        if (
            self.closed
            or self.poisoned
            or self.handle.closed
            or not (self.folder / "consumer.lock").exists()
        ):
            raise ShadowRefused("shadow_writer_lease_lost_or_restart_required")
        if os.fstat(self.handle.fileno()).st_ino != (self.folder / "consumer.lock").stat().st_ino:
            raise ShadowRefused("shadow_writer_lock_identity_changed")

    def quota(self) -> None:
        self.require_writer()
        total = sum(p.stat().st_size for p in self.folder.rglob("*") if p.is_file())
        if (
            total + 65536 > self.config.max_storage_mb * 1048576
            or shutil.disk_usage(self.folder).free < self.config.minimum_free_bytes + 65536
        ):
            raise ShadowRefused("shadow_disk_quota_or_free_space_exhausted")

    def verify(self) -> None:
        """Stream the immutable chain; evidence, frozen decisions and checkpoint must agree."""
        self.require_retained()
        previous, count = "0" * 64, 0
        for row in self.db.execute("SELECT seq,id,payload,digest FROM shadow_events ORDER BY seq"):
            seq, event_id, payload, recorded = row
            event = ShadowEvent.model_validate_json(payload)
            if self.pin.mode == "genuine_shadow":
                retained_row = self.db.execute(
                    "SELECT payload FROM shadow_retention WHERE seq=?", (seq,)
                ).fetchone()
                if (
                    event.retention is None
                    or retained_row is None
                    or json.loads(retained_row[0]) != event.retention.model_dump(mode="json")
                    or event.retention.acquired_at > event.observation.received_at
                ):
                    raise ShadowRefused("shadow_retention_event_binding_failed")
                from tb.core.config import repo_root
                from tb.ingest.history.core import sha256_file
                from tb.shadow.source import read_committed

                source_root = repo_root()
                manifest = (source_root / (event.manifest_path or "")).resolve()
                if (
                    not manifest.is_relative_to(source_root / "data/bronze/twelve_data")
                    or sha256_file(manifest) != event.manifest_sha256
                ):
                    raise ShadowRefused("shadow_recovery_source_manifest_missing_or_corrupt")
                if not any(
                    e.evidence_id == event.evidence_id
                    for e in read_committed(source_root, manifest, self.pin)
                ):
                    raise ShadowRefused("shadow_recovery_source_evidence_missing")
            if (
                event.pin != self.pin
                or event.interval_id != event_id
                or digest(json.loads(payload)) != recorded
                or seq != count + 1
            ):
                raise ShadowRefused("shadow_input_integrity_failed")
            decisions = [
                json.loads(r[0])
                for r in self.db.execute(
                    "SELECT payload_json FROM decisions WHERE json_extract(payload_json,'$.event_id')=? ORDER BY id",
                    (event_id,),
                )
            ]
            if len(decisions) != self.config.decision_count:
                raise ShadowRefused("shadow_incomplete_atomic_decision_set")
            for decision in decisions:
                ResearchDecision.model_validate(decision)
            self._validate_decisions([ResearchDecision.model_validate(d) for d in decisions])
            aggregate = digest(decisions)
            chain = digest([previous, recorded, aggregate])
            check = self.db.execute(
                "SELECT previous,digest,decisions_digest,event_id FROM shadow_checkpoints WHERE seq=?",
                (seq,),
            ).fetchone()
            if check is None or tuple(check) != (previous, chain, aggregate, event_id):
                raise ShadowRefused("shadow_checkpoint_integrity_failed")
            previous, count = chain, count + 1
        if (
            self.db.execute("SELECT COUNT(*) FROM shadow_checkpoints").fetchone()[0] != count
            or self.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            != count * self.config.decision_count
        ):
            raise ShadowRefused("shadow_orphan_or_missing_journal_state")
        for label in self.db.execute("SELECT payload,digest FROM shadow_labels"):
            if digest(json.loads(label[0])) != label[1]:
                raise ShadowRefused("shadow_label_integrity_failed")

    def events(self) -> Iterator[ShadowEvent]:
        self.require_retained()
        for row in self.db.execute("SELECT payload FROM shadow_events ORDER BY seq"):
            yield ShadowEvent.model_validate_json(row[0])

    def require_retained(self) -> None:
        """Check current documentary scope and non-price lifetimes before journal reuse."""
        if self.pin.mode != "genuine_shadow":
            return
        from datetime import UTC

        from tb.core.config import repo_root
        from tb.ingest.retention import require_lifetime
        from tb.ingest.rights_review import check_review

        root, now = repo_root(), datetime.now(UTC)
        rights = check_review(root, root / "config/data_rights.yaml", now)
        if (
            rights.digest != self.pin.rights_digest
            or rights.account_fingerprint != self.pin.identity
        ):
            raise ShadowRefused("shadow_current_rights_changed")
        for (payload,) in self.db.execute("SELECT payload FROM shadow_retention"):
            require_lifetime(rights, json.loads(payload), now)
        if (
            self.db.execute("SELECT COUNT(*) FROM shadow_retention").fetchone()[0]
            != self.db.execute("SELECT COUNT(*) FROM shadow_events").fetchone()[0]
        ):
            raise ShadowRefused("shadow_retention_manifest_missing")

    def _validate_decisions(self, decisions: list[ResearchDecision]) -> None:
        from tb.strategies.reference import REFERENCE_STRATEGIES

        expected = {"do_nothing", "london_sweep_mss_fvg", "trend_vwap_pullback", "xaut_catch_up"}
        if self.config.reference_strategies is not None:
            expected.update(REFERENCE_STRATEGIES)
        for decision in decisions:
            ResearchDecision.model_validate(decision.model_dump())
            if decision.strategy in REFERENCE_STRATEGIES and (
                self.config.reference_strategies is None
                or decision.strategy_config
                != self.config.reference_strategies.model_dump(mode="json")
            ):
                raise ShadowRefused("shadow_reference_strategy_configuration_mismatch")
        if {d.strategy for d in decisions} != expected or any(
            d.strategy_version != self.config.strategy_version
            or d.feature_version != self.config.feature_version
            or digest(d.features) != d.features_sha256
            or (d.strategy_config and digest(d.strategy_config) != d.strategy_config_sha256)
            for d in decisions
        ):
            raise ShadowRefused("shadow_strategy_set_or_version_hash_mismatch")

    def existing(self, event: ShadowEvent) -> str | None:
        row = self.db.execute(
            "SELECT evidence FROM shadow_events WHERE id=?", (event.interval_id,)
        ).fetchone()
        return str(row[0]) if row else None

    def commit(
        self,
        event: ShadowEvent,
        decisions: list[ResearchDecision],
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        self.quota()
        self.require_retained()
        if self.pin.mode == "genuine_shadow":
            from datetime import UTC

            from tb.core.config import repo_root
            from tb.ingest.retention import require_lifetime
            from tb.ingest.rights_review import check_review

            root, now = repo_root(), datetime.now(UTC)
            rights = check_review(root, root / "config/data_rights.yaml", now)
            retained = require_lifetime(rights, event.retention, now)
            if retained.acquired_at > event.observation.received_at:
                raise ShadowRefused("shadow_retention_acquisition_changed")
        self._validate_decisions(decisions)
        if (
            event.pin != self.pin
            or len(decisions) != self.config.decision_count
            or len({d.id for d in decisions}) != self.config.decision_count
            or any(
                d.event_id != event.interval_id or d.evidence_id != event.evidence_id
                for d in decisions
            )
        ):
            raise ShadowRefused("shadow_atomic_decision_set_invalid")
        versions = LedgerVersions(
            model_version=self.config.strategy_version,
            prompt_version="no-model",
            question_set_version="shadow-v1",
            features_version=self.config.feature_version,
        )
        try:
            self.db.execute("BEGIN IMMEDIATE")
            seq = int(
                self.db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM shadow_events").fetchone()[0]
            )
            previous_row = self.db.execute(
                "SELECT digest FROM shadow_checkpoints ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous = str(previous_row[0]) if previous_row else "0" * 64
            payload = event.model_dump(mode="json")
            if self.pin.mode == "genuine_shadow":
                assert event.retention is not None
                self.db.execute(
                    "INSERT INTO shadow_retention VALUES(?,?)",
                    (seq, event.retention.model_dump_json()),
                )
            event_digest = digest(payload)
            self.db.execute(
                "INSERT INTO shadow_events VALUES(?,?,?,?,?,?,?)",
                (
                    seq,
                    event.interval_id,
                    event.evidence_id,
                    event.observation.symbol,
                    event.observation.source_at.isoformat(),
                    json.dumps(payload),
                    event_digest,
                ),
            )
            for decision in decisions:
                self.ledger.append_atomic_decision(
                    self.db,
                    decision.model_dump(mode="json"),
                    versions,
                    row_id=decision.id,
                    created_at=decision.decision_at,
                )
            aggregate = digest(
                [d.model_dump(mode="json") for d in sorted(decisions, key=lambda d: d.id)]
            )
            chain = digest([previous, event_digest, aggregate])
            self.db.execute(
                "INSERT INTO shadow_checkpoints VALUES(?,?,?,?,?)",
                (seq, event.interval_id, previous, chain, aggregate),
            )
            if before_commit:
                before_commit()
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.poisoned = True
            raise

    def health(self, reason: str, at: datetime, **details: Any) -> None:
        self.quota()
        payload = {"at": at.isoformat(), "reason": reason, **details}
        with self.db:
            self.db.execute("INSERT INTO shadow_health(payload) VALUES(?)", (json.dumps(payload),))

    def close(self) -> None:
        if not self.closed:
            self.db.close()
            self._lease.__exit__(None, None, None)
            self.closed = True
