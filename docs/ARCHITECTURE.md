# MarketBridge v1 architecture

## Design goal

MarketBridge is a **market safety control plane**, not a generic trading terminal. The v1 branch is optimized for a zero-paid-data hackathon deployment while preserving a clean upgrade path for a venue's licensed feeds.

The central architectural rule is:

> **Providers are adapters. Capabilities, provenance and trust roles are architecture.**

## System shape

```text
                         MARKETBRIDGE v1

        UNDERLYING MARKET                   TRADING VENUE
        Alpaca / IEX                        Hyperliquid
             │                                   │
             ▼                                   ▼
      ┌────────────────────────────────────────────────┐
      │              NORMALIZED EVIDENCE               │
      │ provider family · venue family · event time    │
      │ receipt time · freshness · eligibility · mode  │
      └──────────────────────┬─────────────────────────┘
                             │
                             ▼
                       MARKET TRUTH
                             │
                     venue divergence
                             │
              account exposure + order intent
                             │
                             ▼
                  DETERMINISTIC RISK GATE
                             │
               ALLOW / CAP / REVIEW / BLOCK
                             │
                             ▼
                     SAFETY PASSPORT
                             │
                             ▼
                  DETERMINISTIC REPLAY

        ───────────── CONTEXT PLANE ─────────────

       Marketaux          SEC EDGAR          FRED
          │                  │                 │
          └──────────────► context ◄───────────┘
                             │
                             ▼
                  UI / human explanation

        Context NEVER creates Market Truth.
```

## Free-first live core

### Alpaca

The hackathon environment defaults to `ALPACA_FEED=iex`. That is intentionally treated as a **single venue/witness**, not full-market consensus. The product displays the limitation instead of pretending one feed is independent truth.

Alpaca also backs historical chart/display APIs already implemented under `marketbridge.market_data`.

### Hyperliquid / Mochatrade venue context

The venue adapter observes mark/oracle/mid/BBO/funding/open-interest context when the exact deployed coin mapping is configured. Venue prices are comparison targets, not inputs that are allowed to prove themselves correct.

## Provider registry

`GET /v1/providers` exposes the v1 registry. Each provider declares:

- `capability`
- `source_class`
- `cost_mode`
- `market_truth_authority`
- `risk_eligible`
- `configured`
- runtime status when available

The registry currently contains Alpaca, Hyperliquid, Marketaux, SEC EDGAR, Nasdaq Symbol Directory, optional Twelve Data, legacy Yahoo research fallback, optional FRED and optional CoinGecko.

Databento is intentionally absent from the v1 registry.

## Intelligence context

`GET /v1/intelligence/{symbol}` combines:

1. ticker-linked Marketaux news;
2. SEC EDGAR company metadata;
3. recent official filings;
4. a small set of latest XBRL facts when available.

The response carries `affects_market_truth=false`. The frontend repeats this boundary visually.

## Risk boundary

`RiskGateway` remains the authority for customer consequence. The input split is maintained:

```text
Market Truth   ≠   Customer Consequence
```

The order gate combines immutable Market Truth with account exposure and order intent. A customer's risk never alters the confidence of the market evidence.

Valid `REDUCE`/`CLOSE` paths are preserved during market-evidence degradation. `OPEN`/`INCREASE` fail closed when required direct qualification, freshness, entitlement, independence or recovery conditions are not satisfied.

## Safety Passport and replay

Every consequential risk check receives a short-lived Safety Passport containing order, account, market, evidence, policy and decision claims. Hashing and predecessor links make mutation detectable.

Replay supports:

- current/original deterministic policy parity;
- a clearly-labelled `WITHOUT_SAFETY_GATE` counterfactual;
- `prevented_additional_exposure_usd` rather than invented profit/loss or savings claims.

## War Room

The judge-facing `/demo/` experience calls the v1 synthetic War Room API, which reuses the existing `RiskGateway` instead of implementing decision logic in JavaScript.

```text
NORMAL
  ↓
POISONED_MARK
  ↓
BLOCK_NEW_RISK
  ↓
CLOSE → ALLOW
  ↓
SAFETY PASSPORT
  ↓
WITHOUT-GATE REPLAY
  ↓
RECOVERY_PENDING
  ↓
NORMAL
```

The War Room is always labelled `SYNTHETIC_DEMO`; no live trade is submitted.

## Deployment

One FastAPI process serves the API and statically exported Next.js frontend for the hackathon deployment. Provider credentials remain server-side. The current architecture deliberately avoids Kafka, Kubernetes, a feature store or unnecessary microservices.

Entrypoint:

```text
marketbridge.app:app
```

`marketbridge.app` layers v1 routes onto the mature API without duplicating the existing safety implementation.
