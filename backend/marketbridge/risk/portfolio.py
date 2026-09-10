"""Deterministic portfolio-risk firewall used after Market Truth is qualified.

This module intentionally avoids pretending that a small hackathon universe has a
production covariance model. It enforces transparent concentration, sector and
correlated-risk-bucket limits. A future licensed-data deployment can replace the
bucket map with a measured factor/covariance model without changing the gate API.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import IntentKind, RiskCheckRequest

D = Decimal

DEFAULT_SECTOR = {
    "NVDA": "SEMICONDUCTORS",
    "AMD": "SEMICONDUCTORS",
    "AAPL": "TECHNOLOGY",
    "MSFT": "TECHNOLOGY",
    "TSLA": "CONSUMER_DISCRETIONARY",
}
DEFAULT_BUCKET = {
    "NVDA": "AI_COMPUTE",
    "AMD": "AI_COMPUTE",
    "AAPL": "MEGA_CAP_TECH",
    "MSFT": "MEGA_CAP_TECH",
    "TSLA": "HIGH_BETA_GROWTH",
}

MAX_SINGLE_NAME = D("0.45")
MAX_SECTOR = D("0.70")
MAX_CORRELATED_BUCKET = D("0.75")


@dataclass(frozen=True)
class Holding:
    symbol: str
    notional: Decimal
    sector: str
    bucket: str


def _holding(
    symbol: str,
    notional: Decimal,
    sector: str | None = None,
    bucket: str | None = None,
) -> Holding:
    symbol = symbol.upper()
    return Holding(
        symbol=symbol,
        notional=abs(notional),
        sector=(sector or DEFAULT_SECTOR.get(symbol) or "OTHER").upper(),
        bucket=(
            bucket
            or DEFAULT_BUCKET.get(symbol)
            or sector
            or DEFAULT_SECTOR.get(symbol)
            or "OTHER"
        ).upper(),
    )


def _base_holdings(request: RiskCheckRequest) -> list[Holding]:
    supplied = [
        _holding(item.symbol, item.notional_usd, item.sector, item.correlation_group)
        for item in request.account.portfolio_positions
        if item.notional_usd > 0
    ]
    if supplied:
        # A supplied portfolio snapshot is the concentration source of truth. Do
        # not silently double-count account.position_notional_usd.
        return supplied
    if request.account.position_notional_usd > 0:
        return [_holding(request.symbol, request.account.position_notional_usd)]
    return []


def _snapshot(holdings: list[Holding]) -> dict:
    gross = sum((holding.notional for holding in holdings), D("0"))
    if gross <= 0:
        return {
            "gross_notional_usd": D("0"),
            "top_symbol": None,
            "single_name_concentration": D("0"),
            "top_sector": None,
            "sector_concentration": D("0"),
            "top_correlation_group": None,
            "correlated_concentration": D("0"),
        }

    symbols: dict[str, Decimal] = {}
    sectors: dict[str, Decimal] = {}
    buckets: dict[str, Decimal] = {}
    for holding in holdings:
        symbols[holding.symbol] = symbols.get(holding.symbol, D("0")) + holding.notional
        sectors[holding.sector] = sectors.get(holding.sector, D("0")) + holding.notional
        buckets[holding.bucket] = buckets.get(holding.bucket, D("0")) + holding.notional

    top_symbol, symbol_value = max(symbols.items(), key=lambda pair: pair[1])
    top_sector, sector_value = max(sectors.items(), key=lambda pair: pair[1])
    top_bucket, bucket_value = max(buckets.items(), key=lambda pair: pair[1])
    return {
        "gross_notional_usd": gross,
        "top_symbol": top_symbol,
        "single_name_concentration": symbol_value / gross,
        "top_sector": top_sector,
        "sector_concentration": sector_value / gross,
        "top_correlation_group": top_bucket,
        "correlated_concentration": bucket_value / gross,
    }


def _with_order(
    request: RiskCheckRequest,
    holdings: list[Holding],
    add_notional: Decimal,
) -> list[Holding]:
    if request.intent.kind in {IntentKind.REDUCE, IntentKind.CLOSE} or add_notional <= 0:
        return holdings
    return holdings + [_holding(request.symbol, add_notional)]


def _within_limits(snapshot: dict) -> bool:
    return (
        snapshot["single_name_concentration"] <= MAX_SINGLE_NAME
        and snapshot["sector_concentration"] <= MAX_SECTOR
        and snapshot["correlated_concentration"] <= MAX_CORRELATED_BUCKET
    )


def _max_safe_additional(
    request: RiskCheckRequest,
    holdings: list[Holding],
) -> Decimal:
    requested = request.intent.notional_usd
    if requested <= 0:
        return D("0")
    if holdings and not _within_limits(_snapshot(holdings)):
        return D("0")
    if _within_limits(_snapshot(_with_order(request, holdings, requested))):
        return requested

    low, high = D("0"), requested
    for _ in range(40):
        mid = (low + high) / D("2")
        if _within_limits(_snapshot(_with_order(request, holdings, mid))):
            low = mid
        else:
            high = mid
    return low.quantize(D("0.01"))


def assess_portfolio(request: RiskCheckRequest) -> dict:
    holdings = _base_holdings(request)
    if not request.account.portfolio_positions:
        return {
            "enabled": False,
            "method": "NOT_PROVIDED",
            "reason": (
                "Host did not provide a portfolio snapshot; account-level exposure "
                "checks still apply."
            ),
            "max_additional_notional_usd": request.intent.notional_usd,
            "limits": {},
            "before": _snapshot(holdings),
            "after_requested": _snapshot(
                _with_order(request, holdings, request.intent.notional_usd)
            ),
            "breaches": [],
        }

    before = _snapshot(holdings)
    after = _snapshot(_with_order(request, holdings, request.intent.notional_usd))
    breaches: list[str] = []
    if after["single_name_concentration"] > MAX_SINGLE_NAME:
        breaches.append("SINGLE_NAME_CONCENTRATION")
    if after["sector_concentration"] > MAX_SECTOR:
        breaches.append("SECTOR_CONCENTRATION")
    if after["correlated_concentration"] > MAX_CORRELATED_BUCKET:
        breaches.append("CORRELATED_EXPOSURE")

    return {
        "enabled": True,
        "method": "DETERMINISTIC_CONCENTRATION_BUCKETS_V1",
        "model_boundary": (
            "Transparent policy buckets, not a claimed live covariance model. "
            "Replace with measured factors when licensed history is available."
        ),
        "max_additional_notional_usd": _max_safe_additional(request, holdings),
        "limits": {
            "single_name": MAX_SINGLE_NAME,
            "sector": MAX_SECTOR,
            "correlated_group": MAX_CORRELATED_BUCKET,
        },
        "before": before,
        "after_requested": after,
        "breaches": breaches,
    }
