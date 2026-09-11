# Proof and evaluation

## Historical reconstruction

Endpoint: GET /v1/proof/historical

The proof surface replays the published July 2026 SK Hynix / TradeXYZ observations already stored in backend/marketbridge/incidents.py.

Every observation is passed to the same deterministic consequence function used by the live order gate: marketbridge.risk.policy.decide.

The decision does not consume a future price or future outcome.

This is intentionally labeled HISTORICAL_RECONSTRUCTION. It is not a licensed consolidated feed or a certified exchange replay. The published reconstruction exposes one external handoff family plus venue oracle/mark values; because the venue cannot validate itself, the gate has insufficient independent evidence and fails closed for new risk. This is counterfactual and does not prove avoided losses.

## Labeled operating benchmark

Endpoint: GET /v1/proof/benchmark

Default suite: 9 categories × 50 cases = 450 deterministic cases.

It covers normal qualified markets, independently confirmed large moves, overnight restrictions, stale evidence, insufficient source independence, correlated vendor labels, poisoned marks, recovery-pending state, and portfolio concentration.

The positive class means the order should be restricted with CAP_LEVERAGE, REVIEW, or BLOCK_NEW_RISK.

The endpoint reports TP/TN/FP/FN, false-positive rate, false-negative rate, precision, recall, accuracy, core-policy p50/p95/p99, and in-process gateway p50/p95/p99. Latency is measured when the endpoint runs.

The suite is explicitly SYNTHETIC_LABELED_BENCHMARK, not a historical-market backtest.

## Portfolio proof

Endpoint: GET /v1/proof/portfolio

This calls the normal RiskGateway with a synthetic account portfolio. Even with qualified Market Truth, the proposed order can be capped by session, account, single-name, sector, and correlated risk-bucket constraints. The response includes a computed safe alternative and a normal Safety Passport.