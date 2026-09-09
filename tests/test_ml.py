from datetime import datetime, timedelta, timezone

from marketbridge.ml import MarketBridgeAI
from marketbridge.shadow import NormalizedObservation, ShadowOracle


def obs(symbol, price, provider, venue, now, event_time=None):
    return NormalizedObservation(
        symbol=symbol,
        price=price,
        event_time=event_time or now,
        received_at=now,
        source_id=f"{provider}-{venue}",
        source_family=f"equity-venue:{venue}",
        venue=venue,
        eligible=True,
        provider_family=provider,
        venue_family=venue,
    )


def qualify(oracle, symbol, price, now):
    oracle.ingest(obs(symbol, price, "provider-a", "Q", now))
    return oracle.ingest(obs(symbol, price * 1.0001, "provider-b", "V", now))


def test_default_ai_bundle_loads_and_exposes_provenance():
    ai = MarketBridgeAI.from_environment()
    status = ai.status()
    assert status["enabled"] is True
    assert status["model_version"] == "marketbridge-ai-v0.3"
    assert status["data_mode"] == "SYNTHETIC_CALIBRATION_DEMO"
    assert "NVDA" in status["symbols"]


def test_learned_fair_value_is_lower_trust_fallback_only():
    t0 = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    oracle = ShadowOracle()
    qualify(oracle, "QQQ", 500, t0)
    qualify(oracle, "SPY", 650, t0)
    qualify(oracle, "SOXX", 310, t0)
    direct = qualify(oracle, "NVDA", 200, t0)
    assert direct["status"] == "QUALIFIED"
    assert direct["ai"]["fair_value_used"] is False

    later = t0 + timedelta(seconds=11)
    qualify(oracle, "QQQ", 502, later)
    qualify(oracle, "SPY", 651.5, later)
    qualify(oracle, "SOXX", 312, later)
    decision = oracle.ingest(obs("NVDA", 200, "provider-a", "Q", later, event_time=t0))

    assert decision["status"] == "ESTIMATED"
    assert decision["ai"]["enabled"] is True
    assert decision["ai"]["fair_value_used"] is True
    assert decision["ai"]["predicted_reference"] == decision["reference"]
    assert decision["recommended_max_leverage"] <= 5
    assert "ML_FAIR_VALUE_FALLBACK" in decision["reasons"]
    assert "ESTIMATE_NOT_DIRECT_MARKET_EVIDENCE" in decision["reasons"]


def test_direct_consensus_always_outranks_ai_prediction():
    t0 = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    oracle = ShadowOracle()
    qualify(oracle, "QQQ", 500, t0)
    qualify(oracle, "SPY", 650, t0)
    qualify(oracle, "SOXX", 310, t0)
    qualify(oracle, "NVDA", 200, t0)

    later = t0 + timedelta(seconds=1)
    qualify(oracle, "QQQ", 501.5, later)
    qualify(oracle, "SPY", 651, later)
    qualify(oracle, "SOXX", 311.5, later)
    oracle.ingest(obs("NVDA", 201.0, "provider-a", "Q", later))
    decision = oracle.ingest(obs("NVDA", 201.01, "provider-b", "V", later))

    assert decision["status"] == "QUALIFIED"
    assert abs(decision["reference"] - 201.005) < 0.01
    assert decision["ai"]["fair_value_used"] is False


def test_anomaly_model_is_advisory_for_synthetic_bundle():
    t0 = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    oracle = ShadowOracle()
    decision = qualify(oracle, "NVDA", 200, t0)
    assert decision["status"] == "QUALIFIED"
    oracle.update_venue_mark("NVDA", 185.0, t0)
    current = oracle.snapshot(now=t0)["decisions"][0]

    assert current["ai"]["anomaly_probability"] is not None
    assert current["ai"]["anomaly_probability"] > 0.8
    assert current["ai"]["risk_signal_enforced"] is False
    # Deterministic divergence rules still decide the actual restriction.
    assert current["risk_state"] in {"RESTRICTED", "HALTED"}
