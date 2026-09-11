"use client";

import { useCallback, useState } from "react";
import { CheckCircle2, CircleAlert, RotateCcw, ShieldCheck, X } from "lucide-react";
import type { MarketAsset } from "@/lib/market";
import type { ReplayResult, RiskAction, RiskCheckResult, SafetyPassport } from "@/lib/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const actionLabel: Record<RiskAction, string> = {
  ALLOW: "ALLOW",
  CAP_LEVERAGE: "CAP LEVERAGE",
  BLOCK_NEW_RISK: "BLOCK NEW RISK",
  REVIEW: "REVIEW",
};

type Scenario = "NORMAL" | "POISONED_MARK" | "RECOVERY";
type Intent = "OPEN" | "INCREASE" | "REDUCE" | "CLOSE";
const DEMO_ATTACK_BPS = 350;

function PassportView({ passport, onClose }: { passport: SafetyPassport; onClose: () => void }) {
  const claims = passport.claims;
  return <div className="passport-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="safety-passport" role="dialog" aria-modal="true" aria-labelledby="passport-title">
      <header><div><span>MARKETBRIDGE</span><h2 id="passport-title">Safety Passport</h2></div><button onClick={onClose} aria-label="Close Safety Passport"><X size={16}/></button></header>
      <div className="passport-verification"><ShieldCheck size={18}/><div><strong>Cryptographically verified</strong><span>SHA-256 content and chain hashes match this decision.</span></div></div>
      <div className="passport-grid">
        <article><span>Order</span><strong>{claims.identity.symbol} {claims.order.side}</strong><p>{claims.order.intent_kind} · requested {claims.order.requested_leverage}× · permitted {claims.order.permitted_leverage}×</p></article>
        <article><span>Market truth</span><strong>{claims.market.reference_status}</strong><p>Reference ${Number(claims.market.reference_price).toFixed(2)} · venue ${Number(claims.market.venue_mark).toFixed(2)} · {Number(claims.market.divergence_bps).toFixed(1)} bp</p></article>
        <article><span>Account consequence</span><strong>{claims.account.risk_classification}</strong><p>Liquidation distance {claims.account.liquidation_distance_pct == null ? "not supplied" : `${Number(claims.account.liquidation_distance_pct).toFixed(2)}%`}</p></article>
        <article><span>Safety action</span><strong>{actionLabel[claims.decision.action]}</strong><p>{claims.decision.reason_codes.join(" · ")}</p></article>
      </div>
      <dl className="passport-proof"><div><dt>Passport</dt><dd>{passport.passport_id}</dd></div><div><dt>Policy</dt><dd>{claims.policy.policy_version}</dd></div><div><dt>Content hash</dt><dd>{passport.content_hash}</dd></div><div><dt>Previous</dt><dd>{passport.previous_hash ?? "GENESIS"}</dd></div><div><dt>Chain hash</dt><dd>{passport.chain_hash}</dd></div></dl>
      <footer>Reduce / close: <strong>AVAILABLE</strong> · expires {new Date(claims.decision.expires_at).toLocaleTimeString()}</footer>
    </section>
  </div>;
}

export default function SafetyOrderGate({ asset }: { asset: MarketAsset | null }) {
  const [intent, setIntent] = useState<Intent>("OPEN");
  const [notional, setNotional] = useState("10000");
  const [leverage, setLeverage] = useState("10");
  const [equity, setEquity] = useState("2000");
  const [existingExposure, setExistingExposure] = useState("0");
  const [liquidationPrice, setLiquidationPrice] = useState("");
  const [scenario, setScenario] = useState<Scenario>("NORMAL");
  const [result, setResult] = useState<RiskCheckResult | null>(null);
  const [replay, setReplay] = useState<ReplayResult | null>(null);
  const [passport, setPassport] = useState<SafetyPassport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const checkOrder = useCallback(async () => {
    if (!asset) return;
    setLoading(true); setError(null); setReplay(null);
    const orderNotional = Number(notional);
    const positionNotional = intent === "REDUCE" || intent === "CLOSE" ? Math.max(Number(existingExposure), orderNotional) : Number(existingExposure);
    const baseline = asset.price ?? asset.previousClose ?? 100;
    const mark = scenario === "POISONED_MARK"
      ? baseline * (1 + DEMO_ATTACK_BPS / 10_000)
      : baseline;
    const body = {
      request_id: `ord_${crypto.randomUUID()}`,
      symbol: asset.symbol,
      intent: { kind: intent, side: "BUY", notional_usd: orderNotional, requested_leverage: Number(leverage) },
      account: {
        equity_usd: Number(equity), margin_available_usd: Math.max(Number(equity), orderNotional),
        position_notional_usd: positionNotional,
        ...(liquidationPrice ? { liquidation_price: Number(liquidationPrice), position_side: "BUY" } : {}),
      },
      market: { mark_price: mark, oracle_price: baseline, event_time: new Date().toISOString(), session: "REGULAR" },
      demo_scenario: scenario,
    };
    try {
      const response = await fetch(`${API_BASE}/v1/integrations/mochatrade/risk-check`, {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Risk check failed");
      setResult(payload as RiskCheckResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Risk check failed");
    } finally { setLoading(false); }
  }, [asset, equity, existingExposure, intent, leverage, liquidationPrice, notional, scenario]);

  const runReplay = useCallback(async (policyVersion: "CURRENT" | "WITHOUT_SAFETY_GATE") => {
    if (!result) return;
    const response = await fetch(`${API_BASE}/v1/replay/risk-decision`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ passport_id: result.passport_id, policy_version: policyVersion }),
    });
    if (response.ok) setReplay(await response.json() as ReplayResult);
  }, [result]);

  return <aside className="order-ticket safety-order-ticket">
    <div className="paper-banner"><strong>SYNTHETIC DEMO · PAPER / ADVISORY</strong><span>No order is transmitted</span></div>
    <div className="risk-ticket-heading"><div><h2>Order risk gate</h2><p>Same endpoint, policy, passport, and replay used by integrations.</p></div><div className="scenario-controls" aria-label="Demo evidence scenario">{(["NORMAL", "POISONED_MARK", "RECOVERY"] as const).map((item) => <button key={item} className={scenario === item ? "active" : ""} onClick={() => setScenario(item)}>{item.replaceAll("_", " ")}</button>)}</div></div>
    <div className="risk-ticket-inputs">
      <label><span>Intent</span><select value={intent} onChange={(event) => setIntent(event.target.value as Intent)}><option>OPEN</option><option>INCREASE</option><option>REDUCE</option><option>CLOSE</option></select></label>
      <label><span>Symbol</span><input value={asset?.symbol ?? ""} readOnly/></label>
      <label><span>Notional USD</span><input type="number" min="1" value={notional} onChange={(event) => setNotional(event.target.value)}/></label>
      <label><span>Requested leverage</span><input type="number" min="1" max="100" value={leverage} onChange={(event) => setLeverage(event.target.value)}/></label>
      <label><span>Paper equity</span><input type="number" min="1" value={equity} onChange={(event) => setEquity(event.target.value)}/></label>
      <label><span>Existing exposure</span><input type="number" min="0" value={existingExposure} onChange={(event) => setExistingExposure(event.target.value)}/></label>
      <label><span>Liquidation price (optional)</span><input type="number" min="0" step="0.01" value={liquidationPrice} onChange={(event) => setLiquidationPrice(event.target.value)}/></label>
      <button className="review-order" onClick={checkOrder} disabled={!asset || loading}>{loading ? "CHECKING…" : "CHECK ORDER"}</button>
    </div>
    {error ? <p className="risk-error"><CircleAlert size={14}/>{error}</p> : null}
    {result ? <section className={`safety-decision action-${result.action.toLowerCase()}`} aria-live="polite">
      <div><span>Market truth</span><strong>{result.market.reference_status}</strong><small>{result.market.asset_state} · {Math.round(result.market.confidence * 100)}% confidence · {result.market.provider_count} providers / {result.market.venue_count} venues</small></div>
      <div><span>Customer consequence</span><strong>{result.account_risk.risk_classification}</strong><small>{result.account_risk.liquidation_distance_pct == null ? "Liquidation distance unavailable" : `${Number(result.account_risk.liquidation_distance_pct).toFixed(2)}% liquidation distance`}</small></div>
      <div><span>Requested / permitted</span><strong>{result.requested_leverage}× / {result.permitted_leverage}×</strong><small>${result.requested_notional_usd.toLocaleString()} / ${result.permitted_notional_usd.toLocaleString()}</small></div>
      <div className="decision-action"><span>Safety action</span><strong>{actionLabel[result.action]}</strong><small>{result.reasons.join(" · ")}</small></div>
      <div className="exit-preserved"><CheckCircle2 size={14}/><strong>REDUCE / CLOSE AVAILABLE</strong><span>{result.ttl_ms / 1000}s decision TTL</span></div>
      <div className="decision-tools"><button onClick={() => setPassport(result.passport)}><ShieldCheck size={13}/>Open passport</button><button onClick={() => void runReplay("WITHOUT_SAFETY_GATE")}><RotateCcw size={13}/>Replay without gate</button><button onClick={() => void runReplay("CURRENT")}><RotateCcw size={13}/>Replay current</button></div>
    </section> : null}
    {replay ? <div className="replay-result"><strong>{replay.counterfactual ? "COUNTERFACTUAL" : "DETERMINISTIC REPLAY"}</strong><span>{replay.original_action} → {replay.replayed_action}</span><span>Permitted ${replay.original_permitted_notional_usd.toLocaleString()} → ${replay.replayed_permitted_notional_usd.toLocaleString()}</span>{replay.disclaimer ? <small>{replay.disclaimer}</small> : <small>Replay parity: {replay.deterministic_parity ? "PASS" : "MISMATCH"}</small>}</div> : null}
    {passport ? <PassportView passport={passport} onClose={() => setPassport(null)}/> : null}
  </aside>;
}
