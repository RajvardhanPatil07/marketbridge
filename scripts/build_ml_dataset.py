"""Build an extended-hours research dataset for MarketBridge ML training.

This script uses Yahoo/yfinance only for offline research/backtesting. It does not
make Yahoo oracle-eligible at runtime. The output schema is consumed by
scripts/train_ai_models.py.
"""

from __future__ import annotations

import argparse
from datetime import time
from pathlib import Path

import pandas as pd
import yfinance as yf

STOCKS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMD"]
FACTORS = ["QQQ", "SPY", "SOXX"]
FEATURE_COLUMNS = [
    "qqq_return_bps",
    "spy_return_bps",
    "soxx_return_bps",
    "single_source_return_bps",
    "minutes_since_anchor",
    "source_age_ms",
    "provider_count",
    "venue_count",
]


def _close_series(symbol: str, period: str, interval: str) -> pd.Series:
    frame = yf.Ticker(symbol).history(
        period=period,
        interval=interval,
        prepost=True,
        auto_adjust=False,
        actions=False,
    )
    if frame.empty:
        raise RuntimeError(f"No historical bars returned for {symbol}")
    series = frame["Close"].dropna().astype(float)
    if series.index.tz is None:
        series.index = series.index.tz_localize("UTC")
    return series.tz_convert("America/New_York")


def _last_regular_close_before(series: pd.Series, timestamp: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    history = series.loc[:timestamp]
    if history.empty:
        return None
    regular = history[(history.index.time >= time(9, 30)) & (history.index.time <= time(16, 0))]
    if regular.empty:
        return None
    # Prefer a bar at/near 16:00; otherwise the last regular-session bar.
    anchor_time = regular.index[-1]
    anchor_price = float(regular.iloc[-1])
    if anchor_time >= timestamp:
        previous_day = regular[regular.index.date < timestamp.date()]
        if previous_day.empty:
            return None
        anchor_time = previous_day.index[-1]
        anchor_price = float(previous_day.iloc[-1])
    return anchor_time, anchor_price


def _value_at(series: pd.Series, timestamp: pd.Timestamp) -> float | None:
    history = series.loc[:timestamp]
    if history.empty:
        return None
    return float(history.iloc[-1])


def build(period: str, interval: str) -> pd.DataFrame:
    factors = {symbol: _close_series(symbol, period, interval) for symbol in FACTORS}
    rows: list[dict] = []
    for symbol in STOCKS:
        stock = _close_series(symbol, period, interval)
        for timestamp, stock_price in stock.items():
            # We only learn from extended-hours observations. Regular session bars
            # provide the trusted anchor but are not targets.
            clock = timestamp.time()
            if time(9, 30) <= clock <= time(16, 0):
                continue
            anchor = _last_regular_close_before(stock, timestamp)
            if anchor is None:
                continue
            anchor_time, anchor_price = anchor
            factor_returns: dict[str, float] = {}
            valid = True
            for factor_symbol, factor_series in factors.items():
                now_price = _value_at(factor_series, timestamp)
                anchor_factor = _value_at(factor_series, anchor_time)
                if now_price is None or anchor_factor is None or anchor_factor <= 0:
                    valid = False
                    break
                factor_returns[factor_symbol] = (now_price / anchor_factor - 1.0) * 10_000
            if not valid or anchor_price <= 0:
                continue
            target_return = (float(stock_price) / anchor_price - 1.0) * 10_000
            rows.append({
                "symbol": symbol,
                "timestamp": timestamp.tz_convert("UTC").isoformat(),
                "qqq_return_bps": factor_returns["QQQ"],
                "spy_return_bps": factor_returns["SPY"],
                "soxx_return_bps": factor_returns["SOXX"],
                # Historical research has only one stock print at this timestamp;
                # do not leak the target into the model. Runtime can populate this
                # with a surviving direct source, but the training value remains 0.
                "single_source_return_bps": 0.0,
                "minutes_since_anchor": max(0.0, (timestamp - anchor_time).total_seconds() / 60.0),
                "source_age_ms": 0.0,
                "provider_count": 1.0,
                "venue_count": 1.0,
                "target_return_bps": target_return,
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("No extended-hours rows were produced")
    return frame.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="6mo", help="Yahoo period, e.g. 3mo, 6mo, 1y")
    parser.add_argument("--interval", default="60m", help="Yahoo interval; 60m is practical for longer windows")
    parser.add_argument("--output", type=Path, default=Path("data/ml_training.csv"))
    args = parser.parse_args()
    frame = build(args.period, args.interval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(f"wrote {len(frame)} rows to {args.output}")


if __name__ == "__main__":
    main()
