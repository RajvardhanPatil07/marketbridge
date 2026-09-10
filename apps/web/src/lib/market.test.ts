import { describe, expect, it } from "vitest";
import { assetsFromSnapshot, mergeDisplaySnapshots } from "./market";
import type { DisplaySnapshot, ShadowSnapshot } from "./types";

describe("live display-price selection", () => {
  it("uses the newest market observation when direct evidence is stale", () => {
    const snapshot = {
      yahoo: {
        observations: [{
          symbol: "TSLA", name: "Tesla, Inc.", observed_price: 102, previous_close: 100,
          currency: "USD", exchange: "NMS", event_time: "2026-09-09T14:00:02Z",
          age_seconds: 0, points: [], change_pct: 2,
          source: { id: "yahoo-finance", name: "Yahoo", family: "yahoo", status: "FRESH" },
          decision: { status: "CAUTION", reference: null, independent_source_families: 1, new_exposure_allowed: false, advisory_exposure_multiplier: 0, reasons: [] },
        }],
      },
      live_bars: { TSLA: [{
        timestamp: "2026-09-09T14:00:03Z", open: 101, high: 103, low: 100, close: 103,
        volume: 10, vwap: 102, trade_count: 2, kind: "BAR", provider: "alpaca", feed: "iex",
        received_at: "2026-09-09T14:00:03.100Z", data_role: "DISPLAY_ONLY_NOT_ORACLE_EVIDENCE",
      }] },
      decisions: [{
        symbol: "TSLA", reference: null, last_valid: null, timestamp: "2026-09-09T14:00:01Z",
        evidence: [{ source_id: "alpaca-trade", price: 101, event_time: "2026-09-09T14:00:01Z" }],
      }],
      decision_log: [],
    } as unknown as ShadowSnapshot;

    const tsla = assetsFromSnapshot(snapshot).find((asset) => asset.symbol === "TSLA");
    expect(tsla?.price).toBe(103);
    expect(tsla?.eventTime).toBe("2026-09-09T14:00:03Z");
    expect(tsla?.priceSource).toBe("Alpaca IEX");
  });
});

describe("batch display snapshots", () => {
  it("adds a new catalog stock with complete quote context without inventing risk evidence", () => {
    const snapshot: DisplaySnapshot = {
      symbol: "AMZN", name: "Amazon.com, Inc.", exchange: "NASDAQ", currency: "USD",
      status: "AVAILABLE", price: 252.84, previous_close: 250, change_pct: 1.136,
      event_time: "2026-09-10T15:00:00Z", bid: 252.8, ask: 252.86,
      day_volume: 1_250_000, feed: "iex", is_delayed: true,
    };

    const [asset] = mergeDisplaySnapshots([], [snapshot]);

    expect(asset).toMatchObject({
      symbol: "AMZN", name: "Amazon.com, Inc.", price: 252.84, previousClose: 250, changePct: 1.136,
      bid: 252.8, ask: 252.86, dayVolume: 1_250_000, priceSource: "Alpaca IEX",
      confidence: null, riskState: null, evidenceCount: 0,
    });
  });
});
