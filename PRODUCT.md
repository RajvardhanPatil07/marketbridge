# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Market operators, risk teams, quantitative researchers, and technically sophisticated traders evaluating the safety of 24/7 equity-perpetual marks and leverage decisions.

## Product purpose

MarketBridge is a **market safety control plane for 24/7 equity perpetuals**.

Its product question is intentionally narrower than a trading terminal:

> **Does this market price deserve enough trust for new leverage to act on it?**

The system combines independent underlying-market evidence, venue context, customer exposure and order intent to return a short-lived `ALLOW`, `CAP_LEVERAGE`, `REVIEW`, or `BLOCK_NEW_RISK` decision. Every consequential check can carry a replayable Safety Passport.

## Positioning

**US stocks sleep. Equity perpetuals don't.**

MarketBridge verifies the market before leverage acts on it. It is not a trading bot, price-prediction agent, fraud engine, exchange, wallet or custody layer.

The distinctive mechanism is proof-carrying market safety:

- direct evidence outranks learned estimation;
- provider/venue independence is explicit;
- venue marks are comparison targets, not self-validating truth;
- customer exposure changes consequence, not market confidence;
- AI may tighten but never loosen deterministic controls;
- valid reduce/close requests remain available during evidence degradation;
- decisions can be sealed and replayed.

## Hackathon operating scene

The primary judge-facing experience is the **Market Truth War Room** rather than the full terminal.

The flagship sequence is:

```text
NORMAL → POISONED MARK → BLOCK NEW RISK → CLOSE ALLOWED → PASSPORT → REPLAY → RECOVERY
```

The deeper market/terminal routes remain available for technical inspection after the core story lands.

## Free-first provider strategy

The public hackathon build must not require a paid market-data subscription.

- Alpaca Basic/IEX: free-first US equity stream and one market witness.
- Hyperliquid: venue context when exact deployed coin mappings are configured.
- Marketaux: cached financial-news context.
- SEC EDGAR: primary-source company filings/facts.
- Nasdaq Symbol Directory: security-master/reference metadata.
- Twelve Data: optional/internal cross-check by default; it becomes risk-eligible only after explicit `TWELVE_DATA_RISK_ELIGIBLE=1` opt-in following account-rights review.
- Yahoo/yfinance: legacy research-only fallback, disabled by default.
- FRED/CoinGecko: optional context/display integrations.

Databento is not part of the v1 free-first product or deployment story.

## Product planes

### Market evidence

Observations that may contribute to Market Truth after freshness, eligibility, entitlement and independence checks.

### Venue context

The current mark/oracle/mid/BBO/funding/OI reported by the trading venue. It is compared against independent Market Truth.

### Intelligence context

News, filings, company facts and macro context. The interface must visibly state that this information cannot create Market Truth or loosen risk.

## Capabilities and constraints

- FastAPI + Next.js remains the deployment shape.
- Provider secrets stay server-side.
- The public War Room is deterministic `SYNTHETIC_DEMO`; no trade is submitted.
- Live free data can be single-source and therefore not fully qualified; the UI must show that honestly.
- Historical/chart data does not automatically become current oracle evidence.
- Counterfactual replay reports prevented **simulated additional exposure**, not guaranteed savings.
- No brokerage order-entry endpoint, exchange signing key, wallet key, custody key or liquidation authority is claimed.
- Learned-model artifacts remain experimental unless separately calibrated and labelled with real evaluation evidence.

## Brand commitments

- Product name: MarketBridge.
- Primary phrase: **Verify the market before leverage acts on it.**
- Hero phrase: **US stocks sleep. Equity perpetuals don't.**
- Visual character: institutional market-infrastructure War Room, not casino/trading-AI slop.
- Dense data must remain calm, legible and provenance-led.
- Green/red is reserved for financial/safety state and paired with text labels.
- Competitor/product references may inspire information architecture, never copied proprietary assets/layouts.

## Success criteria

A judge should understand the product within 15 seconds and be able to watch the complete cause/effect chain within roughly two minutes:

1. independent evidence is healthy;
2. a venue mark becomes implausible relative to Market Truth;
3. new leveraged exposure is blocked;
4. the customer can still close;
5. the decision is provable/replayable;
6. recovery is conservative rather than instant.

## Product principles

1. Market truth before customer consequence.
2. Evidence and provenance before AI narrative.
3. Fail closed for new risk; preserve valid exits.
4. Never manufacture source independence.
5. Never turn context/news into executable price truth.
6. Free-first today, provider-agnostic for licensed production feeds later.
7. One memorable demo is worth more than ten disconnected features.
