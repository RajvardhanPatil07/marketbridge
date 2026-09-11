# MarketBridge: research and finale build plan

Prepared 6 September 2026 from the supplied six-slide deck, primary documentation and research papers. This is a proposed implementation, not a completed or validated pricing model. No backtest results are claimed. Documentation access does not establish your account's data entitlements.

**Review update:** The [subagent debate conclusion](MarketBridge-debate-conclusion.md) refines this plan. Prioritize an independent reference plus source-quality acceptance/recovery checks, paired anomalous-print and genuine-repricing tests, and interactive recording/replay from Day 1. Keep next-open prediction ranges separate from current-observation acceptance rules. Ondo's display-feed warning does not imply an absence of official oracle products elsewhere; the debate note distinguishes those products and their documented coverage.

## Recommended product

Build an independent off-hours reference-price service for NVDA and TSLA. Publish a price estimate, an uncertainty range, the age and origin of its evidence, and a suggested risk state. Demonstrate it alongside the existing perpetual market and a small paper-trading risk simulator.

The promise: “MarketBridge estimates off-hours stock value from available evidence and makes uncertainty visible enough for trading systems to act on.”

Start with two stocks. Add AAPL only after the full pipeline works, with its weekend limitations visible. A well-tested two-stock demonstration is achievable for the deck's two-person team during 8–11 September. A production oracle, exchange integration and defensible 52-weekend study using every proposed feed are separate milestones.

## Findings that change the original deck

1. **Existing weekend pricing is documented.** trade[XYZ] describes external pricing and an internal exponential moving-average mechanism when external inputs disappear. Its external-price documentation also describes discovery bounds. Replace “nobody has solved this” with a specific contribution: an independently evaluated estimator, source-quality diagnostics and explicit uncertainty. This does not prove which deployer Mochatrade uses. [Oracle mechanism](https://docs.trade.xyz/perp-mechanics/oracle-price), [discovery bounds](https://docs.trade.xyz/perp-mechanics/external-price).

2. **Trading hours depend on the venue and instrument.** Alpaca documents overnight access during the trading week. CME equity-index futures also have a weekend closure. Therefore “88 hours with no price” is not a defensible universal statement. Distinguish absent primary-market prices from thin, synthetic or venue-specific prices. [Alpaca sessions](https://docs.alpaca.markets/us/docs/245-trading-for-trading-api), [CME hours](https://www.cmegroup.com/articles/faqs/micro-e-mini-equity-index-futures-frequently-asked-questions.html).

3. **Ondo can supply weekend observations, with important qualifications.** Its current product page lists 24/7 mint/redemption for NVDAon, TSLAon, SPYon, QQQon, CRCLon and GOOGLon, subject to exceptions. Its API requires onboarding. Do not assume support for all stocks or unrestricted access. [Current asset support](https://ondo.finance/ondo-stocks), [API onboarding](https://docs.ondo.finance/api-reference/quickstart).

4. **Ondo's display price is not an approved oracle input.** The current-price endpoint explicitly discourages oracle use. Soft quotes are non-binding indications; they do not prove execution or fair value. Weekend pricing incorporates Ondo's proprietary model. Token prices also require correct conversion using shares per token and corporate-action metadata. Treat these as observations to validate, not ground truth. [Price endpoint](https://docs.ondo.finance/api-reference/assets/get-current-price-for-an-asset), [quote semantics](https://docs.ondo.finance/api-reference/quickstart), [token and quote pricing](https://docs.ondo.finance/ondo-stocks/token-and-quote-pricing).

5. **Mochatrade's control of exchange risk must be confirmed.** Its YC page describes a Hyperliquid-based product. HIP-3 assigns oracle operation to the market deployer. A frontend cannot independently change another deployer's liquidation mark or enforce exchange-wide margin limits. Our integration can initially provide analytics, proposed controls and order warnings. [Mochatrade profile](https://www.ycombinator.com/companies/mochatrade), [HIP-3 responsibilities](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals).

6. **Monday's open is a forecast target.** It contains information arriving after Saturday's estimate. It is not an observed Saturday stock value. Score current-value reconstruction and future-open forecasting separately. See [research notes](research-papers.md).

The deck's August 2026 SEBI report title and date appear in SEBI's official listing. The exact numerical table was not independently extracted in this research. Even accurate aggregate F&O loss statistics do not establish losses caused by off-hours stock-perp marks. Remove that causal implication. [Official report page](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html).

## Product behaviour by market state

| State | Evidence | Reference behaviour | Simulator behaviour |
| --- | --- | --- | --- |
| Regular market | Fresh external stock quotes | Anchor to qualified stock quotes | Normal controls |
| Extended/overnight | Same-stock quotes, available ETFs/futures | Use fresh direct evidence, then factor estimate | Reduce permitted new exposure as uncertainty grows |
| Weekend with qualified observations | Independent stock-equivalent token quotes or other validated sources | Update cautiously, expose synthetic basis and concentration | Conservative exposure caps |
| Evidence unavailable or conflicting | Stale, absent, or inconsistent sources | Hold last defensible estimate, widen range; abstain beyond a limit | Block new exposure in simulator and display escalation reason |
| Reopening | Fresh underlying quotes return | Reconcile to qualified external evidence and log discrepancy | Controlled return to normal state |

These are proposed controls, not certified solvency rules. A frozen reference does not make a position solvent or guarantee that a venue will avoid liquidation. Actual order routing, maintenance margin, funding and liquidation remain subject to the venue's rules.

## Data plan and access decisions

| Input | Initial role | Access and failure plan |
| --- | --- | --- |
| Hyperliquid market contexts and book | Comparison feed and live dashboard | Public read-only API probe succeeded for `xyz:NVDA`, `xyz:TSLA`, `xyz:AAPL`. Recheck markets at runtime. Keep target venue prices out of the independent estimator. |
| Alpaca stocks and ETFs | Historical training, regular and extended-session observations | Requires API keys. Basic feed is IEX, not a consolidated quote. Preserve feed labels. Historical and live access differ. |
| Alpaca overnight / BOATS | Same-stock overnight evidence | Free-plan latest indicative quotes and delayed trades differ from paid BOATS data. Test exact symbols/endpoints; do not label delayed or indicative observations as executable live prices. |
| Ondo | Optional weekend stock-equivalent observations | Obtain API access and verify weekend quote/status behaviour. Use correct token representation and multiplier. If unavailable, show missing-source mode and use permitted recorded evidence for replay. |
| CME NQ/ES through Databento | Optional overnight market factors | Needs account, data access and appropriate license. Keep outside the critical path until access works. No Saturday futures factor updates. |
| News/filings | Event flags in MVP | Timestamped earnings or corporate-action warnings widen uncertainty. Numerical sentiment-to-price jumps are deferred. |

Primary data references: [Alpaca plans and authentication](https://docs.alpaca.markets/us/docs/about-market-data-api), [overnight feed differences](https://docs.alpaca.markets/us/docs/245-trading-for-trading-api), [Databento quickstart](https://databento.com/docs/getting-started/build-first-app?historical=http&live=http), [Hyperliquid SDK schema](https://github.com/hyperliquid-dex/hyperliquid-python-sdk/blob/master/api/info/assetctxs.yaml). Confirm display/redistribution rights for any public demonstration; a personal data subscription alone does not settle these rights.

**First build-day gate:** prove one stock-history request, one external live/indicative source and the Hyperliquid comparison stream end to end. Check available historical date ranges before promising sample sizes. Do not spend the first two days building adapters for unapproved accounts.

The public API was probed using `perpDexs`, then `metaAndAssetCtxs` with `dex="xyz"`. All three stock contexts included `markPx`, `oraclePx`, `midPx`, `funding` and `openInterest`. This verifies read access only. It does not identify Mochatrade's routing or establish independent equity-price evidence.

## Estimator

### Normalize first

Every observation needs: canonical underlying symbol, instrument type, venue, original source family, USD units, bid/ask or trade type, available size, event time, receipt time, source delay, source status and corporate-action version.

Use UTC internally and exchange calendars in `America/New_York`. Convert display times to `Asia/Kolkata`. In September, regular US hours are 19:00–01:30 IST; standard-time months differ. Do not hard-code a fixed UTC offset. [NYSE core session](https://www.nyse.com/trade/trading-information?os=io_).

For a raw total-return token price, a conceptual conversion is:

`stock_equivalent_usd = raw_token_price_usd / shares_per_raw_token`

Some feeds already show a scaled stock-like price. Check the representation and avoid dividing twice. Handle stablecoin/USD basis where applicable. Do not average raw NVDA dollars, NQ index levels and token prices.

Reject malformed/crossed quotes and known halted sources. Soft-penalize age, spread, insufficient depth, unusual venue basis and disagreements. Unknown evidence age is a limitation, not zero age. HTTP receipt timestamps and feed heartbeats do not demonstrate a new underlying observation.

### Factor baseline

Fit a small ridge regression per stock using synchronized, historical log returns. Use one market factor initially, such as QQQ when it trades, and add a sector factor only if it improves forward validation. NQ is an optional alternative for hours with futures access. Use ES and NQ together only after checking redundancy and stability.

`stock_return = intercept + beta_market * market_return + beta_sector * sector_return + residual`

For a simple anchored estimate:

`P_factor(t) = P_anchor * exp(beta_market * log(F_market(t)/F_market(anchor)) + beta_sector * log(F_sector(t)/F_sector(anchor)))`

Both factor endpoints must represent the appropriate synchronized times. Fit and evaluate matched horizons. An intraday beta applied over a weekend is an assumption to test. Use a separate available-factor specification when a source disappears; do not silently feed an old quote as fresh information or double-count returns after re-anchoring. Do not add an unvalidated constant drift every second.

Illustration only: a $100 anchor, a 1% market move and beta 1.4 imply roughly $101.40 before independent stock-specific evidence. This example is not a forecast or measured result.

### Fuse direct observations

The MVP can combine the factor estimate and normalized same-stock observations using a robust weighted estimate in log-price space. Weights depend on observed historical error and current source quality. Expose each contribution in the dashboard. Limit the weight of any single source family and retain a model-error floor.

Three APIs distributing the same original quote count as one source family. An Ondo stock quote and several Ondo factor quotes are not automatically independent. Avoid circularity: do not use the target perpetual's mark to construct a reference against which that mark is graded.

An optional second version can use a small state-space/Kalman filter: factor moves predict the hidden stock value; qualified observations update it; uncertainty grows during gaps. It must not repeatedly treat the same stale observation as new evidence. Use covariance or grouping for correlated observations. This is a method for combining evidence, not proof of weekend predictability.

### Uncertainty and abstention

Maintain a volatility/error scale from past residuals, elapsed time without independent evidence, event flags and source disagreement. Calibrate interval width on earlier held-out data for a specified target and horizon:

`interval = P_estimate * exp(± q * error_scale)`

Here `q` is a quantile of past standardized errors, estimated without test data. Check empirical coverage on later data. A nominal 90% interval is not a per-timestamp guarantee. Until enough appropriate observations exist, label the display “model uncertainty range, calibration pending.”

Keep distinct outputs for current observable-proxy reconstruction and next-open prediction. When current underlying value is unobserved on weekends, its interval cannot be directly calibrated against simultaneous stock truth. Report the proxy, horizon and limitations alongside any coverage figure.

If independent signals disappear, the estimate may stay still while the range grows. After a configured evidence-quality threshold, return `INSUFFICIENT_EVIDENCE`, with the last estimate separately labelled as stale. One-second API publication does not require inventing a new price every second.

## Architecture and output contract

`Feed adapters -> timestamp/unit validation -> session and source-quality state -> estimator -> uncertainty/risk proposal -> FastAPI/WebSocket -> dashboard and simulator`

Use Python, NumPy/pandas and scikit-learn for estimation; FastAPI for the service; Next.js and a chart library for the dashboard. Store append-only observations in Parquet and inspect them with DuckDB. SQLite is sufficient for run metadata. Add TimescaleDB only if an existing setup makes it easier.

Proposed API routes:

- `GET /v1/reference/{symbol}`: estimate, range, target/horizon, state, timestamps, model version and source explanations.
- `GET /v1/health/sources`: source status and evidence ages.
- `GET /v1/evaluation/{run_id}`: baselines, metrics, date ranges and exclusions.
- `WS /v1/stream`: reference and risk-state updates.

Separate fields for the MarketBridge estimate, venue oracle and venue mark. Add `data_mode` (`LIVE`, `DELAYED`, `REPLAY`, `SYNTHETIC_TEST`) and `execution_authority="SIMULATOR_ONLY"` in the demo. Use simulated account equity, maintenance rules and exposure limits explicitly. A suggested initial-margin increase applies to new simulated exposure; it must not silently create retroactive liquidations in the demonstration.

## Validation that can withstand judge questions

### Experiment A: hide observable stock data

Take real periods with a credible same-stock quote. Hide that target stock observation from the model for fixed windows, such as 15, 30 and 60 minutes. Let the estimator see only information available then. Compare with the withheld target series. Use chronological train/calibration/test blocks and a purge gap at least as long as the overlapping target horizon.

This tests reconstruction under missing feeds. It does not establish Saturday performance. Test extended/overnight periods separately because liquidity differs from regular sessions.

### Experiment B: predict the next regular open

Predefine forecast timestamps, e.g. Friday after-hours close and Saturday 12:00 ET. Score each horizon separately against the next regular open. Model B may include only inputs that genuinely existed and were obtainable at the cutoff. A Friday forecast cannot use Saturday or Sunday prices.

Use next trading session rather than hard-coded Monday. Define the target explicitly: official opening print, or a separately labelled first-five-minute VWAP. Do not switch targets after viewing results. Compare regular close, last qualified extended-hours quote, simple factor baseline, normalized token baseline where available, and the combined model on identical samples.

### Required result table

Report actual observation counts, tickers and dates; MAE and RMSE in basis points; nominal versus observed interval coverage; average interval width; worst errors; source availability and abstention rate. Pair coverage with width so a uselessly broad range cannot look successful. Split results by session and earnings/event status where sample size permits.

`error_bps = 10000 * (estimate - target) / target`

`relative_RMSE_improvement = 1 - RMSE_model / RMSE_baseline`

Resample uncertainty in performance by day/weekend, not individual one-second ticks. Many ticks from the same weekend do not create many independent weekend outcomes. Report all forecast attempts, including abstentions and missing-source periods, to prevent cherry-picking.

The deck's 30% improvement is a hypothesis. Its 52-weekend promise depends on actual source history. Run a longer study for older inputs and a shorter study for newer token feeds; do not manufacture old token data. Retain a baseline if the complex model fails to improve it.

### Risk demonstration tests

Inject a stale feed, one extreme quote, duplicate observations, a missing source family, an earnings flag and a reopening gap. Verify timestamps, source rejection/penalties, uncertainty changes, abstention and recovery. Label injected scenarios as synthetic tests. Any count of avoided liquidation triggers is specific to the disclosed simulation; it is not proven real customer savings.

## Four-day delivery schedule

| Day | Rajvardhan: model and evaluation | Ritesh: ingestion and UI | End-of-day proof |
| --- | --- | --- | --- |
| 8 Sep | Define target, clean historical data, last-price baseline | Data-access probes, normalizer, Hyperliquid read adapter, basic chart | One stock reaches UI with genuine source timestamps; replay artifact saved |
| 9 Sep | Ridge baseline, robust fusion, initial uncertainty scale | WebSocket updates, source panel, separate venue/reference charts | Two stocks end to end; stale-feed scenario changes state |
| 10 Sep | Chronological evaluation, coverage/width, ablations | Replay controls and paper-risk simulator | Reproducible result table with actual sample counts |
| 11 Sep | Review bad cases, lock parameters and results | Offline packaging, reconnect behaviour, recorded fallback | Three full rehearsals from a clean start |

Treat 6–7 September as research/access preparation under the supplied instruction to start building on the 8th. Confirm the venue's integration role, available feed credentials, historical access and public-demo rights as planning dependencies. No messages to organizers or providers have been sent.

## Live finale sequence

12 September 2026 is Saturday. The supplied 11:00–18:00 IST finale corresponds to 01:30–08:30 EDT on Saturday. CME and ordinary equity sessions cannot supply fresh Saturday factor moves.

1. Show NVDA or TSLA: last qualified stock price, venue mark, MarketBridge estimate and uncertainty.
2. Show timestamps, live/replay label and which observations currently influence the estimate.
3. Disable a source in the test harness. Its evidence gets older and uncertainty grows.
4. Inject an anomalous observation. Explain why the system rejects it or reduces its influence.
5. Show the proposed new-exposure control in the paper-risk simulator.
6. Replay a real held-out historical episode and reveal the result against the stated baseline.

Use actual live weekend observations if access and quality are confirmed. Otherwise retain a live venue-comparison panel and demonstrate the independent estimator on clearly labelled historical replay. A replay-backed working project proves the software works; it does not meet a literal promise of live independent Saturday equity data, so update that promise before the finale if access remains unavailable.

## Business case and presentation changes

Initial buyer: a stock-perp venue/deployer, market maker or trading interface that needs independent reference diagnostics. Pilot deliverables: source uptime, reproducible pricing discrepancies, calibrated forecast/reconstruction intervals and risk-simulation results. A subscription per covered instrument or venue is a business-model hypothesis to test with the buyer.

The deck's `$5m * 20bps * 25% = $2,500/day` arithmetic is correct as an assumption-based illustration. Price forecast improvement does not directly establish those savings, who earns them, or whether they accrue to Mochatrade. A loss/revenue study needs execution data, inventory, fees, hedges and market structure. Auditability is useful engineering evidence; it does not itself establish regulatory compliance.

Suggested six-slide finale:

1. Team and precise product promise.
2. A documented off-hours pricing discrepancy or clearly labelled hypothetical failure.
3. Source hierarchy, session-aware estimator and uncertainty.
4. Working demonstration with failure injection.
5. Actual evaluation results and limitations.
6. Integration ownership, pilot proposal and next milestone.

Remove the placeholder trader quote. Replace unsupported superiority, savings and liquidation-prevention claims with measured results or explicit hypotheses. Keep a backup slide with data provenance and the research references.

## Completion criteria

The hackathon MVP is complete when a clean start runs the data/replay pipeline, two stocks have traceable outputs, source failure produces an explained response, the risk simulator consumes those outputs, and a chronological evaluation reproduces the displayed results. A production oracle requires substantially more evidence, deployment authority, data agreements, manipulation analysis, operational governance and capital/risk validation.

Research papers and their precise relevance are recorded in [research-papers.md](research-papers.md).
