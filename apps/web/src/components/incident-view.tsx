"use client";

import dynamic from "next/dynamic";
import { ArrowRight, BookOpen, Database, ExternalLink, ShieldOff, TriangleAlert } from "lucide-react";
import type { Incident } from "@/lib/types";

const TradingChart = dynamic(() => import("./trading-chart"), {
  ssr: false,
  loading: () => <div className="chart-skeleton" aria-label="Loading incident chart"/>,
});

const usdCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export default function IncidentView({ incident, loading, error, onTryDemo }: { incident: Incident | null; loading: boolean; error: string | null; onTryDemo: () => void }) {
  if (loading) return <div className="chart-skeleton incident-loading" aria-label="Loading historical reconstruction"/>;
  if (error || !incident) return <div className="incident-error"><TriangleAlert size={22}/><strong>Historical reconstruction unavailable</strong><span>{error ?? "The incident evidence could not be loaded."}</span></div>;
  const series = [
    { key: "reported-mark", label: "Reported perp mark", color: "#3861fb", area: true, data: incident.points.map((point) => ({ time: point.timestamp, value: point.reported_mark })) },
    { key: "oracle", label: "Oracle", color: "#8d6bd1", data: incident.points.map((point) => ({ time: point.timestamp, value: point.oracle_price })) },
    { key: "external", label: "External cash print", color: "#e49a38", dashed: true, data: incident.points.map((point) => ({ time: point.timestamp, value: point.external_price })) },
  ];
  return <div className="incident-view">
    <section className="incident-hero">
      <div>
        <span className="mode-label"><Database size={13}/>Historical reconstruction · published transactions</span>
        <h1>One thin-market print.<br/>A leveraged-market shock.</h1>
        <p>{incident.summary}</p>
        <div className="incident-actions"><button className="button primary" onClick={onTryDemo}>Test the guard in the safety lab<ArrowRight size={15}/></button><a className="button secondary" href={incident.sources[1].url} target="_blank" rel="noopener noreferrer">Inspect transactions<ExternalLink size={14}/></a></div>
      </div>
      <div className="incident-proof" aria-label="Reported incident figures">
        <div><strong>1 share</strong><span>thin NXT pre-market execution</span></div>
        <div><strong>{incident.facts.reported_mark_drop_pct}%</strong><span>reported perpetual mark move</span></div>
        <div><strong>{usdCompact.format(incident.facts.reported_liquidated_notional_usd_approx)}</strong><span>approximate liquidated long notional</span></div>
      </div>
    </section>

    <section className="panel incident-chart-panel">
      <div className="panel-heading incident-chart-heading"><div><h2>{incident.symbol} · external-price handoff</h2><p>Reported and reconstructed values from transaction-linked analysis · {incident.date}</p></div><span className="history-badge">REAL EVENT · RECONSTRUCTED</span></div>
      <div className="chart-legend incident-legend"><span><i className="legend-dot reference"/>Reported perp mark</span><span><i className="legend-dot incident-oracle"/>Oracle</span><span><i className="legend-dot comparator"/>External cash print</span></div>
      <TradingChart series={series} ariaLabel={`Historical reconstruction for ${incident.symbol}. Reported mark moved from ${usd.format(incident.facts.reported_mark_before)} to ${usd.format(incident.facts.reported_mark_low)}.`}/>
      <a className="tradingview-attribution" href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">Charts by TradingView</a>
    </section>

    <div className="incident-decision-grid">
      <section className="operator-decision danger-panel">
        <span className="decision-icon"><ShieldOff size={22}/></span>
        <div><span className="mode-label">Counterfactual advisory</span><h2>Do not publish a liquidation reference.</h2><p>{incident.operator_decision.explanation}</p></div>
        <dl><div><dt>Status</dt><dd>Insufficient evidence</dd></div><div><dt>Independent families</dt><dd>{incident.operator_decision.independent_source_families}</dd></div><div><dt>New exposure</dt><dd>Blocked</dd></div></dl>
      </section>
      <section className="panel evidence-boundary">
        <BookOpen size={20}/><h2>What this evidence can—and cannot—show</h2>
        <ul>{incident.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        <div className="source-links">{incident.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer">{source.title}<ExternalLink size={13}/></a>)}</div>
      </section>
    </div>
  </div>;
}
