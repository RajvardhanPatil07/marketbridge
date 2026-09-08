from datetime import datetime, timedelta, timezone

import pytest

from marketbridge.shadow import NormalizedObservation, ShadowOracle


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


def test_venue_mark_immediately_annotates_current_decision_and_audit_log():
    audited = []
    oracle = ShadowOracle(audited.append)
    oracle.ingest(observation(200.00, "equity-venue:Q", "Q"))
    oracle.ingest(observation(200.04, "equity-venue:V", "V"))

    oracle.update_venue_mark("NVDA", 201.02, NOW)
    snapshot = oracle.snapshot()
    decision = snapshot["decisions"][0]

    assert decision["venue_mark"]["price"] == 201.02
    assert decision["mark_divergence_bps"] == pytest.approx(49.995, rel=1e-3)
    assert decision["reasons"][-1] == "VENUE_MARK_OBSERVED"
    assert snapshot["decision_log"][0] == decision
    assert audited[-1] == decision


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
