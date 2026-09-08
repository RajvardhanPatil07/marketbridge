# MarketBridge

A runnable demonstration of evidence-aware off-hours reference pricing for 24/7 US-stock perpetuals. It combines a deterministic safety lab, a sourced reconstruction of the July 2026 SK Hynix/TradeXYZ incident, an operator-facing advisory payload, and a paper risk simulator for NVDA and TSLA.

The six safety scenarios and their outcomes are synthetic. The incident view reproduces published observations and links its sources; MarketBridge's decision on that incident is explicitly counterfactual. A separate **Live research** view fetches current Yahoo Finance observations through `yfinance` without an API key. It is intentionally not treated as execution-quality or oracle-eligible data, and the deterministic safety lab remains usable without internet access.

## Run locally

Install Python 3.12, Node.js 24, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Make. From the repository root:

```sh
uv sync --frozen
npm --prefix apps/web ci
make demo
```

Open [http://localhost:8000](http://localhost:8000). `make demo` builds the static Next.js frontend and serves it alongside the FastAPI API on port 8000. Stop it with Ctrl+C. Dependency installation needs internet access; the built demo uses its bundled fixtures.

Open **Live research** to inspect the shadow-oracle pipeline. Yahoo bootstrap work runs on a background thread, so it never blocks the decision endpoint. Normalized observations pass through a thread-safe in-memory decision module; decisions are streamed to the browser with server-sent events and appended asynchronously to `artifacts/shadow-decisions.jsonl`. When the US market is closed, prices remain visible with their actual event timestamps and a stale label. No API key or `.env` value is needed for this safe default.

For low-latency, venue-labeled trades, set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` before `make demo`. `ALPACA_FEED` defaults to `iex`; set it to `sip` only when the account is entitled. The adapter reconnects automatically, preserves each trade's original exchange code as its evidence family, and requires two agreeing fresh venue families for an ordinary reference or three for a move larger than 5%. Yahoo remains visible but never counts toward oracle corroboration.

A Mochatrade-compatible shadow-mark adapter accepts signed JSON without placing orders:

```sh
curl -X POST http://localhost:8000/v1/integrations/mochatrade/market \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"NVDA","mark_price":230.25,"event_time":"2026-09-07T12:00:00Z"}'
```

Set `MOCHATRADE_INGEST_KEY` and send it as `X-MarketBridge-Key` outside a local probe. The adapter records the venue mark and computes divergence only when MarketBridge has enough independent underlying evidence.

For separate development servers, run these in two terminals:

```sh
# Terminal 1: API on port 8000
make serve
```

```sh
# Terminal 2: frontend on port 3000, targeting the local API
make dev
```

Open [http://localhost:3000](http://localhost:3000) for development. `make dev` sets `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`; production builds use the same origin as the page. No `.env` file is required. `.env.example` documents the optional settings; the root Makefile does not automatically load it. To change the serving port, use `PORT=8080 make demo`.

## What to demonstrate

Start with **Watch the failure point**: one unsupported print drives the unguarded feed down while MarketBridge abstains, blocks new exposure, and emits a copyable decision payload. Then open **Real incident** for the transaction-linked SK Hynix reconstruction, and **Evaluation** for the same-input comparison against an unguarded feed, last-qualified-price policy, and a 1% bounded-update policy. Use the [90-second demo script](docs/demo-script.md) for a rehearsal.

The engine processes events in receipt order and produces a deterministic trace. The browser controls playback of that trace. It does not receive live prices, and the playback clock is a fixture clock.

The model uses an explicit **unit-beta QQQ factor rule** between accepted stock observations, plus synthetic guard and recovery rules. There is no fitted ridge model in this implementation: no licensed historical training set or provider credentials were supplied. The displayed **Model range · uncalibrated** is a rule-based illustration, not an empirically calibrated confidence or next-open prediction interval.

Two benchmarks have different meanings:

- `Step.baseline` is the QQQ factor-only price path anchored at the scenario's initial stock price.
- `simulation.baseline_equity` values the same paper position against the unguarded primary-feed comparator (`Step.comparator`). It is not a position marked against the QQQ baseline.

Both paper paths use the disclosed fixture assumptions and a common synthetic terminal outcome for final scoring. An unavailable reference creates unresolved current valuation and blocks new simulated exposure. A recorded liquidation remains an exit; the simulator does not silently reopen the position. Fixture MAE and paper equity outcomes are functional demonstrations, not measured stock-market performance or customer savings.

## Verify and export

```sh
make verify
make evaluate
make replay
make benchmark-shadow
SCENARIO=genuine-move SYMBOL=TSLA make replay
```

`make verify` runs Python lint, backend tests, frontend type checking, and a production frontend build. `make evaluate` writes `artifacts/evaluation.json`; default `make replay` writes `artifacts/bad-print-NVDA.json`. `make benchmark-shadow` measures 10,000 in-process decisions and writes `artifacts/shadow-latency.json`; it explicitly excludes provider and browser time. The final replay command writes `artifacts/genuine-move-TSLA.json`. Generated artifacts are ignored by Git.

The GitHub Actions workflow runs the same verification commands and retains synthetic evaluation/replay JSON for seven days. Its presence does not establish that a remote CI run or deployment has passed.

The API exposes:

| Route | Result |
| --- | --- |
| `GET /health` | Service health |
| `GET /v1/demo/scenarios` | Scenarios and supported symbols |
| `GET /v1/demo/scenarios/bad-print?symbol=NVDA` | One complete synthetic trace |
| `GET /v1/demo/evaluation` | Synthetic functional checks and limitations |
| `GET /v1/operator/decision/bad-print?symbol=NVDA&second=24` | Operator advisory derived from the selected trace step |
| `GET /v1/incidents/sk-hynix-july-2026` | Sourced historical reconstruction and counterfactual advisory |
| `GET /v1/live/snapshot` | Cached Yahoo Finance research observations for NVDA, TSLA and QQQ |
| `GET /v1/live/snapshot?refresh=true` | Force a provider refresh |
| `GET /v1/shadow/snapshot` | Non-blocking shadow decisions, providers, latency and recent audit log |
| `GET /v1/shadow/stream` | Server-sent decision updates with sub-250ms delivery target |
| `POST /v1/shadow/refresh` | Manually refresh Yahoo in the background pipeline |
| `POST /v1/integrations/mochatrade/market` | Auth-capable shadow ingestion of a venue mark |

The [integration contract](docs/demo-contract.md) specifies the trace and simulation fields.

## Docker and Railway

Build and run the self-contained image from the repository root:

```sh
docker build -t marketbridge-demo .
docker run --rm -p 8000:8000 marketbridge-demo
```

The multi-stage Dockerfile exports the frontend, installs the locked Python runtime dependencies, and runs FastAPI as a non-root user. One process serves both the site and API. The container honors `PORT`; Railway's checked-in configuration uses `/health` as its health check. This demo requires no database, volume, feed secret, or wallet.

For a deployment through an authorized local [Railway CLI](https://docs.railway.com/cli), first run `make verify`, then select the intended project, environment, and service:

```sh
railway login
railway link
railway status
railway up
railway domain
```

Use an existing demo service when linking. If a new service is needed, create/select it through the CLI before uploading. `railway up` uploads this directory and starts a deployment; `railway domain` exposes the selected service. After deployment, check `/health`, open the returned domain, and rehearse all six scenarios. These are deployment instructions, not a claim that this checkout is already hosted.

The application has no account system or trading actions. The Yahoo adapter is a research-only proof of ingestion, not a licensed production feed. Enterprise authentication, redundant licensed adapters, trained models, calibrated forecasts, exchange-oracle writes, and real execution remain outside this build.

## Vercel

The root `app.py` exposes the same FastAPI application to Vercel. The checked-in `vercel.json` builds the static frontend and prepares its files for hosting beside the API. Deploy from the repository root, using an authorized local [Vercel CLI](https://vercel.com/docs/cli):

```sh
make verify
vercel link --yes --project marketbridge-demo
vercel deploy --yes --project marketbridge-demo
```

The command creates a preview deployment and prints its URL. Open that URL and verify `/health`, all scenarios, and the export controls. Use `vercel curl /health --deployment <deployment-url>` when checking a protected preview through the CLI. The configuration and commands alone do not establish a successful hosted deployment. The GitHub verification workflow does not deploy automatically.

## Research context

[MarketBridge-build-plan.md](MarketBridge-build-plan.md), [MarketBridge-debate-conclusion.md](MarketBridge-debate-conclusion.md), and [research-papers.md](research-papers.md) preserve the research and proposed next stages. Papers motivate evaluation and source-quality choices; they do not validate the fixture model or establish access to any provider's data. Interactive charts use TradingView's open-source Lightweight Charts package with visible attribution.
