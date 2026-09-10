# Verification log

No paid-provider credentials were available during this upgrade, so no entry claims a live
entitlement test.

| Date | Status | Claim tested | Method | Observed behavior | Impact / limitation |
|---|---|---|---|---|---|
| 2026-09-10 | OBSERVED | Risk gate invariants | 22 focused pytest cases | Actions, exits, expiry, HMAC, passports, replay, hysteresis passed | Deterministic CI only |
| 2026-09-10 | OBSERVED | Integrated backend | Full pytest suite | 165 tests passed | No provider network required |
| 2026-09-10 | DOCUMENTED | Alpaca pagination/corrections | Adapter and deterministic mocks | Pagination, retry, cache, corrected-bar reconciliation represented | Live behavior UNKNOWN |
| 2026-09-10 | DOCUMENTED | Databento independence | Adapter schema/tests | EQUS.MINI composite remains one witness | Contractual rights UNKNOWN |
| 2026-09-10 | OBSERVED | Twelve Data normalization | Deterministic stream-event tests | Subscription, timestamp, price, independence, and entitlement failure paths passed | Live account behavior UNKNOWN |
| 2026-09-10 | DOCUMENTED | Hyperliquid context | Read-only adapter inspection | mark/oracle/mid/BBO/OI/funding/volume/trades normalized | Live schema/reconnect UNKNOWN |
| 2026-09-10 | OBSERVED | Calendar prototype | timezone/holiday/weekend tests | Configured cases classify as expected | Future calendar updates ASSUMED |

Remaining UNKNOWN: Alpaca SIP/overnight entitlements, Twelve Data symbol/display entitlements,
Databento retention/redistribution/replay terms, live Hyperliquid schema drift/sequence behavior,
corporate-action provider coverage, and exact Mochatrade/Hyperliquid maintenance-margin mechanics.

The Railway Dockerfile was inspected and updated to copy runtime policy/model artifacts. An image
build was attempted on 2026-09-10 but the local Colima/Docker daemon was unavailable, so image
construction remains UNVERIFIED. The optimized Next.js build and FastAPI-served E2E bundle passed.
