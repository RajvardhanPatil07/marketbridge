# MarketBridge AI / ML layer

## Design rule

**AI estimates uncertainty; deterministic controls keep authority.**

MarketBridge applies the layers in this order:

1. Normalize and timestamp market observations.
2. Require fresh, independent venue evidence for a `QUALIFIED` reference.
3. If direct evidence is insufficient, optionally use a learned fair-value model as an explicitly `ESTIMATED` fallback.
4. Compare the venue mark with the independent/estimated reference and compute an anomaly probability.
5. Apply deterministic risk thresholds. A historically calibrated AI anomaly signal may tighten risk, but it cannot loosen risk or validate an isolated venue mark.

## Fair-value model

The trainer compares two dependency-light models for every stock:

- Ridge regression.
- Gradient-boosted regression stumps.

The lower validation-MAE model is exported for each symbol. Runtime inference reads a small JSON bundle and does not require scikit-learn.

Current features:

- QQQ return since the last trusted stock anchor.
- SPY return since the last trusted stock anchor.
- SOXX return since the last trusted stock anchor.
- Surviving single-source stock return, when available.
- Minutes since the trusted anchor.
- Source event age.
- Independent provider count.
- Independent venue count.

The learned model never turns its own `ESTIMATED` output into a trusted anchor. Only direct qualified evidence can reset anchors.

## Anomaly model

A logistic classifier estimates the probability that the trading venue mark is anomalous using:

- Venue-mark divergence from the MarketBridge reference.
- Cross-source dispersion.
- Source age.
- Provider independence.
- Venue independence.
- Whether the reference itself is estimated.

The critical training regime includes an **isolated bad venue mark while healthy independent feeds agree**, which is the failure mode MarketBridge is designed to catch.

## Provenance

The checked-in bundle is labelled `SYNTHETIC_CALIBRATION_DEMO`. It makes the complete AI path reproducible without licensed data but must not be presented as historical performance.

For a real hackathon backtest:

```bash
make build-ml-dataset
uv run python scripts/train_ai_models.py \
  --csv data/ml_training.csv \
  --data-mode HISTORICAL_RESEARCH
```

Then review `reports/ml-evaluation.json` and only quote metrics from that historical run.

## Safety boundary

The AI can:

- Produce an `ESTIMATED` reference when direct evidence is insufficient.
- Produce a confidence band derived from validation residuals.
- Produce an anomaly probability.
- Explain major feature contributions.
- Tighten risk when using a non-synthetic calibrated model.

The AI cannot:

- Turn one venue into independent corroboration.
- Mark a bad print as `QUALIFIED`.
- Loosen a deterministic leverage restriction.
- Execute an order or liquidation.
- Treat Yahoo live research data as oracle evidence.
