from fastapi.testclient import TestClient

from marketbridge import kalshi
from marketbridge.api import app


client = TestClient(app)


def setup_function():
    kalshi.clear_kalshi_cache()


def test_public_kalshi_pulse_normalizes_probability_quality_and_cache(monkeypatch):
    calls = []

    def fake_request(path, params):
        calls.append((path, params))
        if path == "/series":
            return {
                "series": [
                    {"ticker": "KXTSLA", "title": "Tesla closing price", "volume_fp": "5000"},
                    {"ticker": "KXWEATHER", "title": "Weather in New York", "volume_fp": "9000"},
                ]
            }
        return {
            "markets": [
                {
                    "ticker": "KXTSLA-26SEP09-T400",
                    "event_ticker": "KXTSLA-26SEP09",
                    "series_ticker": "KXTSLA",
                    "title": "Will Tesla close above $400?",
                    "yes_sub_title": "$400 or above",
                    "yes_bid_dollars": "0.4100",
                    "yes_ask_dollars": "0.4500",
                    "previous_yes_bid_dollars": "0.3600",
                    "previous_yes_ask_dollars": "0.4000",
                    "volume_24h_fp": "2400.00",
                    "open_interest_fp": "900.00",
                    "liquidity_dollars": "1200.00",
                    "close_time": "2026-09-09T20:00:00Z",
                }
            ],
            "cursor": "",
        }

    monkeypatch.setattr(kalshi, "_request_kalshi", fake_request)
    first = client.get("/v1/kalshi/pulse?symbol=tsla").json()
    second = client.get("/v1/kalshi/pulse?symbol=TSLA").json()

    assert first["status"] == "AVAILABLE"
    assert first["api_key_required"] is False
    assert first["cost"] == "FREE_PUBLIC_REST"
    assert first["execution_authority"] == "ADVISORY_ONLY"
    assert first["markets"][0]["probability"] == 0.43
    assert round(first["markets"][0]["probability_change_pp"], 6) == 5.0
    assert first["markets"][0]["spread_pp"] == 4.0
    assert first["markets"][0]["quality"] == "HIGH"
    assert second["cached"] is True
    assert len(calls) == 2


def test_kalshi_pulse_is_explicit_when_no_relevant_market_is_open(monkeypatch):
    def fake_request(path, _params):
        return {"series": []} if path == "/series" else {"markets": [], "cursor": ""}

    monkeypatch.setattr(kalshi, "_request_kalshi", fake_request)
    payload = client.get("/v1/kalshi/pulse?symbol=NVDA").json()
    assert payload["status"] == "NO_RELEVANT_MARKETS"
    assert payload["markets"] == []
    assert "No currently open" in payload["message"]


def test_kalshi_pulse_rejects_unsupported_symbols():
    assert client.get("/v1/kalshi/pulse?symbol=RELIANCE").status_code == 404


def test_kalshi_failure_does_not_request_or_leak_credentials(monkeypatch):
    def rate_limited(_path, _params):
        raise kalshi.KalshiError("RATE_LIMITED", "Kalshi public allowance reached")

    monkeypatch.setattr(kalshi, "_request_kalshi", rate_limited)
    payload = client.get("/v1/kalshi/pulse?symbol=TSLA").json()
    assert payload["status"] == "RATE_LIMITED"
    assert payload["api_key_required"] is False
    assert payload["markets"] == []
