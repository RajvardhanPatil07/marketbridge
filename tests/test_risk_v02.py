from datetime import datetime, timedelta, timezone

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


def test_provider_and_venue_independence_are_reported_separately():
    now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    oracle = ShadowOracle()
    oracle.ingest(obs("NVDA", 200, "alpaca", "Q", now))
    decision = oracle.ingest(obs("NVDA", 200.02, "alpaca", "V", now))
    assert decision["status"] == "QUALIFIED"
    assert decision["independent_source_families"] == 2
    assert decision["independent_provider_families"] == 1
    assert "SINGLE_PROVIDER_CONCENTRATION" in decision["reasons"]


def test_factor_fallback_is_explicitly_estimated_and_guarded():
    t0 = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    oracle = ShadowOracle()
    oracle.ingest(obs("NVDA", 200, "alpaca", "Q", t0))
    oracle.ingest(obs("NVDA", 200.02, "direct2", "V", t0))
    later = t0 + timedelta(seconds=11)
    oracle.ingest(obs("QQQ", 500, "alpaca", "Q", later))
    oracle.ingest(obs("QQQ", 500.1, "direct2", "V", later))
    stale_stock = obs("NVDA", 200.02, "alpaca", "Q", later, event_time=t0)
    decision = oracle.ingest(stale_stock)
    assert decision["status"] == "ESTIMATED"
    assert decision["risk_state"] in {"GUARDED", "RESTRICTED"}
    assert decision["recommended_max_leverage"] <= 5
    assert "ESTIMATE_NOT_DIRECT_MARKET_EVIDENCE" in decision["reasons"]
