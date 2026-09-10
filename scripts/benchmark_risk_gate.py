"""Print measured MarketBridge risk-gate operating characteristics."""

import json
from pathlib import Path

from marketbridge.proof import risk_gate_benchmark

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    print(json.dumps(risk_gate_benchmark(ROOT, 50), indent=2, allow_nan=False))