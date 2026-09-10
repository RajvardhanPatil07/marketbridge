# Deterministic replay

`POST /v1/replay/risk-decision` accepts a passport ID and `ORIGINAL`, `CURRENT`,
`mocha-risk-v1.0.0`, or `WITHOUT_SAFETY_GATE`.

Original/current replay uses the recorded normalized request, immutable Market Truth, asset policy,
and deterministic policy code. It reports action, permitted leverage/notional, reason differences,
and replay parity. Expired decisions may be replayed for audit but cannot be reused for execution.

`WITHOUT_SAFETY_GATE` is explicitly a counterfactual simulation. It assumes the requested order was
permitted and reports prevented additional simulated exposure. It does not claim a fill, money saved,
or what Mochatrade would historically have executed.
