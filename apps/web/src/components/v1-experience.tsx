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
  inputs: {
    requested_notional_usd: number;
    requested_leverage: number;
    account_equity_usd: number;
    existing_position_usd: number;
    attack_bps: number;
  };
  story: {
    headline: string;
    detail: string;
    requested_mode: string;
    data_mode: string;
    baseline_source: string;
    baseline_price: number;
    attack_bps: number;
    synthetic: boolean;
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
      reference_status?: string;
      venue_mark: number | null;
      divergence_bps: number | null;
      confidence: number | null;
      provider_count: number;
      venue_count: number;
      asset_state: string;
      data_mode?: string;
      evidence: Array<{
        provider: string;
        provider_family: string;
        venue_family: string;
        observed_price?: number | null;
        event_time?: string | null;
        fresh: boolean;
        eligible: boolean;
        source_mode?: string;
        observation_hash: string;
      }>;
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
  supported?: boolean;
  configured: boolean;
  observed?: boolean;
  health?: string;
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

type WarRoomControls = {
  symbol: string;
  mode: "AUTO" | "LIVE" | "SYNTHETIC";
  requestedNotional: number;
  requestedLeverage: number;
  attackBps: number;
  accountEquity: number;
  existingPosition: number;
  baselinePrice: number | null;
};

async function fetchWarRoom(
  scenario: "NORMAL" | "POISONED_MARK" | "RECOVERY",
  intent: "OPEN" | "CLOSE",
  controls: WarRoomControls,
) {
  const response = await fetch(`${API_BASE}/v1/demo/war-room`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario,
      intent,
      mode: controls.mode,
      symbol: controls.symbol,
      baseline_price: controls.baselinePrice,
      requested_notional_usd: controls.requestedNotional,
      requested_leverage: controls.requestedLeverage,
      attack_bps: controls.attackBps,
      account_equity_usd: controls.accountEquity,
      existing_position_usd: controls.existingPosition,
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `War Room request failed (${response.status})`);
  }
  return await response.json() as WarRoomResult;
}

function evidenceAge(eventTime?: string | null) {
  if (!eventTime) return "age unknown";
  const age = Math.max(0, (Date.now() - new Date(eventTime).getTime()) / 1000);
  return age < 60 ? `${age.toFixed(1)}s old` : `${Math.round(age / 60)}m old`;
}

export function WarRoom() {
  const { assets } = useMarketData();
  const [symbol, setSymbol] = useState("NVDA");
  const [mode, setMode] = useState<"AUTO" | "LIVE" | "SYNTHETIC">("AUTO");
  const [requestedNotional, setRequestedNotional] = useState(10000);
  const [requestedLeverage, setRequestedLeverage] = useState(10);
  const [attackBps, setAttackBps] = useState(350);
  const [accountEquity, setAccountEquity] = useState(10000);
  const [existingPosition, setExistingPosition] = useState(0);
  const [data, setData] = useState<WarRoomResult | null>(null);
  const [replay, setReplay] = useState<ReplayResult | null>(null);
  const [history, setHistory] = useState<Array<{ label: string; action: string; state: string; divergence: number | null }>>([]);
  const [busy, setBusy] = useState(false);
  const [showEvidence, setShowEvidence] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const selectedAsset = assets.find((asset) => asset.symbol === symbol);

  const controls = (): WarRoomControls => ({
    symbol,
    mode,
    requestedNotional: Math.max(1, Number(requestedNotional)),
    requestedLeverage: Math.max(0.1, Number(requestedLeverage)),
    attackBps: Math.max(0, Number(attackBps)),
    accountEquity: Math.max(1, Number(accountEquity)),
    existingPosition: Math.max(0, Number(existingPosition)),
    baselinePrice: selectedAsset?.price ?? null,
  });

  const apply = (next: WarRoomResult, label?: string) => {
    setData(next);
    setReplay(null);
    setHistory((items) => [...items.slice(-5), {
      label: label ?? next.scenario,
      action: next.result.action,
      state: next.result.market.asset_state,
      divergence: next.result.market.divergence_bps,
    }]);
  };

  const run = async (scenario: "NORMAL" | "POISONED_MARK" | "RECOVERY", intent: "OPEN" | "CLOSE" = "OPEN") => {
    setBusy(true);
    setError(null);
    try {
      apply(await fetchWarRoom(scenario, intent, controls()), intent === "CLOSE" ? "CLOSE EXIT" : scenario);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Demo request failed");
    } finally {
      setBusy(false);
    }
  };

  const recover = async () => {
    setBusy(true);
    setError(null);
    try {
      for (let index = 0; index < 3; index += 1) {
        const next = await fetchWarRoom("RECOVERY", "OPEN", controls());
        apply(next, index === 2 ? "RECOVERED" : `RECOVERY ${index + 1}/3`);
        if (index < 2) await new Promise((resolve) => window.setTimeout(resolve, 1100));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Recovery demo failed");
    } finally {
      setBusy(false);
    }
  };

  const compare = async () => {
    if (!data?.result.passport_id) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/v1/demo/war-room/replay`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passport_id: data.result.passport_id, mode: "WITHOUT_SAFETY_GATE" }),
      });
      if (!response.ok) throw new Error(`Replay failed (${response.status})`);
      setReplay(await response.json() as ReplayResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Replay failed");
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    await fetch(`${API_BASE}/v1/demo/war-room/reset`, { method: "POST" });
    setHistory([]);
    setReplay(null);
    setData(null);
    setBusy(false);
  };

  const actionClass = data?.result.action === "BLOCK_NEW_RISK" ? "blocked" : data?.result.action === "ALLOW" ? "allowed" : "guarded";
  return <div className="v1-page war-room">
    <header className="v1-page-head">
      <div>
        <span className="v1-eyebrow">PARAMETERIZED ADVERSARIAL DEMO · SAME RISK POLICY</span>
        <h1>Market Truth War Room</h1>
        <p>Change the market, order and attack. The decision is recomputed; no trade is submitted.</p>
      </div>
      <div className="war-head-actions">
        {data && <span className={`mode-chip ${data.story.synthetic ? "synthetic" : "live"}`}>{data.story.data_mode.replaceAll("_", " ")}</span>}
        <button className="v1-quiet" onClick={reset} disabled={busy}>Reset incident</button>
      </div>
    </header>

    <section className="war-controls">
      <label><span>Symbol</span><select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{["NVDA","TSLA","AAPL","MSFT","AMD"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label><span>Evidence mode</span><select value={mode} onChange={(event) => setMode(event.target.value as "AUTO" | "LIVE" | "SYNTHETIC")}><option>AUTO</option><option>LIVE</option><option>SYNTHETIC</option></select></label>
      <label><span>Order notional</span><input type="number" min="1" step="500" value={requestedNotional} onChange={(event) => setRequestedNotional(Number(event.target.value))}/></label>
      <label><span>Leverage</span><input type="number" min="1" max="100" step="1" value={requestedLeverage} onChange={(event) => setRequestedLeverage(Number(event.target.value))}/></label>
      <label><span>Attack (bps)</span><input type="number" min="0" max="5000" step="25" value={attackBps} onChange={(event) => setAttackBps(Number(event.target.value))}/></label>
      <label><span>Account equity</span><input type="number" min="1" step="1000" value={accountEquity} onChange={(event) => setAccountEquity(Number(event.target.value))}/></label>
      <label><span>Existing position</span><input type="number" min="0" step="1000" value={existingPosition} onChange={(event) => setExistingPosition(Number(event.target.value))}/></label>
      <div className="baseline-readout"><span>Display baseline</span><strong>{usd(selectedAsset?.price)}</strong><small>Used only as a labelled synthetic seed unless LIVE quorum is qualified.</small></div>
    </section>

    <section className="scenario-bar">
      <button onClick={() => run("NORMAL")} disabled={busy}>1 · Normal market</button>
      <button className="danger" onClick={() => run("POISONED_MARK")} disabled={busy}>2 · Poison venue mark</button>
      <button onClick={() => run("POISONED_MARK", "CLOSE")} disabled={busy}>3 · Prove exit stays open</button>
      <button onClick={recover} disabled={busy}>4 · Recover safely</button>
    </section>

    {error && <div className="v1-error">{error}</div>}
    {!data ? <section className="war-empty">
      <strong>Ready for the judge.</strong>
      <p>AUTO uses a genuinely qualified live reference when the provider quorum exists; otherwise it falls back to a clearly labelled synthetic fixture seeded from the current display price.</p>
      <button className="v1-primary" onClick={() => run("NORMAL")} disabled={busy}>Start demo</button>
    </section> : <>
      <section className="provenance-strip">
        <div><span>DATA MODE</span><strong>{data.story.data_mode.replaceAll("_", " ")}</strong></div>
        <div><span>BASELINE SOURCE</span><strong>{data.story.baseline_source.replaceAll("_", " ")}</strong></div>
        <div><span>BASELINE</span><strong>{usd(data.story.baseline_price)}</strong></div>
        <div><span>ATTACK</span><strong>{data.story.attack_bps.toFixed(0)} bps</strong></div>
        <button onClick={() => setShowEvidence((value) => !value)}>{showEvidence ? "Hide evidence" : "Inspect evidence"}</button>
      </section>
      <section className="truth-stage">
        <div className="evidence-column">
          <span className="v1-kicker">EVIDENCE PROVENANCE</span>
          {showEvidence && data.result.market.evidence.length === 0 && <p className="empty-copy">No qualifying evidence is currently available.</p>}
          {showEvidence && data.result.market.evidence.map((item) => <article key={item.observation_hash}>
            <div><i className={item.fresh && item.eligible ? "healthy" : ""}/><strong>{item.provider}</strong></div>
            <b>{item.source_mode?.replaceAll("_", " ") ?? item.provider_family}</b>
            <small>{item.venue_family} · {item.fresh ? "FRESH" : "STALE"} · {item.eligible ? "ELIGIBLE" : "NOT ELIGIBLE"}</small>
            <small>{usd(item.observed_price)} · {evidenceAge(item.event_time)}</small>
          </article>)}
          {!showEvidence && <p className="empty-copy">Evidence details hidden. Use “Inspect evidence” to reveal provider, price, timestamp and mode.</p>}
        </div>
        <div className="truth-core"><span>MARKET TRUTH</span><strong>{usd(data.result.market.reference_price)}</strong><div className="confidence-ring">{Math.round((data.result.market.confidence ?? 0) * 100)}%<small>confidence</small></div><small>{data.result.market.reference_status?.replaceAll("_", " ")}</small></div>
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
  const [data, setData] = useState<ProviderPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const load = () => void fetch(`${API_BASE}/v1/providers`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Provider registry unavailable");
        setData(await response.json() as ProviderPayload);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Provider registry unavailable"));
    load();
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, []);
  const groups = useMemo(() => data ? {
    core: data.providers.filter((item) => ["alpaca", "hyperliquid"].includes(item.id)),
    context: data.providers.filter((item) => ["marketaux", "sec-edgar", "nasdaq-symbols"].includes(item.id)),
    optional: data.providers.filter((item) => !["alpaca", "hyperliquid", "marketaux", "sec-edgar", "nasdaq-symbols"].includes(item.id)),
  } : null, [data]);
  return <div className="v1-page">
    <header className="v1-page-head"><div><span className="v1-eyebrow">CAPABILITY ≠ CONFIGURATION ≠ HEALTH</span><h1>Free-First Provider Mesh</h1><p>Each adapter exposes what it can do, whether it is configured, and what the runtime has actually observed.</p></div><span className="free-chip">₹0-FIRST</span></header>
    {error && <div className="v1-error">{error}</div>}
    {!groups ? <div className="war-empty">Loading provider registry…</div> : <>{(["core", "context", "optional"] as const).map((group) => <section className="provider-section" key={group}>
      <div className="section-title"><span>{group === "core" ? "01" : group === "context" ? "02" : "03"}</span><div><h2>{group === "core" ? "Live safety core" : group === "context" ? "Intelligence context" : "Optional / fallback"}</h2><p>{group === "core" ? "Runtime evidence used to observe the underlying market or trading venue." : group === "context" ? "Useful information that cannot manufacture Market Truth." : "Optional integrations, kept outside the mandatory safety path."}</p></div></div>
      <div className="provider-grid">{groups[group].map((provider) => <article key={provider.id}>
        <div className="provider-top"><strong>{provider.name}</strong><span className={provider.health === "HEALTHY" ? "on" : ""}>{provider.status}</span></div>
        <h3>{provider.capability.replaceAll("_", " ")}</h3>
        <dl>
          <div><dt>Supported</dt><dd>{provider.supported === false ? "NO" : "YES"}</dd></div>
          <div><dt>Configured</dt><dd>{provider.configured ? "YES" : "NO"}</dd></div>
          <div><dt>Observed health</dt><dd>{(provider.health ?? "UNKNOWN").replaceAll("_", " ")}</dd></div>
          <div><dt>Last event</dt><dd>{provider.runtime?.last_event_time ? new Date(String(provider.runtime.last_event_time)).toLocaleTimeString() : "NOT OBSERVED"}</dd></div>
          <div><dt>Market Truth</dt><dd>{provider.market_truth_authority.replaceAll("_", " ")}</dd></div>
          <div><dt>Risk eligible</dt><dd>{provider.risk_eligible ? "YES" : "NO"}</dd></div>
        </dl>
        <p>{provider.note}</p>
      </article>)}</div>
    </section>)}</>}
    {data && <section className="principle-card"><span className="v1-kicker">NON-NEGOTIABLE BOUNDARIES</span>{data.principles.map((item) => <p key={item}>✓ {item}</p>)}</section>}
  </div>;
}

export function IntelligenceWorkspace() {
  const [symbol, setSymbol] = useState("NVDA"); const [data, setData] = useState<IntelligencePayload | null>(null); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(false);
  useEffect(() => { const controller = new AbortController(); setLoading(true); setError(null); void fetch(`${API_BASE}/v1/intelligence/${symbol}`, { signal: controller.signal, cache: "no-store" }).then(async (response) => { if (!response.ok) throw new Error(`Intelligence unavailable (${response.status})`); setData(await response.json() as IntelligencePayload); }).catch((caught) => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Intelligence unavailable"); }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort(); }, [symbol]);
  const facts = data ? Object.entries(data.official_company_context.facts).filter(([, value]) => value) : [];
  return <div className="v1-page"><header className="v1-page-head"><div><span className="v1-eyebrow">CONTEXT PLANE · NEVER PRICE TRUTH</span><h1>Market Intelligence</h1><p>Financial news plus primary-source SEC events, kept outside the executable reference.</p></div><select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{SYMBOLS.map((item) => <option key={item}>{item}</option>)}</select></header><div className="context-boundary"><strong>CONTEXT ONLY</strong><span>{data?.boundary ?? "News and filings can explain events; they cannot qualify a price or loosen risk."}</span></div>{error && <div className="v1-error">{error}</div>}{loading && !data ? <div className="war-empty">Loading intelligence…</div> : data && <section className="intel-grid"><article className="intel-news"><div className="v1-card-title"><span>FINANCIAL NEWS</span><b>{data.news.status}</b></div>{data.news.articles.length ? data.news.articles.map((article) => <a key={article.id} href={article.url} target="_blank" rel="noreferrer"><small>{article.source} · {article.published_at ? new Date(article.published_at).toLocaleString() : "recent"}</small><strong>{article.title}</strong><p>{article.description}</p>{article.sentiment_score != null && <span>Sentiment {article.sentiment_score.toFixed(2)}</span>}</a>) : <p className="empty-copy">{data.news.message ?? "No articles returned."}</p>}</article><article className="intel-sec"><div className="v1-card-title"><span>OFFICIAL COMPANY CONTEXT</span><b>SEC EDGAR</b></div>{data.official_company_context.company ? <><h2>{data.official_company_context.company.name}</h2><p>CIK {data.official_company_context.company.cik} · {data.official_company_context.company.sic_description ?? "US public company"}</p><div className="fact-grid">{facts.map(([key, fact]) => fact && <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{fact.unit === "USD" ? usd(fact.value) : compact(fact.value)}</strong><small>{fact.form ?? "SEC"} · filed {fact.filed ?? "—"}</small></div>)}</div><h3>Recent official filings</h3><div className="filing-list">{data.official_company_context.recent_filings.slice(0, 6).map((filing) => filing.url ? <a key={`${filing.form}-${filing.filing_date}`} href={filing.url} target="_blank" rel="noreferrer"><strong>{filing.form}</strong><span>{filing.filing_date ?? "—"}</span><small>OFFICIAL SOURCE ↗</small></a> : <div key={`${filing.form}-${filing.filing_date}`}><strong>{filing.form}</strong><span>{filing.filing_date ?? "—"}</span></div>)}</div></> : <p className="empty-copy">{data.official_company_context.message ?? "SEC context unavailable."}</p>}</article></section>}</div>;
}
