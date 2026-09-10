from datetime import timedelta

import pytest

from marketbridge.symbols import ActiveSubscriptions, SymbolCatalog


DIRECTORY = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
{rows}
File Creation Time: 0910202621:01|||||||
"""


def directory_rows(count: int = 100) -> str:
    rows = [f"Z{i:03d}|Example {i} - Common Stock|Q|N|N|100|N|N" for i in range(count)]
    rows[0] = "AAPL|Apple Inc. - Common Stock|Q|N|N|40|N|N"
    rows[1] = "TEST|Nasdaq test issue|Q|Y|N|100|N|N"
    rows[2] = "FUND|Example ETF|G|N|N|100|Y|N"
    rows[3] = "LATE|Deficient issuer|S|N|D|100|N|N"
    return DIRECTORY.format(rows="\n".join(rows))


def test_catalog_parses_searches_and_labels_risk(tmp_path):
    catalog = SymbolCatalog(tmp_path / "symbols.sqlite3", universe=None)
    rows = catalog.parse_directory(directory_rows())
    assert len(rows) == 100
    with pytest.MonkeyPatch.context() as monkeypatch:
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def read(self, _limit): return directory_rows().encode()
        monkeypatch.setattr("marketbridge.symbols.urlopen", lambda *_args, **_kwargs: Response())
        assert catalog.refresh()["count"] == 100
    matches, total = catalog.search("apple")
    assert total == 1 and matches[0].symbol == "AAPL"
    assert catalog.get("AAPL").as_json(active=True)["coverage_state"] == "LIVE_RISK_ELIGIBLE"
    assert catalog.get("TEST").risk_eligible is False
    assert catalog.get("FUND").as_json(active=True)["risk_policy"] == "REVIEW_ONLY"
    assert catalog.get("LATE").risk_eligible is False


def test_active_subscriptions_are_bounded_and_priority_ordered():
    active = ActiveSubscriptions(("AAPL", "MSFT"), ttl=timedelta(minutes=15))
    active.touch("NVDA", "view")
    active.touch("TSLA", "order")
    assert active.symbols(3) == ("TSLA", "NVDA", "AAPL")
    snapshot = active.snapshot(alpaca_limit=3, twelve_data_limit=2)
    assert snapshot["alpaca"] == ["TSLA", "NVDA", "AAPL"]
    assert snapshot["twelve_data"] == ["TSLA", "NVDA"]


def test_catalog_rejects_malformed_directory(tmp_path):
    catalog = SymbolCatalog(tmp_path / "symbols.sqlite3", universe=None)
    with pytest.raises(ValueError, match="headers"):
        catalog.parse_directory("symbol,name\nAAPL,Apple")
