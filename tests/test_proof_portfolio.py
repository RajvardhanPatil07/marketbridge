from pathlib import Path

from marketbridge.proof import (
    historical_incident_policy_replay,
    portfolio_demo,
    risk_gate_benchmark,
)
from marketbridge.risk.models import RiskCheckRequest
from marketbridge.risk.portfolio import assess_portfolio


ROOT = Path(__file__).resolve().parents[1]


def portfolio_request():
    return RiskCheckRequest.model_validate(
        {
            "request_id": "portfolio-test-1",
            "symbol": "NVDA",
            "intent": {
                "kind": "OPEN",
                "side": "BUY",
                "notional_usd": 10000,
                "requested_leverage": 10,
            },
            "account": {
                "equity_usd": 10000,
                "margin_available_usd": 10000,
                "position_notional_usd": 22000,
                "current_leverage": 2.2,
                "liquidation_price": 140,
                "position_side": "BUY",
                "portfolio_positions": [
                    {
                        "symbol": "NVDA",
                        "notional_usd": 6000,
                        "sector": "SEMICONDUCTORS",
                        "correlation_group": "AI_COMPUTE",
                    },
                    {
                        "symbol": "AMD",
                        "notional_usd": 5000,
                        "sector": "SEMICONDUCTORS",
                        "correlation_group": "AI_COMPUTE",
                    },
                    {
                        "symbol": "MSFT",
                        "notional_usd": 4000,
                        "sector": "TECHNOLOGY",
                        "correlation_group": "MEGA_CAP_TECH",
                    },
                    {
                        "symbol": "AAPL",
                        "notional_usd": 4000,
                        "sector": "TECHNOLOGY",
                        "correlation_group": "MEGA_CAP_TECH",
                    },
                    {
                        "symbol": "TSLA",
                        "notional_usd": 3000,
                        "sector": "CONSUMER_DISCRETIONARY",
                        "correlation_group": "HIGH_BETA_GROWTH",
                    },
                ],
            },
            "market": {
                "mark_price": 184.51,
                "event_time": "2026-09-10T12:00:00Z",
                "session": "REGULAR",
            },
        }
    )


def test_portfolio_firewall_caps_single_name_concentration():
    assessment = assess_portfolio(portfolio_request())
    assert assessment["enabled"] is True
    assert "SINGLE_NAME_CONCENTRATION" in assessment["breaches"]
    assert 0 < assessment["max_additional_notional_usd"] < 10000


def test_portfolio_demo_recomputes_from_editable_inputs():
    first = portfolio_demo(
        ROOT,
        symbol="NVDA",
        requested_notional_usd=10000,
        requested_leverage=10,
        account_equity_usd=10000,
        existing_position_usd=22000,
    )
    second = portfolio_demo(
        ROOT,
        symbol="NVDA",
        requested_notional_usd=25000,
        requested_leverage=15,
        account_equity_usd=20000,
        existing_position_usd=5000,
    )
    assert first["inputs_are_editable"] is True
    assert second["order"]["requested_notional_usd"] == 25000
    assert second["order"]["requested_leverage"] == 15
    assert first["result"]["passport_id"].startswith("mbp_")
    assert second["result"]["passport_id"].startswith("mbp_")
    assert first["result"]["requested_notional_usd"] != second["result"]["requested_notional_usd"]
    assert first["result"]["portfolio_risk"]["enabled"] is True


def test_historical_reconstruction_uses_live_policy_function_without_hindsight():
    payload = historical_incident_policy_replay()
    assert payload["proof"]["same_policy_function_as_live_gate"] is True
    assert payload["proof"]["hindsight_used_by_decision"] is False
    assert payload["proof"]["data_mode"] == "HISTORICAL_RECONSTRUCTION"
    assert len(payload["timeline"]) >= 20
    assert all(
        item["action"] == "BLOCK_NEW_RISK"
        for item in payload["timeline"]
    )


def test_seeded_benchmark_reports_invariants_and_measured_latency():
    payload = risk_gate_benchmark(ROOT, 250, 20260911)
    assert payload["data_mode"] == "SYNTHETIC_POLICY_REGRESSION"
    assert payload["cases"] == 250
    assert payload["seed"] == 20260911
    assert sum(payload["actions"].values()) == 250
    assert payload["invariants"]["total_violations"] == 0
    assert payload["coverage"]["stale"] > 0
    assert payload["coverage"]["large_divergence"] > 0
    assert payload["latency"]["core_policy_ms"]["p95"] >= 0
    assert payload["latency"]["in_process_gateway_ms"]["p95"] >= 0
    assert payload["economics"]["llm_calls_in_risk_critical_path"] == 0
