"""Validate live-market configuration without printing credentials."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from marketbridge.shadow import LivePipeline, probe_alpaca_subscription  # noqa: E402


def main() -> int:
    configuration = LivePipeline(ROOT / "artifacts" / "live-config-check.jsonl").configuration()
    result = {"configuration": configuration, "runtime_probe": None}
    if configuration["errors"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    if not configuration["alpaca"]["configured_multi_venue"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    result["runtime_probe"] = probe_alpaca_subscription()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["runtime_probe"]["runtime_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
