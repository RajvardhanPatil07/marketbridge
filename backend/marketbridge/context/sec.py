"""Small SEC EDGAR adapter for primary-source company context.

SEC data is context, not executable market evidence.  This adapter deliberately
uses only the Python standard library and caches responses to be polite to EDGAR.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from threading import Lock
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_COMPANY_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
CACHE_SECONDS = 900
TICKER_CACHE_SECONDS = 24 * 60 * 60

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_ticker_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
_lock = Lock()


class SecError(RuntimeError):
    pass


def _user_agent() -> str:
    configured = os.environ.get("MARKETBRIDGE_SEC_USER_AGENT", "").strip()
    return configured or "MarketBridge/1.0 hackathon-research (set MARKETBRIDGE_SEC_USER_AGENT with contact)"


def _json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": _user_agent(),
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed SEC hosts only
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        raise SecError(f"SEC returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise SecError("SEC is temporarily unreachable") from exc
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SecError("SEC returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise SecError("SEC returned an unexpected response")
    return parsed


def _ticker_index() -> dict[str, dict[str, Any]]:
    global _ticker_cache
    now = time.monotonic()
    with _lock:
        if _ticker_cache and now - _ticker_cache[0] < TICKER_CACHE_SECONDS:
            return _ticker_cache[1]
    raw = _json(SEC_TICKERS_URL)
    index: dict[str, dict[str, Any]] = {}
    for item in raw.values():
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("ticker") or "").upper().strip()
        try:
            cik = int(item.get("cik_str"))
        except (TypeError, ValueError):
            continue
        if symbol:
            index[symbol] = {"cik": cik, "name": str(item.get("title") or symbol)}
    with _lock:
        _ticker_cache = (now, index)
    return index


def _recent_filings(submissions: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []
    forms = recent.get("form", [])
    accession = recent.get("accessionNumber", [])
    filed = recent.get("filingDate", [])
    report = recent.get("reportDate", [])
    primary = recent.get("primaryDocument", [])
    accepted = {"8-K", "10-Q", "10-K", "6-K", "20-F", "40-F"}
    rows: list[dict[str, Any]] = []
    for index, form in enumerate(forms if isinstance(forms, list) else []):
        if form not in accepted:
            continue
        acc = accession[index] if index < len(accession) else ""
        doc = primary[index] if index < len(primary) else ""
        acc_compact = str(acc).replace("-", "")
        cik = str(submissions.get("cik") or "").lstrip("0")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_compact}/{doc}"
            if cik and acc_compact and doc
            else None
        )
        rows.append(
            {
                "form": form,
                "filing_date": filed[index] if index < len(filed) else None,
                "report_date": report[index] if index < len(report) else None,
                "accession_number": acc,
                "primary_document": doc,
                "url": url,
                "official_source": True,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _latest_fact(companyfacts: dict[str, Any], concepts: tuple[str, ...]) -> dict[str, Any] | None:
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    if not isinstance(gaap, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for concept in concepts:
        fact = gaap.get(concept)
        if not isinstance(fact, dict):
            continue
        units = fact.get("units", {})
        if not isinstance(units, dict):
            continue
        for unit_name, values in units.items():
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, dict) or value.get("form") not in {"10-K", "10-Q", "20-F"}:
                    continue
                raw = value.get("val")
                try:
                    number = float(raw)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(number):
                    continue
                candidates.append(
                    {
                        "concept": concept,
                        "label": fact.get("label") or concept,
                        "value": number,
                        "unit": unit_name,
                        "filed": value.get("filed"),
                        "period_end": value.get("end"),
                        "form": value.get("form"),
                        "fiscal_year": value.get("fy"),
                        "fiscal_period": value.get("fp"),
                    }
                )
    if not candidates:
        return None
    candidates.sort(key=lambda row: (str(row.get("filed") or ""), str(row.get("period_end") or "")))
    return candidates[-1]


def _base(symbol: str) -> dict[str, Any]:
    return {
        "provider": "sec-edgar",
        "source_class": "OFFICIAL_CONTEXT",
        "affects_market_truth": False,
        "symbol": symbol,
        "status": "UNAVAILABLE",
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "company": None,
        "recent_filings": [],
        "facts": {},
        "message": None,
    }


def get_company_snapshot(symbol: str, *, force: bool = False) -> dict[str, Any]:
    normalized = symbol.upper().strip()
    if not normalized or len(normalized) > 12:
        raise ValueError("invalid symbol")
    now = time.monotonic()
    with _lock:
        cached = _cache.get(normalized)
        if cached and not force and now - cached[0] < CACHE_SECONDS:
            return {**cached[1], "cached": True}

    base = _base(normalized)
    try:
        listing = _ticker_index().get(normalized)
        if listing is None:
            return {**base, "status": "NOT_FOUND", "message": "Symbol is not in the SEC company ticker index."}
        submissions = _json(SEC_SUBMISSIONS.format(cik=listing["cik"]))
        companyfacts = _json(SEC_COMPANY_FACTS.format(cik=listing["cik"]))
        payload = {
            **base,
            "status": "AVAILABLE",
            "cached": False,
            "company": {
                "name": submissions.get("name") or listing["name"],
                "cik": f"{listing['cik']:010d}",
                "sic": submissions.get("sic"),
                "sic_description": submissions.get("sicDescription"),
                "fiscal_year_end": submissions.get("fiscalYearEnd"),
                "state_of_incorporation": submissions.get("stateOfIncorporation"),
            },
            "recent_filings": _recent_filings(submissions),
            "facts": {
                "revenue": _latest_fact(companyfacts, ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues")),
                "net_income": _latest_fact(companyfacts, ("NetIncomeLoss",)),
                "assets": _latest_fact(companyfacts, ("Assets",)),
                "cash": _latest_fact(companyfacts, ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents")),
                "diluted_eps": _latest_fact(companyfacts, ("EarningsPerShareDiluted",)),
            },
            "message": None,
        }
        with _lock:
            _cache[normalized] = (now, payload)
        return payload
    except SecError as exc:
        with _lock:
            cached = _cache.get(normalized)
        if cached:
            return {**cached[1], "status": "DEGRADED", "cached": True, "message": str(exc)}
        return {**base, "message": str(exc)}


def clear_sec_cache() -> None:
    global _ticker_cache
    with _lock:
        _cache.clear()
        _ticker_cache = None
