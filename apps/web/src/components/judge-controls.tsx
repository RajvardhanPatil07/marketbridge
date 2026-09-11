"use client";

import { useState } from "react";
import { useMarketData } from "@/components/market-data-provider";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const LIVE_ATTACK_BPS = 350;
const roundPrice = (value: number) => Math.round(value * 1_000_000) / 1_000_000;

type LiveResult = {
  available: boolean;
  data_mode: string;
  symbol: string;
  clock: { utc: string; ist: string; timezone: string };
  reason?: string;
  provenance: {
    underlying_evidence: string;
    venue_mark: string;
    policy: string;
    trade_submitted?: boolean;
  };
  market_truth?: {
    reference_price: number | null;
    reference_status: string;
    provider_count: number;
    venue_count: number;
    confidence: number;
  };
  venue_mark?: number;
  divergence_bps?: number;
  decision?: {
    action: string;
    passport_id: string;
    reasons: string[];
  };
};

type SafeOrderResult = {
  advisory_only: boolean;
  execution_submitted: boolean;
  applicable: boolean;
  reason?: string;
  original?: { action: string; requested_leverage: number; requested_notional: { usd: number; inr: number | null; usd_inr: number | null } };
  safe_order?: {
    leverage: number;
    notional: { usd: number; inr: number | null; usd_inr: number | null };
    requested_order_reduction_usd: number;
  };
  fresh_passport_id?: string;
  fresh_decision?: string;
  boundary?: string;
};

function usd(value: number | null | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function inr(value: number | null | undefined) {
  if (value == null) return "INR FX not configured";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

function safeOrderPayload(baseline: number) {
  const now = new Date().toISOString();
  return {
    request: {
      request_id: `judge-safe-${Date.now()}`,
      symbol: "NVDA",
      intent: { kind: "OPEN", side: "BUY", notional_usd: 10000, requested_leverage: 10 },
      account: {
        equity_usd: 10000,
        margin_available_usd: 10000,
        position_notional_usd: 22000,
        current_leverage: 2.2,
        liquidation_price: 140,
        position_side: "BUY",
        portfolio_positions: [
          { symbol: "NVDA", notional_usd: 6000, sector: "SEMICONDUCTORS", correlation_group: "AI_COMPUTE" },
          { symbol: "AMD", notional_usd: 5000, sector: "SEMICONDUCTORS", correlation_group: "AI_COMPUTE" },
          { symbol: "MSFT", notional_usd: 4000, sector: "TECHNOLOGY", correlation_group: "MEGA_CAP_TECH" },
          { symbol: "AAPL", notional_usd: 4000, sector: "TECHNOLOGY", correlation_group: "MEGA_CAP_TECH" },
          { symbol: "TSLA", notional_usd: 3000, sector: "CONSUMER_DISCRETIONARY", correlation_group: "HIGH_BETA_GROWTH" },
        ],
      },
      market: { mark_price: baseline, oracle_price: baseline, event_time: now, session: "OVERNIGHT" },
      demo_scenario: "NORMAL",
    },
  };
}

export function JudgeControls() {
  const { assets } = useMarketData();
  const safeBaseline = roundPrice(assets.find((asset) => asset.symbol === "NVDA")?.price ?? 200);
  const [live, setLive] = useState<LiveResult | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [safe, setSafe] = useState<SafeOrderResult | null>(null);
  const [safeLoading, setSafeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runLive = async (injectAttack: boolean) => {
    setLiveLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/demo/live-baseline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: "NVDA", inject_attack: injectAttack, attack_bps: LIVE_ATTACK_BPS, requested_notional_usd: 10000, requested_leverage: 10 }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `Live baseline failed (${response.status})`);
      setLive(body as LiveResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Live baseline failed");
    } finally {
      setLiveLoading(false);
    }
  };

  const applySafeOrder = async () => {
    setSafeLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/order/safe-alternative`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(safeOrderPayload(safeBaseline)),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `Safe order failed (${response.status})`);
      setSafe(body as SafeOrderResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Safe order failed");
    } finally {
      setSafeLoading(false);
    }
  };

  return (
    <section className="judge-upgrades">
      <header>
        <span className="v1-eyebrow">JUDGE MODE · PROVENANCE FIRST</span>
        <h1>Real market baseline. Synthetic venue attack. Production gate.</h1>
        <p>The live mode never fabricates independent witnesses. If the backend cannot qualify a real reference, MarketBridge says so instead of manufacturing consensus.</p>
      </header>

      {error && <div className="v1-error">{error}</div>}

      <div className="judge-grid">
        <article className="judge-card">
          <div className="judge-card-title"><span>LIVE BASELINE ATTACK</span><b>PROVENANCE VISIBLE</b></div>
          <p>Start from the backend&apos;s current evidence. Then inject only the venue mark at +{LIVE_ATTACK_BPS} bps and run the normal risk gate.</p>
          <div className="judge-actions">
            <button disabled={liveLoading} onClick={() => void runLive(false)}>Read live baseline</button>
            <button className="danger" disabled={liveLoading} onClick={() => void runLive(true)}>Inject venue attack</button>
          </div>
          {live && (
            <div className="judge-result">
              <div className="provenance-strip">
                <span><i className="live-dot"/>UNDERLYING · {live.provenance.underlying_evidence}</span>
                <span>VENUE · {live.provenance.venue_mark}</span>
                <span>POLICY · {live.provenance.policy}</span>
              </div>
              {!live.available ? (
                <div className="judge-unavailable"><strong>NO QUALIFIED LIVE BASELINE</strong><p>{live.reason}</p><small>This is the correct fail-closed behavior; one provider is not fake consensus.</small></div>
              ) : (
                <>
                  <div className="judge-metrics">
                    <div><span>Market Truth</span><strong>{usd(live.market_truth?.reference_price)}</strong><small>{live.market_truth?.reference_status}</small></div>
                    <div><span>Venue mark</span><strong>{usd(live.venue_mark)}</strong><small>{live.divergence_bps?.toFixed(1)} bps divergence</small></div>
                    <div><span>Independent families</span><strong>{live.market_truth?.provider_count ?? 0}</strong><small>{live.market_truth?.venue_count ?? 0} source families</small></div>
                    <div><span>Decision</span><strong className={live.decision?.action === "BLOCK_NEW_RISK" ? "blocked" : ""}>{live.decision?.action?.replaceAll("_", " ")}</strong><small>{live.decision?.passport_id}</small></div>
                  </div>
                  <div className="clock-row"><span>UTC {new Date(live.clock.utc).toLocaleString("en-GB", { timeZone: "UTC" })}</span><span>IST {new Date(live.clock.utc).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}</span></div>
                </>
              )}
            </div>
          )}
        </article>

        <article className="judge-card">
          <div className="judge-card-title"><span>ONE-CLICK SAFE ORDER</span><b>ADVISORY ONLY</b></div>
          <p>MarketBridge already calculates the cap. This control rewrites the demo ticket to the permitted leverage/notional and issues a fresh passport. It never executes the order.</p>
          <div className="ticket-before"><span>REQUESTED</span><strong>NVDA · 10× · $10,000</strong><small>Overnight · concentrated demo portfolio</small></div>
          <button className="safe-order-button" disabled={safeLoading} onClick={() => void applySafeOrder()}>{safeLoading ? "Calculating…" : "Apply safe order"}</button>
          {safe && (
            <div className="judge-result">
              {safe.applicable && safe.safe_order ? (
                <div className="ticket-after">
                  <span>SAFE TICKET</span>
                  <strong>{safe.safe_order.leverage}× · {usd(safe.safe_order.notional.usd)}</strong>
                  <small>{inr(safe.safe_order.notional.inr)} · fresh passport {safe.fresh_passport_id}</small>
                  <em>ADVISORY ONLY · NO EXECUTION · NO CUSTODY</em>
                </div>
              ) : <div className="judge-unavailable"><strong>NO POSITIVE SAFE ORDER</strong><p>{safe.reason}</p></div>}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
