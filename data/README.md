# ML research data

`data/ml_training.csv` is intentionally ignored by Git because historical market data can be large and may have redistribution restrictions.

Build a research dataset locally with:

```bash
uv run python scripts/build_ml_dataset.py --period 6mo --interval 60m
```

The builder uses Yahoo/yfinance only for **offline research/backtesting**. Yahoo remains non-oracle-eligible at runtime.

Expected fair-value columns:

- `symbol`
- `timestamp`
- `qqq_return_bps`
- `spy_return_bps`
- `soxx_return_bps`
- `single_source_return_bps`
- `minutes_since_anchor`
- `source_age_ms`
- `provider_count`
- `venue_count`
- `target_return_bps`

Then train/export a historical-research model bundle:

```bash
uv run python scripts/train_ai_models.py \
  --csv data/ml_training.csv \
  --data-mode HISTORICAL_RESEARCH
```

Do not describe the default bundled synthetic calibration metrics as real-market performance.
