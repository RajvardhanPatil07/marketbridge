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

## What changed in v0.2

### ⚡ Lower-latency streaming

- Alpaca WebSocket adapter for live venue-labelled stock trades.
- Optional Hyperliquid active-asset-context observer.
- WebSocket-first browser transport with SSE fallback.
- The old fixed 100 ms SSE polling loop has been removed.
- The engine wakes subscribers when a new decision exists.
- Database/file audit writes remain outside the decision timer.
- Browser updates are coalesced to avoid unnecessary React renders.

### 🧠 Better price-quality logic

- Provider family and venue family are tracked separately.
- Two venues delivered through one provider are no longer treated as fully independent infrastructure.
- Direct multi-venue consensus remains the highest-trust reference.
- A QQQ factor fallback can emit an explicitly labelled `ESTIMATED` reference after a stock has a trusted anchor.
- The fallback is intentionally conservative and **is not presented as a trained production model**.
- Confidence band, confidence score, risk state, maximum leverage and maximum notional multiplier are returned with each decision.

### 🛡️ Security improvements

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

The Live page uses a dense market-information layout inspired by financial market dashboards such as CoinMarketCap, while keeping MarketBridge's own visual identity.

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
- Per-asset reference/mark/band chart.
- Responsive mobile market cards.

---

## Architecture

```text
 Alpaca WS             Optional Hyperliquid WS          Research feed
     │                           │                           │
     └──────────────┬────────────┴──────────────┬────────────┘
                    ▼                           ▼
              Normalization              Provider health
                    │
                    ▼
          In-memory evidence state
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
      consensus   confidence  factor fallback
          └─────────┼─────────┘
                    ▼
                Risk policy
                    │
          ┌─────────┴────────────┐
          ▼                      ▼
  WebSocket / SSE           async audit log
          │
          ▼
      Next.js UI
```

The hot decision path does **not** wait for a database or JSONL write.

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

## Live data

### Alpaca

Set backend-only credentials:

```bash
export ALPACA_API_KEY="..."
export ALPACA_SECRET_KEY="..."
export ALPACA_FEED="iex"
```

`iex` is the safe default for a normal free account. Use `sip`, `boats`, or `overnight` only when your account is entitled to that feed.

### Hyperliquid

MarketBridge does not hard-code HIP-3 coin names. Configure the exact deployed market identifiers:

```bash
export HYPERLIQUID_COIN_MAP='{"NVDA":"xyz:NVDA","TSLA":"xyz:TSLA"}'
```

Hyperliquid/Mochatrade marks are treated as **venue marks to compare against**. They are not used as independent evidence to prove themselves correct.

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
```

Backend tests cover the deterministic guard, API validation, research-feed exclusion and shadow-oracle behavior. The project also includes synthetic incident/replay fixtures so the demo remains usable when live market connectivity is unavailable.

Important: the microsecond in-process benchmark is **not** end-to-end market latency. The UI reports source-event age separately from internal decision latency.

---

## API

| Route | Purpose |
|---|---|
| `GET /health` | Service status |
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Pipeline readiness |
| `GET /health/feeds` | Provider health |
| `GET /v1/shadow/snapshot` | Latest market/risk snapshot |
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

MarketBridge v0.2 is a strong hackathon/pilot architecture, not a production exchange oracle.

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
