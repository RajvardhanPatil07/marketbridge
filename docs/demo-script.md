# 90-second MarketBridge demo

Run `make demo`, open [http://localhost:8000](http://localhost:8000), and confirm `make verify` passes before presenting. The safety lab is synthetic, the incident is a sourced reconstruction, and every MarketBridge output is advisory only.

| Time | Action | Say |
| --- | --- | --- |
| 0:00–0:12 | Stay on **Safety lab** and point to the headline. | “US stocks close, but leveraged perpetuals keep trading. A weak off-hours print can become a liquidation price before the cash market can correct it.” |
| 0:12–0:32 | Select **Watch the failure point**. Point to the unguarded feed at $138.84, the unavailable MarketBridge reference, and blocked exposure. | “At second 24, one unsupported 24% print hits the system. The naive feed accepts it. MarketBridge refuses to call it a price, marks valuation unresolved, and blocks new exposure.” |
| 0:32–0:44 | Show **Operator decision output** and copy the payload. | “This is not just a chart. The same deterministic decision is available to a risk engine: no reference, one independent family, zero advisory exposure, and machine-readable reasons.” |
| 0:44–1:05 | Open **Real incident**. Point to 1 share, −18.7%, ~$60M, then the reconstructed chart. | “This failure mode is real. In July 2026, a single thin-market SK Hynix print preceded an 18.7% reported perpetual-mark move and roughly $60 million of long liquidations. These are sourced observations; our advisory is clearly counterfactual.” |
| 1:05–1:22 | Open **Evaluation** and point to the policy benchmark. | “On identical synthetic truth, the unguarded policy reaches a 2,400-basis-point worst error. MarketBridge cuts that to 0.2 basis points by sacrificing 1.64% availability. We report the tradeoff, not a magic accuracy claim.” |
| 1:22–1:30 | Return to the key takeaway. | “MarketBridge is an evidence firewall between fragile off-hours data and leveraged risk. The next integration is live provider adapters and a venue oracle shadow mode—not customer execution.” |

## Judge questions

- **Is the incident proof that MarketBridge would have prevented the losses?** No. It proves the failure mode occurred; the MarketBridge response is a transparent counterfactual.
- **Why not hold the last price?** A stale value may be useful context, but presenting it as current hides uncertainty. The API returns `reference: null` and keeps `last_valid` separate.
- **What happens on a genuine move?** The corroborated-repricing scenario abstains briefly, then accepts the move after a second original source family confirms it.
- **Is this production ready?** No. It needs licensed live feeds, calibrated thresholds, shadow-mode validation, venue-specific oracle integration, monitoring, and security review.

## Optional live proof

Before or after the timed pitch, open **Live research**. Point out the provider strip, p50/p95 decision latency, actual Yahoo event age and session audit log. If the market is closed, explain that stale evidence is the correct real-world state—not a broken feed. Select TSLA and press **Refresh research feed** to demonstrate the browser, event stream, FastAPI pipeline and yfinance adapter end to end. Alpaca should say Disabled until credentials are configured, and Mochatrade should say Waiting until a mark is posted. Do not describe Yahoo research data as an official SIP feed or a liquidation reference.

## Local fallback

If the UI is unavailable, export the exact deterministic evidence:

```sh
make evaluate
SCENARIO=bad-print SYMBOL=NVDA make replay
```

Present exported scenario data as `SYNTHETIC_TEST`; do not describe synthetic paper outcomes as prevented customer losses.
