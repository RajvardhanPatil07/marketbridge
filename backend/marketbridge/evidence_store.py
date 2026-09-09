"""Append-only analytical storage for issued shadow-oracle decisions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import duckdb


class EvidenceStore:
    """Persist decision receipts off the pricing hot path and export Parquet snapshots."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(database_path))
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id VARCHAR PRIMARY KEY,
                issued_at TIMESTAMPTZ NOT NULL,
                decision_date DATE NOT NULL,
                symbol VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                risk_state VARCHAR NOT NULL,
                reference DOUBLE,
                confidence DOUBLE NOT NULL,
                chain_hash VARCHAR,
                payload JSON NOT NULL
            )
            """
        )

    def append(self, decision: dict) -> None:
        passport = decision.get("passport") or {}
        decision_id = str(decision["decision_id"])
        issued_at = datetime.fromisoformat(str(decision["timestamp"]).replace("Z", "+00:00"))
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=timezone.utc)
        self.connection.execute(
            """
            INSERT OR IGNORE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                decision_id,
                issued_at,
                issued_at.date(),
                decision["symbol"],
                decision["status"],
                decision["risk_state"],
                decision.get("reference"),
                decision["confidence"],
                passport.get("chain_hash"),
                json.dumps(decision, allow_nan=False, separators=(",", ":")),
            ],
        )

    def count(self) -> int:
        return self.connection.execute("SELECT count(*) FROM decisions").fetchone()[0]

    def export_parquet(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        escaped = str(output_path).replace("'", "''")
        self.connection.execute(
            f"COPY (SELECT * FROM decisions ORDER BY issued_at) TO '{escaped}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        return output_path

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "EvidenceStore":
        return self

    def __exit__(self, *_args) -> None:
        self.close()
