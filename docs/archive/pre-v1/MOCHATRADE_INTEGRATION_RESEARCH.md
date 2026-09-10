# MarketBridge × Mochatrade: Market Safety Control Plane

**Decision memo and build specification**  
**Research date:** 10 September 2026  
**Audience:** hackathon team, Mochatrade product/risk/engineering  
**Evidence standard:** public facts are separated from inferences and recommendations

## Executive verdict

MarketBridge is already a credible technical project, but its current product story is narrower than its capability. It proves that a suspicious equity-perpetual mark can be detected, explained, replayed, and audited. What it does not yet prove is that this judgment changes a real customer outcome inside Mochatrade.

The strongest next step is **not another dashboard and not a replacement exchange**. It is:

> **Mochatrade Market Safety Control Plane, powered by MarketBridge** — an application-level safety layer that qualifies market evidence, caps or blocks new risk, keeps reduce-only exits available, and produces a verifiable receipt for every high-consequence decision.

This directly supports Mochatrade's public product: 24/7 leveraged access to US-stock perpetuals with a simple India-first experience.[^1] It also matches the company's stated use of fresh capital to strengthen its risk infrastructure and its public hiring for low-latency perpetual systems, market making, and compliance.[^2]

The honest limitation is important: there is no public evidence that Mochatrade controls a particular Hyperliquid HIP-3 deployer or oracle-updater key. MarketBridge therefore must not claim that it can pause Hyperliquid liquidations or alter protocol marks. Version one should govern orders routed through Mochatrade. A later oracle-publication interlock is possible only if Mochatrade confirms that authority.

## Honest score today

| Dimension | Current score | Why |
|---|---:|---|
| Problem importance | 9.0/10 | A bad mark can trigger irreversible leveraged-liquidation consequences; a July 2026 equity-perp incident reportedly caused tens of millions of dollars of liquidations.[^3] |
| Technical differentiation | 8.5/10 | Independent-source qualification, abstention, deterministic risk states, hash-chained Mark Passports, and counterfactual replay are much stronger than a generic trading UI. |
| Mochatrade alignment | 8.0/10 | 24/7 equity perps, leverage, risk education, and infrastructure are central to Mochatrade's public positioning.[^1][^2] |
| Real integration today | 5.5/10 | The Mochatrade adapter currently accepts only a symbol, mark, and time; the UI's order ticket is paper/advisory and execution is disabled. |
| Demonstrated customer outcome | 6.0/10 | The project explains danger well, but does not yet show an order being capped, blocked, safely reduced, or reconstructed after liquidation. |
| Trust and production readiness | 7.0/10 | HMAC authentication, replay protection, deterministic policy, tests, and audit records are strong; position context, exchange calendars, corporate actions, data entitlements, and an enforcement contract are missing. |

**Overall today: 7.4/10 as a hackathon contender.** It is technically serious and unusually relevant, but a judge can still ask, “What does Mochatrade actually do with this decision?”

**Plausible score after the P0 integration: 9.0/10.** The gain comes from converting a diagnostic oracle into a visibly enforced, consequence-aware product flow—not from adding more AI.

## What Mochatrade publicly says it is solving

### Verified public facts

Mochatrade's current site describes 24/7 US-stock perpetual trading, INR/UPI funding, leverage up to 20×, and automatic square-off at maintenance margin.[^1] Its YC profile describes a broader mission of giving Indian users global market access through a simple, self-custodial experience built on crypto-market infrastructure; the profile still contains older “up to 50×” language.[^4]

Founder Utkarsh Sinha has framed the company around equal market access and a personal desire to obtain leverage safely. Public founder material emphasizes that crypto infrastructure should remain underneath a simpler user experience.[^5] Co-founder Chetan Manda has publicly emphasized that perpetuals are not magic and require education and respect for risk.[^6]

The company's public fundraising coverage says the capital is intended to build the perpetuals engine, strengthen risk infrastructure, and complete regulatory and compliance groundwork.[^2] Public hiring posts seek a systems developer for a low-latency order book/clearinghouse, a quant trader for equity-perp market making, and an India compliance lead.[^7]

Most decisively, Mochatrade's own July 2026 market commentary calls thin and jumpy trading in quiet hours a real concern as exchanges move toward longer sessions.[^19] Another first-party article argues that price alone is insufficient evidence that a move is real; participation and volume matter.[^20] MarketBridge operationalizes those two educational claims as infrastructure.

### Evidence-backed inference

Those statements do **not** prove that Mochatrade has failed to solve a particular internal problem. They do show that four problems remain active and strategically important:

1. Operating a reliable leveraged market around the clock.
2. Keeping liquidity and marks defensible across very different equity sessions.
3. Translating complex risk into safe, simple user behavior.
4. Building an auditable compliance and dispute trail while the product and public claims evolve.

MarketBridge should be pitched as infrastructure for those active problems—not as a claim that Mochatrade's team is incapable of solving them.

## The real problem: a 24/7 derivative sits on a part-time underlying market

US equities do not have one equally liquid, continuously linked price around the clock. FINRA warns that extended-hours trading can have lower liquidity, wider spreads, higher volatility, and prices that differ across trading systems because venues may not be linked.[^8] That makes a leveraged perpetual especially vulnerable during pre-market, post-market, overnight, exchange halts, holidays, and corporate actions.

Hyperliquid already has substantial protections. Its mark is built from the oracle and market-derived inputs; the mark drives margin, liquidation, take-profit/stop-loss triggers, and unrealized PnL.[^9] HIP-3 deployers are responsible for defining and operating their markets and oracle inputs, while the protocol applies update cadence, movement clamps, and open-interest protections.[^10]

The unresolved product gap is therefore more specific than “bad oracles”:

> **How should an India-facing application decide whether a new leveraged equity-perp order is safe right now, given the current session, source independence, customer liquidation distance, asset quality, and data rights—and how can it prove that decision later?**

MarketBridge is well positioned to answer that question.

This framing is also faithful to the founders. Utkarsh's published goal is broad, fast global-market access; CTO Parth Maheshwari emphasizes speed and the right instruments; Chetan emphasizes simpler instruments without pretending that leverage becomes safe.[^5][^6][^21] The integration must therefore be low-latency, cross-asset in its model, and unusually clear when it restricts a user.

## Ranked integration opportunities

| Priority | Module | Problem solved | Why Mochatrade should care |
|---|---|---|---|
| P0 | Mark Integrity Gate | A venue mark can be fresh yet weakly supported, stale relative to the underlying, or based on correlated/duplicative evidence. | Prevents new exposure from being opened against an unqualified reference. |
| P0 | Exposure-Aware Order Risk Gate | The same mark anomaly has radically different consequences for a flat account and a position near liquidation. | Converts evidence into leverage/notional caps before customer harm. |
| P0 | Liquidation Passport and Replay | Users and operators need to know what evidence, policy, and position state produced a restriction or liquidation warning. | Makes disputes, incident response, and postmortems faster and defensible. |
| P1 | Asset Qualification Registry | Public equities, illiquid names, pre-IPO contracts, and corporate-action states do not deserve the same leverage or mark semantics. | Stops a single generic policy from turning weak valuation into false precision. |
| P1 | Market-Data Entitlement Registry | A technically available quote may not be licensed for non-display calculation, retention, display, or redistribution. | Prevents the safety product itself from creating a data-compliance liability. |
| P1 | Session and Corporate-Action Guard | Holidays, early closes, halts, splits, dividends, symbol changes, and IPO conversion can invalidate ordinary thresholds. | Makes “24/7” operationally honest rather than merely always online. |
| Conditional | Oracle Publisher Preflight | A deployer can validate a proposed oracle bundle before signing and publishing it. | Valuable only if Mochatrade confirms control of the relevant HIP-3 updater. |

## Recommended product contract

### 1. Pre-trade request

Add an authenticated endpoint such as:

```http
POST /v1/integrations/mochatrade/risk-check
```

```json
{
  "request_id": "ord_01J...",
  "symbol": "NVDA",
  "venue": {"dex": "confirmed-by-mochatrade", "coin": "dex:NVDA"},
  "intent": {
    "kind": "OPEN",
    "side": "BUY",
    "notional_usd": 2500,
    "requested_leverage": 10
  },
  "account": {
    "position_notional_usd": 0,
    "liquidation_price": null,
    "margin_available_usd": 500
  },
  "market": {
    "mark_price": 181.12,
    "oracle_price": 181.08,
    "mid_price": 181.10,
    "best_bid": 181.06,
    "best_ask": 181.14,
    "open_interest": 12500000,
    "event_time": "2026-09-10T12:10:03.100Z"
  }
}
```

The integration should accept the minimum customer state necessary. A public wallet address can be used for Hyperliquid read-only position queries only with explicit product/privacy approval; no private key or signing authority belongs in MarketBridge.

### 2. Pre-trade response

```json
{
  "action": "CAP_LEVERAGE",
  "max_leverage": 3,
  "max_notional_usd": 1500,
  "reduce_only_allowed": true,
  "expires_at": "2026-09-10T12:10:06.100Z",
  "reasons": ["OVERNIGHT_THIN_EVIDENCE", "LIQUIDATION_DISTANCE_LOW"],
  "confidence": 0.71,
  "passport_id": "mp_01J...",
  "policy_version": "mocha-risk-1.0.0"
}
```

Use only four externally meaningful actions:

- `ALLOW`
- `CAP_LEVERAGE`
- `BLOCK_NEW_RISK`
- `REVIEW`

The result should expire quickly—three seconds by default, never beyond the underlying evidence expiry. Re-evaluate material order changes instead of reusing a decision.

### 3. Non-negotiable safety semantics

1. **Fail closed for `OPEN` and `INCREASE`.** Missing, stale, unauthenticated, or malformed evidence cannot authorize new risk.
2. **Keep `REDUCE` and `CLOSE` available.** A degraded oracle must not trap a user in exposure. Malformed or unauthenticated requests may be rejected technically, but valid reduce-only intent is never blocked by market-risk policy.
3. **A MarketBridge `HALTED` state means block new risk inside Mochatrade.** It must never automatically call Hyperliquid `haltTrading`.
4. **Never claim that an app-level block pauses protocol liquidation.** Hyperliquid liquidations are protocol-controlled and use the mark price.[^11]
5. **Never loosen deterministic limits with AI.** Learned signals may recommend tighter limits or review, not override freshness, independence, session, entitlement, or asset rules.
6. **Separate truth from consequence.** Account exposure may tighten the action, but it cannot make weak market evidence appear more trustworthy.
7. **Keep evidence and execution authority separated.** Version one is read-only with respect to Hyperliquid and holds no customer or deployer signing key.

## Why `haltTrading` is the wrong automatic circuit breaker

Hyperliquid's HIP-3 deployer action `haltTrading` does more than pause order entry: it cancels orders and settles positions at the current mark.[^12] If the mark itself is disputed, invoking that action can crystallize the exact price the safety system distrusts.

Therefore:

```text
MarketBridge HALTED
        │
        ├──> Mochatrade: block OPEN / INCREASE
        ├──> Mochatrade: preserve REDUCE / CLOSE
        ├──> Operations: page + incident record
        └──X Hyperliquid: never auto-call haltTrading
```

Any protocol-level halt or settlement must remain a separately authorized operational decision with explicit mark review.

## Module details

### A. Mark Integrity Gate

Retain the existing MarketBridge strengths: source/provider/venue independence, freshness, bid-ask validity, session-aware thresholds, abstention, deterministic state transitions, and tamper-evident audit records.

Expand Hyperliquid ingestion beyond `markPx`. Official read interfaces expose `oraclePx`, `midPx`, open interest, funding, volume, margin context, BBO, book, and trades.[^13] Preserve each as a distinct observation; do not treat multiple fields from one venue as independent witnesses.

Decision inputs should include:

- reference-versus-mark deviation in basis points;
- mark/oracle/mid/BBO relationships;
- provider, venue, and upstream-source counts;
- source and receive timestamps, clock skew, and sequence gaps;
- spread, update age, market session, and transition proximity;
- open-interest and recent-volume context;
- asset qualification and corporate-action state;
- whether every observation is entitled for its intended use.

### B. Exposure-Aware Order Risk Gate

Read account exposure from a Mochatrade-supplied snapshot or Hyperliquid's public `clearinghouseState`, subject to product/privacy approval.[^13] Compute the proposed order's effect on liquidation distance, not merely its requested leverage.

Example policy:

| Evidence state | Flat / low risk | Existing exposure | Near liquidation |
|---|---|---|---|
| Qualified, regular session | Allow within asset cap | Allow or cap by concentration | Cap; show rupee loss and new liquidation price |
| Qualified, overnight | Lower leverage/notional cap | Tighter cap | Block new risk; preserve reduce-only |
| Guarded | Cap leverage | Block increase | Reduce-only plus warning |
| Restricted / halted | Block new risk | Block increase | Reduce-only; incident escalation |
| Missing or expired | Block new risk | Block increase | Reduce-only; fail-safe warning |

This module is the product bridge the current project lacks: the same evidence decision now produces a visible, testable customer outcome.

### C. Liquidation Passport and Replay

Extend the existing Mark Passport into a consequence receipt containing:

- request and decision IDs;
- order intent and before/after exposure, minimized or hashed where appropriate;
- market evidence identities, ages, exclusions, and content hashes;
- mark/oracle/reference values and uncertainty band;
- policy, configuration, asset-profile, and model versions;
- reason codes and allowed action;
- liquidation distance before and after the proposed order;
- predecessor hash and signed/checkpointed audit proof;
- later outcome: accepted, rejected, reduced, liquidated, reimbursed, or appealed.

Store licensed raw data only when the entitlement permits it. Otherwise retain provider record identifiers, timestamps, normalized metadata, and cryptographic hashes. The passport should prove what was evaluated without becoming an unauthorized quote redistribution channel.

The operator UI should support one-click deterministic replay under both the historical policy and a candidate policy. This turns incident response into a product feature and makes the hackathon demo memorable.

### D. Asset Qualification Registry

Create an explicit profile for every supported contract:

```yaml
symbol: NVDA
underlying_type: PUBLIC_EQUITY
reference_semantics: TRADEABLE_MARK
sessions: [REGULAR, PRE, POST, OVERNIGHT, CLOSED]
max_leverage_by_session: {REGULAR: 10, PRE: 5, POST: 5, OVERNIGHT: 3, CLOSED: 1}
required_independent_providers: 2
corporate_action_state: CLEAR
data_policy: us_equity_non_display_v1
```

Pre-IPO products need a different type and vocabulary. Coinbase's public explanation of pre-launch markets notes that such products may rely on secondary-market or model-based valuations rather than a continuously tradeable public share.[^14] Label these `VALUATION_MARK`, use lower leverage, prefer isolated margin, show wider uncertainty, and define explicit IPO conversion/rebase behavior. Do not present a model valuation as a qualified public-equity spot reference.

### E. Market-Data Entitlement Registry

For every source, record:

- license/agreement identifier and effective dates;
- allowed non-display calculation;
- allowed internal display, customer display, derived output, redistribution, and retention;
- permitted symbols/sessions/environments;
- raw-payload retention duration;
- required attribution and user classification;
- fallback behavior when entitlement is absent or expired.

The engine must exclude an otherwise good observation when its intended use is not entitled. Databento's EQUS.MINI is an aggregated derived feed whose records do not reveal the original exchange venue, so it should count as one provider witness, not several.[^15] Exchange policies also distinguish display, non-display, and automated uses.[^16]

### F. Session and Corporate-Action Guard

Replace the project's weekday/time-only phase logic with an exchange-calendar-aware state machine:

```text
REGULAR | PRE | POST | OVERNIGHT | CLOSED | EXCHANGE_HALT | CORPORATE_ACTION
```

It must support holidays, early closes, daylight-saving transitions, LULD/trading statuses, splits, reverse splits, special dividends, symbol changes, mergers, and IPO conversion. If price adjustment or contract specification is not reconciled, block new risk and permit reduction under an explicitly conservative policy.

### G. Conditional oracle-publisher preflight

Only after Mochatrade confirms its actual DEX and oracle authority, add a non-signing preflight that validates the complete proposed `setOracle` bundle: freshness, provider independence, external-perp inputs, movement/clamp headroom, open-interest stress, and liquidation exposure.[^10]

MarketBridge should return `APPROVE`, `REJECT`, or `HUMAN_REVIEW`; a separate tightly controlled signer remains responsible for publication. Public Hyperliquid DEX discovery currently does not identify a Mochatrade-named DEX, so ownership must be verified directly rather than inferred.

## Build plan mapped to this repository

### P0 — hackathon integration, 2–3 focused days

1. Add `backend/marketbridge/risk_gateway.py` as a deep module containing request normalization, intent semantics, exposure evaluation, deterministic action policy, TTL, and passport construction.
2. Add the authenticated `/v1/integrations/mochatrade/risk-check` endpoint in `backend/marketbridge/api.py`, reusing the existing HMAC timestamp/nonce/replay protection.
3. Expand the read-only Hyperliquid adapter in `backend/marketbridge/shadow.py` to retain oracle, mid, BBO, funding, open interest, volume, and receive/event times—not only the mark.
4. Connect the existing terminal order ticket to the risk-check contract in paper mode. Show requested versus permitted leverage, reason codes, evidence expiry, and “reduce-only remains available.”
5. Add a `Safety Mode` panel showing the customer impact, not just system state: order allowed/capped/blocked, liquidation-distance change, and Mark Passport link.
6. Add an SK Hynix incident scenario that sends a real mock order through the same endpoint and visibly changes its permitted outcome.

The trader-facing language should match Chetan's “better tools plus respect for risk” framing: state why leverage changed, what condition must recover, and when the decision expires. A bare confidence percentage is not an adequate explanation.[^6]

### P1 — production proposal, 1–2 weeks

1. Add exchange-calendar, halt/status, and corporate-action ingestion.
2. Add asset qualification and market-data entitlement registries with versioned policy.
3. Add opt-in position-state ingestion and account-data minimization.
4. Add durable passport indexing, policy replay, and an appeal/operator workflow.
5. Add Prometheus metrics for source age, restrictions, false-restriction duration, bypass/timeout errors, and audit write failures.
6. Run live read-only shadow mode long enough to calibrate session-specific thresholds before enforcing them.

### P2 — only after authority and legal/data diligence

1. Integrate the risk response into Mochatrade's real order router for `OPEN`/`INCREASE` enforcement.
2. Keep direct-protocol bypass visible as an explicit residual risk if customers can submit transactions outside Mochatrade.
3. Add oracle-publisher preflight only if updater ownership is confirmed.
4. Obtain written market-data permission for non-display calculation, derived decisions, customer-facing metadata, retention, and incident replay.
5. Have counsel determine the applicable India-facing derivatives, VDA, FEMA/LRS, tax, advertising, suitability, and complaint obligations. A safety passport supports compliance; it does not decide legal applicability.

## Required tests

### Deterministic policy tests

- qualified regular-session evidence allows within the asset cap;
- overnight evidence lowers leverage even when prices agree;
- stale or missing evidence blocks `OPEN` and `INCREASE`;
- `REDUCE` and `CLOSE` remain available in every market-risk state;
- a near-liquidation position tightens the action but never increases confidence;
- duplicative fields or aggregated feeds do not inflate independence;
- an expired/unentitled data source is excluded;
- an unresolved split, halt, or symbol change blocks new risk;
- AI output can tighten but never relax the deterministic result;
- no code path maps an internal halt to Hyperliquid `haltTrading`.

### Contract and resilience tests

- HMAC, clock-skew, nonce replay, request idempotency, and body canonicalization;
- decision TTL and re-evaluation after material order change;
- Hyperliquid schema fixtures, reconnect, resubscribe, and sequence gaps;
- upstream timeout and partial-source degradation;
- audit write failure fails closed for new risk;
- no signing key is loaded or requested;
- passport verification and deterministic replay parity.

### End-to-end demo tests

1. Normal NVDA evidence → 10× request allowed.
2. Overnight spread and weak independence → request capped to 3×.
3. Injected bad venue mark plus near-liquidation account → new risk blocked, reduce-only preserved, operator alert created.
4. Independent evidence recovers → state returns through a hysteresis/cooldown path, not an instant flip.
5. Passport replay shows exactly which evidence and policy changed the outcome.

## Success metrics

Do not optimize only for anomaly-detection accuracy. Measure the operational consequence:

- bad-mark exposure in basis-point-seconds;
- notional prevented from increasing during unqualified evidence;
- near-liquidation notional warned or reduced;
- time to detect, restrict, explain, and recover;
- false restriction rate and restricted-duration minutes;
- percentage of decisions with valid, replayable passports;
- stale-source and sequence-gap rates by session;
- p50/p95/p99 risk-check latency and timeout rate;
- operator override and appeal rates;
- direct-order bypass rate, if technically observable.

Suggested hackathon targets: local p95 under 50 ms after evidence is in memory, 100% deterministic replay parity, zero new-risk allows on expired evidence, and 100% valid reduce-only requests preserved by risk policy.

## What not to build

- Do not rebuild Mochatrade's exchange, matching engine, wallet, or generic trading terminal.
- Do not make an LLM the mark, the liquidation arbiter, or the policy authority.
- Do not claim multiple independent witnesses from one vendor's composite feed.
- Do not rebroadcast raw licensed equity data in a public dashboard without permission.
- Do not describe app-level restrictions as preventing Hyperliquid liquidations.
- Do not infer HIP-3 deployer/oracle ownership from public branding.
- Do not automate `haltTrading` from a disputed mark.
- Do not claim that FIU registration alone proves every derivative, foreign-exchange, tax, advertising, or suitability conclusion.

## Public trust and disclosure opportunities

Mochatrade's public materials currently contain evolving claims: the current site says up to 20× leverage, while the YC page retains older 50× language.[^1][^4] Its April 2026 public terms describe a pre-launch/waitlist service rather than detailed live-product oracle, liquidation, funding, off-hours, complaint, and appeal mechanics.[^17] The current homepage visually presents an “FIU-IND registered PDF” label, but the returned page does not expose it as a working document link.

These are not proof of wrongdoing or missing internal controls. They are concrete trust opportunities:

1. Publish versioned product disclosures and archive superseded claims.
2. Link the registration evidence the site invites users to inspect.
3. Explain mark, oracle, maintenance margin, auto square-off, funding, and overnight risk in plain language.
4. Provide a risk handbook and a passport-backed liquidation appeal process.
5. Show the rupee loss and projected liquidation price before leverage is accepted.

SEBI reported that 91% of individual traders in equity derivatives lost money in FY2024–25, with aggregate net losses above ₹1 lakh crore.[^18] Even if the precise regulatory perimeter differs, this is a powerful user-protection reason to make leverage comprehension and evidence-conditioned limits central to the product.

## Hackathon narrative

### One-sentence pitch

> MarketBridge gives Mochatrade a verifiable safety layer for 24/7 stock perps: it blocks unsupported new risk, preserves exits, and proves every decision without holding trading keys.

### Three-minute story

1. **The tension:** Mochatrade makes global, leveraged US-stock exposure available around the clock, but the underlying equity market changes quality dramatically outside regular hours.
2. **The failure:** replay the SK Hynix event and show that a technically valid input can still produce enormous liquidation consequences when source assumptions are weak.[^3]
3. **The current protection:** MarketBridge independently qualifies evidence, abstains when it cannot prove a mark, and seals a Mark Passport.
4. **The integration:** enter a 10× customer order. MarketBridge caps or blocks new risk based on session, evidence, asset policy, and liquidation distance while leaving reduce-only available.
5. **The proof:** open the passport, replay the decision, and restore service only after independent evidence and cooldown recover.
6. **The honesty:** MarketBridge governs Mochatrade's order flow today; protocol-level oracle publication is a later, authority-dependent integration.

### Why this can win

- It is attached to the host company's actual product and stated risk priorities.
- It solves a recent, high-consequence failure mode rather than inventing a hypothetical workflow.
- The core is deterministic, auditable, and demoable under failure.
- AI is used conservatively as a supporting signal rather than a theatrical safety claim.
- The same artifact supports users, risk operators, compliance review, and incident disputes.
- The roadmap is credible: read-only shadow mode first, app enforcement second, protocol interlock only with confirmed authority.

## Questions Mochatrade must answer before production

1. Which Hyperliquid DEX and coin identifiers back each product?
2. Does Mochatrade control the HIP-3 deployer, oracle updater, or a sub-deployer key?
3. Can customers bypass Mochatrade's order router and submit directly to Hyperliquid?
4. Where can an application-level gate enforce `OPEN` and `INCREASE` without delaying `REDUCE` and `CLOSE`?
5. Which position fields may MarketBridge receive, and what consent, retention, and minimization rules apply?
6. Which market-data agreements permit non-display calculation, derived decisions, UI evidence, retention, and replay?
7. What are the contract specifications and settlement/conversion rules for pre-IPO products?
8. Who owns operator overrides, protocol halt/settlement decisions, customer appeals, and reimbursements?
9. What p99 latency and availability budget can the order router allocate to a safety check?
10. Which legal entity, user disclosures, and jurisdictional controls apply to each customer flow?

None of these blocks the hackathon P0: it can run against the existing paper order flow and read-only market state. They are gates for enforcement and protocol authority.

## Final recommendation

Build the **Mark Integrity Gate + Exposure-Aware Order Risk Gate + Liquidation Passport** as one vertical slice. Make the demo prove five invariants:

1. real evidence enters the same engine used by replay;
2. weak evidence changes an actual order outcome;
3. new risk fails closed;
4. exits remain available;
5. every result can be independently replayed and verified.

That is the smallest addition that materially changes MarketBridge from “excellent safety observability” into “a Mochatrade product capability.” Asset qualification, data entitlements, corporate actions, and optional oracle preflight then deepen the same product rather than sending the team in a different direction.

## Sources

[^1]: Mochatrade, [official product site](https://www.mochatrade.com/), accessed 10 September 2026.
[^2]: ET Entrepreneur, [“Mochatrade secures pre-seed funding from Y Combinator…”](https://entrepreneur.economictimes.indiatimes.com/news/funding/mochatrade-secures-pre-seed-funding-from-y-combinator-to-transform-perpetual-trading/130855566), 6 May 2026.
[^3]: CoinDesk, [“Company Behind AI Trade That Caused $60 Million Crypto Liquidations to Cover All Losses”](https://www.coindesk.com/markets/2026/07/29/company-behind-ai-trade-that-caused-usd60-million-crypto-liquidations-to-cover-all-losses), 29 July 2026; Allium Research, [“The First Warning From 24/7 Equity Markets”](https://alliumresearch.substack.com/p/the-first-warning-from-247-equity), 2026. Reported loss and liquidation estimates vary by methodology.
[^4]: Y Combinator, [Mochatrade company profile](https://www.ycombinator.com/companies/mochatrade), accessed 10 September 2026.
[^5]: Utkarsh Sinha, [public founder announcement](https://www.linkedin.com/posts/utksn15_excited-to-announce-that-were-backed-by-y-combinator-activity-7454371499039293440-B6_R); Fondo, [START podcast episode with Mochatrade's co-founders](https://share.transistor.fm/s/a84ceecf), 12 June 2026. The public episode page provides a summary/topics but no full transcript.
[^6]: Chetan Manda, [“91% of Indian Traders Lose Money on Options. Here Is What I Think Comes Next.”](https://mochatrade.substack.com/p/91-of-indian-traders-lose-money-on), 13 July 2026.
[^7]: Mochatrade, [public hiring announcement](https://www.linkedin.com/posts/mochatrade_join-us-as-we-make-global-market-access-seamless-activity-7476147093665968128-XANL), 26 June 2026.
[^8]: FINRA, [“Extended-Hours Trading: Know the Risks”](https://www.finra.org/investors/insights/extended-hours-trading).
[^9]: Hyperliquid, [Oracle documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle) and [Robust Price Indices](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices).
[^10]: Hyperliquid, [HIP-3 Builder-Deployed Perpetuals](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals) and [`setOracle` deployer actions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions).
[^11]: Hyperliquid, [Liquidations](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations).
[^12]: Hyperliquid, [HIP-3 deployer actions: `haltTrading`](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions).
[^13]: Hyperliquid, [Perpetual Info endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals) and [WebSocket subscriptions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions).
[^14]: Coinbase International Exchange, [“What are pre-launch markets?”](https://help.coinbase.com/en/international-exchange/pre-ipo-markets/what-are-pre-ipo-perpetual-futures).
[^15]: Databento, [US Equities Mini dataset specification](https://databento.com/docs/venues-and-datasets/equs-mini).
[^16]: NYSE, [Non-Display Use Policy](https://www.nyse.com/publicdocs/nyse/data/Non-Display_Use_Policy.pdf); Nasdaq UTP, [current consolidated data plan](https://www.utpplan.com/DOC/Nasdaq-UTP%20Plan%20after%2035th%20Amendment%20-%20Excluding%2021st%20Amendment%20-%20i.e.%20Effective%20Plan%20as%20of%209-151.pdf).
[^17]: Mochatrade, [Terms of Service](https://www.mochatrade.com/terms), updated 27 April 2026.
[^18]: SEBI, [Study on individual traders in the equity derivatives segment, FY2024–25](https://www.sebi.gov.in/sebi_data/attachdocs/jul-2025/1751900271726.pdf), July 2025.
[^19]: Mochatrade, [“The London Stock Exchange Is Moving Toward 24-Hour Trading. Are Markets Becoming 24/7?”](https://mochatrade.substack.com/p/the-london-stock-exchange-is-moving), 22 July 2026.
[^20]: Mochatrade, [“Volume: The One Number That Tells You If a Move Is Real”](https://mochatrade.substack.com/p/volume-the-one-number-that-tells), 26 July 2026.
[^21]: Parth Maheshwari, [public YC announcement](https://www.linkedin.com/posts/parthm1801_excited-to-share-that-were-backed-by-y-combinator-activity-7447133638141595648-KFd5), 7 April 2026.

### Evidence limitations

Public websites, profiles, hiring posts, interviews, and press coverage show stated priorities, not private architecture or proof of an unsolved internal failure. LinkedIn pages can change or be access-limited. Market-data rights are contract-specific and require written confirmation. Legal and tax applicability require qualified counsel. Hyperliquid protocol behavior cited here is based on its public documentation; production integration must pin schemas and verify current behavior in testnet/shadow mode before enforcement.
