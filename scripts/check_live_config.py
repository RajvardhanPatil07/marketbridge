"""Validate free-first live-market configuration without printing credentials."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from marketbridge.providers import provider_registry  # noqa: E402
from marketbridge.shadow import LivePipeline, probe_alpaca_subscription  # noqa: E402


def main() -> int:
    pipeline = LivePipeline(ROOT / "artifacts" / "live-config-check.jsonl")
    configuration = pipeline.configuration()
    registry = provider_registry(pipeline.snapshot())
    result = {
        "architecture_version": registry["architecture_version"],
        "cost_mode": registry["cost_mode"],
        "configuration": configuration,
        "runtime_probe": None,
        "notes": [
            "Alpaca IEX is the free equity stream and remains one market witness.",
            "Hyperliquid is venue context and never feeds the independent underlying reference.",
            "Twelve Data is optional and is not required for the free-first demo.",
            "News/SEC/macro data are context-only.",
        ],
    }
    if configuration["errors"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    alpaca = configuration["alpaca"]
    if not alpaca["credentials_configured"]:
        result["runtime_probe"] = {"status": "NOT_CONFIGURED", "runtime_eligible": False}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if configuration["strict_live_data"] else 0

    result["runtime_probe"] = probe_alpaca_subscription()
    result["secondary_provider_runtime_check"] = (
        "OPTIONAL_TWELVE_DATA_CONFIGURED"
        if configuration.get("twelve_data", {}).get("credentials_configured")
        else "NOT_REQUIRED_FOR_FREE_DEMO"
    )
    print(json.dumps(result, indent=2, sort_keys=True))

    if configuration["strict_live_data"]:
        return 0 if result["runtime_probe"].get("runtime_eligible") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
