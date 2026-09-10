# MarketBridge: conclusion after adversarial review

Date: 6 September 2026. Compared the user's pasted chatbot proposal with the earlier MarketBridge build plan. Three subagents independently argued product advocacy, quantitative criticism and incident verification; their findings were then cross-examined. This records the resulting design judgment, not an empirical validation of the proposed system.

## Decision

Build **an independent off-hours reference and source-quality guard**, with proposed acceptance/recovery controls demonstrated in a simulator. Keep two stocks, NVDA and TSLA. Make the headline demonstration a questionable price update followed by a separate genuine repricing. Both must be handled well.

Adopt the other chatbot's clearer product emphasis and interactive incident-inspired stress scenario. Retain the original plan's target definitions, independence requirements, limited scope, conditional data access and honest evaluation. Do not adopt its unconditional conformal guarantee, automatic 20-sigma rejection or claimed $60 million saving.

## What the debate changed

The product advocate argued that a guard for external-price handoffs gives the estimator an immediately understandable purpose. The quant reviewer challenged whether the guard merely freezes prices during real crashes. The advocate accepted that criticism and proposed temporary quarantine, explicit evidence checks and a recovery policy. The incident auditor found that exact historical counterfactual claims exceed the available data.

Consensus: a good demo must show both resistance to an isolated anomalous observation and acceptance of a corroborated genuine move. Measure the tradeoff, including delayed repricing and simulated bad debt. Fewer simulated liquidation triggers alone is not sufficient evidence of safety.

## Claim-by-claim verdict

| Other proposal claim | Verdict | Decision |
| --- | --- | --- |
| Saturday availability should drive the demo | Adopt | Verify weekend sources first and visibly show closed/stale source states. The original plan already identified Saturday; the improvement is emphasis. |
| Independent prior and source acceptance are the product | Adopt with qualification | Independent model output plus advisory acceptance/recovery logic; no guarantee of a correct latent price. |
| Automatically redistribute all missing-source weight to live tokens/crypto | Reject | Preserve uncertainty and source-concentration limits. Losing independent evidence must not force full trust in the remaining feed. |
| Expand to four stocks | Defer | Two stocks are sufficient for the four-day team. Add coverage only after validation works. |
| AAPL has no 24/7 tokenized counterpart | Too broad | Absence from a particular provider's six-asset weekend mint/redemption list does not establish absence everywhere. Exclude it from the core demo for scope and verified access reasons. |
| 48 hours replaces 88 hours everywhere | Qualify | Describe the standard conventional weekend gap for the cited venues, subject to holidays and access. Token markets and perps can still have prices; market closure is not absence of all pricing. |
| One-second service publication conflicts with Hyperliquid's three-second oracle | Reject the inference | UI/API cadence, source-update cadence and on-chain publication cadence are distinct. Respect HIP-3 updater constraints for any future integration. |
| ICE/MSCI provide a relevant precedent | Adopt | Cite as established fair-value estimation practice, not proof that this implementation is safe for perp liquidations. |
| Night/day research proves only overnight betas should be used | Overstated | Match models to their target/horizon and compare session-specific estimates on later data. |
| Weekday gaps are statistically the same as weekend gaps | Unsupported | More past data can help training; report weekends as a separate regime and respect historical information cutoffs. |
| The existing plan trains only on 52 weekends | Misreading | The deck promises a 52-weekend evaluation; it does not require training on those observations alone. Actual source history determines feasible evaluation size. |
| Conformal prediction gives unconditional finite-sample guarantees here | Reject | Financial time-series dependence and regime shifts require assumptions and suitable methods. Publish empirical coverage, width and counts. |
| A 20-sigma move proves a corrupt print | Reject | Could be bad data, real news or a failed model. Use source quality and corroboration; test real jumps. |
| Next-open interval should be the current-price acceptance bound | Reject | Different targets and horizons; maintain separate calibrated outputs. |
| Last close is trivially beatable | Unsupported | Retain it, last qualified price, one-factor and appropriate token baselines on identical samples. |
| Ondo on HyperEVM automatically provides free fresh weekend pricing | Unestablished | Verify exact contract/pool, source semantics, update timestamps and liquidity before relying on it. |
| Databento credits necessarily cover the proposed raw history | Unestablished | Price a bounded symbol/schema/date request. Prefer targeted bars over downloading entire raw books. |
| SK Hynix motivates the problem | Adopt carefully | Use documented observations as motivation and label reconstruction honestly. |
| A guard would have saved $60 million | Reject | Liquidated notional is not actual losses; full counterfactual evidence is unavailable. |
| Add 1% annual probability times incident notional to savings | Reject | Neither the probability nor the loss amount is established. |
| Interactive replay through the real pipeline | Adopt | Implement with visible LIVE/REPLAY/SYNTHETIC labels and original event timestamps from Day 1. |

## Source findings that matter

**Existing mechanisms.** Current XYZ mark documentation describes a median of oracle, oracle-plus-EMA basis, and local book/trade inputs, as well as ±50 bps relayer update clamps. Thus “we add a clamp” is not a sufficient novelty claim. Compare against a disclosed EMA/bounded-update baseline; do not call it an exact XYZ reproduction. Current documentation cannot establish the configuration at a past incident. [XYZ mark mechanism](https://docs.trade.xyz/perp-mechanics/mark-price).

**Publication timing.** The native validator-oracle documentation says three seconds. HIP-3 updater documentation separately specifies at least 2.5 seconds between SetOracle calls. Our service can refresh every second while reporting unchanged source timestamps and respecting any downstream update rules. [Native oracle](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle), [HIP-3 actions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions-1).

**Commercial precedent.** ICE describes security-level multifactor adjustments and training history of up to 12 months, with a minimum of 60 trading days. This supports the architecture's motivation, not a replication claim or a performance promise. ICE's confidence measure must not be casually equated with our predictive interval. [ICE Fair Value Information](https://www.ice.com/fixed-income-data-services/data-and-analytics/pricing/fair-value).

**Night/day paper.** Hendershott, Livdan and Rösch study the cross-sectional relationship between expected returns and beta across sessions. That is distinct from asserting a particular stock's hedge sensitivity reverses sign during daytime. Test the proposed session-specific model rather than treating this paper as a universal implementation prescription. [Author-hosted paper](https://faculty.haas.berkeley.edu/hender/CAPMday-night.pdf).

**Conformal inference.** Ordinary coverage statements do not transfer automatically to dependent financial data. Adaptive conformal methods address changing distributions, but their results do not establish useful pointwise certainty for every Saturday. A next-open forecast band cannot validate a contemporaneous latent stock price. [Gibbs and Candès](https://arxiv.org/abs/2106.00170), [Zaffran et al.](https://proceedings.mlr.press/v162/zaffran22a.html).

**Ondo clarification to our previous answer.** The warning about the display-price API remains valid, but must not imply there is no official Ondo oracle elsewhere. Ondo and Chainlink announced official tokenized-equity feeds. Chainlink's cited launch specifies Ethereum Mainnet and 24/5 coverage. Separately, token bridging to HyperEVM does not demonstrate fresh weekend oracle observations on that chain. [Display endpoint](https://docs.ondo.finance/api-reference/assets/get-current-price-for-an-asset), [official feed launch](https://dev.chain.link/changelog/tokenized-equity-feeds-launch-with-ondo-finance), [HyperEVM bridge announcement](https://ondo.finance/blog/tokenized-stocks-bridged-to-hyperliquid).

**Data cost.** Massive currently lists $29/month delayed and $199/month real-time stock plans for individual use, with plan-specific access. Databento offers historical credits and a cost-estimation API. Neither statement settles team eligibility, live-data licensing or public redistribution rights. [Massive pricing](https://massive.com/pricing?product=stocks), [Databento pricing](https://databento.com/pricing/), [cost API](https://databento.com/docs/api-reference-historical).

## SK Hynix evidence limits

The July 2026 event is corroborated by published incident reporting. The reported $57–80 million is **liquidated position notional**, not verified cash losses or reimbursement expenditure. Galaxy's report also describes a substantial genuine decline later that day, reinforcing the need to recognize real repricing. The claim that an arbitrary 1% annual event probability produces $570–800k expected loss is unsupported. [Galaxy analysis, a secondary incident source](https://www.galaxy.com/insights/research/hyperliquid-tradexyz-oracle-liquidations).

The auditor located [TradeXYZ's statement](https://x.com/tradexyz/status/2082260930751082821), but direct access returned 403; its text was checked through reproductions. A [transaction analysis](https://k.odz.jp/posts/tradexyz-incident/) contains explorer links and explicitly reconstructed mark values. The explorer transactions were not independently decoded here. We do not have the complete raw input and position history necessary to claim exact reproduction or avoided historical losses.

Use this label until that evidence is acquired: **“Incident-inspired reconstruction using published observations and stated assumptions. MarketBridge outputs are hypothetical.”**

ADL is relevant to the original deck's oversimplified two-party claim. It can force closure of opposing positions; do not equate that mechanically with identical cash losses for every affected trader. [Hyperliquid ADL specification](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/auto-deleveraging).

## Final implementation scope

The pipeline is `sources -> normalization/provenance -> independent estimate -> source-quality guard -> simulated risk policy -> dashboard/replay`.

Maintain three distinct outputs:

1. **Reference estimate:** estimated current value, evidence quality and an appropriately qualified uncertainty range.
2. **Next-open forecast:** separate target, cutoff and calibrated prediction range, only where historical information permits evaluation.
3. **Observation assessment:** whether a new observation should influence the estimate, with reasons and recovery state.

For the guard, reject malformed observations outright. A large but valid update enters a provisional caution/quarantine state. Check original source independence, two-sided depth where available, venue status, events and persistence. Repeated data from one source is not corroboration; elapsed time alone does not prove validity. Admit qualified repricing under a predeclared recovery rule. If evidence remains inadequate, abstain and restrict new simulated exposure. Do not publish the old estimate as known truth.

Fit a small ridge model with one market factor initially. For observable reconstruction, train and test matched horizons, such as 30-minute returns, and distinguish regular from extended sessions. For next-open forecasting, stop every feature at the declared prediction cutoff. Use chronological fitting, tuning, calibration and test blocks. Older daily gaps may contribute training data; later weekends remain an explicitly reported test regime. Choose actual split dates after checking coverage.

Use standardized residual quantiles estimated on a prior calibration block for the first prediction ranges. Report achieved 80/90/95% coverage together with interval width and sample count; small weekend samples provide preliminary evidence only. Calibrate source-anomaly rules separately from future-price prediction ranges.

## Demonstration and evaluation

Show two paired scenarios of comparable magnitude:

- An isolated, thin or unsupported price update: guard reduces its influence and explains why.
- A persistent repricing corroborated by qualified evidence: estimate re-anchors, with measurable delay.

Also show feed dropout, recovery, duplicate/stale updates and a clearly labelled historical reconstruction test. Use the same adapters and state machine for live and recorded observations.

Pricing metrics: MAE/RMSE, tails, interval coverage/width, availability and abstention. Guard metrics: false rejection of genuine moves, anomaly detection, detection/recovery delay, tracking lag, simulated liquidation triggers and simulated bad debt. Report assumptions of the position simulator. Compare the estimator with last qualified price and a simple factor baseline; compare guard logic with a disclosed EMA/bounded-update baseline.

## Delivery plan

| Day | Build priority | Completion evidence |
| --- | --- | --- |
| 8 September | Verify exact weekend-source access; live venue comparison; normalization; local recording and replay | One stock traverses the complete pipeline with original timestamps |
| 9 September | Two-stock estimator; separate uncertainty and guard outputs; recovery rules | Both questionable update and genuine repricing scenarios work |
| 10 September | Chronological evaluation; stronger baselines; incident-inspired reconstruction | Reproducible metrics, dates, counts and disclosed assumptions |
| 11 September | Freeze parameters and data; test dropouts and clean start; rehearse | Interactive offline fallback and three complete dry runs |

Final pitch: **“MarketBridge helps stock-perp operators evaluate off-hours prices, detect weak evidence, and handle the return of external market data with explainable risk controls.”**

This is a focused change in product emphasis, not evidence of production readiness. The original implementation notes remain useful, subject to the decisions above.
