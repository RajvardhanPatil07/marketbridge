#!/usr/bin/env python3
"""Download licensed EQUS.MINI history to Parquet for replay research."""

import argparse
import os
from pathlib import Path

import databento as db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--start", required=True, help="ISO date/time")
    parser.add_argument("--end", required=True, help="ISO date/time")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("DATABENTO_API_KEY", "").strip()
    if not key:
        raise SystemExit("DATABENTO_API_KEY is required; no sample or synthetic data will be substituted")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    store = db.Historical(key).timeseries.get_range(
        dataset="EQUS.MINI",
        schema="mbp-1",
        symbols=args.symbols,
        start=args.start,
        end=args.end,
    )
    store.to_parquet(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
