"""Measure the in-process shadow decision path without provider/network time."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from statistics import median
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from marketbridge.shadow import NormalizedObservation, ShadowOracle  # noqa: E402


def main(samples: int = 10_000) -> dict:
    oracle = ShadowOracle()
    start = datetime.now(timezone.utc)
    latencies = []
    for index in range(samples):
        moment = start + timedelta(microseconds=index)
        family = "equity-venue:Q" if index % 2 == 0 else "equity-venue:V"
        venue = "Q" if index % 2 == 0 else "V"
        decision = oracle.ingest(NormalizedObservation(
            symbol="NVDA", price=230 + (index % 7) * 0.001, event_time=moment, received_at=moment,
            source_id="benchmark", source_family=family, venue=venue, eligible=True,
        ))
        latencies.append(decision["decision_latency_ms"])
    ordered = sorted(latencies)
    report = {
        "benchmark": "in_process_shadow_decision",
        "samples": samples,
        "p50_ms": median(ordered),
        "p95_ms": ordered[round((samples - 1) * 0.95)],
        "p99_ms": ordered[round((samples - 1) * 0.99)],
        "max_ms": max(ordered),
        "excludes": ["provider network", "browser delivery", "asynchronous audit persistence"],
    }
    target = ROOT / "artifacts" / "shadow-latency.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
