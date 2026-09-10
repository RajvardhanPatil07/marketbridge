# Safety Passport

Every risk check issues `marketbridge-safety-passport-v1` with:

- identity: opaque passport/request IDs, timestamp, symbol;
- order: intent, side, requested and permitted leverage/notional;
- account: minimized exposure, calculated leverage/liquidation distance, classification;
- market/evidence: immutable Market Truth, witness families, freshness, observation hashes;
- policy: risk, asset, model, data, and entitlement versions;
- decision: action, reason codes, expiry, TTL, exit availability;
- provenance: SHA-256 content hash, predecessor hash, and chain hash;
- optional post-decision outcome annotation.

Canonical JSON sorts object keys and uses compact separators. `content_hash` seals the claims.
`chain_hash` seals `{scope, sequence, previous_hash, content_hash}`. Verification recomputes both.
Changing any original claim fails verification. Outcome is stored outside immutable decision claims.

The in-process store is intentionally a prototype. A multi-instance deployment needs an append-only,
transactional shared store for chain heads, idempotency records, and outcomes.
