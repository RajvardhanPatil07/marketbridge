from datetime import datetime, timezone

from marketbridge.providers import provider_registry
from marketbridge.v1free import WarRoomRequest, _war_room_risk_request


def test_free_first_registry_has_no_databento(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    payload = provider_registry({"providers": []})
    ids = {item["id"] for item in payload["providers"]}
    assert payload["cost_mode"] == "FREE_FIRST"
    assert "databento" not in ids
    twelve = next(item for item in payload["providers"] if item["id"] == "twelve-data")
    assert twelve["risk_eligible"] is False
    yahoo = next(item for item in payload["providers"] if item["id"] == "yahoo")
    assert yahoo["market_truth_authority"] == "NONE"


def test_war_room_poisoned_mark_uses_synthetic_demo_contract():
    request = _war_room_risk_request(
        WarRoomRequest(scenario="POISONED_MARK", intent="OPEN", symbol="NVDA"),
        datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
    )
    assert request.demo_scenario == "POISONED_MARK"
    assert request.market.mark_price > 190
    assert request.intent.requested_leverage == 10
    assert request.intent.notional_usd == 10_000


def test_war_room_close_has_existing_position():
    request = _war_room_risk_request(
        WarRoomRequest(scenario="POISONED_MARK", intent="CLOSE", symbol="NVDA"),
        datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
    )
    assert request.account.position_notional_usd == 10_000
