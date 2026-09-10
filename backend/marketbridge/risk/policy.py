"""Deterministic consequence policy. Market confidence is immutable input."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from .models import IntentKind, RiskCheckRequest
from .portfolio import assess_portfolio

POLICY_VERSION = "mocha-risk-v1.1.0"
ACTION_RANK = {"ALLOW": 0, "CAP_LEVERAGE": 1, "REVIEW": 2, "BLOCK_NEW_RISK": 3}


@dataclass(frozen=True)
class ExposureResult:
    current_leverage: Decimal
    projected_leverage: Decimal
    liquidation_distance_pct: Decimal | None
    classification: str


def exposure_for(
    request: RiskCheckRequest,
    reference_price: Decimal | None,
) -> ExposureResult:
    account = request.account
    current = account.current_leverage
    if current is None:
        current = account.position_notional_usd / account.equity_usd
    added = (
        Decimal("0")
        if request.intent.kind in {IntentKind.REDUCE, IntentKind.CLOSE}
        else request.intent.notional_usd
    )
    projected = (account.position_notional_usd + added) / account.equity_usd
    distance = None
    if reference_price is not None and account.liquidation_price is not None:
        distance = (
            abs(reference_price - account.liquidation_price)
            / reference_price
            * Decimal("100")
        )
    if distance is not None and distance < Decimal("2"):
        classification = "CRITICAL"
    elif distance is not None and distance < Decimal("5"):
        classification = "ELEVATED"
    elif projected > Decimal("8"):
        classification = "ELEVATED"
    elif projected > Decimal("6"):
        classification = "GUARDED"
    else:
        classification = "LOW"
    return ExposureResult(current, projected, distance, classification)


def stricter_action(left: str, right: str | None) -> str:
    """AI/candidate policy can only move toward greater restriction."""
    if right is None:
        return left
    return right if ACTION_RANK[right] > ACTION_RANK[left] else left


def decide(
    request: RiskCheckRequest,
    market_truth: dict,
    asset_policy: dict,
    *,
    ai_action: str | None = None,
) -> dict:
    reference = (
        Decimal(str(market_truth["reference_price"]))
        if market_truth.get("reference_price") is not None
        else None
    )
    exposure = exposure_for(request, reference)
    portfolio = assess_portfolio(request)
    intent = request.intent
    reasons: list[str] = []
    session = market_truth["session"]
    configured_cap = Decimal(str(asset_policy["max_leverage"].get(session, 0)))

    if intent.kind in {IntentKind.REDUCE, IntentKind.CLOSE}:
        return {
            "action": "ALLOW",
            "permitted_leverage": intent.requested_leverage,
            "permitted_notional_usd": min(
                intent.notional_usd,
                request.account.position_notional_usd,
            ),
            "reasons": ["VALID_EXIT_PRESERVED"],
            "exposure": exposure,
            "portfolio": portfolio,
        }

    blockers = []
    if market_truth.get("reference_status") != "QUALIFIED":
        blockers.append("DIRECT_QUALIFIED_REFERENCE_REQUIRED")
    if market_truth.get("stale"):
        blockers.append("STALE_MARKET_EVIDENCE")
    if market_truth.get("malformed"):
        blockers.append("MALFORMED_MARKET_EVIDENCE")
    if not market_truth.get("authenticated", True):
        blockers.append("UNAUTHENTICATED_MARKET_EVIDENCE")
    if not market_truth.get("entitled", False):
        blockers.append("EVIDENCE_NOT_ENTITLED_FOR_COMPUTATION")
    if market_truth.get("provider_count", 0) < asset_policy["min_independent_providers"]:
        blockers.append("MINIMUM_PROVIDER_INDEPENDENCE_NOT_MET")
    if asset_policy["corporate_action_state"] != "CLEAR":
        blockers.append("UNRESOLVED_CORPORATE_ACTION")
    if market_truth.get("asset_state") in {"RESTRICTED", "HALTED", "RECOVERY_PENDING"}:
        blockers.append(f"MARKET_{market_truth['asset_state']}")
    if session in {"EXCHANGE_HALT", "CORPORATE_ACTION"}:
        blockers.append(session)
    if reference is None:
        blockers.append("NO_REFERENCE")
    if blockers:
        return {
            "action": "BLOCK_NEW_RISK",
            "permitted_leverage": Decimal("0"),
            "permitted_notional_usd": Decimal("0"),
            "reasons": list(dict.fromkeys(blockers)),
            "exposure": exposure,
            "portfolio": portfolio,
        }

    cap = configured_cap
    if session != "REGULAR":
        reasons.append(f"{session}_SESSION")
    if (
        exposure.liquidation_distance_pct is None
        and request.account.position_notional_usd > 0
    ):
        action = "REVIEW"
        reasons.append("LIQUIDATION_DISTANCE_UNAVAILABLE")
    else:
        action = "ALLOW"

    if exposure.classification == "CRITICAL":
        return {
            "action": "BLOCK_NEW_RISK",
            "permitted_leverage": Decimal("0"),
            "permitted_notional_usd": Decimal("0"),
            "reasons": ["NEAR_LIQUIDATION", "EXISTING_EXPOSURE"],
            "exposure": exposure,
            "portfolio": portfolio,
        }
    if exposure.classification == "ELEVATED":
        cap = min(cap, Decimal("1"))
        reasons.extend(
            [
                "NEAR_LIQUIDATION"
                if exposure.liquidation_distance_pct is not None
                else "EXISTING_EXPOSURE"
            ]
        )
    elif exposure.classification == "GUARDED":
        cap = min(cap, Decimal("3"))
        reasons.append("EXISTING_EXPOSURE")

    margin_cap_notional = request.account.margin_available_usd * max(
        cap,
        Decimal("1"),
    )
    exposure_room = max(
        Decimal("0"),
        request.account.equity_usd * cap - request.account.position_notional_usd,
    )
    portfolio_room = Decimal(str(portfolio["max_additional_notional_usd"]))
    permitted_notional = min(
        intent.notional_usd,
        margin_cap_notional,
        exposure_room,
        portfolio_room,
    )
    permitted_notional = permitted_notional.quantize(
        Decimal("0.01"),
        rounding=ROUND_DOWN,
    )
    permitted_leverage = min(intent.requested_leverage, cap)

    if portfolio.get("enabled") and portfolio.get("breaches"):
        reasons.extend(portfolio["breaches"])
        if permitted_notional < intent.notional_usd:
            action = stricter_action(action, "CAP_LEVERAGE")

    if permitted_notional <= 0:
        action = "BLOCK_NEW_RISK"
        permitted_leverage = Decimal("0")
        reasons.append("NO_RISK_CAPACITY")
    elif (
        permitted_leverage < intent.requested_leverage
        or permitted_notional < intent.notional_usd
    ):
        action = stricter_action(action, "CAP_LEVERAGE")
        reasons.append("POLICY_LIMIT")

    if asset_policy.get("manual_review_required"):
        action = stricter_action(action, "REVIEW")
        reasons.append("NASDAQ_DEFAULT_REVIEW")

    tightened = stricter_action(action, ai_action)
    if tightened != action:
        action = tightened
        reasons.append("AI_TIGHTEN_ONLY")
        if action == "BLOCK_NEW_RISK":
            permitted_leverage = Decimal("0")
            permitted_notional = Decimal("0")

    return {
        "action": action,
        "permitted_leverage": permitted_leverage,
        "permitted_notional_usd": permitted_notional,
        "reasons": list(dict.fromkeys(reasons or ["WITHIN_POLICY"])),
        "exposure": exposure,
        "portfolio": portfolio,
    }
