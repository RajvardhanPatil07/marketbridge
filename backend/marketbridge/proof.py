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


def _benchmark_request(
    index: int,
    session: str = "REGULAR",
    portfolio: bool = False,
) -> RiskCheckRequest:
    account: dict = {
        "equity_usd": 10000,
        "margin_available_usd": 10000,
        "position_notional_usd": 0,
    }
    if portfolio:
        account.update(
            {
                "position_notional_usd": 22000,
                "current_leverage": 2.2,
                "liquidation_price": 140,
                "position_side": "BUY",
                "portfolio_positions": [
                    {
                        "symbol": "NVDA",
                        "notional_usd": 6000,
                        "sector": "SEMICONDUCTORS",
                        "correlation_group": "AI_COMPUTE",
                    },
                    {
                        "symbol": "AMD",
                        "notional_usd": 5000,
                        "sector": "SEMICONDUCTORS",
                        "correlation_group": "AI_COMPUTE",
                    },
                    {
                        "symbol": "MSFT",
                        "notional_usd": 4000,
                        "sector": "TECHNOLOGY",
                        "correlation_group": "MEGA_CAP_TECH",
                    },
                    {
                        "symbol": "AAPL",
                        "notional_usd": 4000,
                        "sector": "TECHNOLOGY",
                        "correlation_group": "MEGA_CAP_TECH",
                    },
                    {
                        "symbol": "TSLA",
                        "notional_usd": 3000,
                        "sector": "CONSUMER_DISCRETIONARY",
                        "correlation_group": "HIGH_BETA_GROWTH",
                    },
                ],
            }
        )
    return RiskCheckRequest.model_validate(
        {
            "request_id": f"bench-{index:05d}",
            "symbol": "NVDA",
            "intent": {
                "kind": "OPEN",
                "side": "BUY",
                "notional_usd": 10000,
                "requested_leverage": 10,
            },
            "account": account,
            "market": {
                "mark_price": 184.52,
                "event_time": "2026-09-10T12:00:00Z",
                "session": session,
            },
        }
    )


def _truth(kind: str) -> dict:
    normal = {
        "reference_price": D("184.52"),
        "reference_status": "QUALIFIED",
        "confidence": D("0.95"),
        "venue_mark": D("184.52"),
        "divergence_bps": D("0"),
        "provider_count": 2,
        "venue_count": 2,
        "session": "REGULAR",
        "asset_state": "NORMAL",
        "stale": False,
        "malformed": False,
        "authenticated": True,
        "entitled": True,
        "evidence": [],
        "data_mode": "SYNTHETIC_BENCHMARK",
        "model_version": "benchmark-v1",
    }
    if kind == "normal":
        return normal
    if kind == "confirmed_news_move":
        return {
            **normal,
            "reference_price": D("192.00"),
            "venue_mark": D("192.04"),
            "divergence_bps": D("2.08"),
        }
    if kind == "overnight":
        return {**normal, "session": "OVERNIGHT"}
    if kind == "stale":
        return {**normal, "stale": True}
    if kind == "single_source":
        return {**normal, "provider_count": 1, "venue_count": 1}
    if kind == "correlated_providers":
        # Two vendor labels can still map to one upstream family. The policy sees
        # independent-family count, not raw vendor count.
        return {**normal, "provider_count": 1, "venue_count": 1}
    if kind == "poisoned_mark":
        return {
            **normal,
            "venue_mark": D("190.20"),
            "divergence_bps": D("307.82"),
            "asset_state": "HALTED",
        }
    if kind == "recovery_pending":
        return {**normal, "asset_state": "RECOVERY_PENDING"}
    if kind == "portfolio_concentration":
        return normal
    raise KeyError(kind)


@lru_cache(maxsize=8)
def risk_gate_benchmark(root: Path, cases_per_class: int = 50) -> dict:
    categories = [
        ("normal", False, "REGULAR", False),
        ("confirmed_news_move", False, "REGULAR", False),
        ("overnight", True, "OVERNIGHT", False),
        ("stale", True, "REGULAR", False),
        ("single_source", True, "REGULAR", False),
        ("correlated_providers", True, "REGULAR", False),
        ("poisoned_mark", True, "REGULAR", False),
        ("recovery_pending", True, "REGULAR", False),
        ("portfolio_concentration", True, "REGULAR", True),
    ]
    asset_policy = RiskGateway(root).assets["NVDA"]
    tp = tn = fp = fn = 0
    latencies_ms: list[float] = []
    category_results: list[dict] = []
    index = 0

    for kind, expected_restrict, session, portfolio in categories:
        local_counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
        actions: dict[str, int] = {}
        for _ in range(cases_per_class):
            request = _benchmark_request(
                index,
                session=session,
                portfolio=portfolio,
            )
            truth = _truth(kind)
            started = time.perf_counter_ns()
            result = decide(request, truth, asset_policy)
            latencies_ms.append(
                (time.perf_counter_ns() - started) / 1_000_000
            )
            predicted_restrict = result["action"] != "ALLOW"
            actions[result["action"]] = actions.get(result["action"], 0) + 1
            if expected_restrict and predicted_restrict:
                tp += 1
                local_counts["tp"] += 1
            elif not expected_restrict and not predicted_restrict:
                tn += 1
                local_counts["tn"] += 1
            elif not expected_restrict and predicted_restrict:
                fp += 1
                local_counts["fp"] += 1
            else:
                fn += 1
                local_counts["fn"] += 1
            index += 1
        category_results.append(
            {
                "category": kind,
                "expected": (
                    "RESTRICT"
                    if expected_restrict
                    else "ALLOW"
                ),
                "cases": cases_per_class,
                "actions": actions,
                **local_counts,
            }
        )

    total = tp + tn + fp + fn
    legitimate = tn + fp
    unsafe = tp + fn

    gateway = RiskGateway(root)
    gateway_latencies: list[float] = []
    gateway_samples = min(
        200,
        max(50, cases_per_class * 2),
    )
    for _ in range(gateway_samples):
        request = RiskCheckRequest.model_validate(
            {
                "request_id": f"gateway-bench-{uuid.uuid4().hex}",
                "symbol": "NVDA",
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
                    "mark_price": 184.51,
                    "event_time": "2026-09-10T12:00:00Z",
                    "session": "REGULAR",
                },
                "demo_scenario": "NORMAL",
            }
        )
        now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
        started = time.perf_counter_ns()
        gateway.check(
            request,
            {"decisions": []},
            now=now,
        )
        gateway_latencies.append(
            (time.perf_counter_ns() - started) / 1_000_000
        )

    return {
        "data_mode": "SYNTHETIC_LABELED_BENCHMARK",
        "generated_at": datetime.now(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "cases": total,
        "classification": {
            "positive_definition": (
                "order should be restricted (CAP/REVIEW/BLOCK)"
            ),
            "confusion_matrix": {
                "tp": tp,
                "tn": tn,
                "fp": fp,
                "fn": fn,
            },
            "false_positive_rate": (
                fp / legitimate
                if legitimate
                else 0.0
            ),
            "false_negative_rate": (
                fn / unsafe
                if unsafe
                else 0.0
            ),
            "precision": (
                tp / (tp + fp)
                if tp + fp
                else 0.0
            ),
            "recall": (
                tp / unsafe
                if unsafe
                else 0.0
            ),
            "accuracy": (
                (tp + tn) / total
                if total
                else 0.0
            ),
            "categories": category_results,
        },
        "latency": {
            "core_policy_ms": {
                "p50": round(_percentile(latencies_ms, 0.50), 4),
                "p95": round(_percentile(latencies_ms, 0.95), 4),
                "p99": round(_percentile(latencies_ms, 0.99), 4),
                "mean": round(statistics.fmean(latencies_ms), 4),
            },
            "in_process_gateway_ms": {
                "p50": round(
                    _percentile(gateway_latencies, 0.50),
                    4,
                ),
                "p95": round(
                    _percentile(gateway_latencies, 0.95),
                    4,
                ),
                "p99": round(
                    _percentile(gateway_latencies, 0.99),
                    4,
                ),
                "mean": round(
                    statistics.fmean(gateway_latencies),
                    4,
                ),
            },
            "boundary": (
                "In-process measurements; network, reverse-proxy and provider "
                "I/O are excluded."
            ),
        },
        "economics": {
            "llm_calls_in_risk_critical_path": 0,
            "paid_api_calls_required_by_policy_function": 0,
            "market_data_license_cost_per_million_decisions_usd": None,
            "note": (
                "Market-data licensing and hosting are deployment-specific; "
                "MarketBridge does not invent a dollar cost without a measured "
                "invoice and entitlement."
            ),
        },
    }


def portfolio_demo(root: Path) -> dict:
    gateway = RiskGateway(root)
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    request = RiskCheckRequest.model_validate(
        {
            "request_id": f"portfolio-demo-{uuid.uuid4().hex}",
            "symbol": "NVDA",
            "intent": {
                "kind": "OPEN",
                "side": "BUY",
                "notional_usd": 10000,
                "requested_leverage": 10,
            },
            "account": {
                "equity_usd": 10000,
                "margin_available_usd": 10000,
                "position_notional_usd": 22000,
                "current_leverage": 2.2,
                "liquidation_price": 140,
                "position_side": "BUY",
                "portfolio_positions": [
                    {
                        "symbol": "NVDA",
                        "notional_usd": 6000,
                        "sector": "SEMICONDUCTORS",
                        "correlation_group": "AI_COMPUTE",
                    },
                    {
                        "symbol": "AMD",
                        "notional_usd": 5000,
                        "sector": "SEMICONDUCTORS",
                        "correlation_group": "AI_COMPUTE",
                    },
                    {
                        "symbol": "MSFT",
                        "notional_usd": 4000,
                        "sector": "TECHNOLOGY",
                        "correlation_group": "MEGA_CAP_TECH",
                    },
                    {
                        "symbol": "AAPL",
                        "notional_usd": 4000,
                        "sector": "TECHNOLOGY",
                        "correlation_group": "MEGA_CAP_TECH",
                    },
                    {
                        "symbol": "TSLA",
                        "notional_usd": 3000,
                        "sector": "CONSUMER_DISCRETIONARY",
                        "correlation_group": "HIGH_BETA_GROWTH",
                    },
                ],
            },
            "market": {
                "mark_price": 184.51,
                "event_time": now.isoformat(),
                "session": "OVERNIGHT",
            },
            "demo_scenario": "NORMAL",
        }
    )
    result = gateway.check(
        request,
        {"decisions": []},
        now=now,
    )
    return {
        "data_mode": "SYNTHETIC_PORTFOLIO_DEMO",
        "order": {
            "symbol": "NVDA",
            "requested_notional_usd": 10000,
            "requested_leverage": 10,
            "session": "OVERNIGHT",
        },
        "result": result,
        "boundary": (
            "Portfolio concentration uses transparent policy buckets, not "
            "claimed live covariance. The host can supply measured sector/factor "
            "metadata later without changing the API."
        ),
    }
