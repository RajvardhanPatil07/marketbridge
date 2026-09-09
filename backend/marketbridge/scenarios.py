"""Synthetic fixture registry and receipt-ordered trace production."""

import json
import os
from pathlib import Path

from .engine import Engine
from .models import DATA_MODE, MODEL_VERSION, SYMBOLS

SCENARIO_DESCRIPTIONS = {
    "normal": (
        "Normal market",
        "Fresh synthetic stock and QQQ observations remain consistent.",
        "A qualified reference follows small changes with visible source provenance.",
    ),
    "bad-print": (
        "Isolated bad print",
        "At second 24, one simulated feed prints a 24% unsupported drop.",
        "Quarantine the isolated observation; recover when that feed returns to the supported price.",
    ),
    "genuine-move": (
        "Corroborated repricing",
        "A genuine synthetic 18% stock-specific drop arrives at 24; an independent family confirms at 27.",
        "Abstain before corroboration and admit the move at 27, even with a flat QQQ factor.",
    ),
    "dropout": (
        "Feed dropout",
        "Underlying observations stop after second 20 and resume at 44 while QQQ continues.",
        "After five seconds show caution, after ten abstain, and recover when fresh evidence returns.",
    ),
    "reopening": (
        "Verified reopening",
        "A closure is followed by a verified synthetic primary opening-auction observation at second 24.",
        "Only the verified official-auction type permits single-reference jump recovery.",
    ),
    "single-source": (
        "Single-source jump",
        "An 18% genuine synthetic drop appears only through one original family and its reseller.",
        "Remain abstained: a reseller and repeated prints do not create independent corroboration.",
    ),
    "clock-skew": (
        "Future-dated observation",
        "At second 25, one stock observation claims an event time ten seconds in the future.",
        "Reject the impossible clock ordering without moving the defended reference.",
    ),
    "crossed-market": (
        "Crossed market",
        "At second 25, one observation carries a bid above its ask.",
        "Reject the malformed market representation before it reaches consensus.",
    ),
    "replayed-tick": (
        "Replayed stale tick",
        "At second 25, a source replays an event older than its previously accepted update.",
        "Reject the rewind and preserve receipt-ordered state.",
    ),
    "overnight-collapse": (
        "Overnight source collapse",
        "All stock witnesses disappear after second 20 while the broad factor continues, then recover at 44.",
        "Widen uncertainty, block exposure after the freshness limit, and recover only on fresh evidence.",
    ),
}

DERIVED_SCENARIOS = {
    "clock-skew": "normal",
    "crossed-market": "normal",
    "replayed-tick": "normal",
    "overnight-collapse": "dropout",
}


def fixture_root() -> Path:
    return Path(os.environ.get("MARKETBRIDGE_FIXTURE_DIR", Path(__file__).resolve().parents[2] / "fixtures"))


def load_fixture(scenario_id: str, symbol: str) -> list[dict]:
    if scenario_id not in SCENARIO_DESCRIPTIONS:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    if symbol not in SYMBOLS:
        raise ValueError(f"Unsupported symbol: {symbol}")
    fixture_id = DERIVED_SCENARIOS.get(scenario_id, scenario_id)
    rows = [
        json.loads(line)
        for line in (fixture_root() / f"{fixture_id}-{symbol}.jsonl").read_text().splitlines()
        if line
    ]
    if not rows or rows[0].get("data_mode") != DATA_MODE:
        raise ValueError("Only explicitly synthetic fixtures are permitted")
    if scenario_id in DERIVED_SCENARIOS:
        for row in rows:
            if row.get("kind") == "metadata":
                row["scenario_id"] = scenario_id
            if fixture_id in str(row.get("id", "")):
                row["id"] = str(row["id"]).replace(fixture_id, scenario_id, 1)
            if row.get("kind") != "observation" or row.get("source_id") != "iex" or row.get("received_at") != 25:
                continue
            if scenario_id == "clock-skew":
                row["event_time"] = row["received_at"] + 10
            elif scenario_id == "crossed-market":
                row["bid"] = row["ask"] + 1
            elif scenario_id == "replayed-tick":
                row["event_time"] = row["received_at"] - 10
    return rows


def describe_scenario(scenario_id: str, rows: list[dict]) -> dict:
    title, description, expected = SCENARIO_DESCRIPTIONS[scenario_id]
    return {
        "id": scenario_id,
        "title": title,
        "description": description,
        "expected_outcome": expected,
        "duration_seconds": 60,
        "event_count": sum(row["kind"] in ("observation", "timer") for row in rows),
        "symbols": list(SYMBOLS),
    }


def list_scenarios() -> list[dict]:
    return [
        describe_scenario(scenario_id, load_fixture(scenario_id, "NVDA"))
        for scenario_id in SCENARIO_DESCRIPTIONS
    ]


def run_scenario(scenario_id: str, symbol: str = "NVDA") -> dict:
    from .evaluation import evaluate_trace

    rows = load_fixture(scenario_id, symbol)
    engine = Engine(symbol)
    steps = []
    truth = {}
    outcome = None
    for row in rows:
        kind = row["kind"]
        if kind in ("observation", "timer"):
            engine.process(row)
            if kind == "timer":
                steps.append(engine.snapshot(len(steps), row["received_at"]))
        elif kind == "truth":
            truth[row["received_at"]] = row["price"]
        elif kind == "outcome":
            outcome = row["price"]
    assumptions = [
        "Every input, price, source role, reference and outcome is synthetic. No live feeds are connected.",
        "Original receipt/ingestion order and explicit timer events determine state; evaluation truth never enters the pricing engine.",
        "Reference uses qualified synthetic stock anchors and a unit-beta QQQ update; no fitted model or real-stock accuracy is claimed.",
        "Step.baseline is the fixed-anchor unit-beta QQQ benchmark; comparator is the unguarded primary quote. Baseline account and baseline MAE refer to that unguarded quote.",
        "Model range is uncalibrated: an illustrative 25-basis-point half-width plus 5 basis points per second of underlying age. No coverage guarantee.",
        "Source weights identify actual stock-anchor contributions; the QQQ factor is a separate ratio input, not another independent stock vote.",
        "Each policy starts with one long share, initial equity equal to 20% of initial notional, maintenance equity 10% of initial notional, and zero funding and fees.",
        "Liquidation occurs once when valued equity falls below maintenance; the hypothetical fill equals that policy's trigger reference. This is a synthetic execution assumption, not a venue reproduction.",
        "A liquidated position remains closed and retains its exit equity. All remaining positions use the same independent synthetic final outcome for ex-post solvency scoring.",
        "Unresolved current valuations block new exposure and are not zero loss. Ex-post final equity may be known even when the current published reference remains unavailable.",
        "New-exposure limits are advisory simulator states; this fixed-position experiment does not open additional positions.",
        "Official-auction recovery is a verified synthetic fixture type; ordinary IEX-like prints and resellers cannot invoke it.",
    ]
    result = {
        "scenario": describe_scenario(scenario_id, rows),
        "symbol": symbol,
        "initial_price": SYMBOLS[symbol],
        "model_version": MODEL_VERSION,
        "data_mode": DATA_MODE,
        "steps": steps,
        "assumptions": assumptions,
        "metrics": evaluate_trace(scenario_id, steps, truth, outcome, engine),
    }
    json.dumps(result, allow_nan=False)
    return result
