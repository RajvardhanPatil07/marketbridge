"""Published market-incident reconstruction used as real-world context.

The observations below are transcribed from a public transaction analysis whose
rows link to the corresponding Hyperliquid explorer transactions. They are not
a licensed consolidated feed and are never represented as live market data.
"""

from functools import lru_cache
from datetime import datetime, timedelta, timezone


GALAXY_SOURCE = "https://www.galaxy.com/insights/research/hyperliquid-tradexyz-oracle-liquidations"
TRANSACTION_SOURCE = "https://k.odz.jp/posts/tradexyz-incident/"

# Seconds after the final pre-incident update, external price, oracle and
# reconstructed mark. Values and timestamps are published in TRANSACTION_SOURCE.
_ROWS = [
    (0, 1113.60, 1131.40, 1127.90),
    (3, 868.18, 954.99, 1116.62),
    (6, 868.17, 954.98, 1105.45),
    (9, 868.17, 945.44, 1094.40),
    (12, 868.17, 935.99, 1083.46),
    (15, 868.17, 926.64, 1072.62),
    (18, 868.17, 917.38, 1061.90),
    (21, 868.17, 908.21, 1051.28),
    (24, 868.17, 899.13, 1040.76),
    (27, 868.17, 899.13, 1030.36),
    (30, 868.17, 890.14, 1020.05),
    (33, 868.17, 881.24, 1009.85),
    (36, 868.17, 872.43, 999.75),
    (39, 868.17, 870.12, 989.76),
    (42, 868.17, 870.26, 979.86),
    (45, 868.17, 870.38, 970.06),
    (48, 868.17, 870.50, 960.36),
    (51, 868.17, 870.63, 954.98),
    (54, 868.17, 870.75, 950.21),
    (60, 868.17, 871.02, 940.74),
    (63, 868.17, 871.16, 936.04),
    (66, 868.17, 871.30, 931.36),
    (69, 868.17, 871.44, 926.71),
    (72, 868.17, 871.56, 922.08),
    (75, 868.17, 871.70, 917.47),
    (78, 868.17, 871.84, 917.25),
]


@lru_cache(maxsize=1)
def incident_reconstruction() -> dict:
    start = datetime(2026, 7, 27, 23, 0, tzinfo=timezone.utc)
    points = [
        {
            "seconds": seconds,
            "timestamp": (start + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z"),
            "external_price": external,
            "oracle_price": oracle,
            "reported_mark": mark,
        }
        for seconds, external, oracle, mark in _ROWS
    ]
    return {
        "id": "sk-hynix-july-2026",
        "data_mode": "HISTORICAL_RECONSTRUCTION",
        "title": "The SK Hynix handoff failure",
        "symbol": "xyz:SKHYNIX",
        "venue": "Hyperliquid / TradeXYZ",
        "date": "2026-07-28",
        "summary": (
            "A single share traded 29.96% below the prior close on a thin pre-market book. "
            "The reported perpetual mark fell 18.7% and roughly $60M of leveraged long notional was liquidated."
        ),
        "facts": {
            "cash_print_usd": 868.17,
            "prior_close_krw": 1816000,
            "cash_print_krw": 1272000,
            "reported_mark_before": 1127.90,
            "reported_mark_low": 917.25,
            "reported_mark_drop_pct": -18.7,
            "reported_liquidated_notional_usd_approx": 60000000,
            "accounts_estimate": 960,
        },
        "points": points,
        "operator_decision": {
            "decision_scope": "COUNTERFACTUAL_ADVISORY",
            "status": "INSUFFICIENT_EVIDENCE",
            "reference": None,
            "last_valid": 1127.90,
            "independent_source_families": 1,
            "new_exposure_allowed": False,
            "advisory_exposure_multiplier": 0,
            "reason": "THIN_SINGLE_VENUE_PRINT_AT_EXTERNAL_PRICE_HANDOFF",
            "explanation": (
                "Multiple providers relaying the same thin venue print are correlated evidence, not independent price discovery."
            ),
        },
        "sources": [
            {"title": "Galaxy Research incident analysis", "url": GALAXY_SOURCE},
            {"title": "Transaction-linked reconstruction", "url": TRANSACTION_SOURCE},
        ],
        "limitations": [
            "This is a reconstruction from published observations, not a live or complete market-data feed.",
            "The MarketBridge decision is counterfactual and does not prove that losses would have been prevented.",
            "Reported liquidation figures describe approximate notional and account counts, not verified customer cash losses.",
            "Current venue rules may differ from the rules operating during the incident.",
        ],
    }
