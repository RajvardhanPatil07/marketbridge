import json
from datetime import datetime, timedelta, timezone

import pytest

from marketbridge.shadow import (
    FRESH_SECONDS,
    LivePipeline,
    NormalizedObservation,
    TRACKED_SYMBOLS,
    TwelveDataStreamError,
    VENUE_MARK_FRESH_SECONDS,
    _classify_alpaca_error,
    probe_alpaca_subscription,
)


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def test_alpaca_connection_limit_is_retryable():
    error = _classify_alpaca_error(
        {"T": "error", "code": 406, "msg": "connection limit exceeded"}, authenticated=False
    )
    assert error.status == "RATE_LIMITED"
    assert error.permanent is False


class RecordingSocket:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))


class ProbeSocket(RecordingSocket):
    def __init__(self, messages: list[list[dict]]):
        super().__init__()
        self.messages = iter(json.dumps(message) for message in messages)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.messages)


def direct_observation(price: float, provider: str, venue: str) -> NormalizedObservation:
    return NormalizedObservation(
        symbol="NVDA",
        price=price,
        event_time=NOW,
        received_at=NOW,
        source_id=f"{provider}-{venue}",
        source_family=f"equity-venue:{venue}",
        venue=venue,
        eligible=True,
        provider_family=provider,
        venue_family=venue,
    )


def test_live_configuration_exposes_iex_limitation_and_strict_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    monkeypatch.setenv("ALPACA_FEED", "iex")
    pipeline = LivePipeline(tmp_path / "audit.jsonl")

    configuration = pipeline.configuration()

    assert configuration["alpaca"]["credentials_configured"] is True
    assert configuration["alpaca"]["feed"] == "iex"
    assert configuration["alpaca"]["qualification_capable"] is False
    assert "ALPACA_IEX_SINGLE_VENUE" in configuration["warnings"]

    monkeypatch.setenv("MARKETBRIDGE_REQUIRE_LIVE_DATA", "1")
    with pytest.raises(RuntimeError, match="multi-venue"):
        LivePipeline(tmp_path / "strict.jsonl").start()


def test_live_configuration_accepts_sip_as_multi_venue(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    monkeypatch.setenv("ALPACA_FEED", "sip")

    configuration = LivePipeline(tmp_path / "audit.jsonl").configuration()

    assert configuration["valid"] is True
    assert configuration["alpaca"]["qualification_capable"] is True
    assert configuration["warnings"] == []


def test_live_configuration_accepts_alpaca_plus_twelve_data(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    monkeypatch.setenv("ALPACA_FEED", "iex")
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "configured")

    configuration = LivePipeline(tmp_path / "audit.jsonl").configuration()

    assert configuration["execution_evidence_configured"] is True
    assert configuration["twelve_data"] == {
        "credentials_configured": True,
        "endpoint": "quotes/price",
        "tracked_symbols": 8,
        "qualification_capable": True,
        "errors": [],
    }


def test_twelve_data_subscription_and_price_form_one_provider_witness(tmp_path):
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    session: dict[str, object] = {"subscribed_symbols": set()}
    subscription = {
        "event": "subscribe-status",
        "status": "ok",
        "success": [{"symbol": symbol, "exchange": "NASDAQ"} for symbol in TRACKED_SYMBOLS],
        "fails": [],
    }

    assert pipeline._handle_twelve_data_event(subscription, session, NOW) == 0
    provider = next(
        item for item in pipeline.snapshot(now=NOW)["providers"] if item["id"] == "twelve-data"
    )
    assert provider["status"] == "AVAILABLE"
    assert provider["qualification_capable"] is True

    pipeline.ingest_direct_observation("NVDA", 200.0, NOW, provider="alpaca", venue="IEX")
    ingested = pipeline._handle_twelve_data_event(
        {
            "event": "price",
            "symbol": "NVDA",
            "price": 200.02,
            "timestamp": NOW.timestamp(),
            "exchange": "NASDAQ",
        },
        session,
        NOW,
    )

    assert ingested == 1
    decision = pipeline.oracle.snapshot(now=NOW)["decisions"][0]
    assert decision["status"] == "QUALIFIED"
    assert decision["independent_provider_families"] == 2
    twelve = next(row for row in decision["evidence"] if row["provider_family"] == "twelve-data")
    assert twelve["venue_family"] == "twelve-data-us-equities"


def test_twelve_data_rejects_unsubscribed_stale_and_entitlement_events(tmp_path):
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    session: dict[str, object] = {"subscribed_symbols": {"NVDA"}}

    assert pipeline._handle_twelve_data_event(
        {"event": "price", "symbol": "TSLA", "price": 200, "timestamp": NOW.timestamp()},
        session,
        NOW,
    ) == 0
    assert pipeline._handle_twelve_data_event(
        {
            "event": "price",
            "symbol": "NVDA",
            "price": 200,
            "timestamp": (NOW - timedelta(seconds=31)).timestamp(),
        },
        session,
        NOW,
    ) == 0
    with pytest.raises(TwelveDataStreamError, match="did not authorize"):
        pipeline._handle_twelve_data_event(
            {
                "event": "subscribe-status",
                "status": "error",
                "success": [],
                "fails": [{"symbol": "NVDA", "message": "not available on your plan"}],
            },
            {"subscribed_symbols": set()},
            NOW,
        )
    with pytest.raises(TwelveDataStreamError) as auth_error:
        pipeline._handle_twelve_data_event(
            {
                "event": "error",
                "status": "error",
                "code": 401,
                "message": "invalid API key db-secret-value",
            },
            session,
            NOW,
        )
    assert auth_error.value.status == "AUTH_ERROR"
    assert "db-secret-value" not in str(auth_error.value)


def test_runtime_probe_reports_entitlement_failure_without_exposing_credentials(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "private-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "private-secret")
    monkeypatch.setenv("ALPACA_FEED", "sip")
    socket = ProbeSocket(
        [
            [{"T": "success", "msg": "authenticated"}],
            [{"T": "error", "code": 409, "msg": "insufficient subscription"}],
        ]
    )

    result = probe_alpaca_subscription(connect_fn=lambda *_args, **_kwargs: socket)

    assert result == {
        "status": "ENTITLEMENT_ERROR",
        "feed": "sip",
        "authenticated": True,
        "subscribed": False,
        "runtime_eligible": False,
        "permanent_error": True,
        "error_code": "409",
        "detail": "insufficient subscription",
    }
    assert "private" not in json.dumps(result)


def test_runtime_probe_confirms_a_qualifying_subscription(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    monkeypatch.setenv("ALPACA_FEED", "sip")
    socket = ProbeSocket(
        [
            [{"T": "success", "msg": "authenticated"}],
            [{"T": "subscription", "trades": list(TRACKED_SYMBOLS)}],
        ]
    )

    result = probe_alpaca_subscription(connect_fn=lambda *_args, **_kwargs: socket)

    assert result["status"] == "AVAILABLE"
    assert result["runtime_eligible"] is True
    assert result["authenticated"] is True
    assert result["subscribed"] is True


def test_live_configuration_rejects_unsupported_hyperliquid_symbols(monkeypatch, tmp_path):
    monkeypatch.setenv("HYPERLIQUID_COIN_MAP", '{"UNKNOWN":"xyz:UNKNOWN"}')

    configuration = LivePipeline(tmp_path / "audit.jsonl").configuration()

    assert configuration["valid"] is False
    assert configuration["hyperliquid_errors"] == ["HYPERLIQUID_COIN_MAP_INVALID"]


def test_alpaca_only_becomes_available_after_auth_and_subscription(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    socket = RecordingSocket()
    session = {"authenticated": False, "subscription_sent": False, "subscribed": False}

    pipeline._handle_alpaca_events(
        [{"T": "success", "msg": "authenticated"}], socket, "sip", session, NOW
    )
    assert pipeline.snapshot(now=NOW)["providers"][1]["status"] == "AUTHENTICATED"
    assert socket.sent == [{
        "action": "subscribe", "trades": list(pipeline.tracked_symbols),
        "quotes": list(pipeline.tracked_symbols), "bars": list(pipeline.tracked_symbols),
        "updatedBars": list(pipeline.tracked_symbols), "dailyBars": list(pipeline.tracked_symbols),
    }]

    pipeline._handle_alpaca_events(
        [{"T": "subscription", "trades": list(pipeline.tracked_symbols), "quotes": list(pipeline.tracked_symbols)}],
        socket,
        "sip",
        session,
        NOW,
    )
    assert pipeline.snapshot(now=NOW)["providers"][1]["status"] == "AVAILABLE"

    with pytest.raises(RuntimeError, match="authentication failed"):
        pipeline._handle_alpaca_events(
            [{"T": "error", "code": 401, "msg": "authentication failed"}],
            socket,
            "sip",
            session,
            NOW,
        )


def test_iex_subscription_is_reported_as_limited(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    session = {"authenticated": True, "subscription_sent": True, "subscribed": False}

    pipeline._handle_alpaca_events(
        [{"T": "subscription", "trades": list(pipeline.tracked_symbols), "quotes": []}],
        RecordingSocket(),
        "iex",
        session,
        NOW,
    )

    provider = next(item for item in pipeline.snapshot(now=NOW)["providers"] if item["id"] == "alpaca")
    assert provider["status"] == "LIMITED"
    assert provider["qualification_capable"] is False


def test_alpaca_trade_filter_rejects_odd_lot_duplicate_out_of_order_and_nbbo_outlier(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    session = {"authenticated": False, "subscription_sent": False, "subscribed": False}
    socket = RecordingSocket()
    pipeline._handle_alpaca_events(
        [{"T": "success", "msg": "authenticated"}], socket, "sip", session, NOW
    )
    pipeline._handle_alpaca_events(
        [{"T": "subscription", "trades": list(TRACKED_SYMBOLS), "quotes": list(TRACKED_SYMBOLS)}],
        socket,
        "sip",
        session,
        NOW,
    )

    pipeline._handle_alpaca_events(
        [{
            "T": "q", "S": "NVDA", "bp": 199.9, "ap": 200.1, "bs": 10, "as": 10,
            "bx": "Q", "ax": "V", "t": NOW.isoformat(), "c": ["R"], "z": "C",
        }],
        socket,
        "sip",
        session,
        NOW,
    )
    regular = {
        "T": "t", "S": "NVDA", "i": 1, "x": "Q", "p": 200.0, "s": 100,
        "t": NOW.isoformat(), "c": ["@"], "z": "C",
    }
    assert pipeline._handle_alpaca_events([regular], socket, "sip", session, NOW) == 1
    assert pipeline._handle_alpaca_events([regular], socket, "sip", session, NOW) == 0

    simultaneous = {**regular, "i": 6, "p": 200.01}
    assert pipeline._handle_alpaca_events([simultaneous], socket, "sip", session, NOW) == 1

    odd_lot = {**regular, "i": 2, "x": "V", "c": ["I"]}
    assert pipeline._handle_alpaca_events([odd_lot], socket, "sip", session, NOW) == 0

    out_of_order = {**regular, "i": 3, "t": (NOW - timedelta(seconds=1)).isoformat()}
    assert pipeline._handle_alpaca_events([out_of_order], socket, "sip", session, NOW) == 0

    outside_nbbo = {**regular, "i": 4, "x": "V", "p": 205.0}
    assert pipeline._handle_alpaca_events([outside_nbbo], socket, "sip", session, NOW) == 0

    second_venue = {**regular, "i": 5, "x": "V", "p": 200.02, "t": (NOW + timedelta(milliseconds=1)).isoformat()}
    assert pipeline._handle_alpaca_events(
        [second_venue], socket, "sip", session, NOW + timedelta(milliseconds=1)
    ) == 1
    assert pipeline.oracle.snapshot(now=NOW + timedelta(milliseconds=1))["decisions"][0]["status"] == "QUALIFIED"

    provider = next(item for item in pipeline.snapshot(now=NOW)["providers"] if item["id"] == "alpaca")
    assert provider["auth_time"] == NOW.isoformat().replace("+00:00", "Z")
    assert provider["subscription_time"] == NOW.isoformat().replace("+00:00", "Z")
    assert provider["last_quote_time"] == NOW.isoformat().replace("+00:00", "Z")
    assert provider["last_trade_time"] == (NOW + timedelta(milliseconds=1)).isoformat().replace("+00:00", "Z")
    assert provider["last_qualified_evidence_time"] == (NOW + timedelta(milliseconds=1)).isoformat().replace("+00:00", "Z")
    assert provider["retry_count"] == 0


def test_alpaca_corrected_bar_replaces_prior_live_candle(tmp_path):
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    session = {"authenticated": True, "subscription_sent": True, "subscribed": True}
    original = {
        "T": "b", "S": "NVDA", "t": NOW.isoformat(), "o": 200.0,
        "h": 201.0, "l": 199.0, "c": 200.5, "v": 1000, "vw": 200.2, "n": 20,
    }
    corrected = {**original, "T": "u", "h": 202.0, "c": 201.5, "v": 1200}

    pipeline._handle_alpaca_events([original], RecordingSocket(), "sip", session, NOW)
    pipeline._handle_alpaca_events([corrected], RecordingSocket(), "sip", session, NOW)

    live_bars = pipeline.snapshot(now=NOW)["live_bars"]["NVDA"]
    assert len(live_bars) == 1
    assert live_bars[0]["close"] == 201.5
    assert live_bars[0]["kind"] == "CORRECTED_BAR"
    assert live_bars[0]["data_role"] == "DISPLAY_ONLY_NOT_ORACLE_EVIDENCE"


def test_market_health_requires_a_qualified_reference_and_fresh_mark(tmp_path):
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    pipeline._started = True
    pipeline._provider_status["yahoo"] = {
        "status": "DISABLED", "kind": "RESEARCH", "detail": "Disabled for deterministic test"
    }
    assert pipeline.snapshot(now=NOW)["market_health"]["status"] == "DEGRADED"

    pipeline.oracle.ingest(direct_observation(200.0, "provider-a", "Q"))
    pipeline.oracle.ingest(direct_observation(200.02, "provider-b", "V"))
    pipeline.ingest_mochatrade("NVDA", 200.01, NOW)
    healthy = pipeline.snapshot(now=NOW)["market_health"]
    assert healthy["status"] == "HEALTHY"
    assert healthy["execution_ready"] is True
    assert healthy["comparable_symbols"] == ["NVDA"]

    stale = pipeline.snapshot(now=NOW + timedelta(seconds=VENUE_MARK_FRESH_SECONDS + 1))["market_health"]
    assert stale["status"] == "DEGRADED"
    assert stale["execution_ready"] is False
    assert "NO_FRESH_VENUE_MARKS" in stale["reasons"]


def test_public_direct_adapter_can_build_a_qualified_execution_reference(tmp_path):
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    pipeline._started = True

    pipeline.ingest_direct_observation("NVDA", 200.0, NOW, provider="fixture-sip", venue="Q")
    decision = pipeline.ingest_direct_observation(
        "NVDA", 200.02, NOW, provider="fixture-sip", venue="V"
    )
    pipeline.ingest_mochatrade("NVDA", 200.01, NOW)

    snapshot = pipeline.snapshot(now=NOW)
    provider = next(item for item in snapshot["providers"] if item["id"] == "fixture-sip")
    assert decision["status"] == "QUALIFIED"
    assert provider["last_trade_time"] == NOW.isoformat().replace("+00:00", "Z")
    assert provider["last_qualified_evidence_time"] == NOW.isoformat().replace("+00:00", "Z")
    assert snapshot["market_health"]["execution_ready"] is True


def test_market_health_expires_direct_evidence_even_while_mark_is_fresh(tmp_path):
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    pipeline._started = True
    pipeline._provider_status["alpaca"] = {
        "status": "AVAILABLE",
        "kind": "DIRECT_MARKET",
        "detail": "sip authenticated multi-venue stream",
        "qualification_capable": True,
        "last_event_time": NOW.isoformat(),
    }
    pipeline.oracle.ingest(direct_observation(200.0, "alpaca", "Q"))
    pipeline.oracle.ingest(direct_observation(200.02, "alpaca", "V"))
    pipeline.ingest_mochatrade("NVDA", 200.01, NOW)

    expired_at = NOW + timedelta(seconds=FRESH_SECONDS + 1)
    snapshot = pipeline.snapshot(now=expired_at)
    decision = snapshot["decisions"][0]
    alpaca = next(item for item in snapshot["providers"] if item["id"] == "alpaca")

    assert decision["status"] == "INSUFFICIENT_EVIDENCE"
    assert decision["reference"] is None
    assert "DIRECT_EVIDENCE_EXPIRED" in decision["reasons"]
    assert snapshot["decision_log"][0]["status"] == "QUALIFIED"
    assert alpaca["status"] == "STALE"
    assert snapshot["market_health"]["status"] == "DEGRADED"
    assert snapshot["market_health"]["execution_ready"] is False
    assert snapshot["market_health"]["authenticated_multi_venue_feeds"] == ["alpaca"]
    assert snapshot["market_health"]["fresh_multi_venue_feeds"] == []
    assert "NO_FRESH_MULTI_VENUE_FEED" in snapshot["market_health"]["reasons"]


def test_strict_readiness_requires_current_reference_and_mark(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "configured")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "configured")
    monkeypatch.setenv("ALPACA_FEED", "sip")
    monkeypatch.setenv("MARKETBRIDGE_REQUIRE_LIVE_DATA", "1")
    pipeline = LivePipeline(tmp_path / "audit.jsonl")
    pipeline._started = True

    assert pipeline.readiness(now=NOW)["ready"] is False

    pipeline.oracle.ingest(direct_observation(200.0, "alpaca", "Q"))
    pipeline.oracle.ingest(direct_observation(200.02, "alpaca", "V"))
    pipeline.ingest_mochatrade("NVDA", 200.01, NOW)

    readiness = pipeline.readiness(now=NOW)
    assert readiness["ready"] is True
    assert readiness["market_health"]["execution_ready"] is True
