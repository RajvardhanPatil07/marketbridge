# Adversarial threat model

MarketBridge assumes an attacker can observe the safety policy and deliberately shape inputs around it. The goal is not to claim perfect oracle security; it is to make trust assumptions explicit, fail closed for new exposure when evidence is not qualified, preserve valid exits, and make decisions replayable.

| Threat | Naive failure | MarketBridge v1 response | Remaining limitation |
|---|---|---|---|
| Single-feed poison | Trust one number | Minimum independent provider-family requirement | Independence metadata must stay correct |
| Correlated providers | Count two vendor names as two votes | Count source/upstream families, not labels | Upstream lineage can be commercially opaque |
| Slow-drift poisoning | Stay below one large per-tick threshold | Preserve state/hysteresis and inspect divergence over time | Dedicated cumulative-drift detector is still a production work item |
| Stale but plausible price | Old value looks normal | Event/receipt time and freshness qualification | Clock quality and upstream timestamps matter |
| Genuine news/earnings move | Treat every large move as manipulation | Independently confirmed repricing can remain qualified; context may tighten but never create truth | v1 evaluation is not a complete historical event corpus |
| Recovery spoof | One clean tick restores leverage | Multiple stable observations plus minimum recovery duration | Production thresholds need real venue calibration |
| Passport replay | Reuse an old allow decision | Short TTL, request fingerprint, policy version, nonce/HMAC support | Host must enforce expiry and request binding |
| Request tamper | Change order after checking it | Canonical request hash in Safety Passport | Host must attach passport to exact order |
| Malformed/crossed market | Garbage reaches policy | Strict schema rejects crossed BBO and malformed fields | Semantically wrong but plausible upstream data is harder |
| Entitlement failure | Use data outside permitted role | Entitlement policy participates in qualification | Commercial terms still need deployment review |
| Venue self-validation | Venue oracle/mark proves itself | Venue values are comparison targets, not independent truth votes | External evidence is required |
| LLM override | Narrative model loosens controls | AI may tighten only; risk-critical path has zero LLM calls | Future AI work must preserve this invariant |

## Slow-drift attack

A sophisticated attacker may move a venue mark gradually: 184.00 → 184.25 → 184.55 → 184.90 → 185.25.

A production version should track cumulative divergence over rolling windows, source-family changes, reference volatility, and rate-of-change consistency. v1 documents this as a known limitation rather than claiming it is already solved.

## Why recovery is sticky

A single good observation can be spoofed or transient. The hackathon policy therefore requires repeated stable observations after a restricted state. The current demo uses three observations and a short minimum duration so the behavior is visible during judging; production values require calibration on real distributions.

## Why provider count is not consensus

Two provider names can relay the same underlying venue or tape. MarketBridge models provider/source family separately from raw vendor count so correlated evidence does not become fake quorum.

## Security boundary

MarketBridge holds no custody key, exchange signing key, or liquidation authority. The broker/venue remains responsible for execution, permissions, compliance, and idempotent routing.