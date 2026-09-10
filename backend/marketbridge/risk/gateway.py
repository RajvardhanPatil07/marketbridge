"""Authoritative order-risk orchestration, passport issuance, and replay."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from .models import RiskCheckRequest
from .passport import PassportStore, canonical_hash
from .policy import POLICY_VERSION, decide
from .recovery import RecoveryTracker
from .session import equity_session

if TYPE_CHECKING:
    from ..symbols import SymbolCatalog


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


class RiskGateway:
    ttl_ms = 3_000

    def __init__(self, root: Path, *, symbol_catalog: "SymbolCatalog | None" = None):
        self.root = root
        asset_config = json.loads((root / "config" / "assets.yaml").read_text())
        self.assets = asset_config["symbols"]
        self.default_asset = asset_config.get("default_nasdaq_policy")
        self.asset_policy_version = asset_config.get("version", "asset-policy-v1.0.0")
        self.symbol_catalog = symbol_catalog
        entitlements = json.loads((root / "config" / "entitlements.yaml").read_text())
        self.entitlements = entitlements["providers"]
        self.entitlement_version = entitlements["version"]
        self.passports = PassportStore()
        self.recovery = RecoveryTracker()
        self._lock = Lock()

    def _asset_policy(self, symbol: str) -> dict | None:
        configured = self.assets.get(symbol)
        if configured is not None:
            return configured
        listing = self.symbol_catalog.get(symbol) if self.symbol_catalog else None
        if listing is None or self.default_asset is None:
            return None
        policy = deepcopy(self.default_asset)
        policy["manual_review_required"] = True
        if not listing.risk_eligible:
            policy["corporate_action_state"] = "REVIEW_REQUIRED"
        return policy

    def market_truth(self, request: RiskCheckRequest, snapshot: dict, now: datetime) -> dict:
        venue_age = max(0.0, (now - request.market.event_time.astimezone(timezone.utc)).total_seconds())
        if request.demo_scenario:
            reference = Decimal("184.52") if request.symbol == "NVDA" else request.market.mark_price
            divergence = abs(request.market.mark_price / reference - 1) * Decimal("10000")
            raw_state = "HALTED" if divergence >= Decimal("250") else "NORMAL"
            if request.demo_scenario == "POISONED_MARK":
                raw_state = "HALTED"
            stable = request.demo_scenario in {"NORMAL", "RECOVERY"} and divergence < Decimal("75")
            recovery = self.recovery.update(request.symbol, raw_state, stable, now)
            evidence = [
                {"provider": "synthetic-demo-alpaca", "provider_family": "synthetic-demo-alpaca", "venue_family": "NASDAQ", "event_time": _iso(now), "fresh": True, "eligible": True, "observation_hash": canonical_hash({"provider": "synthetic-demo-alpaca", "price": "184.50", "event_time": _iso(now)})},
                {"provider": "synthetic-demo-twelve-data", "provider_family": "synthetic-demo-twelve-data", "venue_family": "TWELVE_DATA.US_EQUITIES", "event_time": _iso(now), "fresh": True, "eligible": True, "observation_hash": canonical_hash({"provider": "synthetic-demo-twelve-data", "price": "184.54", "event_time": _iso(now)})},
            ]
            return {
                "reference_price": reference,
                "reference_status": "QUALIFIED",
                "confidence": Decimal("0.95") if raw_state == "NORMAL" else Decimal("0.32"),
                "venue_mark": request.market.mark_price,
                "divergence_bps": divergence,
                "provider_count": 2,
                "venue_count": 2,
                "session": (request.market.session or equity_session(request.market.event_time)).value,
                "asset_state": recovery["state"],
                "recovery": recovery,
                "stale": venue_age > 10,
                "malformed": False,
                "authenticated": True,
                "entitled": True,
                "evidence": evidence,
                "data_mode": "SYNTHETIC_DEMO",
                "model_version": "marketbridge-shadow-v0.3",
            }

        decision = next((item for item in snapshot.get("decisions", []) if item.get("symbol") == request.symbol), None)
        evidence = [] if decision is None else decision.get("evidence", [])
        provider_families = {item.get("provider_family") for item in evidence if item.get("eligible") and item.get("fresh")}
        entitled = bool(provider_families) and all(
            self.entitlements.get(provider, {}).get("non_display_computation", False) for provider in provider_families
        )
        reference = decision.get("reference") if decision else None
        divergence = abs(request.market.mark_price / Decimal(str(reference)) - 1) * Decimal("10000") if reference else None
        raw_state = decision.get("risk_state", "HALTED") if decision else "HALTED"
        stable = bool(decision and decision.get("status") == "QUALIFIED" and divergence is not None and divergence < 75)
        recovery = self.recovery.update(request.symbol, raw_state, stable, now)
        normalized_evidence = [
            {
                "provider": item.get("source_id"), "provider_family": item.get("provider_family"),
                "venue_family": item.get("venue_family"), "event_time": item.get("event_time"),
                "fresh": bool(item.get("fresh")), "eligible": bool(item.get("eligible")),
                "observation_hash": canonical_hash({key: item.get(key) for key in ("source_id", "provider_family", "venue_family", "price", "event_time")}),
            }
            for item in evidence
        ]
        return {
            "reference_price": reference,
            "reference_status": decision.get("status", "INSUFFICIENT_EVIDENCE") if decision else "INSUFFICIENT_EVIDENCE",
            "confidence": Decimal(str(decision.get("confidence", 0))) / Decimal("100") if decision else Decimal("0"),
            "venue_mark": request.market.mark_price,
            "divergence_bps": divergence,
            "provider_count": len(provider_families),
            "venue_count": decision.get("independent_source_families", 0) if decision else 0,
            "session": (request.market.session or equity_session(request.market.event_time)).value,
            "asset_state": recovery["state"],
            "recovery": recovery,
            "stale": venue_age > 10 or not bool(evidence) or any(item.get("eligible") and not item.get("fresh") for item in evidence),
            "malformed": False,
            "authenticated": True,
            "entitled": entitled,
            "evidence": normalized_evidence,
            "data_mode": snapshot.get("data_mode", "SHADOW_ORACLE"),
            "model_version": decision.get("model_version") if decision else None,
        }

    def check(self, request: RiskCheckRequest, snapshot: dict, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        asset_policy = self._asset_policy(request.symbol)
        if asset_policy is None:
            raise KeyError("unsupported symbol")
        body = request.model_dump(mode="json")
        request_hash = canonical_hash(body)
        prior = self.passports.by_request(request.request_id)
        if prior:
            if prior.request_hash != request_hash:
                raise ValueError("request_id already used for materially different order")
            expires_at = datetime.fromisoformat(
                prior.passport["claims"]["decision"]["expires_at"].replace("Z", "+00:00")
            )
            if now > expires_at:
                raise ValueError("decision expired; submit a new request_id")
            return self._response(prior.passport)
        truth = self.market_truth(request, snapshot, now)
        result = decide(request, truth, asset_policy)
        expires_at = now + timedelta(milliseconds=self.ttl_ms)
        exposure = result.pop("exposure")
        claims = {
            "identity": {"request_id": request.request_id, "timestamp": _iso(now), "symbol": request.symbol},
            "order": {
                "intent_kind": request.intent.kind.value, "side": request.intent.side.value,
                "requested_leverage": request.intent.requested_leverage,
                "requested_notional_usd": request.intent.notional_usd,
                "permitted_leverage": result["permitted_leverage"],
                "permitted_notional_usd": result["permitted_notional_usd"],
            },
            "account": {
                "existing_exposure_usd": request.account.position_notional_usd,
                "current_leverage": exposure.current_leverage,
                "projected_leverage": exposure.projected_leverage,
                "liquidation_distance_pct": exposure.liquidation_distance_pct,
                "risk_classification": exposure.classification,
            },
            "market": deepcopy(truth),
            "evidence": deepcopy(truth["evidence"]),
            "policy": {
                "policy_version": POLICY_VERSION, "asset_policy_version": self.asset_policy_version,
                "model_version": truth.get("model_version"), "data_policy_version": asset_policy["data_policy"],
                "entitlement_policy_version": self.entitlement_version,
            },
            "decision": {
                "action": result["action"], "reason_codes": result["reasons"], "expires_at": _iso(expires_at),
                "ttl_ms": self.ttl_ms, "reduce_only_allowed": True,
            },
            "outcome": None,
        }
        # Hash the exact JSON-compatible representation returned over the API so
        # clients can reproduce verification without Decimal coercion rules.
        passport = self.passports.create(_plain(claims), body, truth, request_hash)
        return self._response(passport)

    @staticmethod
    def _response(passport: dict) -> dict:
        claims = passport["claims"]
        return _plain({
            "action": claims["decision"]["action"],
            "requested_leverage": claims["order"]["requested_leverage"],
            "permitted_leverage": claims["order"]["permitted_leverage"],
            "requested_notional_usd": claims["order"]["requested_notional_usd"],
            "permitted_notional_usd": claims["order"]["permitted_notional_usd"],
            "market": claims["market"],
            "account_risk": claims["account"],
            "reasons": claims["decision"]["reason_codes"],
            "reduce_only_allowed": True,
            "expires_at": claims["decision"]["expires_at"],
            "ttl_ms": claims["decision"]["ttl_ms"],
            "passport_id": passport["passport_id"],
            "policy_version": claims["policy"]["policy_version"],
            "passport": passport,
        })

    def replay(self, passport_id: str, policy_version: str, *, now: datetime | None = None) -> dict:
        record = self.passports.get(passport_id)
        if record is None:
            raise KeyError("passport not found")
        original = self._response(record.passport)
        if policy_version == "WITHOUT_SAFETY_GATE":
            replayed = {
                "action": "ALLOW", "permitted_leverage": original["requested_leverage"],
                "permitted_notional_usd": original["requested_notional_usd"],
                "reasons": ["COUNTERFACTUAL_SAFETY_GATE_DISABLED"],
            }
        else:
            request = RiskCheckRequest.model_validate(record.request)
            asset_policy = self._asset_policy(request.symbol)
            if asset_policy is None:
                raise KeyError("unsupported symbol")
            result = decide(request, record.market_truth, asset_policy)
            replayed = _plain({key: value for key, value in result.items() if key != "exposure"})
        return {
            "passport_id": passport_id,
            "policy_version": policy_version,
            "counterfactual": policy_version == "WITHOUT_SAFETY_GATE",
            "original_action": original["action"],
            "replayed_action": replayed["action"],
            "original_permitted_leverage": original["permitted_leverage"],
            "replayed_permitted_leverage": replayed["permitted_leverage"],
            "original_permitted_notional_usd": original["permitted_notional_usd"],
            "replayed_permitted_notional_usd": replayed["permitted_notional_usd"],
            "prevented_additional_exposure_usd": max(0, original["requested_notional_usd"] - original["permitted_notional_usd"]),
            "reason_changes": {"original": original["reasons"], "replayed": replayed["reasons"]},
            "deterministic_parity": policy_version != "WITHOUT_SAFETY_GATE" and original["action"] == replayed["action"] and original["permitted_notional_usd"] == replayed["permitted_notional_usd"],
            "disclaimer": "Counterfactual simulation; it is not proof that Mochatrade would have executed the ungated order." if policy_version == "WITHOUT_SAFETY_GATE" else None,
        }
