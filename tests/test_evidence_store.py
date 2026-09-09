from datetime import datetime, timezone

import duckdb

from marketbridge.evidence_store import EvidenceStore
from marketbridge.shadow import NormalizedObservation, ShadowOracle


def test_decisions_round_trip_through_duckdb_and_parquet(tmp_path):
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    decision = ShadowOracle().ingest(
        NormalizedObservation("NVDA", 200, now, now, "a", "a", "Q", True)
    )
    database = tmp_path / "evidence.duckdb"
    parquet = tmp_path / "decisions.parquet"
    with EvidenceStore(database) as store:
        store.append(decision)
        store.append(decision)
        assert store.count() == 1
        store.export_parquet(parquet)
    assert duckdb.connect().execute(
        "SELECT decision_id, chain_hash FROM read_parquet(?)", [str(parquet)]
    ).fetchone() == (decision["decision_id"], decision["passport"]["chain_hash"])
