from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from marketbridge.risk import RiskCheckRequest, RiskGateway
from marketbridge.risk.passport import PassportStore, canonical_hash
from marketbridge.risk.policy import decide, stricter_action
from marketbridge.risk.recovery import RecoveryTracker
from marketbridge.risk.session import equity_session


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)  # 11:00 New York, regular session


def request(
    *, request_id="ord_policy_1", intent="OPEN", scenario="NORMAL", mark=184.55, reference=184.52,
    event_time=NOW, equity=2000, margin=10000, exposure=0, liquidation=None, leverage=10,
    notional=10000, session="REGULAR",
):
    account = {
        "equity_usd": equity, "margin_available_usd": margin,
        "position_notional_usd": exposure,
    }
    if liquidation is not None:
        account.update({"liquidation_price": liquidation, "position_side": "BUY"})
    if intent in {"REDUCE", "CLOSE"} and exposure == 0:
        account["position_notional_usd"] = notional
    return RiskCheckRequest.model_validate({
        "request_id": request_id,
        "symbol": "NVDA",
        "intent": {"kind": intent, "side": "BUY", "notional_usd": notional, "requested_leverage": leverage},
        "account": account,
        "market": {"mark_price": mark, "oracle_price": reference, "event_time": event_time.isoformat(), "session": session},
        "demo_scenario": scenario,
    })


def check(gateway, **kwargs):
    return gateway.check(request(**kwargs), {"decisions": []}, now=NOW)


def test_qualified_regular_session_allows_low_exposure_order():
    result = check(RiskGateway(ROOT))
    assert result["action"] == "ALLOW"
    assert result["permitted_leverage"] == 10
    assert result["permitted_notional_usd"] == 10000
    assert result["market"]["confidence"] == 0.95


def test_overnight_caps_and_poisoned_mark_blocks_new_risk():
    gateway = RiskGateway(ROOT)
    capped = check(gateway, request_id="ord_overnight", session="OVERNIGHT")
    assert capped["action"] == "CAP_LEVERAGE"
    assert capped["permitted_leverage"] == 3
    assert "OVERNIGHT_SESSION" in capped["reasons"]

    blocked = check(
        gateway, request_id="ord_poison", scenario="POISONED_MARK", mark=190.20,
    )
    assert blocked["action"] == "BLOCK_NEW_RISK"
    assert blocked["permitted_notional_usd"] == 0
    assert blocked["market"]["divergence_bps"] == pytest.approx(307.82, rel=1e-3)


@pytest.mark.parametrize("intent", ["OPEN", "INCREASE"])
def test_stale_evidence_fails_closed_for_new_risk(intent):
    result = check(
        RiskGateway(ROOT), request_id=f"ord_stale_{intent}", intent=intent,
        event_time=NOW - timedelta(seconds=11),
    )
    assert result["action"] == "BLOCK_NEW_RISK"
    assert "STALE_MARKET_EVIDENCE" in result["reasons"]


@pytest.mark.parametrize("intent", ["REDUCE", "CLOSE"])
def test_valid_exits_are_preserved_when_market_evidence_is_bad(intent):
    result = check(
        RiskGateway(ROOT), request_id=f"ord_exit_{intent}", intent=intent,
        scenario="POISONED_MARK", mark=190.20, exposure=10000,
        event_time=NOW - timedelta(minutes=5),
    )
    assert result["action"] == "ALLOW"
    assert result["reduce_only_allowed"] is True
    assert result["reasons"] == ["VALID_EXIT_PRESERVED"]


def test_near_liquidation_blocks_and_missing_distance_requires_review():
    gateway = RiskGateway(ROOT)
    blocked = check(
        gateway, request_id="ord_near_liq", notional=500, exposure=1000,
        equity=10000, liquidation=183.50,
    )
    assert blocked["action"] == "BLOCK_NEW_RISK"
    assert blocked["account_risk"]["liquidation_distance_pct"] < 2

    reviewed = check(
        gateway, request_id="ord_review", notional=500, exposure=1000,
        equity=10000, liquidation=None,
    )
    assert reviewed["action"] == "REVIEW"


def test_account_consequence_never_rewrites_market_confidence():
    gateway = RiskGateway(ROOT)
    safe = check(gateway, request_id="ord_conf_safe", equity=10000, notional=500)
    risky = check(
        gateway, request_id="ord_conf_risky", equity=2000, exposure=14000,
        liquidation=183.50, notional=10000,
    )
    assert safe["market"]["confidence"] == risky["market"]["confidence"] == 0.95
    assert safe["action"] == "ALLOW"
    assert risky["action"] == "BLOCK_NEW_RISK"


def test_ai_action_can_tighten_but_never_loosen_policy():
    assert stricter_action("BLOCK_NEW_RISK", "ALLOW") == "BLOCK_NEW_RISK"
    assert stricter_action("CAP_LEVERAGE", "ALLOW") == "CAP_LEVERAGE"
    assert stricter_action("ALLOW", "CAP_LEVERAGE") == "CAP_LEVERAGE"
    assert stricter_action("CAP_LEVERAGE", "BLOCK_NEW_RISK") == "BLOCK_NEW_RISK"


def test_minimum_provider_independence_and_corporate_action_fail_closed():
    gateway = RiskGateway(ROOT)
    req = request(request_id="ord_direct_policy")
    truth = gateway.market_truth(req, {"decisions": []}, NOW)
    truth["provider_count"] = 1
    result = decide(req, truth, gateway.assets["NVDA"])
    assert result["action"] == "BLOCK_NEW_RISK"
    assert "MINIMUM_PROVIDER_INDEPENDENCE_NOT_MET" in result["reasons"]

    asset = deepcopy(gateway.assets["NVDA"])
    asset["corporate_action_state"] = "SPLIT_RECONCILIATION"
    truth["provider_count"] = 2
    result = decide(req, truth, asset)
    assert result["action"] == "BLOCK_NEW_RISK"
    assert "UNRESOLVED_CORPORATE_ACTION" in result["reasons"]


def test_idempotency_material_change_and_passport_tamper_detection():
    gateway = RiskGateway(ROOT)
    original_request = request(request_id="ord_idempotent")
    first = gateway.check(original_request, {"decisions": []}, now=NOW)
    second = gateway.check(original_request, {"decisions": []}, now=NOW + timedelta(seconds=1))
    assert second["passport_id"] == first["passport_id"]
    assert PassportStore.verify(first["passport"]) is True

    tampered = deepcopy(first["passport"])
    tampered["claims"]["decision"]["action"] = "BLOCK_NEW_RISK"
    assert PassportStore.verify(tampered) is False
    assert canonical_hash(first["passport"]["claims"]) == first["passport"]["content_hash"]

    changed = request(request_id="ord_idempotent", notional=9999)
    with pytest.raises(ValueError, match="materially different"):
        gateway.check(changed, {"decisions": []}, now=NOW)

    with pytest.raises(ValueError, match="decision expired"):
        gateway.check(original_request, {"decisions": []}, now=NOW + timedelta(seconds=4))


def test_passport_chain_and_deterministic_replay_parity():
    gateway = RiskGateway(ROOT)
    first = check(gateway, request_id="ord_chain_1")
    second = check(gateway, request_id="ord_chain_2", session="OVERNIGHT")
    assert first["passport"]["previous_hash"] is None
    assert second["passport"]["previous_hash"] == first["passport"]["chain_hash"]
    replay = gateway.replay(second["passport_id"], "CURRENT")
    assert replay["deterministic_parity"] is True
    counterfactual = gateway.replay(second["passport_id"], "WITHOUT_SAFETY_GATE")
    assert counterfactual["counterfactual"] is True
    assert counterfactual["replayed_action"] == "ALLOW"
    assert "not proof" in counterfactual["disclaimer"]
    annotated = gateway.passports.record_outcome(second["passport_id"], "accepted")
    assert annotated["outcome"] == "accepted"
    assert PassportStore.verify(annotated) is True


def test_recovery_hysteresis_needs_multiple_observations_and_time():
    tracker = RecoveryTracker(stable_observations=3, minimum_duration_seconds=2)
    assert tracker.update("NVDA", "HALTED", False, NOW)["state"] == "HALTED"
    assert tracker.update("NVDA", "NORMAL", True, NOW + timedelta(seconds=1))["state"] == "RECOVERY_PENDING"
    assert tracker.update("NVDA", "NORMAL", True, NOW + timedelta(seconds=2))["state"] == "RECOVERY_PENDING"
    restored = tracker.update("NVDA", "NORMAL", True, NOW + timedelta(seconds=3))
    assert restored["state"] == "NORMAL"


def test_exchange_session_handles_weekends_holidays_and_dst_zone():
    assert equity_session(datetime(2026, 9, 7, 15, tzinfo=timezone.utc)).value == "CLOSED"
    assert equity_session(datetime(2026, 9, 12, 15, tzinfo=timezone.utc)).value == "CLOSED"
    assert equity_session(datetime(2026, 7, 6, 14, tzinfo=timezone.utc)).value == "REGULAR"


def test_strict_contract_rejects_crossed_market_and_extra_fields():
    payload = request().model_dump(mode="json")
    payload["market"].update({"best_bid": "185", "best_ask": "184"})
    with pytest.raises(ValueError, match="best_bid"):
        RiskCheckRequest.model_validate(payload)
    payload = request().model_dump(mode="json")
    payload["account"]["private_key"] = "must-never-be-accepted"
    with pytest.raises(ValueError):
        RiskCheckRequest.model_validate(payload)


def test_canonical_hash_is_stable_across_key_order():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash(json.loads('{"b":2,"a":1}'))
