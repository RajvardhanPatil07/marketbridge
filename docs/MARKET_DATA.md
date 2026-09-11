# Market data and provider policy

MarketBridge v1 is **free-first** and conservative about what a provider is allowed to influence.

## Active roles

| Source | Capability | Market Truth role | Default v1 use |
|---|---|---|---|
| Alpaca / IEX | live US equity | one underlying-market witness | enabled when backend credentials exist |
| Hyperliquid | perp/venue context | venue comparison only | enabled when exact coin map is configured |
| Marketaux | financial news | none | context only |
| SEC EDGAR | filings/company facts | none | official context only |
| Nasdaq Symbol Directory | security master | none | symbol/reference metadata |
| Twelve Data | optional equity cross-check | context/internal by default | risk-eligible only with explicit `TWELVE_DATA_RISK_ELIGIBLE=1` after entitlement review |
| Yahoo/yfinance | research fallback | none | disabled by default |
| FRED | macro | none | optional context |
| CoinGecko | crypto overview | none | optional display/context |

## No paid-provider dependency

Databento is not part of the MarketBridge v1 free-first deployment path. The Python dependency, import workflow and environment requirement are removed from the branch.

## Provider independence

MarketBridge counts **provider family** and **venue family** separately.

Two observations are not magically independent because they appear as two rows in an API response. If both observations share one upstream provider/infrastructure family, that concentration remains visible and confidence is reduced accordingly.

For the free hackathon path, Alpaca IEX remains one venue. It can drive a live display and supply one evidence witness, but it cannot satisfy a two-independent-source rule by itself.

## Data classes

### MARKET_EVIDENCE

Potential input to Market Truth after freshness, eligibility, entitlement and independence checks.

### VENUE_EVIDENCE

What the trading venue currently believes: mark/oracle/mid/BBO/funding/open interest. It is compared against Market Truth and never fed back into the independent underlying reference.

### CONTEXT / OFFICIAL_CONTEXT

News, SEC filings, fundamentals and macro information. Useful for human explanation; never a qualified price observation.

### RESEARCH_ONLY

Convenience data that is explicitly barred from safety qualification. Yahoo/yfinance lives here.

## Time semantics

Every accepted market observation keeps source event time and local receipt time separate. Freshness is based on the event being evaluated, not simply whether the connection is alive.

A heartbeat does not refresh an old price.

## Display versus risk eligibility

The UI may display data that the risk engine refuses to trust. This is intentional.

Example:

```text
Alpaca / IEX    LIVE DISPLAY
Market Truth    SINGLE-SOURCE / NOT FULLY QUALIFIED
New leverage    GUARDED OR BLOCKED BY POLICY
```

That is a feature, not an error state.

## Historical charts

The existing Alpaca historical market-data service remains display-only and is isolated from Market Truth qualification. Historical bars can power charting/indicators without silently becoming current execution evidence.

## News

Marketaux is cached server-side for 20 minutes. The browser never receives the API token. Articles are normalized and labelled `NEWS_CONTEXT` with `affects_market_truth=false`.

## SEC EDGAR

The v1 SEC adapter uses public SEC endpoints to provide:

- company identity/CIK;
- recent 8-K, 10-Q, 10-K and related official filings;
- latest available XBRL facts for revenue, net income, assets, cash and diluted EPS when present.

SEC information is authoritative **company context**, not an exchange quote.

## Optional providers

Twelve Data, FRED and CoinGecko are capability adapters, not required dependencies. Their use must follow the actual account tier and intended display/non-display rights. Unknown permission means disabled for that purpose.

## Synthetic evidence

The public adversarial War Room uses explicit `SYNTHETIC_DEMO` evidence so it can demonstrate poisoned marks, exit preservation and recovery deterministically without pretending free APIs provide institutional coverage.
