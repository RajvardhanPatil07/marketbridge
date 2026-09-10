"""Unified free-first intelligence payload for the frontend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..news import get_market_news
from .sec import get_company_snapshot


def get_market_intelligence(symbol: str, *, force: bool = False) -> dict[str, Any]:
    normalized = symbol.upper().strip()
    news = get_market_news(normalized, force=force)
    company = get_company_snapshot(normalized, force=force)
    return {
        "symbol": normalized,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "affects_market_truth": False,
        "boundary": (
            "News, SEC filings and fundamentals are explanatory context only. "
            "They never qualify a price reference and can never loosen deterministic risk controls."
        ),
        "news": news,
        "official_company_context": company,
    }
