from datetime import datetime, timezone
from pathlib import Path

from marketbridge.risk import RiskCheckRequest, RiskGateway
from marketbridge.risk.policy import decide


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 11, 6, 0, tzinfo=timezone.utc)


def _request(intent="OPEN"):
    exposure = 10000 if intent == "CLOSE" else 0
    return RiskCheckRequest.model_validate(
        {
            "request_id": f"live-divergence-{intent.lower()}",
            "symbol": "NVDA",
            "intent": {
                "kind": intent,
                "side": "BUY",
                "notional_usd": 10000,
                "requested_leverage": 10,
            },
            "account": {
                "equity_usd": 10000,
                "margin_available_usd": 10000,
                "position_notional_usd": exposure,
            },
            "market": {
                "mark_price": 190.20,
                "event_time": NOW.isoformat(),
                "session": "REGULAR",
            },
        }
    )


def _qualified_truth():
    return {
        "reference_price": 184.52,
        "reference_status": "QUALIFIED",
        "confidence": 0.95,
        "venue_mark": 190.20,
        "divergence_bps": 307.82,
        "provider_count": 2,
        "venue_count": 2,
        "session": "REGULAR",
        "asset_state": "NORMAL",
        "stale": False,
        "malformed": False,
        "authenticated": True,
        "entitled": True,
        "evidence": [],
    }


def test_large_live_venue_divergence_blocks_new_risk():
    gateway = RiskGateway(ROOT)
    result = decide(_request("OPEN"), _qualified_truth(), gateway.assets["NVDA"])
    assert result["action"] == "BLOCK_NEW_RISK"
    assert "VENUE_MARK_DIVERGENCE_LIMIT_EXCEEDED" in result["reasons"]


def test_large_live_venue_divergence_does_not_trap_exit():
    gateway = RiskGateway(ROOT)
    result = decide(_request("CLOSE"), _qualified_truth(), gateway.assets["NVDA"])
    assert result["action"] == "ALLOW"
    assert result["reasons"] == ["VALID_EXIT_PRESERVED"]
