"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Clock3, Radio, RefreshCw, ShieldOff, Wifi, WifiOff } from "lucide-react";
import type { ShadowSnapshot } from "@/lib/types";

const TradingChart = dynamic(() => import("./trading-chart"), {
  ssr: false,
  loading: () => <div className="chart-skeleton" aria-label="Loading shadow-oracle chart"/>,
});
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

function words(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/^\w/, (letter) => letter.toUpperCase());
}

function age(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor(seconds % 86400 / 3600)}h`;
}

export default function LiveView({ onFallback }: { onFallback: () => void }) {
  const [snapshot, setSnapshot] = useState<ShadowSnapshot | null>(null);
  const [selected, setSelected] = useState("NVDA");
  const [connected, setConnected] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${API_BASE}/v1/shadow/snapshot`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() as Promise<ShadowSnapshot> : Promise.reject(new Error(`Shadow endpoint returned ${response.status}`)))
      .then(setSnapshot)
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Shadow pipeline unavailable"); });
    const stream = new EventSource(`${API_BASE}/v1/shadow/stream`);
    stream.onopen = () => setConnected(true);
    stream.onmessage = (event) => { setSnapshot(JSON.parse(event.data) as ShadowSnapshot); setConnected(true); setError(null); };
    stream.onerror = () => setConnected(false);
    return () => { controller.abort(); stream.close(); };
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      const response = await fetch(`${API_BASE}/v1/shadow/refresh`, { method: "POST", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Yahoo refresh returned ${response.status}`);
      setSnapshot(await response.json() as ShadowSnapshot);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yahoo refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  const live = snapshot?.yahoo;
  const observation = live?.observations.find((item) => item.symbol === selected) ?? live?.observations[0];
  const decision = snapshot?.decisions.find((item) => item.symbol === observation?.symbol);
  const mochatradeConnected = snapshot?.providers.some((provider) => provider.id === "mochatrade" && provider.status === "AVAILABLE");
  const chartSeries = useMemo(() => observation ? [{
    key: "yahoo-observation", label: `${observation.symbol} Yahoo observation`, color: "#3861fb", area: true,
    data: observation.points.map((point) => ({ time: point.timestamp, value: point.price })),
  }] : [], [observation]);

  if (error && !snapshot) return <div className="live-unavailable"><WifiOff size={28}/><h1>Shadow pipeline unavailable</h1><p>{error}. The deterministic safety lab still works without internet.</p><div><button className="button primary" onClick={() => window.location.reload()}><RefreshCw size={14}/>Retry pipeline</button><button className="button secondary" onClick={onFallback}>Open safety lab</button></div></div>;
  if (!snapshot || !live) return <div className="loading-state live-loading" role="status"><span className="loading-spinner"/><strong>Starting the shadow oracle…</strong><span>Yahoo bootstraps in the background; requests stay responsive.</span></div>;

  return <div className="live-view">
    <section className="live-hero">
      <div><h1>Shadow the mark.<br/>Measure every decision.</h1><p>MarketBridge keeps provider work off the risk path, preserves original source families, and streams advisory decisions to this console.</p></div>
      <button className="button secondary" onClick={() => void refresh()} disabled={refreshing}><RefreshCw size={14} className={refreshing ? "spinning" : ""}/>{refreshing ? "Refreshing Yahoo…" : "Refresh research feed"}</button>
    </section>

    <div className="shadow-runtime" role="status"><span className={connected ? "connected" : "reconnecting"}><Radio size={13}/>{connected ? "Decision stream connected" : "Decision stream reconnecting"}</span><span>Generation {snapshot.generation}</span><span>Advisory only</span></div>

    <div className="provider-strip">{snapshot.providers.map((provider) => <div key={provider.id} className="provider-cell"><span>{provider.id === "yahoo" ? "Yahoo research" : provider.id === "alpaca" ? "Alpaca venues" : "Mochatrade mark"}</span><strong className={provider.status === "AVAILABLE" ? "positive" : provider.status === "DISABLED" ? "muted" : "warning"}><i/>{words(provider.status)}</strong><small>{provider.detail}</small></div>)}</div>

    <div className="live-status-grid shadow-metrics">
      <div className="panel live-stat"><span>US market phase</span><strong>{words(live.market_phase)}</strong><small>Actual event age determines freshness</small></div>
      <div className="panel live-stat"><span>Decision latency · p50</span><strong>{snapshot.latency.p50_ms == null ? "—" : `${snapshot.latency.p50_ms.toFixed(3)} ms`}</strong><small>{snapshot.latency.samples} in-process decisions</small></div>
      <div className="panel live-stat"><span>Decision latency · p95</span><strong>{snapshot.latency.p95_ms == null ? "—" : `${snapshot.latency.p95_ms.toFixed(3)} ms`}</strong><small>Measured before asynchronous audit I/O</small></div>
      <div className="panel live-stat"><span>Console delivery target</span><strong>&lt; {snapshot.latency.ui_delivery_target_ms} ms</strong><small>Server-sent event change detection</small></div>
    </div>

    {error || live.errors.length ? <div className="live-warning"><WifiOff size={15}/><span>{error ?? live.errors.map((item) => `${item.symbol}: ${item.message}`).join(" · ")}</span></div> : null}

    <section className="panel live-market-panel">
      <div className="panel-heading"><div><h2>Observed market data</h2><p>Yahoo research is visible but excluded from oracle corroboration.</p></div><span className="small-label">SOURCE LINEAGE PRESERVED</span></div>
      <div className="table-scroll"><table className="live-market-table"><thead><tr><th>Instrument</th><th>Observed price</th><th>Daily change</th><th>Event age</th><th>Original feed</th></tr></thead><tbody>{live.observations.map((item) => <tr key={item.symbol} className={observation?.symbol === item.symbol ? "selected" : ""} onClick={() => setSelected(item.symbol)}><td><button onClick={() => setSelected(item.symbol)}><strong>{item.symbol}</strong><span>{item.name}</span></button></td><td>{money.format(item.observed_price)}</td><td className={(item.change_pct ?? 0) >= 0 ? "positive" : "negative"}>{item.change_pct == null ? "—" : `${item.change_pct >= 0 ? "+" : ""}${item.change_pct.toFixed(2)}%`}</td><td>{age(item.age_seconds)} <span className={`feed-state ${item.source.status.toLowerCase()}`}>{item.source.status.toLowerCase()}</span></td><td>{item.exchange} · Yahoo research</td></tr>)}</tbody></table></div>
    </section>

    {observation ? <div className="live-detail-grid">
      <section className="panel live-chart-panel"><div className="panel-heading"><div><h2>{observation.symbol} · one-minute observations</h2><p>Latest {observation.points.length} points, including extended hours when Yahoo supplies them.</p></div><Activity size={17}/></div><TradingChart series={chartSeries} ariaLabel={`${observation.symbol} Yahoo research observations. Latest ${money.format(observation.observed_price)}.`} height={330}/><a className="tradingview-attribution" href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">Charts by TradingView</a></section>
      <aside className="panel live-decision"><span className="decision-icon"><ShieldOff size={20}/></span><span className="mode-label">LATEST SHADOW DECISION</span><h2>{decision?.status === "QUALIFIED" ? "Reference qualified" : "Not liquidation eligible"}</h2><p>{decision?.status === "QUALIFIED" ? "At least two fresh original venue families agree within the configured dispersion bound." : "Yahoo is a single research family. MarketBridge displays it without silently turning it into an oracle."}</p><dl><div><dt>Observed</dt><dd>{money.format(observation.observed_price)}</dd></div><div><dt>Oracle reference</dt><dd>{decision?.reference == null ? "Not published" : money.format(decision.reference)}</dd></div><div><dt>Eligible families</dt><dd>{decision?.independent_source_families ?? 0}</dd></div><div><dt>Mochatrade mark</dt><dd>{decision?.venue_mark ? money.format(decision.venue_mark.price) : "Waiting"}</dd></div></dl><button className="text-button" onClick={onFallback}>Stress-test the guard<ArrowRight size={14}/></button></aside>
    </div> : null}

    <section className="panel decision-log-panel"><div className="panel-heading"><div><h2>Decision audit log</h2><p>Newest first · JSONL persistence runs outside the decision timer.</p></div><span className="small-label">{snapshot.decision_log.length} IN SESSION</span></div>{snapshot.decision_log.length ? <div className="decision-log-list">{snapshot.decision_log.slice(0, 8).map((item) => <div key={item.decision_id}><time>{new Date(item.timestamp).toLocaleTimeString()}</time><strong>{item.symbol}</strong><span className={`quality-text ${item.status.toLowerCase()}`}>{words(item.status)}</span><span>{item.reference == null ? "Abstained" : money.format(item.reference)}</span><span>{item.independent_source_families} eligible families</span><span>{item.decision_latency_ms.toFixed(3)} ms</span></div>)}</div> : <div className="decision-log-empty">Waiting for the first normalized observation.</div>}</section>

    <div className="live-boundary"><Clock3 size={15}/><p><strong>Evidence boundary:</strong> Yahoo remains research-only, Alpaca activates only when credentials are configured, and the Mochatrade adapter is {mochatradeConnected ? "receiving advisory venue marks" : "waiting for a venue mark"}. No customer order or production oracle is changed.</p></div>
  </div>;
}
