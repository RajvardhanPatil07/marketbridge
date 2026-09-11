"""Free-first provider registry for MarketBridge v1.

The registry is intentionally capability based.  Provider names are implementation
choices; the risk engine reasons about provenance, independence, freshness and role.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from typing import Any, Iterable


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    name: str
    capability: str
    source_class: str
    cost_mode: str
    credential_env: tuple[str, ...] = ()
    market_truth_authority: str = "NONE"
    risk_eligible: bool = False
    display_allowed_by_architecture: bool = True
    default_enabled: bool = True
    note: str = ""

    def configured(self) -> bool:
        if not self.credential_env:
            return self.default_enabled
        return all(bool(os.environ.get(name, "").strip()) for name in self.credential_env)


PROVIDERS: tuple[ProviderDefinition, ...] = (
    ProviderDefinition(
        id="alpaca",
        name="Alpaca Market Data",
        capability="LIVE_EQUITY",
        source_class="MARKET_EVIDENCE",
        cost_mode="FREE_TIER",
        credential_env=("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
        market_truth_authority="WITNESS_ONLY",
        risk_eligible=True,
        note="Free-first equity stream. IEX is a single venue and never qualifies a reference by itself.",
    ),
    ProviderDefinition(
        id="hyperliquid",
        name="Hyperliquid",
        capability="VENUE_CONTEXT",
        source_class="VENUE_EVIDENCE",
        cost_mode="PUBLIC_API",
        credential_env=("HYPERLIQUID_COIN_MAP",),
        market_truth_authority="VENUE_ONLY",
        risk_eligible=False,
        note="Venue mark/oracle/mid/funding/OI context. It is never fed back into the independent reference.",
    ),
    ProviderDefinition(
        id="marketaux",
        name="Marketaux",
        capability="FINANCIAL_NEWS",
        source_class="CONTEXT",
        cost_mode="FREE_TIER",
        credential_env=("MARKETAUX_API_TOKEN",),
        market_truth_authority="NONE",
        risk_eligible=False,
        note="Ticker-linked news and sentiment. Context only; never creates Market Truth.",
    ),
    ProviderDefinition(
        id="sec-edgar",
        name="SEC EDGAR",
        capability="OFFICIAL_COMPANY_EVENTS",
        source_class="OFFICIAL_CONTEXT",
        cost_mode="PUBLIC_API",
        market_truth_authority="NONE",
        risk_eligible=False,
        note="Primary-source filings and XBRL company facts. No API key; use a descriptive User-Agent.",
    ),
    ProviderDefinition(
        id="nasdaq-symbols",
        name="Nasdaq Symbol Directory",
        capability="SECURITY_MASTER",
        source_class="REFERENCE_DATA",
        cost_mode="PUBLIC_DATA",
        market_truth_authority="NONE",
        risk_eligible=False,
        note="Symbol/name/listing metadata. It does not provide a tradable reference price.",
    ),
    ProviderDefinition(
        id="twelve-data",
        name="Twelve Data",
        capability="OPTIONAL_EQUITY_CROSSCHECK",
        source_class="INTERNAL_CROSSCHECK",
        cost_mode="FREE_TIER_LIMITED",
        credential_env=("TWELVE_DATA_API_KEY",),
        market_truth_authority="OPTIONAL_WITNESS",
        risk_eligible=False,
        note="Optional REST/internal corroboration. Free WebSocket trial is not a production dependency.",
    ),
    ProviderDefinition(
        id="yahoo",
        name="Yahoo Finance via yfinance",
        capability="RESEARCH_FALLBACK",
        source_class="RESEARCH_ONLY",
        cost_mode="UNOFFICIAL_RESEARCH",
        market_truth_authority="NONE",
        risk_eligible=False,
        display_allowed_by_architecture=False,
        default_enabled=False,
        note="Legacy research fallback only. Never eligible for a safety reference.",
    ),
    ProviderDefinition(
        id="fred",
        name="FRED",
        capability="MACRO_CONTEXT",
        source_class="CONTEXT",
        cost_mode="FREE_API_KEY",
        credential_env=("FRED_API_KEY",),
        market_truth_authority="NONE",
        risk_eligible=False,
        note="Optional rates/yields/macro context. It cannot create or loosen Market Truth.",
    ),
    ProviderDefinition(
        id="coingecko",
        name="CoinGecko Demo",
        capability="CRYPTO_OVERVIEW",
        source_class="DISPLAY_CONTEXT",
        cost_mode="FREE_TIER",
        credential_env=("COINGECKO_API_KEY",),
        market_truth_authority="NONE",
        risk_eligible=False,
        note="Optional crypto overview for discovery pages; never used for equity-perp safety decisions.",
    ),
)


def _runtime_by_id(snapshot: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not snapshot:
        return {}
    providers = snapshot.get("providers", [])
    if not isinstance(providers, list):
        return {}
    return {
        str(item.get("id")): item
        for item in providers
        if isinstance(item, dict) and item.get("id")
    }


def provider_registry(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the judge-facing provider mesh without legacy/paid-provider leakage."""
    runtime = _runtime_by_id(snapshot)
    items: list[dict[str, Any]] = []
    for definition in PROVIDERS:
        row = asdict(definition)
        row["credential_env"] = list(definition.credential_env)
        configured = definition.configured()
        observed = runtime.get(definition.id, {})
        status = str(observed.get("status") or ("CONFIGURED" if configured else "NOT_CONFIGURED"))
        if definition.id == "sec-edgar":
            status = "READY"
        elif definition.id == "nasdaq-symbols":
            status = "READY"
        elif definition.id == "yahoo" and os.environ.get("MARKETBRIDGE_DISABLE_RESEARCH_FEED", "1") == "1":
            status = "DISABLED"
        elif definition.id == "twelve-data" and configured:
            # A free key does not imply unrestricted WebSocket/display rights.
            status = "OPTIONAL"
        row.update(
            configured=configured,
            status=status,
            runtime={
                key: observed.get(key)
                for key in (
                    "detail", "last_event_time", "last_message_time", "retry_count",
                    "consecutive_failures", "qualification_capable",
                )
                if key in observed
            },
        )
        items.append(row)

    return {
        "architecture_version": "marketbridge-v1-free-first",
        "cost_mode": "FREE_FIRST",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "principles": [
            "Provider names are adapters, not architecture.",
            "Venue evidence never feeds back into the independent underlying reference.",
            "News, filings, macro and research data are context-only.",
            "One free IEX feed is one witness, not independent market consensus.",
            "Unknown entitlement or public-display permission is treated conservatively.",
            "Synthetic attack fixtures are explicitly labelled and use the same risk policy as the integration demo.",
        ],
        "providers": items,
    }


def definitions(ids: Iterable[str] | None = None) -> tuple[ProviderDefinition, ...]:
    if ids is None:
        return PROVIDERS
    selected = set(ids)
    return tuple(item for item in PROVIDERS if item.id in selected)
