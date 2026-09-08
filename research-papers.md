# MarketBridge: research foundations and a testable MVP

Research date: 6 September 2026. Scope: primary papers relevant to estimating an unavailable single-stock price, managing stale observations, and validating uncertainty. This is a methodological recommendation, not a claim that any paper validates MarketBridge or guarantees a correct weekend price. No codebase exploration was needed.

## Recommendation

For the four-day build, implement one or two liquid stocks, a small explainable factor estimator, a calibrated empirical uncertainty band, source-health checks, and a simulated risk-state output. The demo has no authority to change exchange marks, margin, or liquidations. Start with ridge regression; make Kalman filtering a stretch goal. A live dashboard should demonstrate how the estimate changes when useful observations arrive and how uncertainty and allowed actions change when evidence deteriorates. Do not spend the build on transformers, online reinforcement learning, or a purported news-to-dollar-price engine.

The strongest defensible claim is: **MarketBridge publishes an auditable off-hours reference estimate and tells the venue when available evidence is too weak to rely on it.** Whether it improves on the last trustworthy price must be measured on unseen data.

## Six useful papers

| Paper and verified primary source | What it supports | What it does not establish |
|---|---|---|
| **Chua, Lai & Wu, _Effective Fair Pricing of International Mutual Funds_ (2008; author working paper 2005).** [Author manuscript/abstract on SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=682369); [university-hosted manuscript](https://finance.wharton.upenn.edu/department/Seminar/2005summer/ChuaLaiWu2005.pdf). | This is the closest conceptual precedent: adjust individual stale securities using economically relevant factors. Their Japanese-fund application compares methods using next-day opening prices as proxies for unavailable contemporaneous prices. | Their results do not validate US-stock perps, cryptocurrency as a stock proxy, or weekend valuation. Reopening price is a proxy with intervening information, not observed weekend ground truth. Use their economic design idea; ridge is a simpler MVP choice than their stepwise selection. |
| **Barclay & Hendershott, _Price Discovery and Trading After Hours_ (2003).** [Author-hosted full paper](https://faculty.haas.berkeley.edu/hender/after_hours_price_discovery.pdf). | After-hours trading can contain material information despite low activity; its prices are noisier than regular-session prices. This motivates using actual extended-hours stock observations when available, while considering spread and liquidity. | An old Nasdaq market-structure sample is not evidence for today's numerical spreads or volumes. It does not mean every thin after-hours quote is trustworthy, or that information continues at the same quality when all relevant markets close. |
| **Zitzewitz, _Who Cares About Shareholders? Arbitrage-Proofing Mutual Funds_ (2003; working version 2002).** [Author manuscript/abstract on SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=305410). | Documents the economic problem of stale fund valuations and the motivation for fair-value updating to reduce predictable pricing errors. Useful background for why stale references can transfer value between participants. | Fund-share transactions and perp liquidations have different mechanics. Do not reuse historical arbitrage return numbers as a current market-size claim, or claim that a statistical update eliminates manipulation. |
| **Bańbura & Modugno, _Maximum Likelihood Estimation of Factor Models on Data Sets with Arbitrary Pattern of Missing Data_ (ECB WP 1189, 2010; journal publication 2014).** [ECB full paper](https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp1189.pdf). | Provides a state-space framework for factors with irregular availability, different release delays, and missing observations; explains revisions from newly arrived information. This supports explicitly modeling availability instead of pretending every input updates continuously. | Its application is macroeconomic nowcasting. A Kalman filter cannot manufacture information about a stock-specific event, and model covariance is not automatically a calibrated financial prediction interval. |
| **Gibbs & Candès, _Adaptive Conformal Inference Under Distribution Shift_ (NeurIPS 2021).** [Conference publication](https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html). | An online wrapper adapts prediction-set calibration as observations arrive. The coverage result concerns frequency over long time intervals under distribution change. | It does not guarantee conditional coverage on each weekend, ticker, earnings event, or timestamp. If the target has not yet been observed, the corresponding error cannot update calibration. Extremely wide intervals can be necessary to maintain coverage. |
| **Zaffran et al., _Adaptive Conformal Predictions for Time Series_ (ICML 2022).** [Conference paper and PDF](https://proceedings.mlr.press/v162/zaffran22a.html). | Explains why ordinary exchangeability assumptions do not directly fit time series; studies ACI learning-rate behavior and adaptive aggregation with a real electricity-price application. | Electricity results do not demonstrate stock-price performance. Picking an ACI learning rate after inspecting the test period leaks information. For the MVP, honest rolling empirical bands with reported achieved coverage may be preferable to a rushed claim of formal guarantees. |

The Wharton manuscript appears in search indexing but returned HTTP 403 on direct opening; the corresponding author-uploaded SSRN abstract was readable. Other listed links were accessible in this research session. Paper dates above come from the actual bibliographic content, not search-engine crawl dates.

## What exactly is the target?

Define the product output before fitting a model:

1. **Observed reference:** a fresh, acceptable quote/trade for the same stock from a qualified source. Label the venue and timestamp. A quote midpoint is not the same thing as an executable fill.
2. **Contemporaneous estimate:** the unavailable stock price at time `t`, conditional on information received by `t`. This is latent during a full market closure. A single observed Monday opening print cannot reveal the true Saturday price.
3. **Reopening forecast:** the next regular-session opening price, forecast using information available at an explicitly fixed timestamp. This is observable later but includes new information after the prediction time and opening-auction effects.

Keep these outputs and metrics separate. A model trained to forecast Monday open should be called a reopening forecast; a good next-open score alone does not validate a Saturday liquidation mark. This is our inference from the target definitions and the fair-pricing paper's use of next open as a proxy.

## Feasible estimator

For a stock with last trustworthy anchor price `P_i(t0)`, the simplest candidate is:

`log P_hat_i(t) = log P_i(t0) + sum_j beta_ij * log(F_j(t) / F_j(t0))`.

Use a small set of economically relevant, actually available factors. Fit stock-return sensitivities with regularized regression on historical synchronized observations; select coefficients and regularization strictly before evaluation. Avoid cumulative long-horizon drift terms in the first prototype. A same-stock quote, if fresh and qualified, provides more direct evidence than a proxy estimate and should be shown separately or assimilated using an explicit measurement-quality rule.

Important implementation details:

- **Match horizons and regimes.** Coefficients fit on ordinary five-minute cash-market returns may not transfer to an overnight or weekend. Report this limitation and validate each regime separately.
- **Consistent anchor.** Measure every factor's movement from the same information cutoff as the stock anchor. If a qualified stock update resets the anchor, reset factor baselines consistently. Otherwise repeatedly adding cumulative returns double counts movement.
- **Missing is not zero.** A stale last value is not proof of zero return. Retain original event and received timestamps, age, session status, and the last observed cumulative factor move; missing fresh increments should reduce evidence strength. Never refresh the observation timestamp merely because a provider repeats a cached value.
- **Avoid circularity.** Do not feed the same perp's mark into its own allegedly independent reference and use agreement as validation. Another tokenized/perp venue can contain useful information, but its basis, liquidity, and dependence need separate treatment.
- **News should initially affect state.** A verified material event can trigger wider uncertainty or a pause/review state. An LLM's sentiment score is not a defensible dollar adjustment without a separately validated event model.

A state-space upgrade can propagate the latent state and uncertainty and update only on fresh measurements. Use the forward filter for historical real-time predictions. A smoother that sees observations after the evaluation timestamp would introduce look-ahead leakage. This operational choice is informed by Bańbura–Modugno; the simple fixed-coefficient estimator above is our proposed MVP, not their full algorithm.

## Leakage-free evidence judges can inspect

Use chronological training, calibration, and untouched test blocks. Any model selection happens inside the training/calibration period. Store the prediction, model version, input timestamps, and availability state before revealing the outcome. Historical `received_at` is preferable; if unavailable, explicitly mark the backtest as assuming a data-delivery delay.

Run three distinct experiments:

| Experiment | Observable outcome | What the result means |
|---|---|---|
| Hide same-stock observations during selected regular-session windows; retain only proxies available then. | Actual stock quote/reference at the hidden timestamps. | Tests the mechanics of contemporaneous estimation in an observable regime, not weekend accuracy. |
| Replay real pre/post-market periods using qualified stock observations as the reference; segment by spread, activity, and event status. | Qualified same-stock reference at matched timestamps. | Tests actual extended-hours performance; reference quality must be disclosed. |
| Issue forecasts at fixed close/weekend cutoffs, reveal the next opening price only when available. | Next regular-session opening price. | Measures reopening forecasts. Keep each cutoff/horizon separate; do not label this weekend fair-value ground truth. |

Compare against the last trustworthy price and a one-factor benchmark. Report MAE in basis points, median and tail absolute error, empirical interval coverage, median interval width, and the fraction of time the system abstains. Show metrics for all eligible timestamps as well as active-state timestamps so abstention does not hide bad outcomes. Group uncertainty estimates by session or event blocks: thousands of minute ticks are not thousands of independent overnight events.

For an MVP uncertainty band, use pre-test residual quantiles for the same target and horizon, with a documented conservative policy when source age or disagreement exceeds the calibration regime. Such an inflation rule is an engineering heuristic until independently evaluated. Label a band **target 90% empirical prediction interval**, and show achieved test coverage and sample count; do not display an unexplained “90% confidence” score. Conformal methods calibrate against observable outcomes, not an inaccessible latent Saturday value.

## Four-day scope

- **Day 1:** lock the ticker scope, access data, event schema, market calendar, replay timeline, and observable evaluation target; produce the last-price baseline.
- **Day 2:** implement factor estimate, held-out evaluation, empirical bands, and source-quality/risk-state rules.
- **Day 3:** integrate the API and dashboard; add reproducible stale-feed, conflicting-source, and price-shock scenarios.
- **Day 4:** freeze model and demo data, run the untouched evaluation, prepare both a live observation view and a clearly labeled historical replay, rehearse failure handling.

The research supports treating unavailable prices as an estimation problem with model risk. It does not support claims of guaranteed accuracy, guaranteed liquidation fairness, or a manipulation-proof oracle.
