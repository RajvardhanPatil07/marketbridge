from copy import deepcopy
from datetime import datetime, timedelta, timezone

from hypothesis import given, strategies as st

from marketbridge.shadow import NormalizedObservation, ShadowOracle


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def observed(price: float, venue: str, *, provider: str = "provider-a", age: int = 0):
    return NormalizedObservation(
        symbol="NVDA",
        price=price,
        event_time=NOW - timedelta(seconds=age),
        received_at=NOW,
        source_id=f"{provider}:{venue}",
        source_family=f"equity-venue:{venue}",
        venue=venue,
        eligible=True,
        provider_family=provider,
        venue_family=venue,
    )


@given(st.floats(min_value=10, max_value=1000, allow_nan=False, allow_infinity=False))
def test_one_provider_never_masquerades_as_provider_independence(price):
    oracle = ShadowOracle()
    oracle.ingest(observed(price, "Q"))
    decision = oracle.ingest(observed(price, "V"))
    assert decision["independent_provider_families"] == 1
    assert "SINGLE_PROVIDER_CONCENTRATION" in decision["reasons"]


@given(
    st.floats(min_value=10, max_value=1000, allow_nan=False, allow_infinity=False),
    st.integers(min_value=11, max_value=86_400),
)
def test_stale_evidence_never_qualifies(price, age):
    oracle = ShadowOracle()
    oracle.ingest(observed(price, "Q", provider="a", age=age))
    decision = oracle.ingest(observed(price, "V", provider="b", age=age))
    assert decision["reference"] is None
    assert decision["new_exposure_allowed"] is False


@given(
    confidence=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    divergence=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    anomaly=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
)
def test_ai_signal_can_never_loosen_deterministic_policy(confidence, divergence, anomaly):
    base = ShadowOracle._risk_policy(confidence, divergence, "QUALIFIED")
    learned = ShadowOracle._risk_policy(confidence, divergence, "QUALIFIED", anomaly, True)
    assert learned["recommended_max_leverage"] <= base["recommended_max_leverage"]
    assert learned["max_notional_multiplier"] <= base["max_notional_multiplier"]


@given(st.integers(min_value=0, max_value=99))
def test_any_passport_claim_mutation_breaks_verification(confidence):
    oracle = ShadowOracle()
    passport = oracle.ingest(observed(100, "Q"))["passport"]
    tampered = deepcopy(passport)
    tampered["claims"]["confidence"] = confidence
    if confidence == passport["claims"]["confidence"]:
        tampered["claims"]["reasons"].append("TAMPERED")
    assert ShadowOracle.verify_passport(tampered) is False
