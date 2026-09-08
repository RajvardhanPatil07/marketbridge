import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from marketbridge.api import app
from marketbridge import live

client = TestClient(app)


def test_catalog_and_all_traces_are_finite_and_deterministic():
    response = client.get("/v1/demo/scenarios")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["data_mode"] == "SYNTHETIC_TEST"
    assert len(catalog["scenarios"]) == 6
    for scenario in catalog["scenarios"]:
        for symbol in ["NVDA", "TSLA"]:
            url = f"/v1/demo/scenarios/{scenario['id']}?symbol={symbol}"
            trace = client.get(url)
            assert trace.status_code == 200
            data = trace.json()
            assert len(data["steps"]) == 61
            assert data["symbol"] == symbol
            assert data["data_mode"] == "SYNTHETIC_TEST"
            json.dumps(data, allow_nan=False)
            assert client.get(url).json() == data


def test_bad_inputs_and_mutations_are_rejected():
    assert client.get("/v1/demo/scenarios/no-such-scenario").status_code == 404
    assert client.get("/v1/demo/scenarios/normal?symbol=BTC").status_code == 404
    assert client.post("/v1/demo/scenarios/normal").status_code == 405
    assert client.get("/v1/missing").status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/%2e%2e/pyproject.toml").status_code == 404


def test_synthetic_evaluation_is_explicit_and_passes():
    response = client.get("/v1/demo/evaluation")
    assert response.status_code == 200
    result = response.json()
    assert result["evaluation_kind"] == "synthetic_functional_tests"
    assert result["summary"]["failed"] == 0
    assert len(result["cases"]) == 12
    assert result["limitations"]
    policies = result["cases"][0]["metrics"]["policy_comparison"]
    assert {policy["policy"] for policy in policies} == {
        "MarketBridge guard", "Unguarded feed", "Last qualified price", "1% bounded update"
    }


def test_historical_incident_is_explicit_sourced_and_finite():
    response = client.get("/v1/incidents/sk-hynix-july-2026")
    assert response.status_code == 200
    incident = response.json()
    assert incident["data_mode"] == "HISTORICAL_RECONSTRUCTION"
    assert len(incident["points"]) == 26
    assert len(incident["sources"]) == 2
    assert all(source["url"].startswith("https://") for source in incident["sources"])
    assert incident["operator_decision"]["decision_scope"] == "COUNTERFACTUAL_ADVISORY"
    json.dumps(incident, allow_nan=False)


def test_operator_payload_tracks_the_same_engine_step():
    payload = client.get("/v1/operator/decision/bad-print?symbol=NVDA&second=24").json()
    trace_step = client.get("/v1/demo/scenarios/bad-print?symbol=NVDA").json()["steps"][24]
    assert payload["reference"] == trace_step["reference"]
    assert payload["status"] == "INSUFFICIENT_EVIDENCE"
    assert payload["new_exposure_allowed"] is False
    assert payload["advisory_exposure_multiplier"] == 0


def test_operator_payload_rejects_unknown_inputs():
    assert client.get("/v1/operator/decision/missing").status_code == 404
    assert client.get("/v1/operator/decision/normal?second=61").status_code == 422


def test_live_research_snapshot_is_explicit_and_never_execution_eligible(monkeypatch):
    def fake_fetch(symbol, now):
        return {
            "symbol": symbol,
            "name": live.SYMBOLS[symbol],
            "observed_price": 200.0,
            "previous_close": 199.0,
            "change_pct": 0.5025125628,
            "currency": "USD",
            "exchange": "TEST",
            "event_time": now.isoformat().replace("+00:00", "Z"),
            "age_seconds": 0,
            "points": [{"timestamp": now.isoformat().replace("+00:00", "Z"), "price": 200.0}],
            "source": {"id": "yahoo-finance", "name": "Yahoo Finance via yfinance", "family": "yahoo-research-feed", "status": "FRESH"},
            "decision": {
                "status": "CAUTION",
                "reference": None,
                "independent_source_families": 1,
                "new_exposure_allowed": False,
                "advisory_exposure_multiplier": 0,
                "reasons": ["SINGLE_RESEARCH_FEED_NOT_LIQUIDATION_ELIGIBLE"],
            },
        }

    monkeypatch.setattr(live, "_fetch_symbol", fake_fetch)
    live.clear_live_cache()
    response = client.get("/v1/live/snapshot?refresh=true")
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["data_mode"] == "LIVE_RESEARCH"
    assert snapshot["provider_status"] == "AVAILABLE"
    assert snapshot["api_key_required"] is False
    assert {item["symbol"] for item in snapshot["observations"]} == {"NVDA", "TSLA", "QQQ"}
    assert all(item["decision"]["reference"] is None for item in snapshot["observations"])
    assert all(item["decision"]["new_exposure_allowed"] is False for item in snapshot["observations"])
    json.dumps(snapshot, allow_nan=False)
    live.clear_live_cache()


def test_response_security_and_health():
    response = client.get("/health")
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    response = client.get("/v1/demo/scenarios")
    assert response.headers["cache-control"] == "no-store"


def test_shadow_snapshot_and_mochatrade_mark_adapter(monkeypatch):
    snapshot = client.get("/v1/shadow/snapshot")
    assert snapshot.status_code == 200
    assert snapshot.json()["data_mode"] == "SHADOW_ORACLE"

    event_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {"symbol": "NVDA", "mark_price": 201.25, "event_time": event_time}
    accepted = client.post("/v1/integrations/mochatrade/market", json=payload)
    assert accepted.status_code == 200
    assert accepted.json()["mark"]["price"] == 201.25

    monkeypatch.setenv("MOCHATRADE_INGEST_KEY", "test-secret")
    assert client.post("/v1/integrations/mochatrade/market", json=payload).status_code == 401
    authorized = client.post(
        "/v1/integrations/mochatrade/market", json=payload, headers={"X-MarketBridge-Key": "test-secret"}
    )
    assert authorized.status_code == 200

    future = {**payload, "event_time": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()}
    assert client.post(
        "/v1/integrations/mochatrade/market", json=future, headers={"X-MarketBridge-Key": "test-secret"}
    ).status_code == 422
