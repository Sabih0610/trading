"""Atomic local account checkpoint plus existing DecisionLedger, with replay reconciliation."""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import Any

from tb.core.leases import writer_lease
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ledger.store import DecisionLedger, LedgerVersions
from tb.paper.offline.engine import PaperReducer
from tb.paper.offline.models import (
    VERSION,
    PaperInput,
    PaperPackage,
    PaperRefused,
    PaperState,
    digest,
)
from tb.risk.config import PolicyBundle

VERSIONS = LedgerVersions(
    model_version=VERSION,
    prompt_version="none",
    question_set_version="owned-paper-only",
    features_version="shared-price-only-2.0.0",
)


def code_digest() -> str:
    """Pin all paper, risk, contract, feature, strategy, journal and lock semantics."""
    root = Path(__file__).resolve().parents[2]
    paths = [
        p
        for name in ("paper", "risk", "features", "strategies", "shadow")
        for p in (root / name).glob("*.py")
    ]
    paths += list((root / "paper/offline").glob("*.py"))
    paths += [
        root / p
        for p in (
            "core/instruments.py",
            "core/leases.py",
            "ledger/store.py",
            "ingest/broker/book.py",
            "ingest/broker/models.py",
        )
    ]
    return digest({p.relative_to(root).as_posix(): sha256_file(p) for p in sorted(set(paths))})


class PaperStore:
    """Bounded immutable owned events; a failed writer cannot continue with mutated state."""

    def __init__(
        self, folder: Path, package: PaperPackage, bundle: PolicyBundle, *, create: bool = False
    ) -> None:
        self.folder, self.package, self.bundle = folder.resolve(), package, bundle
        PaperPackage.model_validate(package.model_dump())
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "paper.sqlite"
        self.manifest = self.folder / "paper.manifest.json"
        self._lease = writer_lease(self.folder / "writer.lock")
        self.handle = self._lease.__enter__()
        self.closed, self.poisoned = False, False
        self.recovered_events = 0
        try:
            expected: dict[str, Any] = {
                "version": VERSION,
                "package": package.model_dump(mode="json"),
                "package_sha256": package.digest,
                "risk_sha256": digest(bundle.model_dump(mode="json")),
                "code_sha256": code_digest(),
                "provider": "owned_fixture",
            }
            existed = self.path.exists()
            if existed != self.manifest.exists() or (not existed and not create):
                raise PaperRefused("paper_initialization_incomplete_or_not_authorized")
            if existed:
                if (
                    self.manifest.stat().st_size > 65536
                    or json.loads(self.manifest.read_text(encoding="utf-8")) != expected
                ):
                    raise PaperRefused("paper_manifest_source_risk_or_contract_changed")
                with sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True) as check:
                    if check.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise PaperRefused("paper_database_corrupt")
                    if not check.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='paper_events'"
                    ).fetchone():
                        raise PaperRefused("paper_checkpoint_missing")
            self.ledger = DecisionLedger(self.path)
            self.db = self.ledger.connect()
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS paper_events (seq INTEGER PRIMARY KEY,id TEXT UNIQUE NOT NULL,input_json TEXT NOT NULL,payload_sha TEXT NOT NULL,effects_json TEXT NOT NULL,state_json TEXT NOT NULL,state_sha TEXT NOT NULL,chain_sha TEXT NOT NULL)"
            )
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS paper_recoveries (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)"
            )
            for action in ("UPDATE", "DELETE"):
                self.db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS paper_events_no_{action} BEFORE {action} ON paper_events BEGIN SELECT RAISE(ABORT,'append-only paper'); END"
                )
                self.db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS paper_recoveries_no_{action} BEFORE {action} ON paper_recoveries BEGIN SELECT RAISE(ABORT,'append-only recovery'); END"
                )
            self.db.commit()
            if not existed:
                atomic_write_json(self.manifest, expected)
            self.reducer = PaperReducer(package, bundle)
            self.chain = "0" * 64
            self.verify()
            if existed and self.state.events:
                self._record_recovery()
        except Exception:
            if hasattr(self, "db"):
                self.db.close()
            self._lease.__exit__(None, None, None)
            raise

    @property
    def state(self) -> PaperState:
        return self.reducer.state

    def require_writer(self) -> None:
        if self.closed or self.poisoned or self.handle.closed:
            raise PaperRefused("paper_writer_closed_or_failed")

    def _ledger_rows(
        self, event: PaperInput, effects: list[dict[str, Any]]
    ) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                digest(["paper-ledger", event.id, i]),
                {"mode": "owned_offline_paper", "input_id": event.id, **effect},
            )
            for i, effect in enumerate(effects)
        ]

    def verify(self) -> None:
        """Recompute cash/risk/transitions from inputs; hash agreement alone is insufficient."""
        rows = self.db.execute("SELECT * FROM paper_events ORDER BY seq").fetchall()
        if len(rows) > self.package.max_events:
            raise PaperRefused("paper_recovery_bound_exceeded")
        ledger_count = 0
        prefixes = {}
        for index, row in enumerate(rows, 1):
            event = PaperInput.model_validate_json(row["input_json"])
            state, effects = self.reducer.apply(event)
            state_sha = digest(state.model_dump(mode="json"))
            chain = digest(
                [
                    self.chain,
                    event.id,
                    digest(event.model_dump(mode="json")),
                    state_sha,
                    digest(effects),
                ]
            )
            if (
                row["seq"] != index
                or row["id"] != event.id
                or row["payload_sha"] != digest(event.model_dump(mode="json"))
                or row["state_sha"] != state_sha
                or json.loads(row["state_json"]) != state.model_dump(mode="json")
                or json.loads(row["effects_json"]) != effects
                or row["chain_sha"] != chain
            ):
                raise PaperRefused("paper_replay_account_or_checkpoint_mismatch")
            for identifier, payload in self._ledger_rows(event, effects):
                evidence = self.db.execute(
                    "SELECT * FROM decisions WHERE id=?", (identifier,)
                ).fetchone()
                created = event.received_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
                expected: dict[str, Any] = {
                    "id": identifier,
                    "created_at_utc": created,
                    "decision_id": None,
                    "payload": payload,
                    **VERSIONS.model_dump(),
                }
                if (
                    evidence is None
                    or json.loads(evidence["payload_json"]) != payload
                    or evidence["content_sha256"] != digest(expected)
                ):
                    raise PaperRefused("paper_decision_ledger_mismatch")
                ledger_count += 1
            self.chain = chain
            prefixes[chain] = (state.events, state_sha, event.received_at)
        if self.db.execute("SELECT count(*) FROM decisions").fetchone()[0] != ledger_count:
            raise PaperRefused("paper_unmatched_ledger_rows")
        if any(
            self.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("model_calls", "outcomes", "hypotheses")
        ):
            raise PaperRefused("paper_unexpected_evidence_table")
        recovery_count = 0
        for row in self.db.execute("SELECT id,payload_json FROM paper_recoveries"):
            payload = json.loads(row[1])
            prefix = prefixes.get(payload.get("chain_sha256"))
            if prefix is None or payload != self._recovery_payload(
                prefix[0], payload["chain_sha256"], prefix[1]
            ):
                raise PaperRefused("paper_recovery_record_mismatch")
            identifier = digest(["paper-recovery", self.package.digest, payload["chain_sha256"]])
            evidence = self.db.execute(
                "SELECT * FROM interventions WHERE id=?", (identifier,)
            ).fetchone()
            expected = {
                "id": identifier,
                "created_at_utc": prefix[2].astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "decision_id": None,
                "payload": payload,
                **VERSIONS.model_dump(),
            }
            if (
                row[0] != identifier
                or evidence is None
                or json.loads(evidence["payload_json"]) != payload
                or evidence["content_sha256"] != digest(expected)
            ):
                raise PaperRefused("paper_recovery_ledger_mismatch")
            recovery_count += 1
        if self.db.execute("SELECT count(*) FROM interventions").fetchone()[0] != recovery_count:
            raise PaperRefused("paper_unmatched_recovery_evidence")
        self.recovered_events = len(rows)

    @staticmethod
    def _recovery_payload(events: int, chain: str, state_sha: str) -> dict[str, Any]:
        return {
            "mode": "owned_offline_paper",
            "kind": "recovery_verified",
            "reason": "replayed_accounts_and_latches_reconciled",
            "events": events,
            "chain_sha256": chain,
            "state_sha256": state_sha,
        }

    def _record_recovery(self) -> None:
        payload = self._recovery_payload(
            self.state.events, self.chain, digest(self.state.model_dump(mode="json"))
        )
        identifier = digest(["paper-recovery", self.package.digest, self.chain])
        if self.db.execute("SELECT 1 FROM paper_recoveries WHERE id=?", (identifier,)).fetchone():
            return
        with self.db:
            self.db.execute(
                "INSERT INTO paper_recoveries VALUES (?,?)",
                (identifier, json.dumps(payload, sort_keys=True)),
            )
            self.ledger._append(
                "interventions",
                payload,
                VERSIONS,
                row_id=identifier,
                created_at=self.state.last_at,
                connection=self.db,
            )

    def process(self, event: PaperInput, *, fault: Callable[[str], None] | None = None) -> str:
        """One FULL-sync transaction includes all fills, balances, latches and dedup identity."""
        self.require_writer()
        payload = event.model_dump(mode="json")
        existing = self.db.execute(
            "SELECT payload_sha FROM paper_events WHERE id=?", (event.id,)
        ).fetchone()
        if existing:
            if existing[0] != digest(payload):
                raise PaperRefused("paper_frozen_input_revision_refused")
            return "duplicate"
        if (
            self.state.events >= self.package.max_events
            or shutil.disk_usage(self.folder).free < self.package.minimum_free_bytes + 65536
            or sum(p.stat().st_size for p in self.folder.glob("*") if p.is_file()) + 65536
            > self.package.max_storage_mb * 1048576
        ):
            raise PaperRefused("paper_storage_capacity_or_event_bound")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            state, effects = self.reducer.apply(event)
            if fault:
                fault("after_reduce")
            for identifier, effect in self._ledger_rows(event, effects):
                self.ledger._append(
                    "decisions",
                    effect,
                    VERSIONS,
                    row_id=identifier,
                    created_at=event.received_at,
                    connection=self.db,
                )
            if fault:
                fault("after_ledger")
            state_sha = digest(state.model_dump(mode="json"))
            chain = digest([self.chain, event.id, digest(payload), state_sha, digest(effects)])
            self.db.execute(
                "INSERT INTO paper_events VALUES (?,?,?,?,?,?,?,?)",
                (
                    state.events,
                    event.id,
                    event.model_dump_json(),
                    digest(payload),
                    json.dumps(effects, sort_keys=True),
                    state.model_dump_json(),
                    state_sha,
                    chain,
                ),
            )
            if fault:
                fault("after_checkpoint")
            self.db.commit()
            self.chain = chain
            return "committed"
        except Exception:
            self.db.rollback()
            self.poisoned = True
            raise

    def effects(self) -> list[dict[str, Any]]:
        """Bounded committed journal projection; never current in-memory uncommitted effects."""
        return [
            effect
            for row in self.db.execute("SELECT effects_json FROM paper_events ORDER BY seq")
            for effect in json.loads(row[0])
        ]

    def close(self) -> None:
        """Release the local writer; no account clearing or latch reset."""
        if not self.closed:
            self.db.close()
            self._lease.__exit__(None, None, None)
            self.closed = True
