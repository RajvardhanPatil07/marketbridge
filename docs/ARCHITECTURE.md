# MarketBridge architecture

MarketBridge is a market safety control plane, not an exchange or custody system.

```text
Alpaca / Twelve Data / Databento                 Hyperliquid / Mochatrade venue context
                 |                                             |
                 v                                             |
        evidence firewall                                      |
                 |                                             |
                 v                                             |
        mark integrity engine <--------------------------------+
                 |
                 v
       immutable Market Truth
                 |
         +-------+-------+
         |               |
 account exposure    order intent
         |               |
         +-------+-------+
                 v
          Order Risk Gate
       ALLOW / CAP / BLOCK / REVIEW
                 |
                 v
          Safety Passport
                 |
                 v
       deterministic replay
```

The shadow oracle owns Layer A: reference status, confidence, freshness, provider and venue
independence, venue divergence, anomaly probability, and asset state. `risk/` owns Layer B:
account consequence and the order action. Layer B consumes but never mutates Layer A confidence.

The hot path is process-local and deterministic. JSONL/DuckDB/Parquet remain analytical storage.
The browser uses REST for checks/history and the existing WebSocket-first, SSE-fallback stream for
market state. Provider and integration secrets stay in FastAPI.

Production boundaries: no matching engine, custody, exchange signing key, oracle signer, automatic
liquidation, or `haltTrading` call exists anywhere in MarketBridge.
