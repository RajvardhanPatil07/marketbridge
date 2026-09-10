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
    if not configuration["execution_evidence_configured"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    result["runtime_probe"] = probe_alpaca_subscription()
    secondary_configured = any(
        configuration[provider]["credentials_configured"]
        for provider in ("databento", "twelve_data")
    )
    result["secondary_provider_runtime_check"] = (
        "DEFERRED_TO_PIPELINE_HEALTH" if secondary_configured else "NOT_CONFIGURED"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    alpaca_ready_for_path = result["runtime_probe"]["runtime_eligible"] or (
        result["runtime_probe"]["subscribed"] and secondary_configured
    )
    return 0 if alpaca_ready_for_path else 1


if __name__ == "__main__":
    raise SystemExit(main())
