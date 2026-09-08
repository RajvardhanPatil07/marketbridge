"""Export clearly labeled synthetic functional checks, not a financial backtest."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from marketbridge.evaluation import evaluate_all  # noqa: E402

if __name__ == "__main__":
    result = evaluate_all()
    output = ROOT / "artifacts" / "evaluation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["summary"]))
    print(f"Synthetic functional evaluation saved to {output}")
