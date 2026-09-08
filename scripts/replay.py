"""Export a deterministic trace from one predefined synthetic scenario."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from marketbridge.scenarios import run_scenario  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="bad-print")
    parser.add_argument("--symbol", choices=["NVDA", "TSLA"], default="NVDA")
    args = parser.parse_args()
    try:
        trace = run_scenario(args.scenario, args.symbol)
    except ValueError as error:
        parser.error(str(error))
    output = ROOT / "artifacts" / f"{args.scenario}-{args.symbol}.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(trace, indent=2, allow_nan=False) + "\n")
    print(f"Synthetic replay saved to {output}")
