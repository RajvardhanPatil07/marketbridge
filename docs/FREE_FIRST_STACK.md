# Free-first provider stack

Prepared for the 2026 hackathon build. Provider plans and usage rights can change; verify the account dashboard/terms before any public or commercial deployment.

## Required for the public demo

**Nothing.** `/demo/` uses explicit deterministic `SYNTHETIC_DEMO` fixtures and the real MarketBridge risk policy. This makes the demo reliable and reproducible.

## Recommended free live configuration

### Alpaca Basic / IEX

Use for live US-equity display and one market-evidence witness.

```env
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_FEED=iex
```

Architectural rule: IEX is one venue. Do not label it full US-market consensus.

### Hyperliquid public API/WebSocket

Use as the observed perp/venue side when the exact deployed market identifiers are known.

```env
HYPERLIQUID_COIN_MAP={"NVDA":"...","TSLA":"..."}
```

Architectural rule: venue mark/oracle/mid may be compared to independent Market Truth but cannot be fed back into it.

### Marketaux free tier

Use for ticker-linked news. The backend caches for 20 minutes to preserve the free allowance.

```env
MARKETAUX_API_TOKEN=...
```

Architectural rule: news is context-only.

### SEC EDGAR

No API key is required. Configure a descriptive User-Agent/contact before public deployment.

```env
MARKETBRIDGE_SEC_USER_AGENT="MarketBridge/1.0 team@example.com"
```

Use for official filings/company facts. Never use SEC company facts as a live quote.

### Nasdaq Symbol Directory

Already used by the symbol catalogue for listing metadata. Refresh/cache rather than hitting the source on every browser request.

## Optional

### Twelve Data

Keep only as an optional/internal cross-check. A free key or trial WebSocket does not automatically establish public-display or risk-computation rights.

```env
TWELVE_DATA_API_KEY=...
```

MarketBridge v1 does not require it to run the flagship demo.

### FRED

Optional macro context such as policy rates/yields. Requires a free API key.

```env
FRED_API_KEY=...
```

### CoinGecko Demo

Optional crypto overview. Do not mix its crypto prices into equity-perp Market Truth.

```env
COINGECKO_API_KEY=...
```

### Yahoo/yfinance

Legacy research fallback only. It is disabled by default:

```env
MARKETBRIDGE_DISABLE_RESEARCH_FEED=1
```

It can never become risk/reference eligible.

## Explicitly removed from v1

### Databento

The free-first hackathon product does not require or advertise Databento. Its Python dependency, import workflow and environment key are removed from the v1 deployment path.

## Why this design is stronger

A provider-agnostic system is more credible than a demo that works only because one paid data vendor is hardcoded everywhere. The venue can later connect licensed institutional feeds through the same normalized provider contract without changing the risk gate.
