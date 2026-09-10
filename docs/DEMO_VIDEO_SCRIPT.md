# 90-second judge demo recording script

Use the deployed `/demo/` page. Keep the historical proof visible before the synthetic attack.

## 0–15s — Problem

“US stocks sleep, but equity perpetuals keep trading. MarketBridge asks whether the market price deserves enough trust before leverage is allowed to act.”

Show the architecture line: Market Truth → Portfolio Risk → Safe Action → Verifiable Proof.

## 15–32s — Real-world proof

Show the SK Hynix / TradeXYZ historical reconstruction.

“This is a published historical reconstruction, not synthetic attack data. These observations go through the same deterministic consequence function as the live gate, with no future outcome used by the decision. Because the handoff exposes only one independent external family, MarketBridge fails closed for new leverage instead of letting the venue validate itself.”

## 32–45s — Operating characteristics

Show the benchmark card.

“We measure the gate instead of just claiming it works: false positives, false negatives, precision, recall, and p50/p95/p99 decision latency. The benchmark is explicitly labeled synthetic and the timing numbers are measured in the running process.”

## 45–58s — Portfolio risk

Show requested 10×/$10k versus the safe alternative.

“Even a trustworthy price does not mean this portfolio should take the full risk. MarketBridge checks account and concentration risk and returns the maximum safe leverage and notional.”

## 58–78s — Controlled attack

Run Normal market, then Poison venue mark.

“Now we deliberately poison the venue mark. Independent evidence stays near the reference while the venue diverges. New risk is blocked, but the exit path stays open.”

Click Prove exit stays open.

## 78–87s — Proof

Open/show the Safety Passport and replay-without-gate result.

“Every consequential decision is fingerprinted with the evidence, policy version, expiry, and request. The same inputs replay to the same decision.”

## 87–90s — Close

“Trading AIs predict where markets go. MarketBridge decides whether the market and portfolio deserve leverage in the first place — and proves why.”

## Recording rules

- Keep `HISTORICAL_RECONSTRUCTION` and `SYNTHETIC_DEMO` labels visible.
- Do not claim a live trade was submitted.
- Do not claim prevented exposure equals guaranteed cash savings.
- Do not quote benchmark latency from memory; show the measured value on screen.