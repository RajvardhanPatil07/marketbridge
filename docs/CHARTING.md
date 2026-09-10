# MarketBridge charting

The asset and terminal workspaces use TradingView Lightweight Charts 5.x as a rendering engine. MarketBridge is not TradingView and this repository does not include the proprietary TradingView Advanced Charts library.

The chart defaults to real candlesticks fetched through the MarketBridge backend. Available chart modes are candlestick, OHLC bars, line, area, baseline, and Heikin Ashi. The selected symbol, range, resolution, chart type, scale, adjustment, session, and indicator set use a versioned local-storage workspace.

## Studies and panes

Indicator calculations are pure deterministic TypeScript functions. SMA, EMA, and Bollinger Bands render as price overlays. Volume, RSI, and MACD render in lower panes. Unit tests cover known moving-average/Bollinger results, RSI bounds, and MACD alignment. Indicator instances can be added and removed without changing the selected symbol or range.

MarketBridge reference observations render as a separate blue overlay when available. Crosshair details include real OHLC, volume, VWAP, current reference, and risk state. The status strip labels provider, feed, delay, session, resolution, adjustment, and the display/oracle boundary.

## Updating and performance

Range changes abort obsolete requests. Historical arrays are set when a dataset changes, while the latest raw bar is reconciled incrementally with `series.update()`. Requests are cached and deduplicated on the server. `MAX` history backfills in bounded windows. Hot chart objects live in refs so price refreshes do not recreate the chart.

Screenshots use `takeScreenshot()`. Fullscreen uses the browser Fullscreen API. Keyboard shortcuts are `F` fullscreen, `C` candlestick, `L` line, `1` one-minute, `5` five-minute, and `D` daily.

## Attribution

The chart explicitly keeps `layout.attributionLogo` enabled. The upstream notice is also preserved in `THIRD_PARTY_NOTICES.md`, with a visible link supplied by the chart attribution logo.
