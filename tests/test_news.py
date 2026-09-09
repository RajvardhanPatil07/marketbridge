from fastapi.testclient import TestClient

from marketbridge import news
from marketbridge.api import app


client = TestClient(app)


def setup_function():
    news.clear_news_cache()


def test_news_endpoint_is_explicit_when_marketaux_is_not_configured(monkeypatch):
    monkeypatch.delenv("MARKETAUX_API_TOKEN", raising=False)
    response = client.get("/v1/news")
    assert response.status_code == 200
    assert response.json()["status"] == "UNCONFIGURED"
    assert response.json()["articles"] == []


def test_news_endpoint_normalizes_and_caches_marketaux_articles(monkeypatch):
    monkeypatch.setenv("MARKETAUX_API_TOKEN", "test-token")
    calls = []

    def fake_request(params):
        calls.append(params)
        return {
            "meta": {"found": 10, "returned": 1},
            "data": [
                {
                    "uuid": "story-1",
                    "title": "Nvidia introduces a new platform",
                    "description": "A concise, sourced description.",
                    "url": "https://example.com/story",
                    "source": "Example Wire",
                    "published_at": "2026-09-09T04:00:00Z",
                    "entities": [{"symbol": "NVDA", "sentiment_score": 0.4}],
                }
            ],
        }

    monkeypatch.setattr(news, "_request_marketaux", fake_request)
    first = client.get("/v1/news?symbol=NVDA").json()
    second = client.get("/v1/news?symbol=NVDA").json()

    assert first["status"] == "AVAILABLE"
    assert first["configured"] is True
    assert first["articles"][0]["symbols"] == ["NVDA"]
    assert first["articles"][0]["sentiment_score"] == 0.4
    assert second["cached"] is True
    assert len(calls) == 1
    assert calls[0]["symbols"] == "NVDA"
    assert calls[0]["limit"] == "3"


def test_news_endpoint_rejects_unsupported_symbols(monkeypatch):
    monkeypatch.setenv("MARKETAUX_API_TOKEN", "test-token")
    assert client.get("/v1/news?symbol=RELIANCE").status_code == 404


def test_news_adapter_classifies_rate_limits_without_leaking_token(monkeypatch):
    monkeypatch.setenv("MARKETAUX_API_TOKEN", "secret-token")

    def rate_limited(_params):
        raise news.MarketauxError("RATE_LIMITED", "Marketaux request allowance is exhausted")

    monkeypatch.setattr(news, "_request_marketaux", rate_limited)
    payload = client.get("/v1/news").json()
    assert payload["status"] == "RATE_LIMITED"
    assert "secret-token" not in str(payload)
