# Judge demo — Market Truth War Room

## Run

```bash
make setup
make demo
```

Open:

```text
http://127.0.0.1:8000/demo/
```

The War Room requires no market-data key. It is a deterministic `SYNTHETIC_DEMO` that exercises the same `RiskGateway`, policy and Safety Passport implementation as the integration path.

## 90–150 second pitch

### 0–15s — problem

> US stocks sleep. Equity perpetuals don't. A 24/7 leveraged venue can keep trading while the underlying stock has weak or closed price discovery. MarketBridge verifies the market before leverage acts on it.

### 15–35s — normal

Click **1 · Normal market**.

Point out:

- two visibly synthetic independent evidence witnesses;
- Market Truth around the fixture reference;
- venue mark almost equal to the reference;
- 10× / $10,000 OPEN → `ALLOW`.

### 35–65s — attack

Click **2 · Poison venue mark**.

The venue mark moves roughly 300 bps away while the independent evidence stays stable.

Point to the visual flow:

```text
WITNESS A ──┐
            ├── MARKET TRUTH ── vs ── POISONED VENUE MARK
WITNESS B ──┘                              │
                                           ▼
                                  BLOCK NEW RISK
```

Say:

> We did not ask AI whether this looks scary. A deterministic market-integrity policy sees that the leveraged venue mark no longer agrees with the independent reference and fails new risk closed.

### 65–80s — exit invariant

Click **3 · Prove exit stays open**.

The same poisoned market now receives a `CLOSE` intent and returns `ALLOW`.

Say:

> MarketBridge does not trap the customer. Valid reduce and close paths survive evidence degradation; only new/increased exposure is blocked.

### 80–105s — proof

Show the Safety Passport:

- passport ID;
- policy version;
- expiry;
- evidence count;
- hash fingerprint.

Say:

> The decision is not just a dashboard warning. It is a short-lived, replayable receipt of what the system knew and what policy acted on it.

### 105–125s — counterfactual

Return to the poisoned OPEN scenario if needed and click **Replay without safety gate**.

The comparison must be described as:

> additional **simulated** exposure prevented

Never say guaranteed savings, avoided loss or a fill that did not occur.

### 125–150s — recovery

Click **4 · Recover safely**.

The UI makes repeated stable checks so recovery passes through `RECOVERY_PENDING` rather than flipping instantly after one good observation.

Say:

> One clean tick is not enough to turn leverage back on after a market-integrity incident. Recovery is deliberately sticky.

## Optional technical follow-up

Open `/providers/`:

> The hackathon build is free-first. Alpaca/IEX is the free underlying stream, Hyperliquid is venue context, and news/SEC are a separate context plane. The architecture is provider-agnostic, so a venue can replace adapters with its licensed feeds without rewriting the risk gate.

Open `/intelligence/`:

> This is news plus primary-source SEC context, and notice the boundary: it explicitly cannot change Market Truth.

## Judge questions

### Why not simply average two APIs?

Provider count is not automatically infrastructure independence. MarketBridge tracks provider family and venue family separately and refuses to turn duplicated/correlated delivery into fake confidence.

### Why synthetic attack data?

A deterministic adversarial fixture makes the hackathon demonstration reproducible, works without paid market licenses, and is visibly labelled. Live data remains available separately when credentials/rights exist.

### Why is AI not deciding?

The model can estimate or tighten a risk posture, but direct consensus outranks learned estimates and AI can never loosen deterministic controls.

### What happens if data disappears?

The system exposes insufficient evidence instead of inventing a reference. Valid exits remain available; new risk fails closed according to policy.
