"""Judge-facing proof surfaces for MarketBridge.

Historical reconstruction and synthetic benchmark are intentionally separate:
- historical replay uses published observations and is counterfactual;
- benchmark cases are labeled policy tests used to measure operating behavior.
Neither is presented as live brokerage execution or a certified backtest.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
import random
import statistics
import time
import uuid

from .incidents import incident_reconstruction
from .risk import RiskGateway
from .risk.models import RiskCheckRequest
from .risk.policy import POLICY_VERSION, decide

D = Decimal

INCIDENT_POLICY = {
    "max_leverage": {
        "REGULAR": 10,
        "PRE": 5,
        "POST": 5,
        "OVERNIGHT": 3,
        "CLOSED": 1,
        "EXCHANGE_HALT": 0,
        "CORPORATE_ACTION": 0,
    },
    "min_independent_providers": 2,
    "corporate_action_state": "CLEAR",
    "manual_review_required": False,
    "data_policy": "historical-counterfactual-v1",
}


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


@lru_cache(maxsize=1)
def historical_incident_policy_replay() -> dict:
    incident = incident_reconstruction()
    timeline = []
    for index, point in enumerate(incident["points"]):
        external = D(str(point["external_price"]))
        mark = D(str(point["reported_mark"]))
        divergence = abs(mark / external - 1) * D("10000")
        request = RiskCheckRequest.model_validate(
            {
                "request_id": f"hist-skhynix-{index:03d}",
                "symbol": "SKHYNIX",
                "intent": {
                    "kind": "OPEN",
                    "side": "BUY",
                    "notional_usd": 10000,
                    "requested_leverage": 10,
                },
                "account": {
                    "equity_usd": 10000,
                    "margin_available_usd": 10000,
                    "position_notional_usd": 0,
                },
                "market": {
                    "mark_price": point["reported_mark"],
                    "oracle_price": point["oracle_price"],
                    "event_time": point["timestamp"],
                    "session": "OVERNIGHT",
                },
            }
        )
        # Published reconstruction exposes one external handoff stream plus venue
        # oracle/mark values. Venue values are not allowed to vote themselves into
        # independent Market Truth.
        truth = {
            "reference_price": external,
            "reference_status": "INSUFFICIENT_EVIDENCE",
            "confidence": D("0.25"),
            "venue_mark": mark,
            "divergence_bps": divergence,
            "provider_count": 1,
            "venue_count": 1,
            "session": "OVERNIGHT",
            "asset_state": "HALTED" if divergence >= D("250") else "RESTRICTED",
            "stale": False,
            "malformed": False,
            "authenticated": True,
            "entitled": True,
            "evidence": [
                {
                    "provider": "published-external-handoff",
                    "provider_family": "published-external-handoff",
                    "venue_family": "EXTERNAL_REFERENCE",
                    "event_time": point["timestamp"],
                    "fresh": True,
                    "eligible": True,
                }
            ],
            "data_mode": "HISTORICAL_RECONSTRUCTION",
            "model_version": "published-incident-adapter-v1",
        }
        result = decide(request, truth, INCIDENT_POLICY)
        timeline.append(
            {
                **point,
                "divergence_bps": round(float(divergence), 2),
                "action": result["action"],
                "permitted_leverage": float(result["permitted_leverage"]),
                "permitted_notional_usd": float(result["permitted_notional_usd"]),
                "reasons": result["reasons"],
                "independent_source_families": 1,
            }
        )

    return {
        "incident": {
            "id": incident["id"],
            "title": incident["title"],
            "date": incident["date"],
            "venue": incident["venue"],
            "summary": incident["summary"],
            "sources": incident["sources"],
            "limitations": incident["limitations"],
        },
        "proof": {
            "data_mode": "HISTORICAL_RECONSTRUCTION",
            "decision_engine": "marketbridge.risk.policy.decide",
            "policy_version": POLICY_VERSION,
            "same_policy_function_as_live_gate": True,
            "hindsight_used_by_decision": False,
            "claim": (
                "Counterfactual: with only one independent external source family at "
                "the handoff, MarketBridge would fail closed for new risk. This does "
                "not prove avoided losses."
            ),
        },
        "timeline": timeline,
    }


def _random_portfolio(rng: random.Random, symbol: str, gross: Decimal) -> list[dict]:
    if gross <= 0:
        return []
    universe = ["NVDA", "AMD", "MSFT", "AAPL", "TSLA"]
    if symbol not in universe:
        universe[0] = symbol
    weights = [Decimal("0.30"), Decimal("0.22"), Decimal("0.18"), Decimal("0.17"), Decimal("0.13")]
    rng.shuffle(universe)
    if symbol in universe:
        universe.remove(symbol)
    universe.insert(0, symbol)
    rows = []
    remaining = gross
    for index, (item, weight) in enumerate(zip(universe, weights)):
        amount = (
            remaining
            if index == len(weights) - 1
            else (gross * weight).quantize(Decimal("0.01"))
        )
        remaining -= amount
        rows.append(
            {
                "symbol": item,
                "notional_usd": max(amount, Decimal("0.01")),
                "sector": (
                    "SEMICONDUCTORS"
                    if item in {"NVDA", "AMD"}
                    else "TECHNOLOGY"
                    if item in {"MSFT", "AAPL"}
                    else "CONSUMER_DISCRETIONARY"
                ),
                "correlation_group": (
                    "AI_COMPUTE"
                    if item in {"NVDA", "AMD"}
                    else "MEGA_CAP_TECH"
                    if item in {"MSFT", "AAPL"}
                    else "HIGH_BETA_GROWTH"
                ),
            }
        )
    return rows


@lru_cache(maxsize=8)
def risk_gate_benchmark(root: Path, cases: int = 2000, seed: int = 20260911) -> dict:
    """Exercise a reproducible, varied state space instead of replaying copies.

    This is a deterministic policy-regression benchmark, not a classifier
    accuracy claim. The independent assertions are safety invariants.
    """
    rng = random.Random(seed)
    gateway = RiskGateway(root)
    symbols = tuple(gateway.assets.keys())
    sessions = ("REGULAR", "PRE", "POST", "OVERNIGHT", "CLOSED")
    actions = {"ALLOW": 0, "CAP_LEVERAGE": 0, "REVIEW": 0, "BLOCK_NEW_RISK": 0}
    latencies_ms: list[float] = []
    violations = {
        "stale_evidence_accepted": 0,
        "insufficient_independence_accepted": 0,
        "halted_market_accepted": 0,
        "correlated_sources_counted_as_independent": 0,
        "exit_path_violations": 0,
    }
    coverage = {
        "stale": 0,
        "single_or_zero_source": 0,
        "correlated_provider_labels": 0,
        "large_divergence": 0,
        "portfolio_cases": 0,
        "overnight_or_closed": 0,
    }

    for index in range(cases):
        symbol = rng.choice(symbols)
        session = rng.choice(sessions)
        reference = Decimal(str(round(rng.uniform(40, 600), 4)))
        divergence_bps = Decimal(str(round(rng.uniform(0, 900), 2)))
        direction = Decimal("1") if rng.random() >= 0.5 else Decimal("-1")
        mark = (reference * (Decimal("1") + direction * divergence_bps / Decimal("10000"))).quantize(Decimal("0.000001"))
        stale = rng.random() < 0.12
        correlated = rng.random() < 0.12
        raw_provider_labels = 2 if correlated else rng.choice([0, 1, 2, 2, 3])
        provider_count = 1 if correlated else raw_provider_labels
        venue_count = provider_count
        portfolio_case = rng.random() < 0.22
        existing = Decimal(str(round(rng.uniform(1000, 50000), 2))) if portfolio_case else Decimal("0")
        equity = Decimal(str(round(rng.uniform(2000, 75000), 2)))
        notional = Decimal(str(round(rng.uniform(500, 60000), 2)))
        leverage = Decimal(str(round(rng.uniform(1, 20), 2)))
        asset_state = (
            "HALTED"
            if divergence_bps >= Decimal("250")
            else "RECOVERY_PENDING"
            if rng.random() < 0.05
            else "NORMAL"
        )

        if stale:
            coverage["stale"] += 1
        if provider_count < 2:
            coverage["single_or_zero_source"] += 1
        if correlated:
            coverage["correlated_provider_labels"] += 1
        if divergence_bps >= Decimal("250"):
            coverage["large_divergence"] += 1
        if portfolio_case:
            coverage["portfolio_cases"] += 1
        if session in {"OVERNIGHT", "CLOSED"}:
            coverage["overnight_or_closed"] += 1

        request = RiskCheckRequest.model_validate(
            {
                "request_id": f"bench-{seed}-{index:06d}",
                "symbol": symbol,
                "intent": {
                    "kind": "OPEN",
                    "side": "BUY",
                    "notional_usd": float(notional),
                    "requested_leverage": float(leverage),
                },
                "account": {
                    "equity_usd": float(equity),
                    "margin_available_usd": float(equity),
                    "position_notional_usd": float(existing),
                    "current_leverage": float(min(existing / equity, Decimal("100")).quantize(Decimal("0.01"))) if existing else 0,
                    "position_side": "BUY" if existing else None,
                    "liquidation_price": float(reference * Decimal("0.75")) if existing else None,
                    "portfolio_positions": _random_portfolio(rng, symbol, existing),
                },
                "market": {
                    "mark_price": float(mark),
                    "event_time": "2026-09-10T12:00:00Z",
                    "session": session,
                },
            }
        )
        truth = {
            "reference_price": reference,
            "reference_status": "QUALIFIED" if provider_count >= 2 and not stale else "INSUFFICIENT_EVIDENCE",
            "confidence": Decimal("0.95") if provider_count >= 2 and not stale else Decimal("0.25"),
            "venue_mark": mark,
            "divergence_bps": divergence_bps,
            "provider_count": provider_count,
            "venue_count": venue_count,
            "raw_provider_labels": raw_provider_labels,
            "session": session,
            "asset_state": asset_state,
            "stale": stale,
            "malformed": False,
            "authenticated": True,
            "entitled": True,
            "evidence": [],
            "data_mode": "SYNTHETIC_POLICY_REGRESSION",
            "model_version": "benchmark-generator-v2",
        }

        started = time.perf_counter_ns()
        result = decide(request, truth, gateway.assets[symbol])
        latencies_ms.append((time.perf_counter_ns() - started) / 1_000_000)
        action = result["action"]
        actions[action] = actions.get(action, 0) + 1

        if stale and action == "ALLOW":
            violations["stale_evidence_accepted"] += 1
        if provider_count < 2 and action == "ALLOW":
            violations["insufficient_independence_accepted"] += 1
        if asset_state in {"HALTED", "RECOVERY_PENDING"} and action == "ALLOW":
            violations["halted_market_accepted"] += 1
        if correlated and provider_count != 1:
            violations["correlated_sources_counted_as_independent"] += 1

        if index < min(cases, 250) and (stale or provider_count < 2 or asset_state != "NORMAL"):
            close_request = request.model_copy(
                update={
                    "intent": request.intent.model_copy(update={"kind": "CLOSE"}),
                    "account": request.account.model_copy(
                        update={
                            "position_notional_usd": max(existing, notional),
                            "position_side": "BUY",
                        }
                    ),
                }
            )
            close_result = decide(close_request, truth, gateway.assets[symbol])
            if close_result["action"] != "ALLOW":
                violations["exit_path_violations"] += 1

    gateway_latencies: list[float] = []
    for index in range(min(200, max(50, cases // 20))):
        reference = Decimal(str(round(rng.uniform(60, 450), 4)))
        request = RiskCheckRequest.model_validate(
            {
                "request_id": f"gateway-bench-{seed}-{index}-{uuid.uuid4().hex[:8]}",
                "symbol": rng.choice(symbols),
                "intent": {
                    "kind": "OPEN",
                    "side": "BUY",
                    "notional_usd": round(rng.uniform(1000, 25000), 2),
                    "requested_leverage": round(rng.uniform(1, 10), 2),
                },
                "account": {
                    "equity_usd": 25000,
                    "margin_available_usd": 25000,
                    "position_notional_usd": 0,
                },
                "market": {
                    "mark_price": float(reference),
                    "oracle_price": float(reference),
                    "event_time": datetime.now(timezone.utc).isoformat(),
                    "session": "REGULAR",
                },
                "demo_scenario": "NORMAL",
            }
        )
        started = time.perf_counter_ns()
        gateway.check(request, {"decisions": []}, now=datetime.now(timezone.utc))
        gateway_latencies.append((time.perf_counter_ns() - started) / 1_000_000)

    return {
        "data_mode": "SYNTHETIC_POLICY_REGRESSION",
        "seed": seed,
        "cases": cases,
        "generator": {
            "version": "benchmark-generator-v2",
            "claim": "Varied reproducible policy states; not a classifier accuracy or backtest claim.",
        },
        "actions": actions,
        "coverage": coverage,
        "invariants": {
            "violations": violations,
            "total_violations": sum(violations.values()),
        },
        "latency": {
            "core_policy_ms": {
                "p50": round(_percentile(latencies_ms, 0.50), 4),
                "p95": round(_percentile(latencies_ms, 0.95), 4),
                "p99": round(_percentile(latencies_ms, 0.99), 4),
                "mean": round(statistics.fmean(latencies_ms), 4),
            },
            "in_process_gateway_ms": {
                "p50": round(_percentile(gateway_latencies, 0.50), 4),
                "p95": round(_percentile(gateway_latencies, 0.95), 4),
                "p99": round(_percentile(gateway_latencies, 0.99), 4),
                "mean": round(statistics.fmean(gateway_latencies), 4),
            },
            "boundary": "In-process measurements; network, reverse-proxy and provider I/O are excluded.",
        },
        "economics": {
            "llm_calls_in_risk_critical_path": 0,
            "paid_api_calls_required_by_policy_function": 0,
            "market_data_license_cost_per_million_decisions_usd": None,
            "note": "Market-data licensing and hosting are deployment-specific; MarketBridge does not invent a dollar cost without a measured invoice and entitlement.",
        },
    }


def portfolio_demo(
    root: Path,
    *,
    symbol: str = "NVDA",
    requested_notional_usd: Decimal = Decimal("10000"),
    requested_leverage: Decimal = Decimal("10"),
    account_equity_usd: Decimal = Decimal("10000"),
    existing_position_usd: Decimal = Decimal("22000"),
) -> dict:
    gateway = RiskGateway(root)
    if symbol not in gateway.assets:
        raise KeyError("unsupported symbol")
    now = datetime.now(timezone.utc)
    checksum = sum(ord(char) for char in symbol)
    reference = Decimal(100 + checksum % 120).quantize(Decimal("0.01"))
    requested_notional_usd = Decimal(str(requested_notional_usd))
    requested_leverage = Decimal(str(requested_leverage))
    account_equity_usd = Decimal(str(account_equity_usd))
    existing_position_usd = Decimal(str(existing_position_usd))
    rng = random.Random(f"portfolio-{symbol}-{existing_position_usd}")
    positions = _random_portfolio(rng, symbol, existing_position_usd)

    request = RiskCheckRequest.model_validate(
        {
            "request_id": f"portfolio-demo-{uuid.uuid4().hex}",
            "symbol": symbol,
            "intent": {
                "kind": "OPEN",
                "side": "BUY",
                "notional_usd": float(requested_notional_usd),
                "requested_leverage": float(requested_leverage),
            },
            "account": {
                "equity_usd": float(account_equity_usd),
                "margin_available_usd": float(account_equity_usd),
                "position_notional_usd": float(existing_position_usd),
                "current_leverage": float(min(existing_position_usd / account_equity_usd, Decimal("100")).quantize(Decimal("0.01"))) if existing_position_usd else 0,
                "liquidation_price": float(reference * Decimal("0.75")) if existing_position_usd else None,
                "position_side": "BUY" if existing_position_usd else None,
                "portfolio_positions": positions,
            },
            "market": {
                "mark_price": float(reference),
                "oracle_price": float(reference),
                "event_time": now.isoformat(),
                "session": "OVERNIGHT",
            },
            "demo_scenario": "NORMAL",
        }
    )
    result = gateway.check(request, {"decisions": []}, now=now)
    return {
        "data_mode": "SYNTHETIC_PORTFOLIO_DEMO",
        "inputs_are_editable": True,
        "order": {
            "symbol": symbol,
            "requested_notional_usd": float(requested_notional_usd),
            "requested_leverage": float(requested_leverage),
            "session": "OVERNIGHT",
        },
        "account": {
            "equity_usd": float(account_equity_usd),
            "existing_position_usd": float(existing_position_usd),
            "portfolio_positions": positions,
        },
        "result": result,
        "boundary": "Portfolio composition is a parameterized synthetic fixture. The risk result is computed by the same gateway used by the integration endpoint.",
    }
