"""Persistent Nasdaq symbol catalogue and bounded live-subscription priorities."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import io
import re
import sqlite3
from pathlib import Path
from threading import Lock
from urllib.request import Request, urlopen


NASDAQ_DIRECTORY_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.\-]{0,11}$")
NORMAL_FINANCIAL_STATUS = "N"
NASDAQ_STOCK_UNIVERSE = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "CSCO", "PEP", "TMUS", "INTU", "AMGN", "QCOM", "TXN",
    "AMAT", "ISRG", "BKNG", "SBUX", "GILD", "ADP", "PANW", "MU", "MELI", "CRWD",
)
BOOTSTRAP = (
    ("AAPL", "Apple Inc. - Common Stock", "Q", 0, "N", 40, 0, 0),
    ("MSFT", "Microsoft Corporation - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("NVDA", "NVIDIA Corporation - Common Stock", "Q", 0, "N", 40, 0, 0),
    ("AMZN", "Amazon.com, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("GOOGL", "Alphabet Inc. - Class A Common Stock", "Q", 0, "N", 100, 0, 0),
    ("GOOG", "Alphabet Inc. - Class C Common Stock", "Q", 0, "N", 100, 0, 0),
    ("META", "Meta Platforms, Inc. - Class A Common Stock", "Q", 0, "N", 100, 0, 0),
    ("TSLA", "Tesla, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("AVGO", "Broadcom Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("COST", "Costco Wholesale Corporation - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("NFLX", "Netflix, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("AMD", "Advanced Micro Devices, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("ADBE", "Adobe Inc. - Common Stock", "Q", 0, "N", 40, 0, 0),
    ("CSCO", "Cisco Systems, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("PEP", "PepsiCo, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("TMUS", "T-Mobile US, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("INTU", "Intuit Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("AMGN", "Amgen Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("QCOM", "QUALCOMM Incorporated - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("TXN", "Texas Instruments Incorporated - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("AMAT", "Applied Materials, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("ISRG", "Intuitive Surgical, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("BKNG", "Booking Holdings Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("SBUX", "Starbucks Corporation - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("GILD", "Gilead Sciences, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("ADP", "Automatic Data Processing, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("PANW", "Palo Alto Networks, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("MU", "Micron Technology, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("MELI", "MercadoLibre, Inc. - Common Stock", "Q", 0, "N", 100, 0, 0),
    ("CRWD", "CrowdStrike Holdings, Inc. - Class A Common Stock", "Q", 0, "N", 100, 0, 0),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class NasdaqSymbol:
    symbol: str
    name: str
    market_category: str
    test_issue: bool
    financial_status: str
    round_lot_size: int
    etf: bool
    nextshares: bool

    @property
    def risk_eligible(self) -> bool:
        equity_name = self.name.lower()
        equity_security = any(token in equity_name for token in ("common stock", "common share", "ordinary share", "depositary share", "depository share"))
        return (
            not self.test_issue and self.financial_status == NORMAL_FINANCIAL_STATUS
            and not self.etf and not self.nextshares and equity_security
        )

    def as_json(self, *, active: bool = False, display_data: bool = True, standard_policy: bool = False) -> dict:
        result = asdict(self)
        result.update(
            exchange="NASDAQ",
            coverage_state=(
                "LIVE_RISK_ELIGIBLE" if active and self.risk_eligible
                else "DISPLAY_DATA_AVAILABLE" if display_data else "CATALOGUE_ONLY"
            ),
            risk_policy="STANDARD" if self.risk_eligible and standard_policy else "REVIEW_ONLY",
            live_active=active,
        )
        return result


class SymbolCatalog:
    """SQLite-backed copy of Nasdaq's public Symbol Directory."""

    def __init__(self, path: Path, *, directory_url: str = NASDAQ_DIRECTORY_URL, universe: tuple[str, ...] | None = NASDAQ_STOCK_UNIVERSE):
        self.path = path
        self.directory_url = directory_url
        self.universe = frozenset(universe) if universe is not None else None
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS nasdaq_symbols (
                    symbol TEXT PRIMARY KEY, name TEXT NOT NULL, market_category TEXT NOT NULL,
                    test_issue INTEGER NOT NULL, financial_status TEXT NOT NULL,
                    round_lot_size INTEGER NOT NULL, etf INTEGER NOT NULL, nextshares INTEGER NOT NULL
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_nasdaq_name ON nasdaq_symbols(name)")
            db.execute("CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            count = db.execute("SELECT COUNT(*) FROM nasdaq_symbols").fetchone()[0]
            if count == 0:
                db.executemany("INSERT INTO nasdaq_symbols VALUES (?, ?, ?, ?, ?, ?, ?, ?)", BOOTSTRAP)
                db.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('source', 'bootstrap')")

    def parse_directory(self, payload: str) -> list[tuple]:
        rows: list[tuple] = []
        reader = csv.DictReader(io.StringIO(payload), delimiter="|")
        required = {"Symbol", "Security Name", "Market Category", "Test Issue", "Financial Status", "Round Lot Size", "ETF", "NextShares"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Nasdaq Symbol Directory headers are invalid")
        for row in reader:
            symbol = (row.get("Symbol") or "").strip().upper()
            if not SYMBOL_PATTERN.fullmatch(symbol) or symbol.startswith("FILE CREATION TIME"):
                continue
            if self.universe is not None and symbol not in self.universe:
                continue
            try:
                round_lot = int(row.get("Round Lot Size") or 0)
            except ValueError:
                round_lot = 0
            rows.append((
                symbol, (row.get("Security Name") or symbol).strip(), (row.get("Market Category") or "").strip(),
                int((row.get("Test Issue") or "N").strip() == "Y"),
                (row.get("Financial Status") or "").strip(), round_lot,
                int((row.get("ETF") or "N").strip() == "Y"), int((row.get("NextShares") or "N").strip() == "Y"),
            ))
        minimum = len(self.universe) if self.universe is not None else 100
        if len(rows) < minimum:
            raise ValueError("Nasdaq Symbol Directory response is unexpectedly small")
        return rows

    def refresh(self, *, timeout: float = 8.0) -> dict:
        request = Request(self.directory_url, headers={"User-Agent": "MarketBridge/1.0"})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS source by default
            payload = response.read(4_000_000).decode("utf-8-sig")
        rows = self.parse_directory(payload)
        synced_at = _iso(_utcnow())
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM nasdaq_symbols")
            db.executemany("INSERT INTO nasdaq_symbols VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
            db.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('source', 'nasdaq_symbol_directory')")
            db.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('synced_at', ?)", (synced_at,))
        return {"count": len(rows), "synced_at": synced_at, "source": "nasdaq_symbol_directory"}

    def ensure_fresh(self, *, max_age: timedelta = timedelta(hours=24), timeout: float = 8.0) -> dict:
        status = self.status()
        synced = status.get("synced_at")
        if synced and status["count"] == (len(self.universe) if self.universe is not None else status["count"]):
            age = _utcnow() - datetime.fromisoformat(synced.replace("Z", "+00:00"))
            if age <= max_age:
                return {**status, "refreshed": False}
        return {**self.refresh(timeout=timeout), "refreshed": True}

    def status(self) -> dict:
        with self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM nasdaq_symbols").fetchone()[0]
            meta = dict(db.execute("SELECT key, value FROM catalog_meta").fetchall())
        return {"count": count, "source": meta.get("source", "bootstrap"), "synced_at": meta.get("synced_at")}

    @staticmethod
    def _from_row(row: sqlite3.Row) -> NasdaqSymbol:
        return NasdaqSymbol(
            symbol=row["symbol"], name=row["name"], market_category=row["market_category"],
            test_issue=bool(row["test_issue"]), financial_status=row["financial_status"],
            round_lot_size=row["round_lot_size"], etf=bool(row["etf"]), nextshares=bool(row["nextshares"]),
        )

    def get(self, symbol: str) -> NasdaqSymbol | None:
        symbol = symbol.strip().upper()
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return None
        with self._connect() as db:
            row = db.execute("SELECT * FROM nasdaq_symbols WHERE symbol = ?", (symbol,)).fetchone()
        return self._from_row(row) if row else None

    def search(self, query: str = "", *, limit: int = 20, offset: int = 0) -> tuple[list[NasdaqSymbol], int]:
        query = query.strip().upper()[:80]
        limit = max(1, min(limit, 50))
        offset = max(0, offset)
        if query:
            pattern = f"%{query.replace('%', '').replace('_', '')}%"
            where, params = "WHERE symbol LIKE ? OR UPPER(name) LIKE ?", (pattern, pattern)
            order = "ORDER BY CASE WHEN symbol = ? THEN 0 WHEN symbol LIKE ? THEN 1 ELSE 2 END, symbol"
            order_params = (query, f"{query}%")
        else:
            where, params, order, order_params = "", (), "ORDER BY symbol", ()
        with self._connect() as db:
            total = db.execute(f"SELECT COUNT(*) FROM nasdaq_symbols {where}", params).fetchone()[0]
            rows = db.execute(
                f"SELECT * FROM nasdaq_symbols {where} {order} LIMIT ? OFFSET ?",
                (*params, *order_params, limit, offset),
            ).fetchall()
        return [self._from_row(row) for row in rows], total


class ActiveSubscriptions:
    """Priority/TTL registry that prevents catalogue size from becoming feed load."""

    PRIORITY = {"bootstrap": 10, "recent": 20, "view": 40, "watchlist": 60, "position": 90, "order": 100}

    def __init__(self, bootstrap: tuple[str, ...], *, ttl: timedelta = timedelta(minutes=15)):
        now = _utcnow()
        self._ttl = ttl
        self._lock = Lock()
        self._entries = {symbol: (self.PRIORITY["bootstrap"], now, "bootstrap") for symbol in bootstrap}

    def touch(self, symbol: str, reason: str = "view") -> None:
        if reason not in self.PRIORITY:
            raise ValueError("unsupported subscription reason")
        with self._lock:
            self._entries[symbol] = (self.PRIORITY[reason], _utcnow(), reason)

    def symbols(self, limit: int) -> tuple[str, ...]:
        now = _utcnow()
        with self._lock:
            self._entries = {
                symbol: value for symbol, value in self._entries.items()
                if value[2] == "bootstrap" or now - value[1] <= self._ttl
            }
            ranked = sorted(self._entries.items(), key=lambda item: (-item[1][0], -item[1][1].timestamp()))
        return tuple(symbol for symbol, _ in ranked[:max(1, limit)])

    def snapshot(self, *, alpaca_limit: int = 30, twelve_data_limit: int = 8) -> dict:
        return {
            "policy": "priority_ttl",
            "alpaca_limit": alpaca_limit,
            "twelve_data_limit": twelve_data_limit,
            "alpaca": list(self.symbols(alpaca_limit)),
            "twelve_data": list(self.symbols(twelve_data_limit)),
        }
