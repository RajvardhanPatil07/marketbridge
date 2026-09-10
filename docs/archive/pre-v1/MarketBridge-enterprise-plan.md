# MarketBridge: deployed demo to enterprise advisory pilot

Prepared 6 September 2026. This is an implementation plan, not a report of completed software, achieved accuracy, or production certification.

## 1. Decision and success criteria

Build an **independent off-hours stock reference and source-quality service** for NVDA and TSLA. Explain what evidence supports each estimate, detect questionable observations, admit corroborated genuine repricing, and demonstrate proposed exposure controls in a paper simulator.

The user confirmed a demo-to-pilot delivery path, simulator-only authority, and a **$300/month** combined hosting/data cap. Preserve the 8–11 September demo dates. The initial buyer is a stock-perp operator or market maker evaluating references. The deployed pilot serves one invited design partner; self-service SaaS is deferred.

At assessment start, the workspace contained three planning/research documents and no application implementation or deployment configuration. This plan carries forward their two-stock scope and target separation, and replaces the deployment and delivery assumptions where specified below. The research, platform, and data-access subagents independently reviewed the proposal and current primary sources; the research and platform agents also reviewed this consolidated plan, and their actionable findings were incorporated.

Success has three separate meanings:

| Milestone | Required result |
| --- | --- |
| Deployed demo, 11 September | A working hosted application with deterministic replay, two symbols, source explanations, paired bad-print/genuine-move scenarios, and a reproducible evaluation report. Synthetic data is acceptable when clearly identified. |
| Controlled pilot, approximately six weeks later | An authenticated, monitored advisory service with permitted data use, tested recovery, auditable decisions, a named operating owner, and 28 consecutive days of shadow evidence. Dates move if dependencies or gates fail. |
| Validated model | A specific ticker/target/session model beats its declared baselines on untouched evidence. A completed deployment does not imply this milestone. Unqualified models remain experimental. |

No exchange signing keys, brokerage order submission, real-account margin changes, or liquidation control enter this version. Do not market the pilot as a certified oracle, guaranteed fair value, manipulation-proof system, or contracted high-availability service.

## 2. Research translated into design decisions

These papers motivate methods and tests; none establishes a correct latent Saturday stock price. The implementation choices in the last column are our engineering judgments.

| Primary paper | Supported finding and limitation | Implementation consequence |
| --- | --- | --- |
| Chua, Lai & Wu, **Effective Fair Pricing of International Mutual Funds** (2008), [institutional record](https://ink.library.smu.edu.sg/lkcsb_research/1112/) | Security-level factor adjustments provide a fair-pricing precedent. The application is Japanese mutual-fund holdings, not US-stock perpetuals; the institutional abstract/bibliography was verified, but full-text retrieval failed. | Start with an explainable stock-specific factor estimate; compare it with the last qualified price. Ridge regression is our simplification, not a reproduction of their method. |
| Barclay & Hendershott, **Price Discovery and Trading After Hours** (2003), [author paper](https://faculty.haas.berkeley.edu/hender/after_hours_price_discovery.pdf) | After-hours prices can convey information while being noisier. Its historical Nasdaq sample does not describe current numerical liquidity. | Prefer qualified same-stock evidence; retain spread, source and session. Test premarket and postmarket separately. A large move alone is not proof of corrupt data. |
| Bańbura & Modugno, **Maximum Likelihood Estimation of Factor Models on Data Sets with Arbitrary Pattern of Missing Data** (2010), [ECB paper](https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp1189.pdf) | Factor/state-space methods can account for missing inputs and publication delays. Macroeconomic nowcasting results do not validate weekend stock estimates. | Preserve availability and original timestamps. Missing data must not become fresh zero returns. Introduce a forward-filtered state-space challenger only after the simple baseline works. |
| Gibbs & Candès, **Adaptive Conformal Inference Under Distribution Shift** (2021), [conference paper](https://proceedings.neurips.cc/paper_files/paper/2021/file/0d441de75945e5acbc865406fc9a2559-Paper.pdf) | Adaptive calibration has a long-run coverage result; it is not a guarantee for every ticker, weekend or timestamp. | Resolve forecasts only when their actual target arrives. Report coverage, width and sample count together; do not calibrate a latent Saturday value against Monday's open. |
| Zaffran et al., **Adaptive Conformal Predictions for Time Series** (2022), [conference publication](https://proceedings.mlr.press/v162/zaffran22a.html) | Adaptation choices affect interval efficiency for dependent data; the real application is electricity prices. | Use prior residual quantiles in v1. Compare adaptive methods later with settings fixed before test inspection. |
| Bailey et al., **The Probability of Backtest Overfitting** (2014 working manuscript), [author research-group paper](https://carmamaths.org/resources/jon/backtest2.pdf) | Selecting among many backtests creates selection risk. Its strategy-selection framework does not replace chronological testing. | Record all experiments and tuning trials; keep untouched chronological evaluation blocks. Once inspected, a block cannot qualify the next iteration as an unseen test. |
| Geifman & El-Yaniv, **Selective Classification for Deep Neural Networks** (2017), [conference paper](https://papers.nips.cc/paper_files/paper/2017/file/4a8423d5e91fda00bb7e46540e2b0cf1-Paper.pdf) | Abstention trades answer coverage against error on accepted cases. IID classification guarantees do not transfer to financial regression. | Report error versus availability, including all excluded/abstained periods. A guard that freezes through every difficult event fails evaluation. |

For operations, Dapper motivates propagating identifiers across processing stages, while the SRE Workbook distinguishes API availability from data freshness and correctness. Implement lightweight tracing and separate service/evidence metrics; importing a distributed tracing system does not validate pricing. [Dapper (2010)](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/), [SRE: Implementing SLOs](https://sre.google/workbook/implementing-slos/). The Dataflow paper distinguishes event time from processing time; use this distinction in the receipt-ordered replay contract without introducing a large streaming framework. [Akidau et al., The Dataflow Model (2015)](https://research.google.com/pubs/archive/43864.pdf).

## 3. Data access and permitted use

Use **Alpaca for NVDA/TSLA and QQQ**, **Hyperliquid as the venue comparison**, and **Ondo only as an optional, separately qualified input**. Defer CME/Databento, paid news, additional factors and more tickers.

| Source | v1 role | Required gate and fallback |
| --- | --- | --- |
| Alpaca Basic | Stock/ETF history and live IEX observations | Verify actual accessible dates and feed labels. Basic is a limited venue feed, not consolidated truth. Record its quoted stock-reference quality in evaluation. If access fails, continue with permitted recordings or synthetic fixtures. |
| Alpaca overnight | Optional indicative/delayed observations during the trading week | Preserve indicative quotes versus 15-minute-delayed trades; use the documented historical BOATS feed with its restrictions. Never infer that BOATS history starts in 2016 merely because general equity history does. |
| Hyperliquid | Distinct venue oracle, mark and midpoint displays | Discover the deployer and symbols at runtime. Never feed the target venue's mark/oracle back into the independent estimator. A context response does not establish the underlying equity observation's timestamp. |
| Ondo | Optional off-hours stock-equivalent quote evidence | Enable only after API access, permitted model/advisory use, current asset status, timestamp semantics, spreads, limits and conversion metadata are verified. Exclude the display-price endpoint from the estimator. If unqualified, remain disabled. |

Alpaca currently documents free Basic and $99/month Algo Trader Plus individual Trading API plans. A paid subscription is not evidence of commercial display, storage, redistribution or derived-data permission. Check the applicable account agreement before upgrading or admitting pilot users. [Alpaca plans](https://docs.alpaca.markets/us/docs/about-market-data-api), [overnight semantics](https://docs.alpaca.markets/us/docs/245-trading-for-trading-api).

**Correction to the older notes:** Ondo's dedicated Off-Hours Trading page now lists a broader set, including NVDAon, TSLAon, AAPLon and QQQon; another FAQ still describes six assets. Do not hardcode either count as runtime eligibility. This does not change the two-stock build scope. Off-hours quotes incorporate proprietary pricing and may have wider spreads or be declined. [Off-Hours Trading](https://docs.ondo.finance/ondo-stocks/off-hours-trading), [display-price restriction](https://docs.ondo.finance/api-reference/assets/get-current-price-for-an-asset).

Maintain a versioned **source register**: provider, original source family, instruments, feed mode, permitted purposes/audience, retention terms, timestamp meaning, expected update cadence, freshness policy, corporate-action representation and operational owner. Unknown permission means disabled for that audience. Recorded historical data and derived outputs also need a permitted use; replay is not a licensing exemption.

The public demo defaults to a synthetic fixture set. An entitled internal research deployment and a real-data pilot use separate environments and credentials. If the necessary pilot license exceeds the budget, keep the synthetic deployment and defer external real-data access; a customer-hosted installation requires documented customer entitlements first.

HIP-3 assigns oracle and market-control responsibilities to the deployer. A working comparison API does not authorize MarketBridge to change those controls. [HIP-3 responsibilities](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals), [venue information API](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals).

## 4. Application and data architecture

### Deployment shape

Use a modular Python application with **FastAPI, Pydantic, NumPy/pandas and scikit-learn**, plus a **Next.js/TypeScript static dashboard**. Serve the built dashboard from the API container under the same origin. Separate the feed/estimator worker from the API so client traffic cannot stall ingestion. Run training and historical evaluation offline or in bounded jobs, never inside an HTTP request or the always-on inference loop.

Deploy the API, one live worker and PostgreSQL on **Railway Pro in one US region**. A separate job-runner service executes bounded replay/simulation jobs from a PostgreSQL queue; it never shares the live worker's process. Start it for scheduled demo/pilot sessions, limit it to one global job, 1 GB memory and a 15-minute job timeout, and support cancellation. Expose runner unavailability instead of silently queuing work indefinitely. Include its measured active usage in the hosting budget; historical training stays local. Use an external private S3-compatible bucket, initially Cloudflare R2 Standard, for encrypted exports and permitted Parquet archives; budget storage and request operations explicitly. Keep secrets server-side and the database on private networking. Development uses Docker Compose with the same PostgreSQL schema. Pin supported runtime, dependency and PostgreSQL versions at bootstrap; CI builds an immutable image used in staging and pilot. [R2 pricing and included usage](https://developers.cloudflare.com/r2/pricing/).

Start with three clear repository boundaries: `apps/web` for presentation, `apps/api` for HTTP/auth/stream delivery, and `packages/marketbridge` for adapters, domain events, estimation, quality policy, simulation and offline evaluation. The worker imports the shared Python package. Its pricing engine takes explicit events/configuration/clock values and performs no direct network or database calls.

Do not introduce Kubernetes, Kafka, Redis, a feature store, GPUs or independent per-module services in this pilot. PostgreSQL is the durable source of truth; DuckDB reads exported Parquet for research. Railway's volume-backed database is not an HA cluster. [Railway plans](https://docs.railway.com/pricing/plans), [volume limitations](https://docs.railway.com/volumes/reference).

### Event flow and replay

`adapter → durable input → normalization → pre-update quality check → estimate → uncertainty/advisory state → durable output → API/SSE → dashboard/simulator`

1. Preserve every observation actually consumed by the model, including the provider payload fields used, source timestamp, receipt timestamp, provider sequence/revision when supplied, and a monotonically increasing ingestion sequence. Prefer vendor event IDs for deduplication; otherwise use source/instrument/event-time/payload hashes. A heartbeat is a separate event.
2. Poll grouped stock/ETF snapshots at a configurable one-second cadence within actual account limits; slower feeds retain their own cadence and labels. This v1 assesses sampled observations, not every exchange tick. Store only changed observations plus explicit health transitions; keep the original observation time when the same quote repeats.
3. The worker uses a dedicated PostgreSQL session advisory lock so only one process advances live state. Execute every state-advancing transaction on that same lock-owning connection, never a separate pooled connection. Session loss aborts processing; reacquire the lock and reload the checkpoint before resuming. Each transaction checks the checkpoint version, records outputs, advances the checkpoint and writes the publication event atomically. At-least-once receipt plus unique event identities prevents duplicated effects; do not claim end-to-end exactly-once delivery.
4. Replay follows **recorded receipt/ingestion order**, with an injected clock and recorded timer events. Historical event-time sorting cannot substitute for what the system actually knew. Late/revised inputs are appended; an older event cannot rewind a live source's latest accepted state. Corrections produce new versioned outputs and never overwrite published history.
5. Export permitted events and outputs to partitioned Parquet with checksums and manifests. Replay identifies the dataset, ingestion sequence range, model/configuration hashes, calendar/corporate-action versions and code version. The same frozen input must reproduce the same output sequence in the pinned runtime.
6. Isolate `LIVE`, `DELAYED`, `REPLAY` and `SYNTHETIC_TEST` runs. Scenario injection cannot target the live namespace. A deployment with no qualified live observations does not silently switch to replay and continue claiming to be live.

### Public interfaces and minimum types

Version the API as `/v1`; generate its OpenAPI specification and TypeScript client from Pydantic types. Prices use USD decimal strings at API/storage boundaries; model calculations use log prices with explicitly controlled numeric conversion.

| Interface/type | Contract |
| --- | --- |
| `Observation` | Symbol, instrument/provider/feed/source-family identity, currency/representation, bid/ask or trade, available size, event/receipt times, sequence, source delay/status, corporate-action version, payload hash and data mode. Unknown metadata is explicit. |
| `ReferenceSnapshot` | Symbol, reference/last-valid values, `as_of`, `generated_at`, evidence cutoff/age, quality state and reasons, estimate method, source contributions, uncertainty label, model/config versions, run ID and sequence. Venue mark/oracle remain separate fields. |
| `Forecast` | Target definition, fixed issue cutoff, next-session target time, estimate and interval, calibration version/status, and outcome status. It cannot stand in for a current observation assessment. |
| `ObservationAssessment` | Observation ID, `ACCEPT`, `REJECT` or `QUARANTINE`, reason codes, pre-update reference/version, corroborating event IDs, and any recovery transition. Assess before allowing the candidate to influence its own reference. |
| `GET /v1/reference/{symbol}` | Latest permitted snapshot; returns an explicit unavailable/insufficient state when evidence is absent. Unsupported symbols return 404. |
| `GET /v1/forecast/{symbol}` | Latest forecast for the selected declared cutoff, or explicit unavailability with a reason. |
| `GET /v1/stream` | Server-sent events for one-way snapshot/state updates. Durable sequence IDs support reconnect. If retained history is unavailable, send a reset and current snapshot. This replaces the earlier proposed WebSocket API; no existing consumers need migration. |
| `GET /v1/health/sources`, `GET /v1/evaluations/{run_id}` | Entitled source diagnostics and reproducible evaluation results, including actual samples/exclusions. Source health is authenticated; public liveness exposes no credentials or vendor detail. |
| `POST /v1/replays`, `POST /v1/simulations` | Operator-only bounded jobs with idempotency keys, run IDs and status endpoints. Reusing a key with a different body returns a conflict. Only approved fixture IDs are accepted; no arbitrary URL/file ingestion. |

Every snapshot has `execution_authority="SIMULATOR_ONLY"`. Transport mode and evidence quality are independent: a live connection can carry old evidence. Publish a one-second state heartbeat without inventing a fresh price observation.

Use SSE heartbeats every 15 seconds; clients reconnect with backoff and show disconnection immediately. Each client has a bounded queue; slow clients receive a reset or disconnect rather than growing server memory. The API independently detects an expired worker heartbeat and labels served snapshots stale even if the worker cannot publish its own failure.

## 5. Pricing, uncertainty and observation acceptance

### Small, explainable first model

Use QQQ as the only initial factor. Fit ridge coefficients on synchronized, matched-horizon log returns. Maintain explicit stock and factor anchors and reset both together when qualified direct evidence re-anchors the model. Freeze three benchmark formulas before tuning: carried last regular close, carried last qualified price, and the unit-beta factor estimate `P_anchor × QQQ(t) / QQQ(anchor)`. The fitted ridge coefficient is the challenger, not its own comparator. All methods share information cutoffs and source-availability rules. Do not add unvalidated per-second drift, crypto proxies or an LLM sentiment-to-price adjustment.

Reject malformed/crossed/nonpositive prices and invalid representation metadata. Convert token observations using their actual shares-per-token representation and any relevant USD/stablecoin basis; do not divide already-scaled quotes twice. Unknown conversion metadata disables that input. Treat several resellers of one original quote as one source family.

For fusion, use a robust weighted estimate in log-price space. Derive quality penalties from source age, spread, availability, historical residual error and disagreement. Model weights and a source-family cap are versioned calibration outputs. Losing sources must increase uncertainty rather than automatically reallocating all trust to the last surviving family. Until the candidate passes evaluation, serve the last qualified reference, or the unit-beta baseline when its factor observations meet the declared quality policy, with the applicable experimental/stale label. Store the candidate separately for shadow comparison.

### Distinct targets

- **Qualified observed reference:** an actual acceptable same-stock observation with source and timestamp; a midpoint is not an executable fill.
- **Observable reconstruction:** estimate a stock reference hidden for predefined 15/30/60-minute windows, using only inputs available during the window. Its evaluation applies to that observable session regime.
- **Closure estimate:** estimate current value while the underlying is unavailable. Its range is labeled model uncertainty/calibration pending, not empirically established Saturday coverage.
- **Next-open forecast:** forecast the next regular session's opening print from fixed Friday 20:00 ET and Saturday 12:00 ET cutoffs, scored separately. Use the exchange calendar for holidays. If the official opening print is unavailable, report the target missing; a first-five-minute VWAP can be a separate experiment, never a silent replacement.

Use UTC internally and an exchange calendar in `America/New_York`; convert the UI to the user's timezone. Historical feature eligibility follows receipt/availability time. When historical receipt times are unavailable, disclose the assumed delivery delay and qualify that experiment.

### Guard and recovery state machine

Keep source assessment separate from forecast bands. Large valid changes enter `QUARANTINE` for additional evidence; a high standardized residual is not proof of corruption. The provisional candidate is compared against the state immediately before its arrival.

Use four reference states: `QUALIFIED`, `CAUTION`, `INSUFFICIENT_EVIDENCE`, and `RECOVERING`. Source failures and clock timers can change state even without a new price. In insufficient evidence, the current actionable estimate is null; retain the last defensible estimate separately with its original timestamp.

Automatic jump recovery requires agreement from at least two genuinely independent qualified source families within the versioned tolerance. The only v1 single-reference exception is a verified official primary-exchange opening-auction price for the correct instrument/session and corporate-action version; enable it only if an entitled adapter can actually establish that reference type. An ordinary IEX latest quote/trade is never that exception, during reopening or an already-open session. All evidence must meet its source-specific freshness rules. Repeated observations from one family or elapsed time alone are not corroboration. A genuine large move observed only through IEX therefore remains abstained, with a dedicated test and visible availability cost. When neither route is available, an operator may pause service or annotate the incident but cannot relabel weak evidence as independently validated.

Source freshness windows, disagreement tolerances, anomaly cutoffs, model-error floors and recovery checks live in one versioned policy. Select them only on training/calibration data, record the search and chosen values, and freeze them before evaluation. Missing policy/calibration for a source or session yields an experimental/insufficient state, never an undocumented numeric default. Synthetic demo policies are fixed fixture parameters and carry no calibration claim.

The simulator consumes the exact published state. `CAUTION` lowers permitted new simulated exposure; `INSUFFICIENT_EVIDENCE` blocks new exposure. Every live simulator action also checks worker liveness and evidence validity server-side at action time: expired or unverifiable state blocks new exposure regardless of the last persisted state. Record that decision and its clock/liveness inputs for replay. Use an explicit, versioned margin/funding/fee policy and paper account ledger. Do not retroactively liquidate positions merely because a new-exposure cap tightened. When a valid valuation is unavailable, flag unresolved valuation rather than silently reporting zero bad debt. These controls do not reproduce a venue's liquidation engine unless that separate model is implemented and validated.

For ex-post solvency scoring, mark every policy's remaining positions against the same subsequent qualified independent reference, with identical fees, funding and liquidation-fill assumptions. Record when insolvency becomes observable. If no defensible outcome exists, retain the liability as unresolved; omitting it cannot satisfy a no-worse-bad-debt gate.

## 6. Evaluation and promotion gates

Build one evaluation harness for live recordings, entitled historical replay and synthetic tests. Save dataset manifests, actual symbols/dates, train/tune/calibration/test boundaries, exclusions, candidate counts, seed, code and configuration hashes. Partition chronologically; purge overlapping targets across partitions by at least the longest evaluated horizon. Fit transforms, select parameters and calibrate intervals before opening the test block.

Report MAE/RMSE and median/p95/worst absolute error in basis points, 80/90/95% interval coverage and width, source availability, abstention duration and counts. Use session/weekend block resampling for uncertainty estimates; thousands of ticks from one weekend are not independent weekends. Publish results on all eligible observations and on answered observations, with the missing/abstained cases explicit.

Compare pricing on identical samples with the three frozen benchmarks above and an eligible token-only baseline. Give each observable-target benchmark its own prediction intervals calibrated from prior residuals for that target/regime, so width comparisons have a defined incumbent. Compare the guard with a disclosed EMA/bounded-update baseline; do not claim an exact reproduction of a venue mechanism. Forecasts, reconstruction and incident-inspired simulations have separate result tables.

| Gate | Acceptance rule |
| --- | --- |
| Engine correctness | Duplicate/revised/out-of-order events, stale clocks, restarts and replay do not invent freshness or alter prior published history. Frozen replay outputs match within a declared numerical tolerance in the pinned runtime. |
| Guard tradeoff | Paired equal-magnitude fixtures reject an unsupported bad print and admit a corroborated genuine move. A corroborated stock-specific jump with flat QQQ must recover; an IEX-only jump must abstain. Detection/recovery occurs within two processing cycles after the required evidence is ingested. This is a fixture latency test, not a market guarantee. |
| Candidate price promotion | For every advertised ticker/target/regime, the paired session-block 95% confidence interval for MAE improvement over each applicable incumbent baseline is above zero, with no increase in p95 absolute error on the same eligible sample. Otherwise keep the incumbent and publish the negative/uncertain result. |
| Prediction-interval promotion | For an observable target/regime, require at least 30 distinct held-out target blocks, the lower endpoint of the predeclared 95% block-based coverage interval to reach nominal coverage minus five percentage points, and mean width no greater than the incumbent interval at that nominal level. Thirty blocks alone are not sufficient evidence. Failing or inconclusive intervals remain experimental; passing is an internal empirical gate, not proof of conditional coverage. |
| Guard statistical promotion | Use a preregistered suite and disclose false rejections, genuine-move admission delay, lag, availability, unresolved valuations and simulated bad debt. Require anomaly robustness to improve without worse genuine-move recovery or ex-post simulated bad debt at matched availability. Score liabilities against the common independent outcome; unresolved cases cannot pass this comparison. Fewer liquidations alone cannot qualify a policy. |
| Advanced methods | State-space filtering or adaptive conformal intervals enter as shadow challengers behind the existing contracts and must pass the same gates. No complexity upgrade is required to complete the pilot. |

Minimum scenario set: normal session; 15/30/60-minute target dropout; weekend with no independent evidence; cached quote with fresh HTTP receipt; duplicate source family; malformed/crossed quote; isolated large print; corroborated crash; idiosyncratic earnings move; split/token conversion change; DST/holiday reopening; late correction; HTTP 429; vendor disconnect; database loss; worker restart; stale SSE connection; unauthorized replay injection.

Label any SK Hynix scenario **incident-inspired reconstruction with hypothetical MarketBridge outputs** unless full raw inputs and positions are acquired. Do not equate liquidated notional with customer cash losses or claim historical losses were prevented.

## 7. Operator experience, security and reliability

### Dashboard behavior

Provide four views: **Overview**, **Evidence**, **Replay & Simulator**, and **Evaluation**. Overview prioritizes the reference state, evidence age and source quality before the price. Plot the independent reference, uncertainty, venue mark and venue oracle as distinct series; explain unavailable bands. Evidence shows source-family contributions, original timestamps and the reasons for rejected/quarantined observations.

Replay has a visible mode banner, pause/step/speed controls and a synchronized event/decision timeline. Simulator results include policy assumptions, account state and unresolved valuations. Evaluation displays actual date ranges, sample counts, baselines and negative results alongside improvements. Use keyboard-accessible controls, sufficient contrast, textual status labels and a desktop-first layout usable on a phone for monitoring.

### Access and integrity

- Use Google OIDC through Authlib with authorization code + PKCE, state/nonce validation and issuer/audience checks. Match invitations using verified email, then bind membership to issuer/subject. Issue opaque, revocable database-backed sessions with 30-minute idle and 8-hour absolute expiry in Secure/HttpOnly/SameSite=Lax cookies; store OAuth transaction state server-side and build no custom password system. Provide Viewer and Operator roles. [Authlib integration documentation](https://docs.authlib.org/en/v1.6.5/client/starlette.html).
- Machine clients initially receive read-only, expiring, scoped opaque API keys stored only as hashes. Derive tenant and symbol permissions server-side. Enforce the same authorization on snapshots, streams, exports and job status; a run ID does not grant access. SSE sessions recheck revocation on each heartbeat.
- Keep pilot-private simulations, runs and access records tenant-scoped with PostgreSQL row-level policies, transaction-scoped tenant context and non-owner application roles without BYPASSRLS. Scope related foreign keys by tenant; migration credentials never serve requests. Source entitlements control access to reference data; do not assume a shared quote is licensed for every tenant. Test with two fixture tenants even though the first pilot has one customer.
- Use same-origin delivery, explicit CORS, CSRF protection for cookie-authenticated writes, payload limits, job concurrency limits and per-key/IP rate limits. Use fixed provider egress destinations; arbitrary replay URLs and file uploads are excluded from v1. Start with one concurrent replay/evaluation job per tenant and a global worker limit.
- Audit model/policy promotions, source enablement, operator actions, key lifecycle and data exports. Record actor, time, reason, before/after versions and trace/run IDs. Append-only database permissions and external checksum manifests improve tamper detection but are not a compliance certification.
- Keep API keys out of browsers, fixtures and logs. Mask payloads in error telemetry, rotate/revoke credentials through a tested runbook, and use separate development/pilot secrets. Dependency and secret scanning are release checks. Remediate exploitable critical/high findings before an external pilot.

These are application requirements, guided by [OWASP REST security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html); a provider's own security certifications do not transfer to MarketBridge.

### Pilot service objectives

| Measure | Initial internal target and measurement |
| --- | --- |
| API availability | 99.5% successful authenticated snapshot probes over rolling 28 days, measured every minute from outside the deployment. An accurately reported insufficient-evidence state can be an API success; outages and 5xx responses cannot. |
| API latency | p95 below 300 ms at the stated pilot test load of 10 snapshot requests/second and 20 concurrent SSE clients. Measure from a US probe; report India-facing latency separately. |
| Processing delay | p95 receipt-to-durable-output below 2 seconds for accepted sampled observations. Track source event age separately; a delayed feed cannot satisfy freshness merely by processing quickly. |
| Worker/client failure | API marks snapshots stale within 5 seconds after the last worker heartbeat; UI marks a stream disconnected after two missed 15-second stream heartbeats. Last-known values keep their original times. |
| Recovery | Measured infrastructure RPO at most 24 hours and RTO at most 4 hours for this advisory pilot, using external backups. This is not zero data loss or an HA guarantee. |
| Evidence quality | Publish source freshness, useful-reference availability, disagreements and abstention by session. Do not count a closed conventional market as a vendor incident, or count a weekend abstention as successful pricing. |

Use structured logs and trace/run IDs across adapter, worker, API and job stages; instrument queue age, adapter errors/429s, event lag, rejected observations, worker heartbeat, SSE reconnects, database capacity, archive/export success and forecast outcome resolution. Keep telemetry bounded and redact licensed raw payloads. Configure a dashboard and one alert channel for the named operators.

Enable daily Railway backups and an encrypted daily PostgreSQL logical export to the separate private bucket. Keep seven daily exports initially; retain archives for 30 days only when the source agreement permits, and audit/model manifests for 90 days. Shorter contractual retention wins. Delete expired data from every controlled copy. Test restore into a fresh environment weekly and after material schema changes. Railway's native restore is confined to the same project/environment and volume destruction can remove its backups, so it cannot be the only recovery copy. [Railway backups](https://docs.railway.com/volumes/backups).

Use a rolling 28-day error budget. Exhaustion freezes feature/model promotions until reliability recovers. Wrong source labels, cross-tenant exposure, corrupted replay or unauthorized publication trigger immediate incident handling regardless of percentage uptime. Rajvardhan owns model decisions; Ritesh owns platform operations, with each as the other's backup. Outside declared staffed hours, automated degradation must remain safe; this pilot does not promise staffed 24/7 response.

## 8. Delivery sequence and ownership

Ownership follows the two-person team in the existing plan. Assignments are implementation defaults, not claims of availability.

| When | Rajvardhan: model/evidence | Ritesh: platform/product | Exit proof |
| --- | --- | --- | --- |
| 8 Sep, Day 1 | Define target contracts, fixtures and baseline; inspect actual history | Bootstrap app/DB, source register, one adapter, recording, static UI and hosted synthetic skeleton | One symbol completes the real pipeline with original timestamps; replay works. Complete access/rights inventory before dependent integrations. |
| 9 Sep, Day 2 | QQQ/ridge candidate; quality state machine; separate forecast/uncertainty outputs | Two symbols, evidence panel, SSE, simulator/replay controls | Isolated print and genuine repricing scenarios both pass. Missing sources produce explicit states. |
| 10 Sep, Day 3 | Chronological evaluator, baseline tables, frozen candidate/policies | Authentication for any restricted deployment; clean startup, failure handling and CI checks | Reproducible report with dates/counts and negative results; no live/replay leakage; hosted walkthrough works. |
| 11 Sep, Day 4 | Freeze model/data; concise findings and limitations | Fix demo regressions; deploy pinned artifact; rehearse offline fallback | Three full dry runs, one including a provider outage. No last-minute scope expansion. |
| Week 1 after demo | Harden as-of joins, revisions, corporate actions and model registry | Durable checkpoint/outbox flow, tenant isolation, API contracts and entitlement enforcement | Contract/replay/security integration tests pass; replace demo shortcuts before partner access. |
| Week 2 | Finalize preregistered evaluation/promotion policies | Backups/restore, staging releases, monitoring, rate/load limits and incident runbooks | First restore and rollback drills pass; begin a frozen 28-day prospective shadow window. |
| Weeks 3–6 | Collect shadow predictions; score resolved targets; investigate lag/abstentions | Monitor cost/SLOs; exercise failures; conduct invited partner workflow review when licensed | 28-day evidence report, passing operational gates, rights confirmation and signed pilot checklist. |

The demo does not need advanced model promotion, full multitenant provisioning or the 28-day reliability record. Features implemented after the demo must be clearly separated from what is demonstrated on 11 September.

During implementation, use bounded subagent work after shared contracts are fixed: one owns model/evaluation, one owns ingestion/API/storage, and one owns UI/end-to-end workflows; the lead owns integration, deployment and release decisions. Give each explicit file/module ownership and require them to preserve concurrent edits. A reviewer agent evaluates the frozen candidate and failure evidence independently; agent agreement is not empirical validation.

### Build and release checks

Create explicit `dev`, `demo`, `verify`, `evaluate` and `replay` commands. A clean checkout should run the synthetic demo without provider credentials. Keep license-restricted history out of Git. CI runs lint/type checks, focused unit/property tests for invariants, PostgreSQL integration tests, OpenAPI/client compatibility, and a Playwright synthetic walkthrough. Protect the main branch and require a second-person review of model/policy/security changes.

Release immutable images and immutable model/configuration bundles separately. Promote a tested bundle through staging, run smoke tests, then enable it for the pilot. Use backward-compatible database expansion before application changes; remove old fields only after consumers migrate. Rollback the image and compatible model/config bundle together. Never edit live coefficients to rescue a demo; retain the incumbent or abstain.

## 9. Budget and launch gates

These are monthly **spending envelopes**, not provider quotes or a measured bill. Training runs locally. No subscription or cloud purchase is made by this plan.

| Allocation | Ceiling | Policy |
| --- | ---: | --- |
| Hosting, database, backups, object storage, auth/monitoring and small egress | $100 | Railway Pro usage is included in its minimum subscription, not added twice. Confirm measured seven-day resource burn before inviting a partner; staging is temporary where possible. |
| Permitted market data | $150 | Start with Basic; consider the documented $99 Plus tier only after account eligibility and intended-use checks. Keep Ondo optional. The envelope cannot guarantee a commercial license. |
| Taxes, variability and contingency | $50 | Preserve as reserve; do not preallocate it to extra feeds. |
| **Total** | **$300** | If licensed data plus required hosting exceeds this, defer the external real-data pilot. |

Set hosting spend alerts at $60 and $80 and forecast the full bill weekly. Railway hard limits can stop all workloads; if a cap is used, document that outage behavior and rely on client stale/disconnected states. Do not silently disable safety, backups or source-quality checks to lower spending. [Railway pricing](https://docs.railway.com/pricing/plans), [cost-control behavior](https://docs.railway.com/pricing/cost-control).

An invited real-data pilot opens only when all of these are evidenced:

- Named users and provider-permitted processing/display/derived-output/retention for every enabled feed.
- Proven source labels, timestamps, normalization, independent-family mapping and mode isolation.
- Passing paired anomaly/repricing, deterministic replay, tenant authorization and stale-worker tests.
- Passing restore/rollback drills, acceptable load-test results, 28-day shadow record and the agreed internal service objectives.
- A frozen model card identifying validated versus experimental ticker/target/session outputs; insufficient weekend evidence remains visible and may prevent live weekend estimates.
- A forecast bill under $300/month, named primary/backup owners, working incident channel and documented degradation procedures.

Later enterprise procurement may require a stronger data contract, SAML/SCIM, penetration testing, formal retention/audit controls, redundant databases, regional recovery and staffed response. Treat these as a separately funded release. Any real trading/oracle authority additionally requires operator agreement and its own execution, manipulation and capital-risk validation.

**First implementation slice:** create the synthetic fixture, shared observation/snapshot contracts, deterministic core, PostgreSQL event/checkpoint storage and one-symbol hosted view. Add the first entitled adapter through that same path. This produces reviewable evidence before expanding models or integrations.
