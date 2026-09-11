"""MarketBridge v1 free-first routes.

The War Room can use a qualified live Market Truth when it exists. When the
required independent evidence is unavailable it falls back to an explicitly
labelled synthetic fixture. Both paths execute the same RiskGateway policy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .context import get_market_intelligence
from .proof import (
    historical_incident_policy_replay,
    portfolio_demo,
    risk_gate_benchmark,
)
from .providers import provider_registry
from .risk.models import (
    AccountExposure,
    IntentKind,
    OrderIntent,
    RiskCheckRequest,
    Side,
    VenueMarketContext,
)


class WarRoomRequest(BaseModel):
    scenario: str = Field(pattern=r"^(NORMAL|POISONED_MARK|RECOVERY)$")
    intent: str = Field(default="OPEN", pattern=r"^(OPEN|CLOSE)$")
    mode: str = Field(default="AUTO", pattern=r"^(AUTO|LIVE|SYNTHETIC)$")
    symbol: str = Field(default="NVDA", pattern=r"^(NVDA|TSLA|AAPL|MSFT|AMD)$")
    baseline_price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"))
    requested_notional_usd: Decimal = Field(default=Decimal("10000"), gt=0, le=Decimal("100000000"))
    requested_leverage: Decimal = Field(default=Decimal("10"), gt=0, le=Decimal("100"))
    attack_bps: Decimal = Field(default=Decimal("350"), ge=Decimal("0"), le=Decimal("5000"))
    account_equity_usd: Decimal = Field(default=Decimal("10000"), gt=0, le=Decimal("1000000000"))
    margin_available_usd: Decimal | None = Field(default=None, ge=0, le=Decimal("1000000000"))
    existing_position_usd: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1000000000"))


class PortfolioDemoRequest(BaseModel):
    symbol: str = Field(default="NVDA", pattern=r"^(NVDA|TSLA|AAPL|MSFT|AMD)$")
    requested_notional_usd: Decimal = Field(default=Decimal("10000"), gt=0, le=Decimal("100000000"))
    requested_leverage: Decimal = Field(default=Decimal("10"), gt=0, le=Decimal("100"))
    account_equity_usd: Decimal = Field(default=Decimal("10000"), gt=0, le=Decimal("1000000000"))
    existing_position_usd: Decimal = Field(default=Decimal("22000"), ge=0, le=Decimal("1000000000"))


class WarRoomReplayRequest(BaseModel):
    passport_id: str = Field(pattern=r"^mbp_[0-9a-f]{24}$")
    mode: str = Field(
        default="WITHOUT_SAFETY_GATE",
        pattern=r"^(CURRENT|WITHOUT_SAFETY_GATE)$",
    )


def _decision(snapshot: dict, symbol: str) -> dict | None:
    return next(
        (
            item
            for item in snapshot.get("decisions", [])
            if item.get("symbol") == symbol
        ),
        None,
    )


def _qualified_live_reference(snapshot: dict, symbol: str) -> tuple[Decimal, dict] | None:
    decision = _decision(snapshot, symbol)
    if not decision or decision.get("status") != "QUALIFIED":
        return None
    reference = decision.get("reference")
    if reference is None:
        return None
    families = {
        item.get("provider_family")
        for item in decision.get("evidence", [])
        if item.get("eligible") and item.get("fresh") and item.get("provider_family")
    }
    required = int(decision.get("required_independent_sources") or 2)
    if len(families) < required:
        return None
    return Decimal(str(reference)), decision


def _synthetic_fallback(symbol: str) -> Decimal:
    # Stable, clearly synthetic fallback. It is a scenario seed, not an observed price.
    checksum = sum(ord(char) for char in symbol)
    return Decimal(100 + checksum % 120).quantize(Decimal("0.01"))


def _resolve_reference(payload: WarRoomRequest, snapshot: dict) -> tuple[Decimal, str, bool]:
    live = _qualified_live_reference(snapshot, payload.symbol)
    if payload.mode != "SYNTHETIC" and live is not None:
        return live[0], "LIVE_QUALIFIED_REFERENCE", False
    if payload.mode == "LIVE":
        raise HTTPException(
            status_code=409,
            detail="LIVE mode requires a currently QUALIFIED reference with the configured independent-provider quorum.",
        )
    if payload.baseline_price is not None:
        return payload.baseline_price, "CLIENT_DISPLAY_SNAPSHOT", True
    decision = _decision(snapshot, payload.symbol)
    if decision and decision.get("reference") is not None:
        return Decimal(str(decision["reference"])), "LATEST_PIPELINE_REFERENCE", True
    return _synthetic_fallback(payload.symbol), "SYNTHETIC_FALLBACK", True


def _war_room_risk_request(
    payload: WarRoomRequest,
    now: datetime,
    snapshot: dict,
) -> tuple[RiskCheckRequest, dict]:
    symbol = payload.symbol.upper()
    reference, baseline_source, synthetic = _resolve_reference(payload, snapshot)

    normal_offset_bps = Decimal("0.5")
    if payload.scenario == "POISONED_MARK":
        mark = reference * (Decimal("1") + payload.attack_bps / Decimal("10000"))
    elif payload.scenario == "RECOVERY":
        mark = reference * (Decimal("1") + normal_offset_bps / Decimal("10000"))
    else:
        mark = reference * (Decimal("1") - normal_offset_bps / Decimal("10000"))
    mark = mark.quantize(Decimal("0.000001"))

    intent_kind = IntentKind.CLOSE if payload.intent == "CLOSE" else IntentKind.OPEN
    existing_position = payload.existing_position_usd
    if intent_kind == IntentKind.CLOSE and existing_position <= 0:
        existing_position = payload.requested_notional_usd
    margin_available = (
        payload.margin_available_usd
        if payload.margin_available_usd is not None
        else payload.account_equity_usd
    )

    request = RiskCheckRequest(
        request_id=f"warroom-{uuid.uuid4().hex[:20]}",
        symbol=symbol,
        intent=OrderIntent(
            kind=intent_kind,
            side=Side.BUY,
            notional_usd=payload.requested_notional_usd,
            requested_leverage=payload.requested_leverage,
        ),
        account=AccountExposure(
            equity_usd=payload.account_equity_usd,
            margin_available_usd=margin_available,
            position_notional_usd=existing_position,
            current_leverage=(
                (existing_position / payload.account_equity_usd).quantize(Decimal("0.01"))
                if existing_position
                else Decimal("0")
            ),
            liquidation_price=(
                reference * Decimal("0.80")
                if existing_position
                else None
            ),
            position_side=(Side.BUY if existing_position else None),
        ),
        market=VenueMarketContext(
            mark_price=mark,
            oracle_price=reference if synthetic else None,
            event_time=now,
            session="REGULAR",
        ),
        demo_scenario=payload.scenario if synthetic else None,
    )
    return request, {
        "requested_mode": payload.mode,
        "data_mode": "SYNTHETIC_DEMO" if synthetic else "LIVE_DERIVED_DEMO",
        "baseline_source": baseline_source,
        "baseline_price": float(reference),
        "attack_bps": float(payload.attack_bps),
        "synthetic": synthetic,
    }


def _story(payload: WarRoomRequest, result: dict, provenance: dict) -> dict:
    market = result.get("market", {})
    scenario_copy = {
        "NORMAL": {
            "headline": "Reference evidence and venue mark agree.",
            "detail": "MarketBridge can permit new exposure subject to account and leverage policy.",
        },
        "POISONED_MARK": {
            "headline": "The simulated venue mark diverges from the reference evidence.",
            "detail": "New exposure fails closed while a valid reduce/close path remains available.",
        },
        "RECOVERY": {
            "headline": "Evidence has converged again, but recovery remains deliberately sticky.",
            "detail": "Hysteresis prevents one good tick from instantly re-enabling leverage after an incident.",
        },
    }[payload.scenario]
    return {
        **scenario_copy,
        **provenance,
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
    root = Path(__file__).resolve().parents[2]

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

    @app.get("/v1/proof/historical")
    def proof_historical():
        return historical_incident_policy_replay()

    @app.get("/v1/proof/benchmark")
    def proof_benchmark(cases: int = 2000, seed: int = 20260911):
        bounded = min(max(cases, 250), 10000)
        return risk_gate_benchmark(root, bounded, seed)

    @app.get("/v1/proof/portfolio")
    def proof_portfolio():
        return portfolio_demo(root)

    @app.post("/v1/proof/portfolio")
    def proof_portfolio_custom(payload: PortfolioDemoRequest):
        return portfolio_demo(
            root,
            symbol=payload.symbol,
            requested_notional_usd=payload.requested_notional_usd,
            requested_leverage=payload.requested_leverage,
            account_equity_usd=payload.account_equity_usd,
            existing_position_usd=payload.existing_position_usd,
        )

    @app.post("/v1/demo/war-room")
    def war_room(payload: WarRoomRequest):
        now = datetime.now(timezone.utc)
        snapshot = pipeline.snapshot()
        request, provenance = _war_room_risk_request(payload, now, snapshot)
        result = risk_gateway.check(request, snapshot, now=now)
        return {
            "scenario": payload.scenario,
            "intent": payload.intent,
            "symbol": payload.symbol,
            "inputs": {
                "requested_notional_usd": float(payload.requested_notional_usd),
                "requested_leverage": float(payload.requested_leverage),
                "account_equity_usd": float(payload.account_equity_usd),
                "existing_position_usd": float(payload.existing_position_usd),
                "attack_bps": float(payload.attack_bps),
            },
            "story": _story(payload, result, provenance),
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
