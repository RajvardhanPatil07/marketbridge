"""Behavioral tests for causality, source independence, and synthetic accounting."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from marketbridge.engine import Engine
from marketbridge.evaluation import evaluate_all, evaluate_trace
from marketbridge.models import PaperAccount, SYMBOLS
from marketbridge.scenarios import SCENARIO_DESCRIPTIONS, list_scenarios, load_fixture, run_scenario


def observation(source="iex", time=0, price=182.5, **overrides):
    event = {
        "kind": "observation",
        "id": f"{source}:{time}",
        "source_id": source,
        "received_at": time,
        "event_time": time,
        "price": price,
        "bid": price,
        "ask": price,
        "representation": "USD_SHARE",
    }
    event.update(overrides)
    return event


def snapshot(engine, time):
    engine.process({"kind": "timer", "received_at": time})
    return engine.snapshot(time, time)


def initialized_engine(symbol="NVDA"):
    engine = Engine(symbol)
    engine.process(observation("qqq", price=480))
    engine.process(observation(price=SYMBOLS[symbol]))
    snapshot(engine, 0)
    return engine


def replay_engine(rows, symbol):
    engine = Engine(symbol)
    steps = []
    for event in rows:
        if event["kind"] in ("timer", "observation"):
            engine.process(event)
            if event["kind"] == "timer":
                steps.append(engine.snapshot(len(steps), event["received_at"]))
    return engine, steps


@pytest.mark.parametrize("symbol", SYMBOLS)
@pytest.mark.parametrize("scenario_id", SCENARIO_DESCRIPTIONS)
def test_all_scenarios_are_deterministic_finite_and_fully_labeled(scenario_id, symbol):
    first = run_scenario(scenario_id, symbol)
    assert first == run_scenario(scenario_id, symbol)
    assert first["data_mode"] == "SYNTHETIC_TEST"
    assert first["symbol"] == symbol
    assert len(first["steps"]) == 61
    assert [step["seconds"] for step in first["steps"]] == list(range(61))
    assert all(check["passed"] for check in first["metrics"]["checks"])
    assert "uncalibrated" in " ".join(first["assumptions"]).lower()
    json.dumps(first, allow_nan=False)


@pytest.mark.parametrize("symbol", SYMBOLS)
@pytest.mark.parametrize("scenario_id", SCENARIO_DESCRIPTIONS)
def test_changing_future_events_and_truth_cannot_change_published_prefix(scenario_id, symbol):
    rows = load_fixture(scenario_id, symbol)
    _, original = replay_engine(rows, symbol)
    changed = deepcopy(rows)
    for event in changed:
        if event["kind"] in ("truth", "outcome"):
            event["price"] = 1.0
        if event["kind"] == "observation" and event["received_at"] > 30:
            for field in ("price", "bid", "ask"):
                event[field] *= 0.6
    _, alternate = replay_engine(changed, symbol)
    _, prefix = replay_engine([row for row in rows if row.get("received_at", 0) <= 30], symbol)
    assert original[:31] == alternate[:31] == prefix
    assert original[31:] != alternate[31:]


def test_original_timestamps_survive_duplicate_and_cached_delivery():
    engine = initialized_engine()
    original = deepcopy(engine.sources["iex"])
    engine.process(observation(time=6, price=80, id="iex:0"))
    assert engine.assessments[-1]["decision"] == "NONE"
    assert engine.sources["iex"] == original
    engine.process(observation(time=7, event_time=0, id="cached-new-http-response"))
    assert engine.sources["iex"].event_time == 0
    assert engine.last_valid_at == 0
    assert engine.last_valid == SYMBOLS["NVDA"]
    assert snapshot(engine, 7)["quality"] == "CAUTION"


def test_explicit_timer_degrades_stock_even_when_factor_keeps_updating():
    engine = initialized_engine()
    engine.process(observation("qqq", time=5, price=481))
    assert snapshot(engine, 5)["quality"] == "QUALIFIED"
    engine.process(observation("qqq", time=6, price=482))
    caution = snapshot(engine, 6)
    assert caution["quality"] == "CAUTION"
    assert caution["reference"] is not None
    assert caution["simulation"]["exposure_limit"] == 0.5
    engine.process(observation("qqq", time=11, price=483))
    absent = snapshot(engine, 11)
    assert absent["quality"] == "INSUFFICIENT_EVIDENCE"
    assert absent["reference"] is None
    assert absent["last_valid"] == SYMBOLS["NVDA"]
    assert absent["simulation"]["equity"] is None
    assert absent["simulation"]["valuation_status"] == "UNRESOLVED"
    assert absent["simulation"]["new_exposure_allowed"] is False


def test_factor_and_stock_reanchoring_does_not_double_count_returns():
    engine = initialized_engine()
    engine.process(observation("qqq", time=1, price=484.8))
    assert snapshot(engine, 1)["reference"] == pytest.approx(182.5 * 1.01)
    engine.process(observation(time=2, price=184.325))
    assert snapshot(engine, 2)["reference"] == pytest.approx(184.325)
    engine.process(observation("qqq", time=3, price=489.648))
    later = snapshot(engine, 3)
    assert later["reference"] == pytest.approx(184.325 * 1.01)
    assert later["baseline"] == pytest.approx(182.5 * 489.648 / 480)


def test_same_family_reseller_and_repeated_prices_cannot_corroborate():
    engine = initialized_engine()
    base = SYMBOLS["NVDA"]
    for time, source in ((1, "iex"), (2, "reseller"), (3, "iex"), (4, "reseller")):
        engine.process(observation(source, time=time, price=base * 0.82))
        step = snapshot(engine, time)
        assert step["reference"] is None
        assert step["quality"] == "INSUFFICIENT_EVIDENCE"
        assert step["simulation"]["new_exposure_allowed"] is False
    assert engine.recovery_seconds is None


def test_stale_independent_candidate_cannot_validate_a_later_jump():
    engine = initialized_engine()
    price = SYMBOLS["NVDA"] * 0.82
    engine.process(observation("iex", time=1, price=price))
    snapshot(engine, 1)
    engine.process(observation("independent", time=7, price=price))
    assert snapshot(engine, 7)["reference"] is None
    engine.process(observation("iex", time=8, price=price))
    assert snapshot(engine, 8)["quality"] == "RECOVERING"


def test_disagreeing_independent_candidates_do_not_form_quorum():
    engine = initialized_engine()
    engine.process(observation("iex", time=1, price=140))
    engine.process(observation("independent", time=2, price=150))
    assert snapshot(engine, 2)["reference"] is None
    assert engine.recovery_seconds is None


def test_pre_update_assessment_remains_independent_of_candidate_price():
    engine = initialized_engine()
    base = SYMBOLS["NVDA"]
    engine.process(observation(time=1, price=base * 0.82))
    first = deepcopy(engine.assessments[-1])
    assert first["decision"] == "QUARANTINE"
    assert first["pre_update_reference"] == base
    engine.process(observation("independent", time=2, price=base * 0.82))
    assert engine.assessments[-1]["pre_update_reference"] == base
    assert engine.last_valid == pytest.approx(base * 0.82)
    assert first == engine.assessments[-2]


@pytest.mark.parametrize("changes", [
    {"price": -1}, {"price": 0}, {"price": float("nan")}, {"price": float("inf")},
    {"price": "182.5"}, {"price": True}, {"bid": 200, "ask": 100},
    {"bid": 0}, {"event_time": 2}, {"event_time": -1},
    {"representation": "UNKNOWN_TOKEN"}, {"symbol": "TSLA"}, {"source_id": "unregistered"},
])
def test_malformed_observation_cannot_change_anchor_or_freshness(changes):
    engine = initialized_engine()
    engine.process(observation(time=1, **changes))
    assert engine.assessments[-1]["decision"] == "REJECT"
    assert engine.last_valid == SYMBOLS["NVDA"]
    assert engine.last_valid_at == 0
    assert engine.sources["iex"].event_time == 0


def test_receipt_order_and_late_original_time_are_preserved():
    engine = initialized_engine()
    engine.process(observation(time=3, price=183))
    published = snapshot(engine, 3)
    preserved = deepcopy(published)
    engine.process(observation(time=4, event_time=2, price=180))
    assert engine.assessments[-1]["reason"] == "LATE_EVENT_CANNOT_REWIND_SOURCE"
    assert engine.sources["iex"].event_time == 3
    assert engine.last_valid == 183
    assert published == preserved
    with pytest.raises(ValueError, match="Receipt order"):
        engine.process(observation(time=2, price=183))


def test_delayed_observation_is_not_fresh_because_http_receipt_is_recent():
    engine = initialized_engine()
    engine.process(observation(time=20, event_time=10, price=184))
    assert engine.assessments[-1]["reason"] == "OBSERVATION_ALREADY_STALE"
    assert engine.last_valid_at == 0
    assert snapshot(engine, 20)["reference"] is None


@pytest.mark.parametrize("source,verified,expected", [
    ("iex", True, "QUARANTINE"),
    ("auction", False, "REJECT"),
    ("auction", True, "ACCEPT"),
])
def test_only_verified_auction_type_can_use_single_reference_exception(source, verified, expected):
    engine = initialized_engine()
    engine.process(observation(source, time=1, price=160, official_open=True, verified=verified))
    assert engine.assessments[-1]["decision"] == expected
    if source == "auction" and verified:
        assert snapshot(engine, 1)["quality"] == "RECOVERING"
        assert engine.last_valid == 160


def test_unit_beta_benchmark_is_distinct_from_unguarded_print():
    trace = run_scenario("bad-print", "NVDA")
    step = trace["steps"][24]
    assert step["comparator"] < trace["initial_price"] * 0.8
    assert step["baseline"] > trace["initial_price"]
    assert step["reference"] is None


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_correlated_real_crash_liquidates_once_and_disallows_new_exposure(symbol):
    trace = run_scenario("genuine-move", symbol)
    initial_cash = trace["initial_price"] * 0.2
    assert trace["steps"][0]["simulation"]["equity"] == pytest.approx(initial_cash)
    assert trace["steps"][24]["simulation"]["baseline_liquidated"] is True
    assert trace["steps"][26]["simulation"]["reference_liquidated"] is False
    assert trace["steps"][27]["simulation"]["reference_liquidated"] is True
    exit_cash = trace["steps"][27]["simulation"]["equity"]
    for step in trace["steps"][27:]:
        simulation = step["simulation"]
        assert simulation["reference_liquidated"] is True
        assert simulation["new_exposure_allowed"] is False
        assert simulation["exposure_limit"] == 0
        assert simulation["equity"] == exit_cash


def test_closed_cash_is_preserved_and_negative_equity_is_not_clipped():
    account = PaperAccount(100)
    assert account.mark(100) == 20
    assert account.mark(70) == -10
    assert account.liquidated is True
    assert account.mark(150) == -10
    assert account.mark(None) == -10
    assert account.ex_post_equity(200) == -10


def test_common_ex_post_outcome_scores_liability_while_reference_abstains():
    rows = load_fixture("single-source", "NVDA")
    engine, steps = replay_engine(rows, "NVDA")
    truth = {row["received_at"]: row["price"] for row in rows if row["kind"] == "truth"}
    assert steps[-1]["reference"] is None
    assert steps[-1]["simulation"]["equity"] is None
    assert engine.reference_account.liquidated is False
    bad_outcome = SYMBOLS["NVDA"] * 0.5
    evaluated = evaluate_trace("single-source", steps, truth, bad_outcome, engine)
    assert evaluated["final_equity"] == pytest.approx(-0.3 * SYMBOLS["NVDA"])
    assert evaluated["baseline_final_equity"] == engine.baseline_account.exited_equity
    unresolved = evaluate_trace("single-source", steps, truth, None, engine)
    assert unresolved["final_equity"] is None
    assert any(not check["passed"] for check in unresolved["checks"] if check["name"] == "Common ex-post outcome")


def test_evaluation_summary_counts_cases_and_not_individual_assertions():
    report = evaluate_all()
    assert report["evaluation_kind"] == "synthetic_functional_tests"
    assert report["summary"] == {"total": 12, "passed": 12, "failed": 0}
    assert len(report["cases"]) == 12
    assert sum(len(case["metrics"]["checks"]) for case in report["cases"]) > 12


def test_registry_counts_only_events_consumed_by_engine():
    scenarios = list_scenarios()
    assert {scenario["id"] for scenario in scenarios} == set(SCENARIO_DESCRIPTIONS)
    for scenario in scenarios:
        rows = load_fixture(scenario["id"], "NVDA")
        assert scenario["event_count"] == sum(row["kind"] in ("timer", "observation") for row in rows)


def test_committed_fixture_generator_reproduces_every_payload_without_writing():
    generator_path = Path(__file__).resolve().parents[1] / "fixtures" / "generate_fixtures.py"
    spec = importlib.util.spec_from_file_location("marketbridge_fixture_generator", generator_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for scenario in SCENARIO_DESCRIPTIONS:
        for symbol in SYMBOLS:
            assert module.generate(scenario, symbol) == load_fixture(scenario, symbol)


@pytest.mark.parametrize("scenario_id,symbol", [("../../secrets", "NVDA"), ("normal", "AAPL"), ("missing", "TSLA")])
def test_unregistered_scenario_and_symbol_are_rejected(scenario_id, symbol):
    with pytest.raises(ValueError):
        run_scenario(scenario_id, symbol)
