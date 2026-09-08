"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ArrowRight, CircleAlert, Gauge, Radio, RefreshCw, Search,
  ShieldCheck, ShieldOff, Wifi, WifiOff,
} from "lucide-react";
import type { RiskState, ShadowDecision, ShadowSnapshot } from "@/lib/types";

const TradingChart = dynamic(() => import("./trading-chart"), {
  ssr: false,
  loading: () => <div className="chart-skeleton" aria-label="Loading market chart"/>,
});

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const fmt = (value: number | null | undefined, digits = 1) => value == null ? "—" : value.toFixed(digits);

function words(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/^\w/, (letter) => letter.toUpperCase());
}

function riskClass(state: RiskState) {
  return state === "NORMAL" ? "risk-normal" : state === "GUARDED" ? "risk-guarded" : state === "RESTRICTED" ? "risk-restricted" : "risk-halted";
}

function transportUrl() {
  if (API_BASE) return API_BASE.replace(/^http/, "ws") + "/v1/shadow/ws";
  if (typeof window === "undefined") return "";
  return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/v1/shadow/ws`;
}

export default function LiveView({ onFallback }: { onFallback: () => void }) {
  const [snapshot, setSnapshot] = useState<ShadowSnapshot | null>(null);
  const [selected, setSelected] = useState("NVDA");
  const [connected, setConnected] = useState(false);
  const [transport, setTransport] = useState<"WS" | "SSE" | "OFFLINE">("OFFLINE");
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const renderTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<ShadowSnapshot | null>(null);

  function coalesce(next: ShadowSnapshot) {
    pending.current = next;
    if (renderTimer.current) return;
    renderTimer.current = setTimeout(() => {
      if (pending.current) setSnapshot(pending.current);
      pending.current = null;
      renderTimer.current = null;
    }, 120);
  }

  useEffect(() => {
    const controller = new AbortController();
    let stream: EventSource | null = null;
    let socket: WebSocket | null = null;
    let stopped = false;

    void fetch(`${API_BASE}/v1/shadow/snapshot`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() as Promise<ShadowSnapshot> : Promise.reject(new Error(`Shadow endpoint returned ${response.status}`)))
      .then(setSnapshot)
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Shadow pipeline unavailable"); });

    const startSse = () => {
      if (stopped || stream) return;
      stream = new EventSource(`${API_BASE}/v1/shadow/stream`);
      stream.onopen = () => { setConnected(true); setTransport("SSE"); };
      stream.onmessage = (event) => { coalesce(JSON.parse(event.data) as ShadowSnapshot); setConnected(true); setError(null); };
      stream.onerror = () => setConnected(false);
    };

    try {
      socket = new WebSocket(transportUrl());
      socket.onopen = () => { setConnected(true); setTransport("WS"); setError(null); };
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as { type: string; data?: ShadowSnapshot };
        if (payload.type === "shadow_snapshot" && payload.data) coalesce(payload.data);
      };
      socket.onerror = () => { socket?.close(); startSse(); };
      socket.onclose = () => { if (!stopped) { setConnected(false); startSse(); } };
    } catch {
      startSse();
    }

    return () => {
      stopped = true;
      controller.abort();
      socket?.close();
      stream?.close();
      if (renderTimer.current) clearTimeout(renderTimer.current);
    };
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      const response = await fetch(`${API_BASE}/v1/shadow/refresh`, { method: "POST", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Research refresh returned ${response.status}`);
      setSnapshot(await response.json() as ShadowSnapshot);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Research refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  const decisions = useMemo(() => (snapshot?.decisions ?? []).filter((item) => item.symbol.toLowerCase().includes(query.toLowerCase())), [snapshot, query]);
  const selectedDecision = snapshot?.decisions.find((item) => item.symbol === selected) ?? decisions[0];
  const selectedObservation = snapshot?.yahoo?.observations.find((item) => item.symbol === selectedDecision?.symbol);
  const history = useMemo(() => (snapshot?.decision_log ?? []).filter((item) => item.symbol === selectedDecision?.symbol).slice().reverse(), [snapshot, selectedDecision?.symbol]);
  const chartSeries = useMemo(() => {
    const output = [] as { key: string; label: string; color: string; data: { time: string; value: number | null }[]; area?: boolean; dashed?: boolean }[];
    if (selectedObservation) output.push({ key: "research", label: "Observed research price", color: "#3861fb", area: true, data: selectedObservation.points.map((point) => ({ time: point.timestamp, value: point.price })) });
    if (history.length) {
      output.push({ key: "reference", label: "MarketBridge reference", color: "#16c784", data: history.map((item) => ({ time: item.timestamp, value: item.reference })) });
      output.push({ key: "mark", label: "Venue mark", color: "#ea3943", dashed: true, data: history.map((item) => ({ time: item.timestamp, value: item.venue_mark?.price ?? null })) });
      output.push({ key: "upper-bound", label: "Upper band", color: "#8a9cc8", dashed: true, data: history.map((item) => ({ time: item.timestamp, value: item.band_upper })) });
      output.push({ key: "lower-bound", label: "Lower band", color: "#8a9cc8", dashed: true, data: history.map((item) => ({ time: item.timestamp, value: item.band_lower })) });
    }
    return output;
  }, [selectedObservation, history]);

  const guarded = snapshot?.decisions.filter((item) => item.risk_state !== "NORMAL").length ?? 0;
  const healthyFeeds = snapshot?.providers.filter((item) => item.status === "AVAILABLE").length ?? 0;

  if (error && !snapshot) return <div className="live-unavailable"><WifiOff size={28}/><h1>Live pipeline unavailable</h1><p>{error}. The deterministic replay lab still works without market connectivity.</p><div><button className="button primary" onClick={() => window.location.reload()}><RefreshCw size={14}/>Retry</button><button className="button secondary" onClick={onFallback}>Open safety lab</button></div></div>;
  if (!snapshot) return <div className="loading-state live-loading" role="status"><span className="loading-spinner"/><strong>Starting MarketBridge…</strong><span>Connecting the risk engine and market-data adapters.</span></div>;

  return <div className="live-view cmc-live">
    <section className="market-topbar">
      <div><span className="eyebrow"><Radio size={12}/>MARKETBRIDGE LIVE</span><h1>Market integrity for 24/7 equity perps</h1><p>Independent evidence, fair-value confidence and dynamic risk in one operator console.</p></div>
      <div className="market-top-actions"><span className={`transport-pill ${connected ? "online" : "offline"}`}><i/>{connected ? `${transport} connected` : "reconnecting"}</span><button className="button secondary" onClick={() => void refresh()} disabled={refreshing}><RefreshCw size={14} className={refreshing ? "spinning" : ""}/>{refreshing ? "Refreshing…" : "Refresh"}</button></div>
    </section>

    <section className="market-kpis">
      <div className="panel kpi"><span>System health</span><strong className={connected ? "positive" : "warning"}>{connected ? "Healthy" : "Degraded"}</strong><small>Generation {snapshot.generation}</small></div>
      <div className="panel kpi"><span>Live feeds</span><strong>{healthyFeeds}/{snapshot.providers.length}</strong><small>Provider health is visible below</small></div>
      <div className="panel kpi"><span>p95 decision</span><strong>{snapshot.latency.p95_ms == null ? "—" : `${snapshot.latency.p95_ms.toFixed(3)} ms`}</strong><small>Receipt → advisory decision</small></div>
      <div className="panel kpi"><span>Guarded markets</span><strong className={guarded ? "warning" : "positive"}>{guarded}</strong><small>Restricted or guarded right now</small></div>
    </section>

    <section className="panel market-screener">
      <div className="market-screener-head"><div><h2>Markets</h2><p>Venue mark versus MarketBridge reference. Select an asset to inspect its evidence.</p></div><label className="market-search"><Search size={15}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search assets" aria-label="Search assets"/></label></div>
      <div className="table-scroll"><table className="integrity-table"><thead><tr><th>Asset</th><th>MB reference</th><th>Venue mark</th><th>Δ bps</th><th>Confidence</th><th>Band</th><th>Risk</th><th>Max lev.</th><th>Evidence</th></tr></thead><tbody>{decisions.map((item) => <tr key={item.symbol} className={selectedDecision?.symbol === item.symbol ? "selected" : ""} onClick={() => setSelected(item.symbol)}><td><button className="market-symbol" onClick={() => setSelected(item.symbol)}><strong>{item.symbol}</strong><span>{item.status === "ESTIMATED" ? "factor estimate" : item.status === "QUALIFIED" ? "direct consensus" : "waiting for evidence"}</span></button></td><td className="price-cell">{item.reference == null ? "—" : money.format(item.reference)}</td><td>{item.venue_mark ? money.format(item.venue_mark.price) : "Waiting"}</td><td className={(item.mark_divergence_bps ?? 0) > 75 ? "negative" : "muted"}>{item.mark_divergence_bps == null ? "—" : `${fmt(item.mark_divergence_bps)} bp`}</td><td><div className="confidence-cell"><span>{fmt(item.confidence, 0)}%</span><i><b style={{ width: `${Math.max(0, Math.min(100, item.confidence))}%` }}/></i></div></td><td>±{fmt(item.band_bps, 0)} bp</td><td><span className={`risk-badge ${riskClass(item.risk_state)}`}>{item.risk_state}</span></td><td>{item.recommended_max_leverage}×</td><td>{item.independent_provider_families}P / {item.independent_source_families}V</td></tr>)}</tbody></table></div>
      {!decisions.length ? <div className="empty-market"><CircleAlert size={18}/>No matching assets have a live decision yet.</div> : null}
    </section>

    {selectedDecision ? <div className="integrity-detail-grid">
      <section className="panel integrity-chart"><div className="panel-heading"><div><span className="eyebrow">{selectedDecision.symbol} · LIVE DETAIL</span><h2>{selectedDecision.reference == null ? "Waiting for a defensible reference" : money.format(selectedDecision.reference)}</h2><p>{selectedDecision.status === "QUALIFIED" ? "Direct independent venues agree." : selectedDecision.status === "ESTIMATED" ? "Conservative factor estimate; risk is automatically tighter." : "Evidence is not strong enough to publish a reference."}</p></div><span className={`risk-badge big ${riskClass(selectedDecision.risk_state)}`}>{selectedDecision.risk_state}</span></div>{chartSeries.length ? <TradingChart series={chartSeries} ariaLabel={`${selectedDecision.symbol} MarketBridge reference, venue mark and confidence band`} height={350}/> : <div className="chart-empty"><Activity size={22}/><span>Chart history appears as live decisions arrive.</span></div>}</section>
      <aside className="panel risk-card"><div className={`risk-icon ${riskClass(selectedDecision.risk_state)}`}>{selectedDecision.risk_state === "NORMAL" ? <ShieldCheck/> : <ShieldOff/>}</div><span className="eyebrow">RISK RECOMMENDATION</span><h2>{selectedDecision.recommended_max_leverage}× max leverage</h2><p>Prototype advisory policy only. MarketBridge never executes a liquidation or order in this demo.</p><dl><div><dt>Confidence</dt><dd>{fmt(selectedDecision.confidence, 0)}%</dd></div><div><dt>Divergence</dt><dd>{selectedDecision.mark_divergence_bps == null ? "—" : `${fmt(selectedDecision.mark_divergence_bps)} bp`}</dd></div><div><dt>Notional multiplier</dt><dd>{Math.round(selectedDecision.max_notional_multiplier * 100)}%</dd></div><div><dt>Status</dt><dd>{words(selectedDecision.status)}</dd></div></dl><button className="text-button" onClick={onFallback}>Stress-test this policy <ArrowRight size={14}/></button></aside>
    </div> : null}

    {selectedDecision ? <section className="panel evidence-console"><div className="panel-heading"><div><h2>Source evidence</h2><p>Provider and venue independence are tracked separately.</p></div><span className="small-label">{selectedDecision.evidence.length} OBSERVATIONS</span></div><div className="evidence-list">{selectedDecision.evidence.map((item) => <div key={`${item.provider_family}-${item.venue_family}-${item.source_id}`}><span className={`feed-dot ${item.fresh && item.eligible ? "healthy" : "muted"}`}/><div><strong>{item.provider_family} · {item.venue_family}</strong><span>{item.source_id} · {item.eligible ? "eligible" : "display only"}</span></div><b>{money.format(item.price)}</b><small>{Math.round(item.age_seconds * 1000)} ms age</small></div>)}</div></section> : null}

    <div className="ops-grid">
      <section className="panel provider-health"><div className="panel-heading"><div><h2>Provider health</h2><p>Disconnected feeds lower confidence instead of silently disappearing.</p></div><Wifi size={17}/></div>{snapshot.providers.map((provider) => <div key={provider.id} className="provider-health-row"><span className={`feed-dot ${provider.status === "AVAILABLE" ? "healthy" : provider.status === "DISABLED" ? "muted" : "warning"}`}/><div><strong>{provider.id}</strong><small>{provider.kind}</small></div><b>{words(provider.status)}</b><span>{provider.detail}</span></div>)}</section>
      <section className="panel latency-pipeline"><div className="panel-heading"><div><h2>Latency pipeline</h2><p>Measure the chain that matters, not only function runtime.</p></div><Gauge size={17}/></div><div className="latency-flow"><div><span>Source event age · p95</span><strong>{snapshot.latency.source_event_age_p95_ms == null ? "—" : `${fmt(snapshot.latency.source_event_age_p95_ms)} ms`}</strong></div><i>→</i><div><span>Decision · p50</span><strong>{snapshot.latency.p50_ms == null ? "—" : `${fmt(snapshot.latency.p50_ms, 3)} ms`}</strong></div><i>→</i><div><span>Decision · p95</span><strong>{snapshot.latency.p95_ms == null ? "—" : `${fmt(snapshot.latency.p95_ms, 3)} ms`}</strong></div><i>→</i><div><span>UI target</span><strong>&lt; {snapshot.latency.ui_delivery_target_ms} ms</strong></div></div></section>
    </div>
  </div>;
}
