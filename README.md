<div align="center">

# 🌉 MarketBridge

### Real-time mark integrity for 24/7 US-stock perpetuals

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)
![Railway](https://img.shields.io/badge/Railway-ready-7B2CF5?logo=railway&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-ready-black?logo=vercel)
![Security](https://img.shields.io/badge/security-HMAC%20%2B%20replay%20protection-16c784)
![Tests](https://img.shields.io/badge/backend-tests-passing-16c784)

**MarketBridge sits between market data and a risk engine. It checks whether a venue mark is supported by independent evidence, estimates a conservative reference when direct evidence becomes weak, measures uncertainty, and converts that uncertainty into an advisory risk limit.**

</div>

---

## Why this exists

US stocks do not have the same price-discovery schedule as a 24/7 perpetual market. During thin overnight periods, weekends, outages, or bad prints, a leveraged market can see a mark that is stale, isolated, or difficult to verify.

MarketBridge does not blindly accept the newest number. It asks:

1. **Where did this price come from?**
2. **Is the source fresh?**
3. **Do independent venues agree?**
4. **Are all venues coming through the same provider?**
5. **How far is the trading venue mark from the independent reference?**
6. **How much leverage should be allowed while evidence is weak?**

The result is an easy-to-read operator decision such as:

```text
NVDA
MarketBridge reference     $184.51
Venue mark                 $184.76
Divergence                   13.5 bps
Confidence                   94%
Risk state                   NORMAL
Recommended max leverage     20x
```

If evidence becomes weak, MarketBridge can return `GUARDED`, `RESTRICTED`, or `HALTED` instead of pretending a low-confidence price is certain.

---

## What changed in v0.3

### ⚡ Lower-latency streaming

- Alpaca WebSocket adapter for live venue-labelled stock trades.
- Databento EQUS.MINI MBP-1 live adapter and entitlement-gated historical importer.
- Optional Hyperliquid active-asset-context observer.
- WebSocket-first browser transport with SSE fallback.
- The old fixed 100 ms SSE polling loop has been removed.
- The engine wakes subscribers when a new decision exists.
- JSONL plus DuckDB audit writes remain outside the decision timer, with Parquet export for research.
- Browser updates are coalesced to avoid unnecessary React renders.

### 🧠 AI-assisted fair value and anomaly detection

- Provider family and venue family are tracked separately.
- Two venues delivered through one provider are no longer treated as fully independent infrastructure.
- Direct multi-venue consensus remains the highest-trust reference and **always outranks AI**.
- A learned fair-value layer compares Ridge Regression with Gradient-Boosted Regression Stumps per stock and automatically selects the lower-validation-error model.
- The model uses QQQ, SPY and SOXX factor moves plus evidence quality and time-since-anchor features.
- A separate learned anomaly classifier scores the venue mark against the independent MarketBridge reference.
- AI can provide an explicitly labelled `ESTIMATED` fallback and confidence band, but it never creates a trusted anchor.
- AI can only tighten risk after non-synthetic calibration; it can never loosen deterministic controls.
- The checked-in model bundle is deliberately labelled `SYNTHETIC_CALIBRATION_DEMO`. Its metrics are functional calibration, **not live-market performance**.
- Confidence band, confidence score, risk state, maximum leverage and maximum notional multiplier are returned with each decision.

### 🛡️ Security improvements

- Every issued decision includes a `marketbridge-passport-v1` receipt with sealed claims, per-observation evidence hashes and a per-symbol predecessor link.
- Passport content and chain hashes use canonical JSON plus SHA-256, making later claim changes detectable without retaining or redistributing raw provider payloads.
- HMAC-SHA256 signed Mochatrade integration requests.
- Timestamp-expiry checks.
- Nonce replay protection.
- Request rate limiting.
- Strict symbol/price/time validation.
- WebSocket origin checks.
- Configurable CORS allowlist.
- CSP, HSTS, `nosniff`, frame protection and permissions headers.
- No wallet keys, order execution, liquidation endpoint or custody logic.

### 📊 New live frontend

The Next.js 16 frontend is a route-based financial terminal. It uses React 19, TypeScript, Lucide icons, and TradingView Lightweight Charts, with a shared WebSocket-first market-data context and SSE fallback. The build remains a static export that FastAPI serves same-origin in production.

Main product routes:

| Route | Purpose |
|---|---|
| `/` | Concise product entry and live market monitor. |
| `/markets` | Market rankings, movement, reference quality, and category navigation. |
| `/markets/stocks`, `/markets/crypto`, `/markets/etfs` | Asset-class views; unavailable providers are shown explicitly instead of populated with sample listings. |
| `/asset/[symbol]` | Price chart, supported market metrics, deterministic risk explanation, and compact AI insight. |
| `/screener` | Filters over the fields currently provided by the backend. |
| `/terminal` | Watchlist, primary chart, advisory paper order ticket, positions boundary, and risk monitor. |
| `/portfolio` | Account/positions shell that stays empty until a server-side paper brokerage ledger is connected. |
| `/news` | Ticker-linked Marketaux financial news, fetched through the backend so its token stays private. |
| `/watchlist` | Device-local supported-asset watchlist. |
| `/insights` | Learned-model signal, provenance, and links into research workflows. |
| `/lab` | Existing scenario replay, incident reconstruction, live evidence console, and evaluation tools. |

The terminal UI uses a restrained dark design system with thin separators, compact controls, tabular numerals, and green/red reserved for financial movement. Large tables scroll horizontally on mobile; secondary columns and panes collapse before core price, chart, risk, and action information.

Market data flows through the security boundary below:

```text
Next.js UI → MarketBridge REST/WebSocket/SSE API → server-side providers
```

The browser never connects with Alpaca, Databento, or Mochatrade secrets. `NEXT_PUBLIC_API_BASE` may contain only the public MarketBridge API origin for split local development; provider credentials use backend-only variables documented below.

Marketaux news uses the same boundary. Set `MARKETAUX_API_TOKEN` only in the backend environment; `/v1/news` returns a normalized three-article feed cached for five minutes to protect the free request allowance.

The live surfaces show:

It now shows:

- System health.
- Feed health.
- p50/p95/p99 decision latency.
- MarketBridge reference vs venue mark.
- Divergence in basis points.
- Confidence bars.
- Fair-value band.
- Risk state.
- Recommended leverage.
- Provider/venue evidence counts.
- Source evidence details.
- Interactive evidence-to-reference-to-risk lineage graph.
- Uncertainty thermostat that makes confidence-driven restriction visible.
- Hash-chained Mark Passport receipts.
- Per-asset reference/mark/band chart.
- Responsive mobile market cards.

---

## Architecture

```text
 Alpaca WS       Databento EQUS.MINI      Hyperliquid mark       Research feed
     │                    │                       │                    │
     └──────────────┬─────┴───────────────────────┴──────────────┬─────┘
                    ▼                           ▼
              Normalization              Provider health
                    │
                    ▼
             Evidence firewall
                    │
          ┌─────────┴───────────────┐
          ▼                         ▼
  Direct consensus         Learned fair value
   (highest trust)          (ESTIMATED only)
          │                         │
          └────────────┬────────────┘
                       ▼
                Confidence band
                       │
            Venue mark comparison
                       │
                 ML anomaly score
                       │
                       ▼
             Deterministic risk policy
             (AI may only tighten)
                       │
             ┌─────────┴──────────┐
             ▼                    ▼
     WebSocket / SSE         async audit log
             │
             ▼
         Next.js UI
```

The hot decision path does **not** wait for a database or JSONL write.

The synthetic Chaos Lab contains ten deterministic regimes: normal, poisoned print, corroborated
repricing, feed dropout, verified reopening, correlated single-source failure, future clock skew,
crossed market, replayed stale tick, and overnight source collapse. It reports detection time,
bad-mark exposure and false-freeze seconds alongside availability and error.

---

## Decision states

| Reference status | Meaning |
|---|---|
| `QUALIFIED` | Fresh direct venues agree within configured limits. |
| `ESTIMATED` | Direct evidence is insufficient, but a conservative factor estimate is available. |
| `INSUFFICIENT_EVIDENCE` | MarketBridge refuses to manufacture a reference. |

| Risk state | Prototype action |
|---|---|
| `NORMAL` | Normal advisory leverage limit. |
| `GUARDED` | Lower leverage/notional while uncertainty rises. |
| `RESTRICTED` | Strong risk reduction. |
| `HALTED` | Do not open new exposure in this prototype policy. |

These thresholds are **prototype advisory policy**, not Mochatrade's production risk rules.

---

## 🤖 AI / ML model

MarketBridge intentionally uses ML **inside** the pricing/risk stack rather than adding an LLM chatbot.

The learned fair-value model predicts the stock return from the last trusted anchor using factor moves and evidence-quality features. The trainer evaluates **Ridge Regression vs Gradient-Boosted Regression Stumps** for each symbol and exports the best validation model to a small JSON bundle. A separate logistic classifier estimates the probability that the trading venue mark is anomalous.

The safety boundary is strict:

```text
Direct independent consensus > learned estimate > no reference
```

A learned estimate is always `ESTIMATED`, never `QUALIFIED`. A model prediction cannot turn itself into the next trusted anchor, cannot create source independence, and cannot loosen a deterministic risk restriction.

### Checked-in model provenance

The default `models/marketbridge-ai-v0.3.json` is trained on deterministic synthetic calibration regimes so the full system works offline. `reports/ml-evaluation.json` therefore **must not be presented as historical market performance**.

To create a real research backtest before the hackathon:

```bash
make build-ml-dataset
uv run python scripts/train_ai_models.py \
  --csv data/ml_training.csv \
  --data-mode HISTORICAL_RESEARCH
```

Then use the new held-out metrics from `reports/ml-evaluation.json`. See [`docs/AI_MODEL.md`](docs/AI_MODEL.md) for the model design and claim boundary.

---

## Live data

### Alpaca

Set backend-only credentials:

```bash
export ALPACA_API_KEY="..."
export ALPACA_SECRET_KEY="..."
export ALPACA_FEED="sip"
```

`iex` remains useful for free-account development, but it contains only one exchange and therefore cannot satisfy MarketBridge's two-venue qualification rule by itself. Use `sip` only when the account is entitled to current SIP data. The adapter now waits for explicit authentication and subscription acknowledgements, labels non-multi-venue feeds `LIMITED`, rejects odd-lot (`I`) trades by default, deduplicates and orders trades per venue, and rejects extreme trades against a fresh NBBO midpoint.

Validate configuration without exposing credentials:

```bash
make live-check
```

The command exits `0` only when configuration is valid and the configured Alpaca feed can produce multi-venue evidence. Enable `MARKETBRIDGE_REQUIRE_LIVE_DATA=1` on the production backend to fail startup/readiness when that condition is not met. Keep it disabled for the offline safety-lab demo.

### Databento

Databento is an optional independent live/history source:

```bash
export DATABENTO_API_KEY="..."
```

The live adapter subscribes to `EQUS.MINI` `mbp-1`. Because that dataset is consolidated,
MarketBridge deliberately counts it as one provider/venue witness—not as several exchanges.
Access is subscription/entitlement gated. Historical data can be downloaded without silently
substituting demo data:

```bash
uv run python scripts/import_databento.py \
  --symbols NVDA TSLA --start 2026-08-01 --end 2026-08-02 \
  --output data/databento/equs-mini.parquet
```

### Hyperliquid

MarketBridge does not hard-code HIP-3 coin names. Configure the exact deployed market identifiers:

```bash
export HYPERLIQUID_COIN_MAP='{"NVDA":"xyz:NVDA","TSLA":"xyz:TSLA"}'
```

Hyperliquid/Mochatrade marks are treated as **venue marks to compare against**. They are not used as independent evidence to prove themselves correct.
Venue marks become `STALE` after 30 seconds by default and are then excluded from divergence and anomaly calculations. Override with `MARKETBRIDGE_VENUE_MARK_TTL_SECONDS` if the venue contract requires a different heartbeat.

### Yahoo Finance

Yahoo/yfinance remains available as a research/display feed. It is **not oracle eligible**.

---

## Local setup

Requirements:

- Python 3.12+
- Node.js 22+
- `uv`
- `make`

```bash
uv sync --frozen
npm --prefix apps/web ci
make demo
```

Open:

```text
http://localhost:8000
```

For separate frontend/backend development:

```bash
# terminal 1
make serve

# terminal 2
make dev
```

---

## Verification

```bash
make verify
make evaluate
make replay
make benchmark-shadow
make live-check
make e2e
make train-ai
uv run python scripts/export_evidence.py
# optional, needs internet for Yahoo research history:
make build-ml-dataset
```

Backend tests cover deterministic guards, API validation, research-feed exclusion, learned fair-value fallback, AI provenance, anomaly scoring, tamper-evident mark-passport chaining, DuckDB/Parquet persistence and Hypothesis-generated safety invariants. Prometheus metrics are exposed at `/metrics`. The project also includes synthetic incident/replay fixtures so the demo remains usable when live market connectivity is unavailable.

Important: the microsecond in-process benchmark is **not** end-to-end market latency. The UI reports source-event age separately from internal decision latency.

---

## API

| Route | Purpose |
|---|---|
| `GET /health` | Service status |
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Process + strict live-data readiness |
| `GET /health/feeds` | Provider freshness, configuration and market health |
| `GET /metrics` | Prometheus decision, latency, freshness and divergence metrics |
| `GET /v1/shadow/snapshot` | Latest market/risk snapshot |
| `GET /v1/ml/status` | Loaded AI model provenance and safety boundary |
| `GET /v1/ml/evaluation` | Latest offline ML evaluation report |
| `GET /v1/shadow/stream` | Event-driven SSE fallback |
| `WS /v1/shadow/ws` | Primary live browser stream |
| `POST /v1/shadow/refresh` | Refresh research observations |
| `POST /v1/integrations/mochatrade/market` | Advisory venue-mark ingestion |
| `GET /v1/demo/scenarios` | Synthetic safety scenarios |
| `GET /v1/demo/evaluation` | Synthetic functional evaluation |
| `GET /v1/incidents/sk-hynix-july-2026` | Historical reconstruction |

---

## Signed Mochatrade requests

Preferred production/pilot mode:

```bash
export MOCHATRADE_HMAC_SECRET="a-long-random-secret"
```

For every request create:

```text
timestamp = unix time
nonce     = unique random value
signature = HMAC_SHA256(secret, timestamp + "." + nonce + "." + raw_json_body)
```

Send:

```text
X-MarketBridge-Timestamp
X-MarketBridge-Nonce
X-MarketBridge-Signature
```

MarketBridge rejects invalid signatures, expired requests and reused nonces.

A backward-compatible `MOCHATRADE_INGEST_KEY` mode is kept for simple local/pilot testing.

---

## Railway deployment

The repository contains `Dockerfile` and `railway.toml`.

Recommended split:

- **Railway:** FastAPI, live provider connections and risk engine.
- **Vercel:** Next.js frontend if you want a separate global frontend.

For the simplest hackathon deployment, the Railway Docker image can serve both the built frontend and FastAPI API.

```bash
railway up
```

Set secrets in Railway variables, not in Git.

---

## Vercel frontend

For a split deployment, set the frontend's public API base to your Railway backend:

```text
NEXT_PUBLIC_API_BASE=https://your-marketbridge-api.up.railway.app
```

Also configure the backend:

```text
MARKETBRIDGE_ALLOWED_ORIGINS=https://your-marketbridge.vercel.app
```

Do not expose Alpaca or HMAC secrets as `NEXT_PUBLIC_*` variables.

---

## Honest scope

MarketBridge v0.3 is a strong hackathon/pilot architecture, not a production exchange oracle.

It does **not** claim:

- a trained Ridge model when no real training dataset was supplied;
- guaranteed Saturday direct-equity price discovery;
- licensed SIP/BOATS access without provider entitlement;
- real customer savings from synthetic evaluation;
- permission to change Mochatrade's production liquidation engine;
- production-ready multi-region consensus.

Those boundaries are intentional. A trustworthy risk system should say what it knows and what it does not know.

---

## Project structure

```text
backend/marketbridge/
  api.py           FastAPI, WebSocket/SSE and integration endpoints
  shadow.py        live evidence, reference and risk engine
  security.py      HMAC, replay protection and rate limiting
  engine.py        deterministic synthetic safety engine
  live.py          research-only market observations
  evidence_store.py DuckDB and Parquet analytical evidence storage
  metrics.py       bounded-cardinality Prometheus instrumentation

apps/web/src/
  components/      live market UI, incident lab and replay views
  styles/          responsive dashboard styles

fixtures/          synthetic scenario event streams
tests/             backend/API tests
docs/              demo and integration notes
```

---

## Security

Read [`SECURITY.md`](SECURITY.md) before deployment.

The original shared archive contained a local Vercel credential file. This cleaned project deliberately excludes it. Rotate any credential that may have been shared previously.

---

<div align="center">

**MarketBridge — strong evidence when possible, safer risk when certainty disappears.**

</div>
