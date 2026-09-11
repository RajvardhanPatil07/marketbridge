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

The War Room uses the same `RiskGateway`, policy and Safety Passport implementation as the integration path.

It has three evidence modes:

- **AUTO** — use a genuinely qualified live reference if the independent-provider quorum exists; otherwise use a clearly labelled synthetic fixture.
- **LIVE** — require a qualified live reference or return an explicit error.
- **SYNTHETIC** — force the parameterized synthetic fixture.

No synthetic evidence is presented under a real provider's name.

## 90–150 second pitch

### 0–15s — problem

> US stocks sleep. Equity perpetuals don't. A 24/7 leveraged venue can keep trading while the underlying stock has weak or closed price discovery. MarketBridge verifies the market before leverage acts on it.

### 15–30s — prove the inputs are real inputs

Before clicking the scenario buttons, change at least two controls:

- symbol;
- requested notional;
- leverage;
- attack bps;
- account equity;
- existing exposure.

Point out the **DATA MODE**, **BASELINE SOURCE** and **DISPLAY BASELINE** fields.

Say:

> These numbers are inputs, not a prepared screenshot. Every click recomputes the decision through the same risk gateway.

### 30–50s — normal

Click **1 · Normal market**.

Point out:

- the explicit live/synthetic mode;
- the evidence provider identities;
- observed price and evidence age;
- Market Truth and venue mark;
- the recomputed order decision.

If AUTO falls back to synthetic mode, say so explicitly. That is expected when a two-family live quorum is unavailable.

### 50–75s — attack

Choose an attack magnitude, then click **2 · Poison venue mark**.

The venue mark is calculated from the current scenario baseline and the selected basis-point attack.

Say:

> We did not ask AI whether this looks scary. The venue mark is compared against independently qualified Market Truth, and the deterministic consequence policy decides whether new risk may proceed.

### 75–90s — exit invariant

Click **3 · Prove exit stays open**.

The same degraded market receives a `CLOSE` intent and should return `ALLOW`.

Say:

> MarketBridge does not trap the customer. Valid reduce and close paths survive evidence degradation; only new or increased exposure is restricted.

### 90–110s — proof

Show the Safety Passport:

- passport ID;
- policy version;
- expiry;
- evidence count;
- hash fingerprint.

Say:

> The decision is not just a dashboard warning. It is a short-lived, replayable receipt of what the system knew and what policy acted on it.

### 110–130s — counterfactual

Return to a restricted OPEN scenario and click **Replay without safety gate**.

Describe the result only as:

> additional **simulated** exposure prevented

Never say guaranteed savings, avoided loss or a fill that did not occur.

### 130–150s — recovery

Click **4 · Recover safely**.

The UI makes repeated stable checks so recovery passes through `RECOVERY_PENDING` rather than flipping instantly after one good observation.

Say:

> One clean tick is not enough to turn leverage back on after a market-integrity incident. Recovery is deliberately sticky.

## Proof-first technical follow-up

At the top of `/demo/`, show the **seeded policy regression**:

- varied cases, not 50 copies of the same scenario;
- reported random seed;
- action distribution;
- invariant violations;
- measured p50/p95/p99;
- coverage counts.

Then change the **Portfolio Risk Firewall** inputs and click **Recompute risk**. The safe notional and leverage should change.

Open `/providers/`:

> Supported capability, configuration and observed health are separate. An unprobed adapter is not labelled READY.

Open `/intelligence/`:

> This is news plus primary-source SEC context, and notice the boundary: it explicitly cannot change Market Truth.

## Judge questions

### Why not simply average two APIs?

Provider count is not automatically infrastructure independence. MarketBridge tracks provider family and venue family separately and refuses to turn duplicated or correlated delivery into fake confidence.

### Why keep synthetic mode?

A deterministic adversarial fixture makes the attack reproducible and works without paid market licences. The fixture is visibly labelled, parameterized, and uses generic witness identities. AUTO/LIVE can use qualified runtime evidence when it really exists.

### Why is AI not deciding?

The model can estimate or tighten a risk posture, but direct consensus outranks learned estimates and AI can never loosen deterministic controls.

### What happens if data disappears?

The system exposes insufficient evidence instead of inventing a reference. Valid exits remain available; new risk fails closed according to policy.
