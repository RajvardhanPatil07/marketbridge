"""Regenerate committed deterministic fixtures: python fixtures/generate_fixtures.py."""

import json
import math
from pathlib import Path

BASES = {"NVDA": 182.5, "TSLA": 346.8}
SCENARIOS = ("normal", "bad-print", "genuine-move", "dropout", "reopening", "single-source")


def generate(scenario: str, symbol: str) -> list[dict]:
    base = BASES[symbol]
    rows = [{"kind": "metadata", "scenario_id": scenario, "symbol": symbol,
             "data_mode": "SYNTHETIC_TEST", "generator_version": "1", "duration_seconds": 60}]
    sequence = 0

    def emit(kind: str, t: int, **fields: object) -> None:
        nonlocal sequence
        sequence += 1
        rows.append({"kind": kind, "received_at": t, "ingestion_sequence": sequence, **fields})

    def observation(t: int, source: str, price: float, **fields: object) -> None:
        emit("observation", t, id=f"{scenario}:{symbol}:{source}:{t}", source_id=source,
             symbol="QQQ" if source == "qqq" else symbol, event_time=t,
             price=round(price, 8), bid=round(price * 0.9999, 8), ask=round(price * 1.0001, 8),
             representation="USD_SHARE", **fields)

    for t in range(61):
        factor = 480 * (1 + 0.00006 * t)
        truth = base * (1 + 0.00006 * t + 0.0004 * math.sin(t / 5))
        if scenario in ("genuine-move", "single-source"):
            factor = 480.0
            truth = base if t < 24 else base * 0.82 * (1 + 0.00002 * (t - 24))
        elif scenario == "reopening" and t >= 24:
            truth = base * 0.88 * (1 + 0.00006 * (t - 24))
        observation(t, "qqq", factor)
        live_primary = not (scenario == "dropout" and 21 <= t < 44)
        live_primary = live_primary and not (scenario == "reopening" and 13 <= t < 24)
        if live_primary:
            primary = truth * 0.76 if scenario == "bad-print" and t == 24 else truth
            observation(t, "iex", primary)
        # Repeated source-family updates cannot validate the single-source shock.
        if scenario == "single-source" and t % 3 == 0:
            observation(t, "reseller", truth)
        elif scenario != "single-source" and t % 3 == 0:
            independent_on = not (scenario == "genuine-move" and 24 <= t < 27)
            independent_on = independent_on and not (scenario == "dropout" and 21 <= t < 44)
            independent_on = independent_on and not (scenario == "reopening" and 13 <= t < 27)
            if independent_on:
                observation(t, "independent", truth * (1 + 0.00002 * math.sin(t)))
        if scenario == "reopening" and t == 24:
            observation(t, "auction", truth, official_open=True, verified=True)
        emit("timer", t, id=f"timer:{t}")
        # Evaluation-only truth follows the timer and is never sent into Engine.
        emit("truth", t, price=round(truth, 8))
    emit("outcome", 60, price=round(truth, 8), source_family="independent-synthetic-outcome")
    return rows


def main() -> None:
    root = Path(__file__).resolve().parent
    for scenario in SCENARIOS:
        for symbol in BASES:
            content = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in generate(scenario, symbol))
            (root / f"{scenario}-{symbol}.jsonl").write_text(content)


if __name__ == "__main__":
    main()
