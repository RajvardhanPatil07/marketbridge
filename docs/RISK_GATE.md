# Order Risk Gate

`POST /v1/integrations/mochatrade/risk-check` validates a strict request, authenticates live
integration traffic, reads current Market Truth, calculates account consequence, and returns a
3-second advisory action plus a Safety Passport.

Primary actions are only `ALLOW`, `CAP_LEVERAGE`, `BLOCK_NEW_RISK`, and `REVIEW`.

| Condition | OPEN / INCREASE | REDUCE / CLOSE |
|---|---|---|
| Qualified, fresh, entitled, independent, within limits | ALLOW | ALLOW |
| Requested leverage/notional exceeds session or account capacity | CAP_LEVERAGE | ALLOW |
| Consequence cannot be resolved safely | REVIEW | ALLOW |
| Missing/stale/non-qualified/unauthenticated/unentitled evidence | BLOCK_NEW_RISK | ALLOW |
| RESTRICTED, HALTED, recovery pending, or unresolved corporate action | BLOCK_NEW_RISK | ALLOW |
| Liquidation distance below 2% (prototype threshold) | BLOCK_NEW_RISK | ALLOW |

Prototype session caps are versioned in `config/assets.yaml`: regular 10x, pre/post 5x,
overnight 3x, closed 1x, exchange halt/corporate action 0x. These are not claimed to be Mochatrade
or Hyperliquid production margin rules.

`current_leverage = existing_notional / equity` when not supplied.
`projected_leverage = (existing_notional + requested_new_notional) / equity`.
Liquidation distance is `abs(reference - liquidation_price) / reference * 100`. It is an explicit
paper/advisory distance measure, isolated from any undocumented exchange maintenance-margin model.

The maximum permitted new notional is the minimum of requested notional, available margin times
the applicable cap, and remaining account exposure room. Decimal arithmetic is used through policy
evaluation and rounded down to cents.

AI may only select an action with a higher restriction rank:
`ALLOW < CAP_LEVERAGE < REVIEW < BLOCK_NEW_RISK`.

## Request contract

```json
{
  "request_id": "ord_01J...",
  "symbol": "NVDA",
  "intent": {"kind": "OPEN", "side": "BUY", "notional_usd": 10000, "requested_leverage": 10},
  "account": {"equity_usd": 2000, "margin_available_usd": 500, "position_notional_usd": 14000, "liquidation_price": 176.25, "current_leverage": 7, "position_side": "BUY"},
  "market": {"mark_price": 184.61, "oracle_price": 184.52, "mid_price": 184.56, "best_bid": 184.51, "best_ask": 184.60, "open_interest": 12500000, "funding": 0.0001, "volume": 8000000, "event_time": "2026-09-10T10:00:00Z", "session": "REGULAR"}
}
```

`demo_scenario` is optional and accepts only `NORMAL`, `POISONED_MARK`, or `RECOVERY`. It is
synthetic fixture selection, never live evidence. Unknown fields are rejected. Monetary fields have
positive/bounded decimal constraints; books cannot be crossed; timestamps must be timezone-aware.

## Response contract

```json
{
  "action": "CAP_LEVERAGE",
  "requested_leverage": 10,
  "permitted_leverage": 3,
  "requested_notional_usd": 10000,
  "permitted_notional_usd": 3000,
  "market": {"reference_price": 184.52, "venue_mark": 184.61, "divergence_bps": 4.9, "confidence": 0.74, "reference_status": "QUALIFIED", "provider_count": 2, "venue_count": 2, "session": "OVERNIGHT", "asset_state": "NORMAL"},
  "account_risk": {"liquidation_distance_pct": 4.5, "existing_exposure_usd": 14000, "risk_classification": "ELEVATED"},
  "reasons": ["OVERNIGHT_SESSION", "EXISTING_EXPOSURE"],
  "reduce_only_allowed": true,
  "expires_at": "2026-09-10T10:00:03Z",
  "ttl_ms": 3000,
  "passport_id": "mbp_...",
  "policy_version": "mocha-risk-v1.0.0",
  "passport": {"version": "marketbridge-safety-passport-v1"}
}
```
