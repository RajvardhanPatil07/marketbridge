# Historical market data

MarketBridge exposes display-only OHLCV through `GET /v1/market/bars/{symbol}`. Provider credentials remain in the FastAPI process and are never serialized to the browser.

Historical/display bars never become order-qualification evidence. Order checks consume independent
Market Truth; venue mark/oracle/mid/BBO fields remain one venue context under test. Entitlement for
non-display computation is versioned separately in `config/entitlements.yaml` and defaults conservatively.

## Request model

`range` controls the visible date window; `resolution` controls candle width. They are deliberately independent. Supported ranges are `1D`, `5D`, `1M`, `3M`, `6M`, `YTD`, `1Y`, `5Y`, and `MAX`. Defaults are `1Min`, `5Min`, `30Min`, `1Hour`, `1Day`, `1Day`, `1Day`, `1Week`, and `1Month` respectively.

The remaining parameters are:

- `feed=iex|sip|boats`
- `adjustment=raw|all`
- `session=regular|extended|all`
- optional ISO-8601 `start` and `end` overrides

Every response includes provider, feed, entitlement, delay, timezone, session, adjustment and cache metadata. Missing periods remain missing; the service never inserts candles for closures, weekends, outages, or absent entitlements.

## Alpaca flow

1. FastAPI validates the symbol, range, resolution, feed, adjustment, and session.
2. A bounded TTL cache coalesces identical concurrent requests.
3. The Alpaca adapter requests ascending pages, follows every `next_page_token`, and deduplicates bars by UTC timestamp.
4. Retryable `429` and `5xx` responses use bounded exponential backoff. Authentication, entitlement, symbol, malformed-data, and provider failures become safe normalized errors.
5. Bars are normalized to timestamp, OHLC, volume, VWAP, and trade count.
6. Session filtering uses `America/New_York`, while timestamps remain UTC on the wire.

`MAX` starts with a bounded ten-year monthly window. The response supplies `has_more_history` and `next_end`; the UI requests older windows and prepends them. It never sends an unbounded lifetime array to the browser.

## Integrity boundary

Historical chart bars are not MarketBridge oracle evidence. The response states
`data_role=DISPLAY_ONLY_NOT_ORACLE_EVIDENCE`. Alpaca IEX is a valid display feed but a single venue
and cannot create independent consensus on its own. Twelve Data's `quotes/price` WebSocket may act
as one additional provider/venue witness when its subscription is acknowledged and current;
Databento remains an optional paid source. Each vendor aggregate counts once, regardless of named
upstream exchanges. A venue mark is the value being evaluated and never validates itself.

Raw and adjusted history are never silently mixed. Incremental refresh runs only in `raw` mode; adjusted charts remain historical until a matching adjusted live policy is explicitly designed.

## Nasdaq catalogue and live limits

MarketBridge keeps a local SQLite copy of 30 selected stocks from Nasdaq's public `nasdaqlisted.txt`
Symbol Directory and refreshes it at most once per day. `GET /v1/symbols` searches that curated universe; selecting a result
opens its asset workspace and loads display-only Alpaca history on demand. The last verified copy is
retained if Nasdaq is temporarily unavailable.

Catalogue size never becomes WebSocket load. `POST /v1/market/active-symbols/{symbol}` adds a symbol
to a bounded priority/TTL scheduler. Orders and positions outrank watchlists, views, recents, and the
bootstrap set. Alpaca defaults to 30 active symbols and Twelve Data to 8; both limits are configurable
downward with `ALPACA_LIVE_SYMBOL_LIMIT` and `TWELVE_DATA_LIVE_SYMBOL_LIMIT` to match the account's
actual entitlement. Inactive view/recent entries expire after 15 minutes.

Every catalogue record exposes one of `CATALOGUE_ONLY`, `DISPLAY_DATA_AVAILABLE`, or
`LIVE_RISK_ELIGIBLE`. Curated stocks without a symbol-specific policy use a conservative 1×,
manual-review policy; valid reduce/close intents remain preserved by the risk gateway.
