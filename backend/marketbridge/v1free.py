"""MarketBridge v1 free-first routes layered onto the existing API.

These routes deliberately reuse the existing RiskGateway. Synthetic War Room
scenarios are labelled and never masquerade as live exchange executions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .context import get_market_intelligence
from .providers import provider_registry
from .risk.models import AccountExposure, IntentKind, OrderIntent, RiskCheckRequest, Side, VenueMarketContext


class WarRoomRequest(BaseModel):
    scenario: str = Field(pattern=r"^(NORMAL|POISONED_MARK|RECOVERY)$")
    intent: str = Field(default="OPEN", pattern=r"^(OPEN|CLOSE)$")
    symbol: str = Field(default="NVDA", pattern=r"^(NVDA|TSLA)$")


class WarRoomReplayRequest(BaseModel):
    passport_id: str = Field(pattern=r"^mbp_[0-9a-f]{24}$")
    mode: str = Field(default="WITHOUT_SAFETY_GATE", pattern=r"^(CURRENT|WITHOUT_SAFETY_GATE)$")


def _war_room_risk_request(payload: WarRoomRequest, now: datetime) -> RiskCheckRequest:
    symbol = payload.symbol.upper()
    base_reference = Decimal("184.52") if symbol == "NVDA" else Decimal("346.80")
    mark = {
        "NORMAL": base_reference - Decimal("0.01"),
        "POISONED_MARK": (base_reference * Decimal("1.03078")).quantize(Decimal("0.000001")),
        "RECOVERY": base_reference + Decimal("0.01"),
    }[payload.scenario]
    intent_kind = IntentKind.CLOSE if payload.intent == "CLOSE" else IntentKind.OPEN
    position_notional = Decimal("10000") if intent_kind == IntentKind.CLOSE else Decimal("0")
    return RiskCheckRequest(
        request_id=f"warroom-{uuid.uuid4().hex[:20]}",
        symbol=symbol,
        intent=OrderIntent(
            kind=intent_kind,
            side=Side.BUY,
            notional_usd=Decimal("10000"),
            requested_leverage=Decimal("10"),
        ),
        account=AccountExposure(
            equity_usd=Decimal("10000"),
            margin_available_usd=Decimal("10000"),
            position_notional_usd=position_notional,
            current_leverage=Decimal("1") if position_notional else Decimal("0"),
            liquidation_price=(base_reference * Decimal("0.80")) if position_notional else None,
            position_side=Side.BUY if position_notional else None,
        ),
        market=VenueMarketContext(
            mark_price=mark,
            event_time=now,
            session="REGULAR",
        ),
        demo_scenario=payload.scenario,
    )


def _story(payload: WarRoomRequest, result: dict) -> dict:
    market = result.get("market", {})
    scenario_copy = {
        "NORMAL": {
            "headline": "Independent evidence and venue mark agree.",
            "detail": "MarketBridge can permit new exposure subject to account and leverage policy.",
        },
        "POISONED_MARK": {
            "headline": "Venue mark diverges sharply from independent Market Truth.",
            "detail": "New exposure fails closed while a valid reduce/close path remains available.",
        },
        "RECOVERY": {
            "headline": "Evidence has converged again, but recovery is deliberately sticky.",
            "detail": "Hysteresis prevents one good tick from instantly re-enabling leverage after an incident.",
        },
    }[payload.scenario]
    return {
        **scenario_copy,
        "data_mode": "SYNTHETIC_DEMO",
        "no_trade_submitted": True,
        "reference_price": market.get("reference_price"),
        "venue_mark": market.get("venue_mark"),
        "divergence_bps": market.get("divergence_bps"),
        "confidence": market.get("confidence"),
        "market_state": market.get("asset_state"),
        "decision": result.get("action"),
        "exit_invariant": "VALID REDUCE/CLOSE REMAINS AVAILABLE",
    }


def install_v1_free(app: FastAPI, pipeline, risk_gateway) -> None:
    if getattr(app.state, "marketbridge_v1_free_installed", False):
        return
    app.state.marketbridge_v1_free_installed = True

    @app.get("/v1/providers")
    def providers():
        return provider_registry(pipeline.snapshot())

    @app.get("/v1/intelligence/{symbol}")
    def intelligence(symbol: str, refresh: bool = False):
        normalized = symbol.upper().strip()
        if normalized not in {"NVDA", "TSLA", "AAPL", "MSFT", "AMD", "QQQ"}:
            raise HTTPException(status_code=404, detail="Unsupported intelligence symbol")
        try:
            return get_market_intelligence(normalized, force=refresh)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/demo/war-room")
    def war_room(payload: WarRoomRequest):
        now = datetime.now(timezone.utc)
        request = _war_room_risk_request(payload, now)
        result = risk_gateway.check(request, pipeline.snapshot(), now=now)
        return {
            "scenario": payload.scenario,
            "intent": payload.intent,
            "symbol": payload.symbol,
            "story": _story(payload, result),
            "result": result,
        }

    @app.post("/v1/demo/war-room/replay")
    def war_room_replay(payload: WarRoomReplayRequest):
        try:
            return risk_gateway.replay(payload.passport_id, payload.mode)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/demo/war-room/reset")
    def war_room_reset():
        risk_gateway.recovery.reset()
        return {"status": "RESET", "data_mode": "SYNTHETIC_DEMO"}
