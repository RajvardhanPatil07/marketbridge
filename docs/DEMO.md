# Deterministic demo

```bash
make setup
make demo
```

Open `http://127.0.0.1:8000/terminal/`.

1. Keep `NORMAL`, `OPEN`, NVDA, $10,000, and 10x. Press **CHECK ORDER**: `ALLOW`.
2. Select `POISONED MARK`; the venue becomes $190.20 while two synthetic observations remain
   $184.50/$184.54. Press **CHECK ORDER**: `BLOCK NEW RISK`.
3. Change intent to `CLOSE` and check: `ALLOW`; reduce/close stays available.
4. Open the Safety Passport; inspect the order, market, consequence, action, and hash chain.
5. Run **Replay without gate**, then **Replay current**.
6. Return to `OPEN`, select `RECOVERY`, and check: `RECOVERY_PENDING`, not normal.

All values are labelled `SYNTHETIC_DEMO`. No trade is submitted. For a public hosted demo, set
`MARKETBRIDGE_ENABLE_PUBLIC_DEMO=1`; this exception applies only to an allowed synthetic scenario.
Live/shadow checks and mark ingestion remain signed.
