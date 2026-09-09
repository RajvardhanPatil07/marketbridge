#!/usr/bin/env python3
"""Export the append-only DuckDB decision store to a compressed Parquet file."""

import argparse
from pathlib import Path

from marketbridge.evidence_store import EvidenceStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("artifacts/marketbridge.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/parquet/decisions.parquet"))
    args = parser.parse_args()
    with EvidenceStore(args.database) as store:
        print(store.export_parquet(args.output))


if __name__ == "__main__":
    main()
