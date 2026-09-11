# Proof and evaluation

## Historical reconstruction

Endpoint: `GET /v1/proof/historical`

The proof surface replays the published July 2026 SK Hynix / TradeXYZ observations already stored in `backend/marketbridge/incidents.py`.

Every observation is passed to the same deterministic consequence function used by the live order gate: `marketbridge.risk.policy.decide`.

The decision does not consume a future price or future outcome.

This is intentionally labeled `HISTORICAL_RECONSTRUCTION`. It is not a licensed consolidated feed or a certified exchange replay. The published reconstruction exposes one external handoff family plus venue oracle/mark values; because the venue cannot validate itself, the gate has insufficient independent evidence and fails closed for new risk. This is counterfactual and does not prove avoided losses.

## Seeded policy-regression benchmark

Endpoint: `GET /v1/proof/benchmark?cases=2000&seed=20260911`

The benchmark generates a reproducible but varied state space instead of repeating copies of a handful of fixtures. The seed is returned with the result.

Inputs vary across:

- supported symbols;
- regular, pre/post, overnight and closed sessions;
- reference prices and venue divergence;
- fresh vs stale evidence;
- zero, one, two and three independent provider families;
- correlated provider labels that still count as one independent family;
- requested notional and leverage;
- account equity and existing exposure;
- parameterized portfolio-concentration cases;
- halted and recovery-pending market states.

This is a **deterministic policy regression**, not a classifier-accuracy benchmark. It therefore does not advertise self-generated precision/recall. Instead the endpoint reports:

- action distribution: `ALLOW`, `CAP_LEVERAGE`, `REVIEW`, `BLOCK_NEW_RISK`;
- scenario-coverage counts;
- safety-invariant violations, including stale evidence accepted, insufficient independence accepted, halted markets accepted, correlated sources miscounted and valid exits blocked;
- core-policy and in-process gateway p50/p95/p99 latency measured when the endpoint runs.

The suite is explicitly `SYNTHETIC_POLICY_REGRESSION`, not a historical-market backtest.

## Portfolio proof

Endpoints:

- `GET /v1/proof/portfolio` — default parameterized fixture.
- `POST /v1/proof/portfolio` — editable symbol, requested notional, leverage, account equity and existing exposure.

The portfolio surface calls the normal `RiskGateway`. The portfolio composition is a transparent synthetic fixture scaled from the submitted inputs. Even with qualified Market Truth, the proposed order can be capped by session, account, single-name, sector and correlated risk-bucket constraints.

The response includes the computed safe alternative and a normal Safety Passport. Changing the inputs recomputes the result; the displayed cap is not a stored screenshot value.

## War Room provenance

`POST /v1/demo/war-room` accepts:

- symbol;
- requested notional;
- leverage;
- account equity;
- existing position;
- attack magnitude in basis points;
- evidence mode: `AUTO`, `LIVE` or `SYNTHETIC`.

`AUTO` uses a currently `QUALIFIED` live reference only when the configured independent-provider quorum is actually present. Otherwise it falls back to a clearly labelled synthetic fixture seeded from the current display snapshot.

Synthetic witnesses are named `Synthetic Witness A` and `Synthetic Witness B`. They never borrow the name of Alpaca, Twelve Data or another real provider. Every evidence row exposes its source mode, observed price, timestamp, freshness and eligibility.
