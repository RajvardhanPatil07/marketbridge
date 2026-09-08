"""Synthetic functional checks, never a financial-performance backtest."""

from .models import DATA_MODE, MODEL_VERSION, SYMBOLS


def compare_policies(steps: list[dict], truth: dict) -> list[dict]:
    """Compare simple reference policies on identical synthetic observations."""
    paths: dict[str, list[float | None]] = {
        "MarketBridge guard": [step["reference"] for step in steps],
        "Unguarded feed": [step["comparator"] for step in steps],
        "Last qualified price": [step["last_valid"] for step in steps],
    }
    bounded = []
    previous = steps[0]["comparator"]
    for step in steps:
        candidate = step["comparator"]
        previous = max(previous * 0.99, min(previous * 1.01, candidate))
        bounded.append(previous)
    paths["1% bounded update"] = bounded

    comparisons = []
    for policy, values in paths.items():
        scored = [
            (value, truth[step["seconds"]])
            for step, value in zip(steps, values)
            if value is not None and step["seconds"] in truth
        ]
        errors = [abs(value / target - 1) * 10000 for value, target in scored]
        comparisons.append(
            {
                "policy": policy,
                "availability_pct": 100 * sum(value is not None for value in values) / len(values),
                "mae_bps": sum(errors) / len(errors) if errors else None,
                "worst_error_bps": max(errors) if errors else None,
                "max_step_move_pct": max(
                    (
                        abs(current / previous_value - 1) * 100
                        for previous_value, current in zip(values, values[1:])
                        if previous_value is not None and current is not None
                    ),
                    default=0,
                ),
            }
        )
    return comparisons


def evaluate_trace(scenario_id: str, steps: list[dict], truth: dict, outcome: float | None, engine) -> dict:
    answered = [step for step in steps if step["reference"] is not None and step["seconds"] in truth]
    baseline = [step for step in steps if step["seconds"] in truth]
    mae = (
        sum(abs(step["reference"] / truth[step["seconds"]] - 1) * 10000 for step in answered) / len(answered)
        if answered
        else None
    )
    baseline_mae = (
        sum(abs(step["comparator"] / truth[step["seconds"]] - 1) * 10000 for step in baseline) / len(baseline)
        if baseline
        else None
    )
    final_equity = engine.reference_account.ex_post_equity(outcome)
    baseline_final = engine.baseline_account.ex_post_equity(outcome)
    checks = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check(
        "Complete deterministic timeline",
        len(steps) == 61 and [s["seconds"] for s in steps] == list(range(61)),
        "Exactly 61 receipt-ordered snapshots, seconds 0–60.",
    )
    check(
        "Unavailable means blocked",
        all(s["reference"] is not None or not s["simulation"]["new_exposure_allowed"] for s in steps),
        "Missing reference never permits new simulated exposure.",
    )
    check(
        "Common ex-post outcome",
        outcome is not None and final_equity is not None and baseline_final is not None,
        "All remaining positions use the same independent synthetic outcome; unresolved outcomes cannot pass.",
    )
    check(
        "Permanent liquidation",
        all(
            not steps[i]["simulation"]["reference_liquidated"]
            or steps[i + 1]["simulation"]["reference_liquidated"]
            for i in range(len(steps) - 1)
        ),
        "A liquidated reference account cannot silently reopen.",
    )
    if scenario_id == "normal":
        check(
            "Normal evidence remains available",
            all(s["quality"] == "QUALIFIED" for s in steps),
            "Fresh small moves remain qualified under the fixed fixture policy.",
        )
    elif scenario_id == "bad-print":
        check(
            "Unsupported print quarantined",
            steps[24]["assessment"] == "QUARANTINE" and steps[24]["reference"] is None,
            "The isolated 24% synthetic print cannot set the guarded reference.",
        )
        check(
            "Feed correction restores evidence",
            steps[25]["reference"] is not None and not steps[25]["simulation"]["reference_liquidated"],
            "The next qualified observation restores the reference without accepting the bad print.",
        )
    elif scenario_id == "genuine-move":
        check(
            "Wait for independent evidence",
            all(steps[t]["reference"] is None for t in (24, 25, 26)),
            "Repeated updates from the first family cannot establish corroboration.",
        )
        check(
            "Admit genuine repricing",
            steps[27]["quality"] == "RECOVERING"
            and steps[27]["reference"] is not None
            and engine.recovery_seconds == 3,
            "An independent family at 27 admits the stock-specific move despite flat QQQ.",
        )
    elif scenario_id == "dropout":
        check(
            "Freshness timers degrade state",
            steps[26]["quality"] == "CAUTION" and steps[31]["quality"] == "INSUFFICIENT_EVIDENCE",
            "Underlying age >5 seconds warns; >10 seconds removes the current reference.",
        )
        check(
            "Fresh feed restores reference",
            steps[44]["reference"] is not None,
            "Evidence returns at second 44 without rewriting outage history.",
        )
    elif scenario_id == "reopening":
        check(
            "Verified auction admits reopening",
            steps[24]["quality"] == "RECOVERING"
            and "VERIFIED_SYNTHETIC_OPENING_AUCTION" in steps[24]["reasons"],
            "The official-auction fixture permits the specifically authorized single-reference exception.",
        )
    elif scenario_id == "single-source":
        check(
            "Same-family repetition cannot recover",
            all(s["reference"] is None for s in steps[24:]),
            "The genuine jump remains abstained because a reseller is not an independent family.",
        )
        check(
            "Abstention does not erase liability",
            final_equity is not None
            and final_equity < engine.reference_account.initial_equity
            and steps[-1]["simulation"]["valuation_status"] == "UNRESOLVED",
            "The final common outcome reveals the held position's loss despite unresolved current valuation.",
        )
    return {
        "availability_pct": 100 * sum(s["reference"] is not None for s in steps) / len(steps),
        "quarantined_count": engine.quarantined_count,
        "accepted_count": engine.accepted_count,
        "recovery_seconds": engine.recovery_seconds,
        "mae_bps": mae,
        "baseline_mae_bps": baseline_mae,
        "final_equity": final_equity,
        "baseline_final_equity": baseline_final,
        "policy_comparison": compare_policies(steps, truth),
        "checks": checks,
    }


def evaluate_all() -> dict:
    from .scenarios import SCENARIO_DESCRIPTIONS, run_scenario

    cases = [
        {
            "scenario_id": scenario_id,
            "symbol": symbol,
            "metrics": run_scenario(scenario_id, symbol)["metrics"],
        }
        for scenario_id in SCENARIO_DESCRIPTIONS
        for symbol in SYMBOLS
    ]
    passed = sum(all(check["passed"] for check in case["metrics"]["checks"]) for case in cases)
    return {
        "data_mode": DATA_MODE,
        "evaluation_kind": "synthetic_functional_tests",
        "model_version": MODEL_VERSION,
        "summary": {"total": len(cases), "passed": passed, "failed": len(cases) - passed},
        "cases": cases,
        "limitations": [
            "These are synthetic functional fixtures, not empirical stock forecasting or investment results.",
            "MAE scores use synthetic truth; answered-case MAE must be read with availability and abstention.",
            "The uncalibrated model range has no estimated coverage. No claim of a true weekend stock price is made.",
            "Two tickers and repeated seconds do not provide independent real-world validation.",
            "Liquidation fill-at-trigger-price, zero fees and one fixed long unit are explicit hypothetical simulator assumptions.",
            "A single-source genuine jump remains unavailable; ex-post losses are still scored against the common independent outcome.",
            "Paper methodology motivates interfaces and checks; no cited paper validates this implementation.",
        ],
        "research": [
            {
                "title": "Effective Fair Pricing of International Mutual Funds",
                "url": "https://ink.library.smu.edu.sg/lkcsb_research/1112/",
                "application": "Security-level factor adjustment precedent; does not validate US-stock weekend estimates.",
            },
            {
                "title": "Price Discovery and Trading After Hours",
                "url": "https://faculty.haas.berkeley.edu/hender/after_hours_price_discovery.pdf",
                "application": "Distinguish useful after-hours information from noisy observations; test genuine jumps as well as bad prints.",
            },
            {
                "title": "Maximum Likelihood Estimation of Factor Models with Missing Data",
                "url": "https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp1189.pdf",
                "application": "Preserve input availability; stale observations do not become fresh zero returns.",
            },
            {
                "title": "Adaptive Conformal Inference Under Distribution Shift",
                "url": "https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html",
                "application": "Keep observable forecast targets separate; demo ranges remain explicitly uncalibrated.",
            },
            {
                "title": "The Probability of Backtest Overfitting",
                "url": "https://carmamaths.org/resources/jon/backtest2.pdf",
                "application": "Freeze experiments and distinguish synthetic checks from untouched empirical evidence.",
            },
            {
                "title": "Selective Classification for Deep Neural Networks",
                "url": "https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html",
                "application": "Report answer availability and abstention alongside error; IID guarantees do not transfer here.",
            },
        ],
    }
