"""Judge-facing routes that exercise production risk primitives honestly.

The live baseline route never invents independent market evidence. It can inject a
synthetic venue mark, but Market Truth remains whatever the real backend snapshot
currently qualifies. The safe-order route rewrites an order only as an advisory
and binds the rewritten ticket to a fresh Safety Passport.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os
import uuid
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .risk.models import (
    AccountExposure,
    OrderIntent,
    RiskCheckRequest,
    Side,
    VenueMarketContext,
)

IST = ZoneInfo("Asia/Kolkata")


class LiveBaselineRequest(BaseModel):
    symbol: str = Field(default="NVDA", pattern=r"^(NVDA|TSLA|AAPL|MSFT|AMD)$")
    inject_attack: bool = False
    requested_notional_usd: Decimal = Field(default=Decimal("10000"), gt=0)
    requested_leverage: Decimal = Field(default=Decimal("10"), gt=0, le=100)


class SafeAlternativeRequest(BaseModel):
    request: RiskCheckRequest


def _money_context(usd_value: Decimal | float | int | None) -> dict:
    raw = os.getenv("USDINR", "").strip()
    try:
        usd_inr = Decimal(raw) if raw else None
    except Exception:
        usd_inr = None
    usd = Decimal(str(usd_value)) if usd_value is not None else None
    return {
        "usd": float(usd) if usd is not None else None,
        "inr": float((usd * usd_inr).quantize(Decimal("0.01"))) if usd is not None and usd_inr else None,
        "usd_inr": float(usd_inr) if usd_inr else None,
        "fx_source": "USDINR environment configuration" if usd_inr else "UNCONFIGURED",
    }


def _clock(now: datetime) -> dict:
    return {
        "utc": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ist": now.astimezone(IST).isoformat(),
        "timezone": "Asia/Kolkata",
    }


def install_judge_routes(app: FastAPI, pipeline, risk_gateway) -> None:
    if getattr(app.state, "marketbridge_judge_routes_installed", False):
        return
    app.state.marketbridge_judge_routes_installed = True

    @app.post("/v1/demo/live-baseline")
    def live_baseline(payload: LiveBaselineRequest):
        now = datetime.now(timezone.utc)
        snapshot = pipeline.snapshot()
        symbol = payload.symbol.upper()
        decision = next(
            (item for item in snapshot.get("decisions", []) if item.get("symbol") == symbol),
            None,
        )
        reference = None if decision is None else decision.get("reference")
        if reference is None:
            return {
                "available": False,
                "data_mode": "LIVE_BASELINE_UNAVAILABLE",
                "symbol": symbol,
                "clock": _clock(now),
                "reason": "No backend-qualified reference is currently available for this symbol.",
                "provenance": {
                    "underlying_evidence": "LIVE_BACKEND_SNAPSHOT",
                    "venue_mark": "NOT_INJECTED",
                    "policy": "PRODUCTION_GATE",
                },
            }

        reference_decimal = Decimal(str(reference))
        mark = (
            reference_decimal * Decimal("1.03078")
            if payload.inject_attack
            else reference_decimal
        ).quantize(Decimal("0.000001"))
        request = RiskCheckRequest(
            request_id=f"live-baseline-{uuid.uuid4().hex[:20]}",
            symbol=symbol,
            intent=OrderIntent(
                kind="OPEN",
                side=Side.BUY,
                notional_usd=payload.requested_notional_usd,
                requested_leverage=payload.requested_leverage,
            ),
            account=AccountExposure(
                equity_usd=Decimal("10000"),
                margin_available_usd=Decimal("10000"),
                position_notional_usd=Decimal("0"),
                current_leverage=Decimal("0"),
            ),
            market=VenueMarketContext(
                mark_price=mark,
                event_time=now,
            ),
        )
        result = risk_gateway.check(request, snapshot, now=now)
        market = result.get("market", {})
        return {
            "available": True,
            "data_mode": "LIVE_BASELINE_WITH_SYNTHETIC_VENUE_ATTACK" if payload.inject_attack else "LIVE_BASELINE",
            "symbol": symbol,
            "clock": _clock(now),
            "provenance": {
                "underlying_evidence": "LIVE_BACKEND_SNAPSHOT",
                "venue_mark": "SYNTHETIC_INJECTED" if payload.inject_attack else "REFERENCE_ALIGNED_CONTROL",
                "policy": "PRODUCTION_GATE",
                "trade_submitted": False,
            },
            "market_truth": {
                "reference_price": market.get("reference_price"),
                "reference_status": market.get("reference_status"),
                "provider_count": market.get("provider_count"),
                "venue_count": market.get("venue_count"),
                "confidence": market.get("confidence"),
            },
            "venue_mark": float(mark),
            "divergence_bps": market.get("divergence_bps"),
            "decision": result,
            "requested_notional": _money_context(payload.requested_notional_usd),
        }

    @app.post("/v1/order/safe-alternative")
    def safe_alternative(payload: SafeAlternativeRequest):
        now = datetime.now(timezone.utc)
        snapshot = pipeline.snapshot()
        original = risk_gateway.check(payload.request, snapshot, now=now)
        safe = original.get("safe_alternative") or {}
        permitted_notional = Decimal(str(safe.get("max_notional_usd") or 0))
        permitted_leverage = Decimal(str(safe.get("max_leverage") or 0))
        requested_notional = payload.request.intent.notional_usd

        if not safe.get("available") or permitted_notional <= 0 or permitted_leverage <= 0:
            return {
                "advisory_only": True,
                "execution_submitted": False,
                "applicable": False,
                "clock": _clock(now),
                "original": original,
                "reason": "No positive safe alternative is available under the current market/account state.",
            }

        rewritten = payload.request.model_copy(
            update={
                "request_id": f"safe-{uuid.uuid4().hex[:24]}",
                "intent": payload.request.intent.model_copy(
                    update={
                        "notional_usd": permitted_notional,
                        "requested_leverage": permitted_leverage,
                    }
                ),
            }
        )
        rebound = risk_gateway.check(rewritten, snapshot, now=now)
        return {
            "advisory_only": True,
            "execution_submitted": False,
            "applicable": True,
            "clock": _clock(now),
            "original": {
                "request_id": payload.request.request_id,
                "passport_id": original.get("passport_id"),
                "action": original.get("action"),
                "requested_leverage": float(payload.request.intent.requested_leverage),
                "requested_notional": _money_context(requested_notional),
            },
            "safe_order": {
                "request_id": rewritten.request_id,
                "symbol": rewritten.symbol,
                "side": rewritten.intent.side.value,
                "intent": rewritten.intent.kind.value,
                "leverage": float(permitted_leverage),
                "notional": _money_context(permitted_notional),
                "requested_order_reduction_usd": float((requested_notional - permitted_notional).quantize(Decimal("0.01"))),
            },
            "fresh_passport_id": rebound.get("passport_id"),
            "fresh_decision": rebound.get("action"),
            "boundary": "Advisory rewrite only. MarketBridge does not execute, custody, or sign the order.",
        }
