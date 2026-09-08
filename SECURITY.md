# Security policy

MarketBridge is an **advisory-only** hackathon system. It reads market data and returns risk recommendations. It does not hold funds, sign exchange transactions, place orders, or liquidate accounts.

## Important rules

- Never commit `.env`, `.env.local`, API keys, tokens, wallet keys, or provider secrets.
- Keep Alpaca and integration secrets on the backend only.
- Prefer `MOCHATRADE_HMAC_SECRET` over a shared plaintext API key.
- Signed requests use a timestamp, nonce, and HMAC-SHA256 signature. Old timestamps and reused nonces are rejected.
- CORS and WebSocket origins should be restricted with `MARKETBRIDGE_ALLOWED_ORIGINS` in production.
- Remote market ingestion is disabled unless authentication is configured.
- MarketBridge validates price ranges, timestamps, symbols, and request rates before a venue mark reaches the risk engine.
- Audit persistence is asynchronous so a slow disk does not block pricing decisions.

## Secrets found in older project archives

The original hackathon archive contained a local Vercel credential file. This cleaned repository does **not** include that file. Any credential that was exposed in a shared ZIP should be rotated/revoked before deployment.

## Production note

The prototype rate limiter and nonce cache are process-local. A multi-instance production deployment should move shared replay/rate state to a suitable centralized service or enforce it at the gateway/WAF layer.
