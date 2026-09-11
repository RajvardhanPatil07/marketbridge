# MarketBridge demo integration contract

Scope: six deterministic synthetic scenarios for NVDA and TSLA, plus a sourced historical incident reconstruction. Scenario inputs and outcomes are synthetic; the incident observations are published historical values and its MarketBridge decision is counterfactual. No live-data or empirical stock-performance claims.

Backend Python package lives in `backend/marketbridge`. FastAPI entrypoint is `marketbridge.api:app` (parent owns api.py). Core agent owns models.py, engine.py, scenarios.py, evaluation.py, fixtures and backend unit tests. Frontend agent owns apps/web entirely. Parent owns root packaging, API integration, docs, browser checks and deployment. Do not overwrite others' files.

Core exported functions: `list_scenarios() -> list[dict]`, `run_scenario(scenario_id: str, symbol: str) -> dict`, `evaluate_all() -> dict`, `incident_reconstruction() -> dict`. Unknown scenario or symbol raises ValueError. Outputs JSON-serializable finite values. Engine generates all steps sequentially, without future inputs.

GET /v1/demo/scenarios returns {scenarios: Scenario[], symbols: [{symbol:'NVDA',name:'NVIDIA',base_price:182.5},{symbol:'TSLA',name:'Tesla',base_price:346.8}], data_mode:'SYNTHETIC_TEST'}.

Scenario = {id,title,description,expected_outcome,duration_seconds,event_count,symbols:['NVDA','TSLA']}. IDs: normal, bad-print, genuine-move, dropout, reopening, single-source. Use 61 steps at seconds 0..60, with main event around second 24 and corroboration around 27; duration_seconds=60. Actual event_count defined from fixtures.

GET /v1/demo/scenarios/{id}?symbol=NVDA returns Trace = {scenario:Scenario,symbol,initial_price,model_version,data_mode:'SYNTHETIC_TEST',steps:Step[],assumptions:string[],metrics:Metrics}.

Step = {index:number,seconds:number,timestamp:string,reference:number|null,last_valid:number|null,comparator:number,factor:number,baseline:number,lower:number|null,upper:number|null,quality:'QUALIFIED'|'CAUTION'|'INSUFFICIENT_EVIDENCE'|'RECOVERING',assessment:'ACCEPT'|'REJECT'|'QUARANTINE'|'NONE',reasons:string[],source_count:number,age_seconds:number,sources:Source[],simulation:Simulation}.

Source = {id:string,name:string,family:string,price:number|null,event_time:string|null,age_seconds:number,status:'FRESH'|'STALE'|'QUARANTINED'|'MISSING',weight:number}. Every source clearly synthetic by trace mode and names/assumptions; names may indicate simulated exchange/source role. An IEX-like synthetic source may be named 'IEX · simulated'. No purported actual feed access.

Simulation = {equity:number|null,baseline_equity:number|null,new_exposure_allowed:boolean,exposure_limit:number,valuation_status:'RESOLVED'|'UNRESOLVED',reference_liquidated:boolean,baseline_liquidated:boolean}. Fixed long position, explicitly stated initial equity/units/maintenance/fees, independent common synthetic outcome for final ex-post scoring. Unavailable reference yields unresolved current valuation and blocks exposure, not zero loss. Preserve exited equity after liquidation; do not repeatedly liquidate/reopen each step.

Metrics = {availability_pct:number,quarantined_count:number,accepted_count:number,recovery_seconds:number|null,mae_bps:number|null,baseline_mae_bps:number|null,final_equity:number|null,baseline_final_equity:number|null,policy_comparison:PolicyComparison[],checks:{name:string,passed:boolean,detail:string}[]}. Each policy comparison reports availability, MAE, worst error, and largest step update against identical synthetic observations and truth. MAE is explicitly only against synthetic fixture truth. Counterfactuals have identical position/fee/fill assumptions and common synthetic outcome. No savings claims.

GET /v1/demo/evaluation returns {data_mode:'SYNTHETIC_TEST',evaluation_kind:'synthetic_functional_tests',model_version:string,summary:{total:number,passed:number,failed:number},cases:[{scenario_id,symbol,metrics:Metrics}],limitations:string[],research:[{title,url,application}]}.

GET /v1/operator/decision/{id}?symbol=NVDA&second=24 returns the exact trace-derived advisory fields: symbol, reference, status, independent_source_families, new_exposure_allowed, advisory_exposure_multiplier and reasons. It does not place orders or write an oracle.

GET /v1/incidents/sk-hynix-july-2026 returns `data_mode:'HISTORICAL_RECONSTRUCTION'`, 26 published price points, incident facts with source URLs, a `COUNTERFACTUAL_ADVISORY` decision, and explicit evidence limitations.

GET /v1/live/snapshot returns a 15-second cached `LIVE_RESEARCH` snapshot for NVDA, TSLA and QQQ. Each observation contains the Yahoo price, original event timestamp, event age, one-minute chart points, source family and an advisory decision. `refresh=true` forces a provider request. Provider failure is represented as `DEGRADED` or `UNAVAILABLE` data so the synthetic safety lab remains usable. A Yahoo-only observation never becomes an oracle reference and never permits new exposure.

The low-latency seam is `ShadowOracle.ingest(NormalizedObservation) -> decision`. Provider I/O is outside that interface. Yahoo is an ineligible research adapter; Alpaca trade messages are labeled by original exchange code; Mochatrade marks are stored separately from underlying evidence. Ordinary references require two fresh venue families agreeing within 75 bps. Moves beyond 500 bps from the last valid reference require three. Decision latency is measured before asynchronous JSONL audit persistence.

GET /v1/shadow/snapshot returns cached provider states, current decisions, up to 40 recent decisions and p50/p95 in-process latency. GET /v1/shadow/stream emits a snapshot only when the generation changes and reconnects every 30 seconds. POST /v1/shadow/refresh forces Yahoo provider work without changing execution state. POST /v1/integrations/mochatrade/market accepts `{symbol,mark_price,event_time}` and requires `X-MarketBridge-Key` when `MOCHATRADE_INGEST_KEY` is configured.

UI: fetch same-origin API. Read-only client playback cursor (default begins index0 paused), scenario/symbol controls, play/pause/reset/step/scrub/speed, Safety lab/Live research/Real incident/Evaluation/Methodology tabs, working downloads of trace JSON, copyable operator output, and keyboard/phone-friendly behavior. The live view polls every 15 seconds, supports manual refresh and instrument selection, and displays provider, session, event-age and execution-eligibility states. TradingView Lightweight Charts renders replay, historical and Yahoo research graphs with visible attribution. Catch loading/error states. Persistent evidence-mode labels; range label 'Model range · uncalibrated'. Do not draw future points in main price trace except optional empty axis. No fake nav buttons or fabricated performance counts. Derive stats from current data.

Frontend must export static output with Next.js output:'export'; no server-only routes or runtime next/font Google dependency. System sans stack or locally bundled font. Parent serves apps/web/out via FastAPI. Dev allowed next.config dev proxy only when not exporting, or use NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 with API allowing localhost3000. Production uses same origin.
