# Mochatrade pre-trade integration

MarketBridge is designed to sit immediately before a leveraged order is accepted by the host product.

Flow: Mochatrade order snapshot → POST /v1/integrations/mochatrade/risk-check → ALLOW / CAP_LEVERAGE / REVIEW / BLOCK_NEW_RISK → Safety Passport → broker-owned execution.

REDUCE and CLOSE remain available during degraded market evidence when the request is otherwise valid.

## Host rules

- ALLOW: proceed only before expires_at.
- CAP_LEVERAGE: apply the returned safe alternative; if material fields change, obtain a fresh check.
- REVIEW: route to the host secondary/manual policy.
- BLOCK_NEW_RISK: prevent open/increase; do not disable a valid exit.
- Bind passport_id to the exact checked order.
- Reject expired decisions.

## Authentication

Remote integrations should configure MOCHATRADE_HMAC_SECRET. Signed requests use timestamp, nonce, and HMAC headers; the server rejects clock-skewed signatures and nonce replay.

## Execution boundary

This repository deliberately does not contain a broker signing key or live order router. Execution, compliance, custody, customer permissions, and idempotency remain broker-owned.

See examples/mochatrade-pretrade.ts for a host-side reference.