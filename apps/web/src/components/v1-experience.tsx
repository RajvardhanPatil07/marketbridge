"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMarketData } from "@/components/market-data-provider";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const SYMBOLS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMD", "QQQ"];

function usd(value: number | null | undefined) {
  return value == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function compact(value: number | null | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

type WarRoomResult = {
  scenario: string;
  intent: string;
  symbol: string;
  story: {
    headline: string;
    detail: string;
    data_mode: string;
    no_trade_submitted: boolean;
    reference_price: number | null;
    venue_mark: number | null;
    divergence_bps: number | null;
    confidence: number | null;
    market_state: string;
    decision: string;
    exit_invariant: string;
  };
  result: {
    action: string;
    requested_leverage: number;
    permitted_leverage: number;
    requested_notional_usd: number;
    permitted_notional_usd: number;
    reasons: string[];
    passport_id: string;
    policy_version: string;
    expires_at: string;
    reduce_only_allowed: boolean;
    market: {
      reference_price: number | null;
      venue_mark: number | null;
      divergence_bps: number | null;
      confidence: number | null;
      provider_count: number;
      venue_count: number;
      asset_state: string;
      evidence: Array<{ provider: string; provider_family: string; venue_family: string; fresh: boolean; eligible: boolean; observation_hash: string }>;
      recovery?: { stable_observations: number; required_observations: number; elapsed_seconds: number; minimum_duration_seconds: number };
    };
    passport: { chain_hash?: string; content_hash?: string; claims?: { policy?: { policy_version?: string } } };
  };
};

type ReplayResult = {
  original_action: string;
  replayed_action: string;
  prevented_additional_exposure_usd: number;
  deterministic_parity: boolean;
  counterfactual: boolean;
  disclaimer: string | null;
};

type ProviderRow = {
  id: string;
  name: string;
  capability: string;
  source_class: string;
  cost_mode: string;
  market_truth_authority: string;
  risk_eligible: boolean;
  configured: boolean;
  status: string;
  note: string;
  runtime?: Record<string, string | number | boolean | null>;
};

type ProviderPayload = { architecture_version: string; cost_mode: string; principles: string[]; providers: ProviderRow[] };

type IntelligencePayload = {
  symbol: string;
  boundary: string;
  news: {
    status: string;
    articles: Array<{ id: string; title: string; description: string; url: string; source: string; published_at: string; sentiment_score: number | null }>;
    message?: string | null;
  };
  official_company_context: {
    status: string;
    company: { name: string; cik: string; sic_description?: string | null } | null;
    recent_filings: Array<{ form: string; filing_date: string | null; report_date: string | null; url: string | null }>;
    facts: Record<string, { label: string; value: number; unit: string; filed?: string | null; form?: string | null } | null>;
    message?: string | null;
  };
};

export function V1Home() {
  const { assets, snapshot, connection } = useMarketData();
  const nvda = assets.find((asset) => asset.symbol === "NVDA");
  return <div className="v1-page">
    <section className="v1-hero">
      <div className="v1-hero-copy">
        <span className="v1-eyebrow">MARKETBRIDGE v1 · FREE-FIRST MARKET SAFETY</span>
        <h1><span>US stocks sleep.</span><br/>Equity perpetuals don&apos;t.</h1>
        <p>MarketBridge independently verifies the market before leverage is allowed to act — then seals every consequential decision in a replayable Safety Passport.</p>
        <div className="v1-actions"><Link className="v1-primary" href="/demo/">Run the attack demo</Link><Link className="v1-secondary" href="/providers/">Inspect provider mesh</Link></div>
        <div className="v1-proof-row"><span>NO CUSTODY</span><span>NO EXECUTION KEYS</span><span>AI CAN ONLY TIGHTEN</span><span>FREE-FIRST DATA</span></div>
      </div>
      <div className="v1-live-card">
        <div className="v1-card-title"><span>LIVE SAFETY SURFACE</span><b className={`v1-dot ${connection}`}>{connection.toUpperCase()}</b></div>
        <div className="v1-live-symbol"><strong>NVDA</strong><span>{usd(nvda?.price)}</span></div>
        <dl className="v1-metrics"><div><dt>Market Truth</dt><dd>{nvda?.status?.replaceAll("_", " ") ?? "AWAITING EVIDENCE"}</dd></div><div><dt>Risk</dt><dd>{nvda?.riskState?.replaceAll("_", " ") ?? "NOT EVALUATED"}</dd></div><div><dt>Qualified refs</dt><dd>{snapshot?.market_health.qualified_symbols.length ?? 0}</dd></div><div><dt>Provider mode</dt><dd>FREE FIRST</dd></div></dl>
        <p className="v1-boundary">Live data is shown with provenance. A single IEX feed is never promoted into fake independent consensus.</p>
      </div>
    </section>
    <section className="v1-flow"><div><b>01</b><strong>Observe</strong><span>Free live equity + venue context</span></div><i>→</i><div><b>02</b><strong>Verify</strong><span>Freshness + independence + divergence</span></div><i>→</i><div><b>03</b><strong>Gate</strong><span>ALLOW / CAP / BLOCK / REVIEW</span></div><i>→</i><div><b>04</b><strong>Prove</strong><span>Safety Passport + deterministic replay</span></div></section>
    <section className="v1-home-grid"><article><span className="v1-kicker">THE 90-SECOND STORY</span><h2>Poison the mark. Watch MarketBridge stop new leverage.</h2><p>The judge sees independent evidence, a manipulated venue mark, a 10× order, a BLOCK decision, the preserved exit path, cryptographic proof and the counterfactual — without leaving one screen.</p><Link href="/demo/">Open War Room →</Link></article><article><span className="v1-kicker">THE DIFFERENCE</span><h2>Not another trading AI.</h2><p>Trading tools predict. Fraud tools score users. MarketBridge asks a different question: <strong>does this market price deserve enough trust for leverage?</strong></p><Link href="/intelligence/">See context boundary →</Link></article></section>
  </div>;
}

async function fetchWarRoom(scenario: "NORMAL" | "POISONED_MARK" | "RECOVERY", intent: "OPEN" | "CLOSE" = "OPEN") {
  const response = await fetch(`${API_BASE}/v1/demo/war-room`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario, intent, symbol: "NVDA" }) });
  if (!response.ok) throw new Error(`War Room request failed (${response.status})`);
  return await response.json() as WarRoomResult;
}

export function WarRoom() {
  const [data, setData] = useState<WarRoomResult | null>(null);
  const [replay, setReplay] = useState<ReplayResult | null>(null);
  const [history, setHistory] = useState<Array<{ label: string; action: string; state: string; divergence: number | null }>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apply = (next: WarRoomResult, label?: string) => {
    setData(next); setReplay(null);
    setHistory((items) => [...items.slice(-5), { label: label ?? next.scenario, action: next.result.action, state: next.result.market.asset_state, divergence: next.result.market.divergence_bps }]);
  };
  const run = async (scenario: "NORMAL" | "POISONED_MARK" | "RECOVERY", intent: "OPEN" | "CLOSE" = "OPEN") => {
    setBusy(true); setError(null);
    try { apply(await fetchWarRoom(scenario, intent), intent === "CLOSE" ? "CLOSE EXIT" : scenario); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Demo request failed"); }
    finally { setBusy(false); }
  };
  const recover = async () => {
    setBusy(true); setError(null);
    try {
      for (let index = 0; index < 3; index += 1) {
        const next = await fetchWarRoom("RECOVERY", "OPEN"); apply(next, index === 2 ? "RECOVERED" : `RECOVERY ${index + 1}/3`);
        if (index < 2) await new Promise((resolve) => window.setTimeout(resolve, 1100));
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Recovery demo failed"); }
    finally { setBusy(false); }
  };
  const compare = async () => {
    if (!data?.result.passport_id) return;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/demo/war-room/replay`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ passport_id: data.result.passport_id, mode: "WITHOUT_SAFETY_GATE" }) });
      if (!response.ok) throw new Error(`Replay failed (${response.status})`);
      setReplay(await response.json() as ReplayResult);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Replay failed"); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true); await fetch(`${API_BASE}/v1/demo/war-room/reset`, { method: "POST" }); setHistory([]); setReplay(null); setData(null); setBusy(false);
  };
  const actionClass = data?.result.action === "BLOCK_NEW_RISK" ? "blocked" : data?.result.action === "ALLOW" ? "allowed" : "guarded";
  return <div className="v1-page war-room">
    <header className="v1-page-head"><div><span className="v1-eyebrow">SYNTHETIC ADVERSARIAL DEMO · SAME RISK POLICY</span><h1>Market Truth War Room</h1><p>One screen. One attack. One decision trail. No trade is submitted.</p></div><button className="v1-quiet" onClick={reset} disabled={busy}>Reset incident</button></header>
    <section className="scenario-bar"><button onClick={() => run("NORMAL")} disabled={busy}>1 · Normal market</button><button className="danger" onClick={() => run("POISONED_MARK")} disabled={busy}>2 · Poison venue mark</button><button onClick={() => run("POISONED_MARK", "CLOSE")} disabled={busy}>3 · Prove exit stays open</button><button onClick={recover} disabled={busy}>4 · Recover safely</button></section>
    {error && <div className="v1-error">{error}</div>}
    {!data ? <section className="war-empty"><strong>Ready for the judge.</strong><p>Start with a normal market, then poison the venue mark. MarketBridge will compare the mark against independent synthetic witnesses, block new risk, preserve the exit path and issue a Safety Passport.</p><button className="v1-primary" onClick={() => run("NORMAL")} disabled={busy}>Start demo</button></section> : <>
      <section className="truth-stage">
        <div className="evidence-column"><span className="v1-kicker">INDEPENDENT EVIDENCE</span>{data.result.market.evidence.map((item, index) => <article key={item.observation_hash}><div><i className="healthy"/><strong>{index === 0 ? "Witness A" : "Witness B"}</strong></div><b>{item.provider_family.replace("synthetic-demo-", "")}</b><small>{item.venue_family} · FRESH · ELIGIBLE</small></article>)}</div>
        <div className="truth-core"><span>MARKET TRUTH</span><strong>{usd(data.result.market.reference_price)}</strong><div className="confidence-ring">{Math.round((data.result.market.confidence ?? 0) * 100)}%<small>confidence</small></div></div>
        <div className={`venue-column ${actionClass}`}><span className="v1-kicker">VENUE MARK</span><strong>{usd(data.result.market.venue_mark)}</strong><b>{data.result.market.divergence_bps == null ? "—" : `${data.result.market.divergence_bps.toFixed(1)} bps`}</b><small>DIVERGENCE</small></div>
        <div className="flow-arrow">→</div>
        <div className={`decision-monolith ${actionClass}`}><span>ORDER DECISION</span><strong>{data.result.action.replaceAll("_", " ")}</strong><p>{data.story.headline}</p><dl><div><dt>Requested</dt><dd>{data.result.requested_leverage}× · {usd(data.result.requested_notional_usd)}</dd></div><div><dt>Permitted</dt><dd>{data.result.permitted_leverage}× · {usd(data.result.permitted_notional_usd)}</dd></div><div><dt>Reduce / close</dt><dd>{data.result.reduce_only_allowed ? "AVAILABLE" : "UNAVAILABLE"}</dd></div></dl></div>
      </section>
      <section className="war-lower">
        <article className="timeline-card"><div className="v1-card-title"><span>MARKET TRUTH TIMELINE</span><b>{data.result.market.asset_state}</b></div><div className="timeline-track">{history.map((item, index) => <div key={`${item.label}-${index}`} className={item.action === "BLOCK_NEW_RISK" ? "stop" : item.state === "RECOVERY_PENDING" ? "recover" : "go"}><i/><strong>{item.label}</strong><span>{item.divergence == null ? "—" : `${item.divergence.toFixed(0)} bps`}</span><small>{item.action.replaceAll("_", " ")}</small></div>)}</div><p>{data.story.detail}</p></article>
        <article className="passport-card"><div className="v1-card-title"><span>SAFETY PASSPORT</span><b>VERIFIED FORMAT</b></div><h3>{data.result.passport_id}</h3><dl><div><dt>Policy</dt><dd>{data.result.policy_version}</dd></div><div><dt>Expires</dt><dd>{new Date(data.result.expires_at).toLocaleTimeString()}</dd></div><div><dt>Evidence</dt><dd>{data.result.market.provider_count} provider families</dd></div><div><dt>Fingerprint</dt><dd className="mono">{(data.result.passport.chain_hash ?? data.result.passport.content_hash ?? "pending").slice(0, 18)}…</dd></div></dl><button onClick={compare} disabled={busy}>Replay without safety gate</button></article>
      </section>
      {replay && <section className="counterfactual"><div><span>WITHOUT MARKETBRIDGE</span><strong>{replay.replayed_action}</strong><small>Requested exposure can proceed in this counterfactual.</small></div><b>VS</b><div><span>WITH MARKETBRIDGE</span><strong>{replay.original_action.replaceAll("_", " ")}</strong><small>Deterministic policy decision.</small></div><aside><span>ADDITIONAL SIMULATED EXPOSURE PREVENTED</span><strong>{usd(replay.prevented_additional_exposure_usd)}</strong><small>{replay.disclaimer}</small></aside></section>}
      <section className="reason-strip"><span>WHY</span>{data.result.reasons.map((reason) => <b key={reason}>{reason.replaceAll("_", " ")}</b>)}</section>
    </>}
  </div>;
}

export function ProviderMesh() {
  const [data, setData] = useState<ProviderPayload | null>(null); const [error, setError] = useState<string | null>(null);
  useEffect(() => { void fetch(`${API_BASE}/v1/providers`, { cache: "no-store" }).then(async (response) => { if (!response.ok) throw new Error("Provider registry unavailable"); setData(await response.json() as ProviderPayload); }).catch((caught) => setError(caught instanceof Error ? caught.message : "Provider registry unavailable")); }, []);
  const groups = useMemo(() => data ? { core: data.providers.filter((item) => ["alpaca", "hyperliquid"].includes(item.id)), context: data.providers.filter((item) => ["marketaux", "sec-edgar", "nasdaq-symbols"].includes(item.id)), optional: data.providers.filter((item) => !["alpaca", "hyperliquid", "marketaux", "sec-edgar", "nasdaq-symbols"].includes(item.id)) } : null, [data]);
  return <div className="v1-page"><header className="v1-page-head"><div><span className="v1-eyebrow">CAPABILITY-BASED · PROVIDER-AGNOSTIC</span><h1>Free-First Provider Mesh</h1><p>Providers declare what they are allowed to influence. Vendor names are adapters, not architecture.</p></div><span className="free-chip">₹0-FIRST</span></header>{error && <div className="v1-error">{error}</div>}{!groups ? <div className="war-empty">Loading provider registry…</div> : <>{(["core", "context", "optional"] as const).map((group) => <section className="provider-section" key={group}><div className="section-title"><span>{group === "core" ? "01" : group === "context" ? "02" : "03"}</span><div><h2>{group === "core" ? "Live safety core" : group === "context" ? "Intelligence context" : "Optional / fallback"}</h2><p>{group === "core" ? "Data used to observe the underlying market and the trading venue." : group === "context" ? "Useful information that never manufactures Market Truth." : "Helpful when configured, never required for the flagship demo."}</p></div></div><div className="provider-grid">{groups[group].map((provider) => <article key={provider.id}><div className="provider-top"><strong>{provider.name}</strong><span className={provider.configured || provider.status === "READY" ? "on" : "off"}>{provider.status}</span></div><h3>{provider.capability.replaceAll("_", " ")}</h3><dl><div><dt>Cost mode</dt><dd>{provider.cost_mode.replaceAll("_", " ")}</dd></div><div><dt>Source class</dt><dd>{provider.source_class.replaceAll("_", " ")}</dd></div><div><dt>Market Truth</dt><dd>{provider.market_truth_authority.replaceAll("_", " ")}</dd></div><div><dt>Risk eligible</dt><dd>{provider.risk_eligible ? "YES" : "NO"}</dd></div></dl><p>{provider.note}</p></article>)}</div></section>)}</>}
    {data && <section className="principle-card"><span className="v1-kicker">NON-NEGOTIABLE BOUNDARIES</span>{data.principles.map((item) => <p key={item}>✓ {item}</p>)}</section>}
  </div>;
}

export function IntelligenceWorkspace() {
  const [symbol, setSymbol] = useState("NVDA"); const [data, setData] = useState<IntelligencePayload | null>(null); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(false);
  useEffect(() => { const controller = new AbortController(); setLoading(true); setError(null); void fetch(`${API_BASE}/v1/intelligence/${symbol}`, { signal: controller.signal, cache: "no-store" }).then(async (response) => { if (!response.ok) throw new Error(`Intelligence unavailable (${response.status})`); setData(await response.json() as IntelligencePayload); }).catch((caught) => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Intelligence unavailable"); }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort(); }, [symbol]);
  const facts = data ? Object.entries(data.official_company_context.facts).filter(([, value]) => value) : [];
  return <div className="v1-page"><header className="v1-page-head"><div><span className="v1-eyebrow">CONTEXT PLANE · NEVER PRICE TRUTH</span><h1>Market Intelligence</h1><p>Financial news plus primary-source SEC events, kept outside the executable reference.</p></div><select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{SYMBOLS.map((item) => <option key={item}>{item}</option>)}</select></header><div className="context-boundary"><strong>CONTEXT ONLY</strong><span>{data?.boundary ?? "News and filings can explain events; they cannot qualify a price or loosen risk."}</span></div>{error && <div className="v1-error">{error}</div>}{loading && !data ? <div className="war-empty">Loading intelligence…</div> : data && <section className="intel-grid"><article className="intel-news"><div className="v1-card-title"><span>FINANCIAL NEWS</span><b>{data.news.status}</b></div>{data.news.articles.length ? data.news.articles.map((article) => <a key={article.id} href={article.url} target="_blank" rel="noreferrer"><small>{article.source} · {article.published_at ? new Date(article.published_at).toLocaleString() : "recent"}</small><strong>{article.title}</strong><p>{article.description}</p>{article.sentiment_score != null && <span>Sentiment {article.sentiment_score.toFixed(2)}</span>}</a>) : <p className="empty-copy">{data.news.message ?? "No articles returned."}</p>}</article><article className="intel-sec"><div className="v1-card-title"><span>OFFICIAL COMPANY CONTEXT</span><b>SEC EDGAR</b></div>{data.official_company_context.company ? <><h2>{data.official_company_context.company.name}</h2><p>CIK {data.official_company_context.company.cik} · {data.official_company_context.company.sic_description ?? "US public company"}</p><div className="fact-grid">{facts.map(([key, fact]) => fact && <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{fact.unit === "USD" ? usd(fact.value) : compact(fact.value)}</strong><small>{fact.form ?? "SEC"} · filed {fact.filed ?? "—"}</small></div>)}</div><h3>Recent official filings</h3><div className="filing-list">{data.official_company_context.recent_filings.slice(0, 6).map((filing) => filing.url ? <a key={`${filing.form}-${filing.filing_date}`} href={filing.url} target="_blank" rel="noreferrer"><strong>{filing.form}</strong><span>{filing.filing_date ?? "—"}</span><small>OFFICIAL SOURCE ↗</small></a> : <div key={`${filing.form}-${filing.filing_date}`}><strong>{filing.form}</strong><span>{filing.filing_date ?? "—"}</span></div>)}</div></> : <p className="empty-copy">{data.official_company_context.message ?? "SEC context unavailable."}</p>}</article></section>}</div>;
}
