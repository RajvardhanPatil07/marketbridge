"""Print measured MarketBridge risk-gate operating characteristics."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from marketbridge.proof import risk_gate_benchmark  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(risk_gate_benchmark(ROOT, 50), indent=2, allow_nan=False))