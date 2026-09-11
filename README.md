<div align="center">

# 🌉 MarketBridge v1

### Market Truth → Portfolio Risk → Safe Action → Verifiable Proof

**US stocks sleep. Equity perpetuals don’t.**

**Verify the market before leverage acts on it.**

[Live Demo](https://marketbridge-production-d284.up.railway.app/) · [Health](https://marketbridge-production-d284.up.railway.app/health) · [Proof + War Room](https://marketbridge-production-d284.up.railway.app/demo/) · [Historical proof](./docs/PROOF.md) · [Architecture](./docs/ARCHITECTURE.md) · [Threat model](./docs/THREAT_MODEL.md) · [Mochatrade integration](./docs/MOCHATRADE_INTEGRATION.md)

</div>

![MarketBridge architecture](./docs/media/architecture.svg)

---

## Positioning in one glance

| System | Primary question |
|---|---|
| Trading AI / agent terminal | Where might price go? |
| Fraud / trust engine | Can we trust the user or activity? |
| Margin engine | How much leverage can the account survive? |
| **MarketBridge** | **Can we trust the market price that leverage depends on?** |

## What MarketBridge does

A 24/7 equity perpetual can keep trading when the underlying US stock has thin, stale, closed-session, or conflicting price discovery. MarketBridge sits beside the venue and asks a simple question before new leverage is allowed:

> **Does this market price deserve enough trust for this order?**

The safety path is intentionally small:

```text
free/live market evidence ──┐
                            ├──> Market Truth ──┐
venue mark / perp context ──┘                   │
                                                ├──> Order Risk Gate
account exposure + order intent ────────────────┘          │
                                                           ├── ALLOW
                                                           ├── CAP_LEVERAGE
                                                           ├── REVIEW
                                                           └── BLOCK_NEW_RISK
                                                                    │
                                                                    ▼
                                                             Safety Passport
                                                                    │
                                                                    ▼
                                                             deterministic replay
```

Valid `REDUCE` and `CLOSE` requests remain available when evidence degrades. `OPEN` and `INCREASE` fail closed when Market Truth is not sufficiently qualified.

> **Mochatrade users post rupee margin against a market that can keep price-discovering while they sleep.**

## Proof before the synthetic attack

The `/demo/` judge flow starts with evidence before the controlled War Room:

1. **Historical reconstruction** — published July 2026 SK Hynix / TradeXYZ observations pass through the same deterministic consequence function used by the live risk gate. It is explicitly counterfactual and consumes no future outcome.
2. **Seeded policy regression** — thousands of varied, reproducible market/account/order states exercise the deterministic safety policy. The report shows action distribution, safety-invariant violations, scenario coverage, and measured core/gateway p50/p95/p99 latency. It deliberately does **not** claim classifier precision/recall from self-labelled fixtures.
3. **Portfolio Risk Firewall** — editable account, exposure, symbol, notional and leverage inputs are recomputed through the same RiskGateway; qualified Market Truth can still be capped by concentration, account, or session risk.
4. **Safe Alternative** — capped requests return the maximum permitted leverage and notional instead of a binary no.
5. **Host integration proof** — a reference Mochatrade pre-trade adapter shows how a host binds the short-lived Safety Passport to the exact order.

Proof endpoints:

```text
GET /v1/proof/historical
GET  /v1/proof/benchmark?cases=2000&seed=20260911
GET  /v1/proof/portfolio
POST /v1/proof/portfolio
```

The historical view is `HISTORICAL_RECONSTRUCTION`, not a licensed consolidated feed. The operating suite is `SYNTHETIC_POLICY_REGRESSION`, not a classifier benchmark or historical-market backtest. Its seed is reported so the varied state space is reproducible, and latency values are measured when the endpoint runs rather than hard-coded into this README.

See [proof methodology](./docs/PROOF.md), [threat model](./docs/THREAT_MODEL.md), [Mochatrade integration](./docs/MOCHATRADE_INTEGRATION.md), and the [90-second demo recording script](./docs/DEMO_VIDEO_SCRIPT.md).

---
## The hackathon demo

Open `/demo/` and run the judge flow:

1. **Choose the inputs** — change symbol, order notional, leverage, account equity, existing exposure, attack magnitude and evidence mode.
2. **Normal market** — AUTO uses a genuinely qualified live reference when the configured independent-provider quorum exists; otherwise it uses a clearly labelled synthetic fixture seeded from the current display price.
3. **Poison venue mark** — apply the judge-selected basis-point attack and recompute the order decision.
4. **Prove exit stays open** — the same degraded market still allows a valid close.
5. **Inspect provenance** — evidence cards show provider identity, observed price, event age, eligibility and whether the evidence is live or a synthetic fixture.
6. **Safety Passport + replay** — inspect the decision fingerprint and compare the actual safety decision with a clearly-labelled no-gate counterfactual.
7. **Recover safely** — repeated stable evidence moves through `RECOVERY_PENDING` instead of enabling leverage after one good tick.

The War Room reports `LIVE_DERIVED_DEMO` when a qualified live quorum is actually available and `SYNTHETIC_DEMO` otherwise. Synthetic witnesses use generic fixture names and never impersonate Alpaca, Twelve Data, or another real provider. No trade is submitted and no fake fill/savings claim is made.

## Free-first provider mesh

MarketBridge v1 is provider-agnostic and does not require a paid institutional feed for the public hackathon demo.

| Capability | Provider | v1 role |
|---|---|---|
| Live US equity display/evidence | **Alpaca Basic / IEX** | Free-first underlying-equity stream; IEX remains one witness |
| Perp / venue state | **Hyperliquid** | Venue mark, oracle, mid, funding/OI context; never fed back into independent Market Truth |
| Financial news | **Marketaux** | Cached ticker-linked context only |
| Official company events/facts | **SEC EDGAR** | Primary-source filings and XBRL context; no API key |
| Symbol/reference metadata | **Nasdaq Symbol Directory** | Security master |
| Optional equity cross-check | **Twelve Data** | Context/internal by default; risk-eligible only after explicit `TWELVE_DATA_RISK_ELIGIBLE=1` entitlement opt-in |
| Research fallback | **Yahoo/yfinance** | Legacy research-only, disabled by default, never risk eligible |
| Optional macro context | **FRED** | Context only |
| Optional crypto overview | **CoinGecko Demo** | Display/context only |

**Databento is not part of the v1 free-first product/deployment path.** The paid dependency, environment requirement and import workflow are removed from this branch.

Every provider exposed by `/v1/providers` separates **supported capability**, **configuration**, and **observed runtime health**. A public adapter that has not been probed is reported as `SUPPORTED / NOT_PROBED`, not falsely labelled `READY`.

## Three planes, one boundary

### 1. Market evidence plane

Used to reason about the underlying market. Provenance, event time, receipt time, provider family, venue family, freshness and eligibility remain explicit.

### 2. Venue plane

Hyperliquid/Mochatrade context tells MarketBridge what the trading venue currently believes. It is compared **against** independent Market Truth; it is never allowed to manufacture that truth.

### 3. Intelligence context plane

Marketaux news, SEC filings/fundamentals, FRED and optional research sources help explain events. They return `affects_market_truth=false` and cannot loosen deterministic safety controls.

## New judge-facing routes

| Route | Purpose |
|---|---|
| `/` | v1 product thesis and first-view demo CTA |
| `/demo/` | proof-first judge flow + Market Truth War Room |
| `/providers/` | Free-first capability/provider mesh and trust boundaries |
| `/intelligence/` | Marketaux news + official SEC context, visibly separated from Market Truth |
| `/markets/` | Existing live market monitor |
| `/terminal/` | Existing deeper market/risk workstation |

## API additions

```text
GET  /v1/providers
GET  /v1/intelligence/{symbol}
GET  /v1/proof/historical
GET  /v1/proof/benchmark
GET  /v1/proof/portfolio
POST /v1/proof/portfolio
POST /v1/demo/war-room
POST /v1/demo/war-room/replay
POST /v1/demo/war-room/reset
POST /v1/demo/live-baseline
POST /v1/order/safe-alternative
```

The mature safety APIs remain intact:

```text
POST /v1/integrations/mochatrade/risk-check
GET  /v1/passports/{passport_id}
POST /v1/replay/risk-decision
POST /v1/passports/{passport_id}/outcome
```

## Run locally

Requirements: Python 3.12+, Node 24+, `uv`, npm.

```bash
cp .env.example .env
make setup
make demo
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo/
```

The War Room needs no market-data key because AUTO can fall back to its explicit synthetic fixture. To enable real free-first market display, add Alpaca credentials to the backend `.env`. Provider credentials must never be exposed through `NEXT_PUBLIC_*` variables.

The canonical backend entrypoint is `marketbridge.app:app`. Railway/Docker serves both API and the exported frontend from one process. The Vercel configuration is frontend-only; for a split Vercel frontend, set `NEXT_PUBLIC_API_BASE` to the deployed backend URL at build time.

## Verify

```bash
make verify
make benchmark-risk
make e2e
make live-check
```

CI checks Python lint/tests, TypeScript, frontend unit tests/build, browser flows, synthetic evaluation and deterministic replay.

## Safety / honesty boundary

MarketBridge is a hackathon/pilot advisory architecture, **not** a certified exchange oracle, broker, custody system or liquidation authority.

- No exchange signing key, wallet key or custody key is held.
- No live trade is submitted by the demo.
- AI may tighten but never loosen deterministic controls.
- Learned estimates never become trusted anchors on their own.
- One provider is never presented as independent consensus.
- Multiple vendor labels sharing one upstream are not counted as independent witnesses.
- News, filings, macro and research data do not create Market Truth.
- Unknown entitlement/display rights are treated conservatively.
- Counterfactual replay reports prevented **simulated additional exposure**, not guaranteed savings.

## Attribution and license

Repository attribution is intentionally limited to contributors visible in this project rather than claiming another hackathon team identity:

- `@RajvardhanPatil07`
- `@ritz2607`

Before final submission, ensure the official hackathon registration names exactly match the submission form. See [TEAM.md](./TEAM.md).

Licensed under MIT. See [LICENSE](./LICENSE).

## Deployment economics

The deterministic risk-critical policy path uses **0 LLM calls** and **0 paid API calls inside the policy function**. Hosting and market-data licensing remain deployment/entitlement specific; MarketBridge does not invent a dollar cost without measured inputs.

## Why this is different

Trading AI asks: **Where will price go?**

Fraud systems ask: **Can we trust this user or transaction?**

Traditional margin systems ask: **How much leverage can this account survive?**

MarketBridge asks upstream:

> **Can we trust this market enough for this portfolio to take this leverage — and can we prove why we allowed or denied it?**

That is the product.