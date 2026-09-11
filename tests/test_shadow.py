from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest

from marketbridge.shadow import VENUE_MARK_FRESH_SECONDS, NormalizedObservation, ShadowOracle
from marketbridge.shadow import LivePipeline


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def observation(price, family, venue, *, eligible=True, age=0):
    return NormalizedObservation(
        symbol="NVDA",
        price=price,
        event_time=NOW - timedelta(seconds=age),
        received_at=NOW,
        source_id=family,
        source_family=family,
        venue=venue,
        eligible=eligible,
    )


def test_research_feed_is_visible_but_never_oracle_eligible():
    oracle = ShadowOracle()
    decision = oracle.ingest(observation(200, "yahoo-research-feed", "NMS", eligible=False))
    assert decision["reference"] is None
    assert decision["independent_source_families"] == 0
    assert decision["new_exposure_allowed"] is False
    assert "RESEARCH_FEED_VISIBLE_NOT_COUNTED" in decision["reasons"]


def test_two_fresh_original_venues_can_qualify_a_reference():
    oracle = ShadowOracle()
    oracle.ingest(observation(200.00, "equity-venue:Q", "Q"))
    decision = oracle.ingest(observation(200.04, "equity-venue:V", "V"))
    assert decision["status"] == "QUALIFIED"
    assert decision["reference"] == pytest.approx(200.02)
    assert decision["new_exposure_allowed"] is True
    assert decision["decision_latency_ms"] < 10


def test_twelve_data_price_is_one_aggregated_provider_witness():
    observation = LivePipeline._normalized_twelve_data_price(
        "NVDA", 200.0, NOW, NOW, "NASDAQ"
    )
    assert observation is not None
    assert observation.provider == "twelve-data"
    assert observation.venue == "NASDAQ"
    assert observation.venue_key == "twelve-data-us-equities"
    assert LivePipeline._normalized_twelve_data_price("NVDA", float("nan"), NOW, NOW) is None


def test_venue_mark_immediately_annotates_current_decision_and_audit_log():
    audited = []
    oracle = ShadowOracle(audited.append)
    oracle.ingest(observation(200.00, "equity-venue:Q", "Q"))
    oracle.ingest(observation(200.04, "equity-venue:V", "V"))

    oracle.update_venue_mark("NVDA", 201.02, NOW)
    snapshot = oracle.snapshot(now=NOW)
    decision = snapshot["decisions"][0]

    assert decision["venue_mark"]["price"] == 201.02
    assert decision["mark_divergence_bps"] == pytest.approx(49.995, rel=1e-3)
    assert decision["reasons"][-1] == "VENUE_MARK_OBSERVED"
    assert snapshot["decision_log"][0] == decision
    assert audited[-1] == decision


def test_mark_passports_are_hash_chained_and_tamper_evident():
    oracle = ShadowOracle()
    first = oracle.ingest(observation(200.00, "equity-venue:Q", "Q"))
    second = oracle.ingest(observation(200.04, "equity-venue:V", "V"))

    assert first["passport"]["sequence"] == 1
    assert first["passport"]["previous_hash"] is None
    assert second["passport"]["sequence"] == 2
    assert second["passport"]["previous_hash"] == first["passport"]["chain_hash"]
    assert len(second["passport"]["claims"]["evidence"]) == 2
    assert all(len(item["evidence_hash"]) == 64 for item in second["passport"]["claims"]["evidence"])
    assert ShadowOracle.verify_passport(second["passport"]) is True

    tampered = deepcopy(second["passport"])
    tampered["claims"]["risk_state"] = "HALTED"
    assert ShadowOracle.verify_passport(tampered) is False

    oracle.update_venue_mark("NVDA", 185.0, NOW)
    marked = oracle.snapshot(now=NOW)["decisions"][0]
    assert marked["passport"]["sequence"] == 3
    assert marked["passport"]["previous_hash"] == second["passport"]["chain_hash"]
    assert marked["passport"]["claims"]["risk_state"] == "HALTED"
    assert ShadowOracle.verify_passport(marked["passport"]) is True


def test_stale_venue_mark_is_visible_but_not_used_for_divergence():
    oracle = ShadowOracle()
    oracle.ingest(observation(200.00, "equity-venue:Q", "Q"))
    oracle.ingest(observation(200.04, "equity-venue:V", "V"))
    oracle.update_venue_mark("NVDA", 201.02, NOW)

    snapshot = oracle.snapshot(now=NOW + timedelta(seconds=VENUE_MARK_FRESH_SECONDS + 1))
    decision = snapshot["decisions"][0]

    assert decision["venue_mark"]["fresh"] is False
    assert decision["venue_mark"]["age_seconds"] == VENUE_MARK_FRESH_SECONDS + 1
    assert decision["mark_divergence_bps"] is None
    assert "VENUE_MARK_STALE" in decision["reasons"]


def test_disagreeing_or_stale_venues_do_not_qualify():
    oracle = ShadowOracle()
    oracle.ingest(observation(200, "equity-venue:Q", "Q"))
    disagreement = oracle.ingest(observation(204, "equity-venue:V", "V"))
    assert disagreement["reference"] is None
    assert "CROSS_VENUE_DISAGREEMENT" in disagreement["reasons"]

    stale_oracle = ShadowOracle()
    stale_oracle.ingest(observation(200, "equity-venue:Q", "Q", age=11))
    stale = stale_oracle.ingest(observation(200.01, "equity-venue:V", "V"))
    assert stale["reference"] is None
    assert stale["independent_source_families"] == 1


def test_large_move_requires_a_third_venue_family():
    oracle = ShadowOracle()
    oracle.ingest(observation(200, "equity-venue:Q", "Q"))
    oracle.ingest(observation(200.02, "equity-venue:V", "V"))
    oracle.ingest(observation(180, "equity-venue:Q", "Q"))
    two_venues = oracle.ingest(observation(180.03, "equity-venue:V", "V"))
    assert two_venues["reference"] is None
    assert "LARGE_MOVE_NEEDS_THREE_VENUE_FAMILIES" in two_venues["reasons"]
    three_venues = oracle.ingest(observation(180.01, "equity-venue:P", "P"))
    assert three_venues["status"] == "QUALIFIED"
    assert three_venues["reference"] == 180.01
