"""Run the v1 API with continuously refreshed deterministic direct evidence for browser E2E."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from threading import Event, Thread

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from marketbridge.app import app  # noqa: E402
from marketbridge.api import pipeline  # noqa: E402


def seed(stop: Event) -> None:
    while not stop.is_set():
        now = datetime.now(timezone.utc)
        pipeline.ingest_direct_observation("NVDA", 200.00, now, provider="fixture-sip", venue="Q")
        pipeline.ingest_direct_observation("NVDA", 200.02, now, provider="fixture-sip", venue="V")
        pipeline.ingest_mochatrade("NVDA", 200.01, now)
        stop.wait(2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8014)
    args = parser.parse_args()
    stop = Event()
    worker = Thread(target=seed, args=(stop,), name="marketbridge-e2e-seed", daemon=True)
    worker.start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    finally:
        stop.set()
        worker.join(timeout=2)


if __name__ == "__main__":
    main()
