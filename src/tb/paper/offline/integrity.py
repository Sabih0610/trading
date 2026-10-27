"""Read-only schema and evidence checks shared by recovery and dashboard projections."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from tb.paper.offline.models import digest


def schema_digest(db: sqlite3.Connection) -> str:
    """Bind table, index and trigger definitions; reopening may never silently rebuild them."""
    return digest(
        [
            tuple(row)
            for row in db.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )
        ]
    )


def ledger_matches(row: sqlite3.Row | None, expected: dict[str, Any]) -> bool:
    """Check persisted metadata as well as its payload and canonical evidence checksum."""
    return row is not None and (
        json.loads(row["payload_json"]) == expected["payload"]
        and row["content_sha256"] == digest(expected)
        and all(row[key] == value for key, value in expected.items() if key != "payload")
    )
