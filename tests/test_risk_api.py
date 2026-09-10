from datetime import datetime, timedelta, timezone
import json
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from marketbridge.api import app
from marketbridge import api
from marketbridge.security import sign_request
from marketbridge.symbols import ActiveSubscriptions, NASDAQ_STOCK_UNIVERSE, SymbolCatalog


client = TestClient(app)


def test_curated_nasdaq_catalogue_and_activation(monkeypatch, tmp_path):
    catalog = SymbolCatalog(tmp_path / "symbols.sqlite3")
    active = ActiveSubscriptions(("NVDA", "TSLA"))
    monkeypatch.setattr(api, "symbol_catalog", catalog)
    monkeypatch.setattr(api, "active_subscriptions", active)
    response = client.get("/v1/symbols?query=Crowd&limit=10")
    assert response.status_code == 200
    assert response.json()["count"] == len(NASDAQ_STOCK_UNIVERSE) == 30
    assert [item["symbol"] for item in response.json()["items"]] == ["CRWD"]
    activated = client.post("/v1/market/active-symbols/CRWD", json={"reason": "view"})
    assert activated.status_code == 200
    assert activated.json()["alpaca"][0] == "CRWD"
    assert client.get("/v1/symbols/QQQ").status_code == 404


def payload(request_id=None, *, intent="OPEN", mark=184.55):
    return {
        "request_id": request_id or f"ord_{uuid4().hex}", "symbol": "NVDA",
        "intent": {"kind": intent, "side": "BUY", "notional_usd": 10000, "requested_leverage": 10},
        "account": {"equity_usd": 2000, "margin_available_usd": 10000, "position_notional_usd": 10000 if intent in {"REDUCE", "CLOSE"} else 0},
        "market": {"mark_price": mark, "event_time": datetime.now(timezone.utc).isoformat(), "session": "REGULAR"},
        "demo_scenario": "POISONED_MARK" if mark > 190 else "NORMAL",
    }


def signed(body: bytes, secret: str, *, timestamp=None, nonce=None):
    timestamp = timestamp or str(time.time())
    nonce = nonce or uuid4().hex
    return {
        "Content-Type": "application/json", "X-MarketBridge-Timestamp": timestamp,
        "X-MarketBridge-Nonce": nonce,
        "X-MarketBridge-Signature": sign_request(secret, timestamp, nonce, body),
    }


def test_risk_check_actions_passport_and_replay():
    allowed = client.post("/v1/integrations/mochatrade/risk-check", json=payload())
    assert allowed.status_code == 200
    assert allowed.json()["action"] == "ALLOW"
    passport_id = allowed.json()["passport_id"]
    assert client.get(f"/v1/passports/{passport_id}").json()["verification_status"] == "VERIFIED"

    blocked = client.post("/v1/integrations/mochatrade/risk-check", json=payload(mark=190.20))
    assert blocked.status_code == 200
    assert blocked.json()["action"] == "BLOCK_NEW_RISK"
    closed = client.post("/v1/integrations/mochatrade/risk-check", json=payload(intent="CLOSE", mark=190.20))
    assert closed.json()["action"] == "ALLOW"

    replay = client.post("/v1/replay/risk-decision", json={"passport_id": blocked.json()["passport_id"], "policy_version": "CURRENT"})
    assert replay.status_code == 200
    assert replay.json()["deterministic_parity"] is True


def test_risk_check_hmac_body_tamper_nonce_replay_and_clock_skew(monkeypatch):
    secret = "risk-api-test-secret"
    monkeypatch.setenv("MOCHATRADE_HMAC_SECRET", secret)
    body = json.dumps(payload(), separators=(",", ":")).encode()
    headers = signed(body, secret)
    assert client.post("/v1/integrations/mochatrade/risk-check", content=body, headers=headers).status_code == 200
    assert client.post("/v1/integrations/mochatrade/risk-check", content=body, headers=headers).status_code == 409

    modified = body.replace(b"10000", b"10001", 1)
    assert client.post("/v1/integrations/mochatrade/risk-check", content=modified, headers=signed(body, secret)).status_code == 401

    old = str(time.time() - 30)
    assert client.post("/v1/integrations/mochatrade/risk-check", content=body, headers=signed(body, secret, timestamp=old)).status_code == 401
    assert client.post("/v1/integrations/mochatrade/risk-check", content=body, headers={"Content-Type": "application/json"}).status_code == 401


def test_risk_check_rejects_future_and_malformed_market_data():
    future = payload()
    future["market"]["event_time"] = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    assert client.post("/v1/integrations/mochatrade/risk-check", json=future).status_code == 422
    malformed = payload()
    malformed["market"].update({"best_bid": 190, "best_ask": 180})
    assert client.post("/v1/integrations/mochatrade/risk-check", json=malformed).status_code == 422


def test_public_demo_exception_is_synthetic_only(monkeypatch):
    monkeypatch.setattr(api, "_client_key", lambda _request: "203.0.113.10")
    monkeypatch.setenv("MARKETBRIDGE_ENABLE_PUBLIC_DEMO", "1")
    assert client.post("/v1/integrations/mochatrade/risk-check", json=payload()).status_code == 200
    live_request = payload()
    live_request.pop("demo_scenario")
    assert client.post("/v1/integrations/mochatrade/risk-check", json=live_request).status_code == 403
