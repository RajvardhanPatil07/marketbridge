from datetime import datetime, timezone

from marketbridge.providers import provider_registry
from marketbridge.v1free import WarRoomRequest, _war_room_risk_request


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def test_free_first_registry_separates_capability_from_health(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    payload = provider_registry({"providers": []})
    ids = {item["id"] for item in payload["providers"]}
    assert payload["cost_mode"] == "FREE_FIRST"
    assert "databento" not in ids
    alpaca = next(item for item in payload["providers"] if item["id"] == "alpaca")
    assert alpaca["supported"] is True
    assert alpaca["configured"] is False
    assert alpaca["health"] == "NOT_OBSERVED"
    sec = next(item for item in payload["providers"] if item["id"] == "sec-edgar")
    assert sec["status"] == "SUPPORTED"
    assert sec["health"] == "NOT_PROBED"


def test_war_room_poisoned_mark_is_parameterized_and_synthetic():
    payload = WarRoomRequest(
        scenario="POISONED_MARK",
        intent="OPEN",
        mode="SYNTHETIC",
        symbol="NVDA",
        baseline_price=200,
        requested_notional_usd=25000,
        requested_leverage=15,
        attack_bps=500,
    )
    request, provenance = _war_room_risk_request(payload, NOW, {"decisions": []})
    assert request.demo_scenario == "POISONED_MARK"
    assert request.market.oracle_price == 200
    assert request.market.mark_price == 210
    assert request.intent.requested_leverage == 15
    assert request.intent.notional_usd == 25_000
    assert provenance["data_mode"] == "SYNTHETIC_DEMO"
    assert provenance["baseline_source"] == "CLIENT_DISPLAY_SNAPSHOT"


def test_war_room_close_has_existing_position_without_fixed_fixture():
    payload = WarRoomRequest(
        scenario="POISONED_MARK",
        intent="CLOSE",
        mode="SYNTHETIC",
        symbol="TSLA",
        baseline_price=350,
        requested_notional_usd=17000,
    )
    request, _ = _war_room_risk_request(payload, NOW, {"decisions": []})
    assert request.account.position_notional_usd == 17_000


def test_auto_mode_uses_qualified_live_reference_when_quorum_exists():
    snapshot = {
        "decisions": [
            {
                "symbol": "NVDA",
                "status": "QUALIFIED",
                "reference": 250.0,
                "required_independent_sources": 2,
                "evidence": [
                    {"provider_family": "provider-a", "fresh": True, "eligible": True},
                    {"provider_family": "provider-b", "fresh": True, "eligible": True},
                ],
            }
        ]
    }
    payload = WarRoomRequest(
        scenario="POISONED_MARK",
        mode="AUTO",
        symbol="NVDA",
        attack_bps=400,
    )
    request, provenance = _war_room_risk_request(payload, NOW, snapshot)
    assert request.demo_scenario is None
    assert request.market.oracle_price is None
    assert request.market.mark_price == 260
    assert provenance["data_mode"] == "LIVE_DERIVED_DEMO"
    assert provenance["baseline_source"] == "LIVE_QUALIFIED_REFERENCE"
