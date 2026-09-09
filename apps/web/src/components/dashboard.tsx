"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowDown, ArrowDownToLine, ArrowRight, ArrowUp, BookOpen, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, Clock3, ExternalLink, FlaskConical, Layers3, Pause, Play, Radio, RotateCcw, ShieldCheck, ShieldOff, SkipForward, SlidersHorizontal, TriangleAlert, X } from "lucide-react";
import IncidentView from "./incident-view";
import LiveView from "./live-view";
import OperatorPayload from "./operator-payload";
import type { Catalog, Evaluation, Incident, Quality, Scenario, Source, Step, SymbolInfo, Trace } from "@/lib/types";

const TradingChart = dynamic(() => import("./trading-chart"), {
  ssr: false,
  loading: () => <div className="chart-skeleton" aria-label="Loading financial chart"/>,
});

type Tab = "overview" | "live" | "incident" | "evaluation" | "methodology";
type SeriesKey = "reference" | "comparator" | "baseline";
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const qualityLabels: Record<Quality, string> = { QUALIFIED: "Qualified", CAUTION: "Caution", INSUFFICIENT_EVIDENCE: "Insufficient evidence", RECOVERING: "Recovering" };
const assessmentLabels = { ACCEPT: "Observation accepted", REJECT: "Observation rejected", QUARANTINE: "Observation quarantined", NONE: "No new observation" };
const seriesLabels: Record<SeriesKey, string> = { reference: "MarketBridge", comparator: "Unguarded feed", baseline: "QQQ factor baseline" };
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const money = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? "—" : usd.format(value);
const metric = (value: number | null | undefined, suffix = "") => value == null || !Number.isFinite(value) ? "—" : `${number.format(value)}${suffix}`;
const elapsed = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
const change = (value: number | null | undefined, base: number) => value == null || base === 0 ? null : (value / base - 1) * 100;
const humanize = (text: string) => text.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());

async function getJSON<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`The demo service returned ${response.status}. Please try again.`);
  return response.json() as Promise<T>;
}

function downloadJSON(value: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Mark({ small = false }: { small?: boolean }) {
  return <span className={`brand-mark${small ? " small" : ""}`} aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M6 23V13.5C6 9.4 10.2 7.7 13 10.8L16 14l3-3.2c2.8-3.1 7-1.4 7 2.7V23" stroke="currentColor" strokeWidth="3.3" strokeLinecap="round" strokeLinejoin="round"/><path d="M6 19h20M16 14v9" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg></span>;
}

function AssetIcon({ symbol, small = false }: { symbol: string; small?: boolean }) {
  return <span aria-hidden="true" className={`asset-icon ${symbol.toLowerCase()}${small ? " small" : ""}`}>{symbol === "NVDA" ? "N" : symbol === "TSLA" ? "T" : symbol.slice(0, 1)}</span>;
}

function QualityBadge({ quality }: { quality: Quality }) {
  return <span className={`quality-badge ${quality.toLowerCase()}`}><span className="status-dot"/>{qualityLabels[quality]}</span>;
}

function PriceChange({ value }: { value: number | null }) {
  if (value == null) return <span className="muted">—</span>;
  return <span className={`price-change ${value >= 0 ? "positive" : "negative"}`}>{value >= 0 ? <ArrowUp size={12}/> : <ArrowDown size={12}/>} {Math.abs(value).toFixed(2)}%</span>;
}

function Sparkline({ steps, blue = false }: { steps: Step[]; blue?: boolean }) {
  const values = steps.map((step) => step.reference).filter((value): value is number => value !== null);
  if (!values.length) return <span className="muted tiny">No reference</span>;
  const low = Math.min(...values), high = Math.max(...values), range = Math.max(high - low, 0.1);
  const points = values.map((value, index) => `${4 + index / Math.max(values.length - 1, 1) * 110},${29 - (value - low) / range * 22}`).join(" ");
  return <svg className={`sparkline${blue ? " blue" : values[values.length - 1] >= values[0] ? " up" : " down"}`} viewBox="0 0 118 36" aria-label="Reference price up to the replay cursor" role="img"><polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>{values.length === 1 && <circle cx="4" cy="29" r="2.5" fill="currentColor"/>}</svg>;
}

function Loading({ message = "Loading the market scenarios…" }: { message?: string }) {
  return <div className="loading-state" role="status"><span className="loading-spinner"/><strong>{message}</strong><span>Preparing your deterministic replay.</span></div>;
}

function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return <div className="error-state" role="alert"><TriangleAlert size={25}/><h2>We couldn’t load this view</h2><p>{message}</p><button className="button primary" onClick={retry}><RotateCcw size={15}/>Try again</button></div>;
}

function InteractivePriceChart({ steps, current, endTime, series, onPlay, playing }: { steps: Step[]; current: Step; endTime: string; series: Record<SeriesKey, boolean>; onPlay: () => void; playing: boolean }) {
  const chartSeries = useMemo(() => [
    { key: "reference", label: "MarketBridge", color: "#3861fb", area: true, visible: series.reference, data: steps.map((step) => ({ time: step.timestamp, value: step.reference })) },
    { key: "comparator", label: "Unguarded feed", color: "#e6a04a", visible: series.comparator, data: steps.map((step) => ({ time: step.timestamp, value: step.comparator })) },
    { key: "baseline", label: "QQQ factor baseline", color: "#9ba7ba", dashed: true, visible: series.baseline, data: steps.map((step) => ({ time: step.timestamp, value: step.baseline })) },
    { key: "lower-bound", label: "Range lower", color: "#b7c5f6", dashed: true, visible: series.reference, data: steps.map((step) => ({ time: step.timestamp, value: step.lower })) },
    { key: "upper-bound", label: "Range upper", color: "#b7c5f6", dashed: true, visible: series.reference, data: steps.map((step) => ({ time: step.timestamp, value: step.upper })) },
  ], [series, steps]);
  return <div className="price-chart interactive-price-chart">
    <TradingChart series={chartSeries} endTime={endTime} ariaLabel={`Synthetic reference chart through ${elapsed(current.seconds)}. MarketBridge ${money(current.reference)}. Unguarded feed ${money(current.comparator)}.`}/>
    {current.reference === null ? <div className="chart-abstain-banner">Reference unavailable · last valid value is not a current price</div> : null}
    {steps.length === 1 && !playing ? <div className="chart-ready"><span className="chart-ready-icon"><Activity size={22}/></span><strong>The market story starts here</strong><span>Play the scenario to follow each observation.</span><button className="button primary compact" onClick={onPlay}><Play size={13} fill="currentColor"/>Play replay</button></div> : null}
  </div>;
}

function EvidencePanel({ step }: { step: Step }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return <section className="panel evidence-panel" aria-labelledby="evidence-title">
    <div className="panel-heading"><div><h2 id="evidence-title">Source evidence</h2><p>What supports this reference</p></div><span className="icon-tile"><Layers3 size={17}/></span></div>
    <div className="evidence-summary"><span><strong>{step.source_count}</strong> independent {step.source_count === 1 ? "source" : "sources"}</span><span className="tiny muted">At {elapsed(step.seconds)}</span></div>
    <div className="source-list">{step.sources.map((source, index) => <SourceRow key={source.id} source={source} index={index} expanded={expanded === source.id} onToggle={() => setExpanded(expanded === source.id ? null : source.id)}/>)}</div>
    <div className={`assessment-box ${step.assessment.toLowerCase()}`}><div><ShieldCheck size={16}/><strong>{assessmentLabels[step.assessment]}</strong></div><ul>{step.reasons.length ? step.reasons.map((reason, index) => <li key={index}>{humanize(reason)}</li>) : <li>Waiting for the next observation.</li>}</ul></div>
    <div className="evidence-footnote"><CircleHelp size={13}/><span>Source families determine independence. All sources shown here are simulated.</span></div>
  </section>;
}

function SourceRow({ source, index, expanded, onToggle }: { source: Source; index: number; expanded: boolean; onToggle: () => void }) {
  return <div className={`source-item ${source.status.toLowerCase()}`}><button className="source-trigger" onClick={onToggle} aria-expanded={expanded} aria-label={`${source.name}, ${source.status.toLowerCase()}, show source details`}><span className="source-symbol">{String(index + 1).padStart(2, "0")}</span><span className="source-main"><strong>{source.name}</strong><span><i className="status-dot"/>{humanize(source.status.toLowerCase())}<span className="source-age">{source.status === "MISSING" || source.event_time === null ? "No observation" : metric(source.age_seconds, "s old")}</span></span></span><span className="source-price">{money(source.price)}<ChevronDown size={13} className={expanded ? "rotated" : ""}/></span></button>{expanded && <dl className="source-details"><div><dt>Original family</dt><dd>{source.family}</dd></div><div><dt>Model weight</dt><dd>{metric(source.weight * 100, "%")}</dd></div><div><dt>Event time (UTC)</dt><dd>{source.event_time ? new Date(source.event_time).toISOString().slice(11, 19) : "Unavailable"}</dd></div></dl>}</div>;
}

function Simulator({ step, trace }: { step: Step; trace: Trace }) {
  const simulation = step.simulation;
  return <section className="panel simulator-panel" aria-labelledby="simulator-title">
    <div className="panel-heading"><div><div className="heading-with-tag"><h2 id="simulator-title">Paper account</h2><span className="small-label">SIMULATOR ONLY</span></div><p>The same position. Two ways to handle the evidence.</p></div><span className="icon-tile"><ShieldCheck size={18}/></span></div>
    <div className="simulator-grid"><div className="account-stat"><span><i className="legend-dot reference"/>With MarketBridge</span><strong>{money(simulation.equity)}</strong><small>{simulation.valuation_status === "UNRESOLVED" ? "Valuation unresolved" : simulation.reference_liquidated ? "Position liquidated · exit equity" : "Current account equity"}</small></div><div className="account-stat"><span><i className="legend-dot comparator"/>Unguarded feed</span><strong>{money(simulation.baseline_equity)}</strong><small>{simulation.baseline_liquidated ? "Position liquidated · exit equity" : "Same position and fill assumptions"}</small></div><div className={`exposure-state ${simulation.new_exposure_allowed ? "allowed" : "blocked"}`}>{simulation.new_exposure_allowed ? <ShieldCheck size={19}/> : <ShieldOff size={19}/>}<div><strong>{simulation.new_exposure_allowed ? "New exposure permitted" : "New exposure blocked"}</strong><p>{simulation.new_exposure_allowed ? `Demo exposure allowance: ${number.format(simulation.exposure_limit * 100)}%` : "Waiting for sufficient qualified evidence"}</p></div></div></div>
    <details className="assumptions"><summary><CircleHelp size={14}/>Position & simulation assumptions<ChevronDown size={14}/></summary><ul>{trace.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul><p>Scenario outcomes are hypothetical. They do not demonstrate prevented losses or replicate a real venue’s liquidation engine.</p></details>
  </section>;
}

function PolicyComparisonTable({ evaluation }: { evaluation: Evaluation }) {
  const benchmark = evaluation.cases.find((item) => item.scenario_id === "bad-print" && item.symbol === "NVDA");
  if (!benchmark) return null;
  return <section className="panel policy-comparison">
    <div className="panel-heading"><div><h2>Four policies. The same observations.</h2><p>Bad-print synthetic stress test · identical fixture truth · availability must be read beside error.</p></div><span className="small-label">POLICY BENCHMARK</span></div>
    <div className="table-scroll"><table><thead><tr><th>Policy</th><th>Availability</th><th>Mean error</th><th>Worst error</th><th>Largest update</th></tr></thead><tbody>{benchmark.metrics.policy_comparison.map((policy) => <tr key={policy.policy}><td><strong>{policy.policy}</strong></td><td>{metric(policy.availability_pct, "%")}</td><td>{metric(policy.mae_bps, " bps")}</td><td>{metric(policy.worst_error_bps, " bps")}</td><td>{metric(policy.max_step_move_pct, "%")}</td></tr>)}</tbody></table></div>
    <p className="benchmark-note">This comparison demonstrates policy behavior on synthetic truth; it is not a claim of historical market performance.</p>
  </section>;
}

function EvaluationView({ evaluation, catalog, loading, error, retry, inspect }: { evaluation: Evaluation | null; catalog: Catalog | null; loading: boolean; error: string | null; retry: () => void; inspect: (scenario: string, symbol: string) => void }) {
  if (loading) return <Loading message="Loading the evaluation report…"/>;
  if (error || !evaluation) return <ErrorState message={error ?? "The evaluation report is unavailable."} retry={retry}/>;
  return <div className="evaluation-view"><div className="page-heading"><div><h1>Evidence before promises.</h1><p>Functional results from synthetic fixtures, compared across realistic reference policies.</p></div><button className="button secondary" onClick={() => downloadJSON(evaluation, "marketbridge-synthetic-evaluation.json")}><ArrowDownToLine size={15}/>Download results</button></div><div className="evaluation-summary"><div className="panel report-stat"><span>Scenario runs passed</span><strong>{evaluation.summary.passed}<small> / {evaluation.summary.total}</small></strong><span className={evaluation.summary.failed ? "negative" : "positive"}>{evaluation.summary.failed ? `${evaluation.summary.failed} need attention` : "All reported results pass"}</span></div><div className="panel report-stat"><span>Assertions checked</span><strong>{evaluation.cases.reduce((total, item) => total + item.metrics.checks.length, 0)}</strong><span className="muted">Across every reported scenario run</span></div><div className="panel report-stat"><span>Evaluation type</span><strong className="text-value">Synthetic safety tests</strong><span className="muted">No measured stock-performance claim</span></div></div><PolicyComparisonTable evaluation={evaluation}/><section className="panel"><div className="panel-heading"><div><h2>Scenario results</h2><p>Synthetic truth only. Exposure is basis-point-seconds; freeze counts safe seconds without a reference.</p></div><span className="small-label">{evaluation.model_version}</span></div><div className="table-scroll"><table className="evaluation-table"><thead><tr><th>Scenario</th><th>Symbol</th><th>Availability</th><th>Reference MAE</th><th>Detect</th><th>Bad-mark exposure</th><th>False freeze</th><th>Checks</th><th><span className="sr-only">Inspect</span></th></tr></thead><tbody>{evaluation.cases.map((item) => { const scenario = catalog?.scenarios.find((candidate) => candidate.id === item.scenario_id); const passed = item.metrics.checks.filter((check) => check.passed).length; return <tr key={`${item.scenario_id}-${item.symbol}`}><td><button className="table-link" onClick={() => inspect(item.scenario_id, item.symbol)}>{scenario?.title ?? humanize(item.scenario_id)}</button></td><td><span className="symbol-tag">{item.symbol}</span></td><td>{metric(item.metrics.availability_pct, "%")}</td><td>{metric(item.metrics.mae_bps, " bps")}</td><td>{item.metrics.time_to_detect_seconds == null ? "—" : metric(item.metrics.time_to_detect_seconds, "s")}</td><td>{metric(item.metrics.bad_mark_exposure_bps_seconds, " bp·s")}</td><td>{metric(item.metrics.false_freeze_seconds, "s")}</td><td><span className={`check-count ${passed === item.metrics.checks.length ? "passed" : "failed"}`}>{passed === item.metrics.checks.length ? <Check size={13}/> : <X size={13}/>} {passed}/{item.metrics.checks.length}</span></td><td><button className="icon-button" aria-label={`Replay ${scenario?.title ?? item.scenario_id} for ${item.symbol}`} onClick={() => inspect(item.scenario_id, item.symbol)}><ArrowRight size={15}/></button></td></tr>; })}</tbody></table></div></section><section className="limitations-note"><FlaskConical size={20}/><div><h2>How to read these results</h2><ul>{evaluation.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></div></section></div>;
}

function MethodologyView({ evaluation }: { evaluation: Evaluation | null }) {
  return <div className="methodology-view"><div className="page-heading"><div><h1>A reference is only as good as its evidence.</h1><p>MarketBridge makes provenance, uncertainty, abstention, and recovery visible to the operator.</p></div><span className="method-icon"><BookOpen size={26}/></span></div><div className="method-flow">{[{ icon: Layers3, title: "Read the evidence", description: "Preserve each source’s original timestamp, family and price. Repeated observations are not independent corroboration." }, { icon: SlidersHorizontal, title: "Qualify the update", description: "Assess an observation before it influences the reference. A large move can be bad data or a genuine repricing." }, { icon: ShieldCheck, title: "Drive risk policy", description: "Publish an advisory reference and exposure state. When evidence is insufficient, abstain instead of inventing certainty." }].map((item) => <div className="panel method-step" key={item.title}><div className="method-step-top"><span className="icon-tile"><item.icon size={19}/></span></div><h2>{item.title}</h2><p>{item.description}</p></div>)}</div><section className="panel method-definitions"><div className="panel-heading"><div><h2>Three lines. Three different meanings.</h2><p>Keep the estimator and its comparisons separate.</p></div></div><dl><div><dt><i className="legend-dot reference"/>MarketBridge reference</dt><dd>An estimate supported by qualified observations. A missing reference is shown as unavailable, with the last valid price labeled separately.</dd></div><div><dt><i className="legend-dot comparator"/>Unguarded feed</dt><dd>The primary quote without the source-quality guard. This is the comparison policy used in the paper-account simulation.</dd></div><div><dt><i className="legend-dot baseline"/>QQQ factor baseline</dt><dd>A fixed-anchor, unit-beta factor comparison. It is a separate price baseline and is not the unguarded paper-account policy.</dd></div></dl></section><div className="method-bottom"><section className="panel honest-scope"><FlaskConical size={22}/><h2>Two evidence modes, clearly separated</h2><p>The safety lab uses synthetic fixtures and an uncalibrated model range to make failure policies reproducible.</p><p>The SK Hynix view reconstructs published transaction-linked observations. Its MarketBridge response is counterfactual, not proof of prevented losses.</p><span className="small-label">ADVISORY · NO REAL EXECUTION</span></section><section className="panel research-panel"><div className="panel-heading"><div><h2>Research behind the approach</h2><p>Method inspiration, not a claim of validation.</p></div></div>{evaluation?.research.length ? evaluation.research.map((paper) => <a href={paper.url} target="_blank" rel="noopener noreferrer" className="research-link" key={paper.url}><BookOpen size={16}/><span><strong>{paper.title}</strong><span>{paper.application}</span></span><ExternalLink size={14}/></a>) : <p className="research-placeholder">Research references appear here when the evaluation report is available.</p>}</section></div></div>;
}

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState("bad-print");
  const [symbol, setSymbol] = useState("NVDA");
  const [traces, setTraces] = useState<Record<string, Trace> | null>(null);
  const [traceError, setTraceError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(true);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [incidentError, setIncidentError] = useState<string | null>(null);
  const [incidentLoading, setIncidentLoading] = useState(true);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [retryToken, setRetryToken] = useState(0);
  const [series, setSeries] = useState<Record<SeriesKey, boolean>>({ reference: true, comparator: true, baseline: true });
  const requestedCursor = useRef<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogError(null);
    getJSON<Catalog>("/v1/demo/scenarios", controller.signal).then((value) => {
      if (!value.scenarios.length || !value.symbols.length) throw new Error("No scenarios are available in this demo.");
      setCatalog(value);
      setScenarioId((previous) => value.scenarios.some((scenario) => scenario.id === previous) ? previous : value.scenarios[0].id);
    }).catch((error: unknown) => { if (!controller.signal.aborted) setCatalogError(error instanceof Error ? error.message : "Unable to connect to the demo service."); });
    setEvaluationLoading(true);
    setEvaluationError(null);
    getJSON<Evaluation>("/v1/demo/evaluation", controller.signal).then(setEvaluation).catch((error: unknown) => { if (!controller.signal.aborted) setEvaluationError(error instanceof Error ? error.message : "Unable to load the report."); }).finally(() => { if (!controller.signal.aborted) setEvaluationLoading(false); });
    setIncidentLoading(true);
    setIncidentError(null);
    getJSON<Incident>("/v1/incidents/sk-hynix-july-2026", controller.signal).then(setIncident).catch((error: unknown) => { if (!controller.signal.aborted) setIncidentError(error instanceof Error ? error.message : "Unable to load the reconstruction."); }).finally(() => { if (!controller.signal.aborted) setIncidentLoading(false); });
    return () => controller.abort();
  }, [retryToken]);

  useEffect(() => {
    if (!catalog) return;
    const controller = new AbortController();
    setTraces(null);
    setTraceError(null);
    setCursor(0);
    setPlaying(false);
    Promise.all(catalog.symbols.map(async (asset) => {
      const value = await getJSON<Trace>(`/v1/demo/scenarios/${encodeURIComponent(scenarioId)}?symbol=${encodeURIComponent(asset.symbol)}`, controller.signal);
      if (!value.steps.length) throw new Error("This scenario has no recorded steps.");
      return [asset.symbol, value] as const;
    })).then((entries) => {
      setTraces(Object.fromEntries(entries));
      if (requestedCursor.current !== null) {
        setCursor(requestedCursor.current);
        requestedCursor.current = null;
      }
    }).catch((error: unknown) => { if (!controller.signal.aborted) setTraceError(error instanceof Error ? error.message : "Unable to load this scenario."); });
    return () => controller.abort();
  }, [catalog, scenarioId, retryToken]);

  const trace = traces?.[symbol];
  const current = trace?.steps[Math.min(cursor, trace.steps.length - 1)];
  const visibleSteps = useMemo(() => trace?.steps.slice(0, cursor + 1) ?? [], [trace, cursor]);
  const asset = catalog?.symbols.find((item) => item.symbol === symbol);
  const scenario = catalog?.scenarios.find((item) => item.id === scenarioId);
  const lastIndex = trace ? trace.steps.length - 1 : 0;

  useEffect(() => {
    if (!playing || !trace) return;
    if (cursor >= lastIndex) { setPlaying(false); return; }
    const timeout = setTimeout(() => setCursor((previous) => Math.min(previous + 1, lastIndex)), 1000 / speed);
    return () => clearTimeout(timeout);
  }, [playing, cursor, lastIndex, speed, trace]);

  function changeTab(next: Tab) { setTab(next); setPlaying(false); }
  function selectScenario(next: string) { setPlaying(false); setCursor(0); setScenarioId(next); }
  function togglePlayback() { if (cursor >= lastIndex) setCursor(0); setPlaying((previous) => !previous); }
  function inspect(nextScenario: string, nextSymbol: string) { setSymbol(nextSymbol); selectScenario(nextScenario); setTab("overview"); }
  function showBadPrint() {
    setTab("overview");
    setPlaying(false);
    if (scenarioId === "bad-print") {
      requestedCursor.current = null;
      setCursor(24);
    } else {
      requestedCursor.current = 24;
      setScenarioId("bad-print");
    }
  }
  const retry = () => setRetryToken((previous) => previous + 1);

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="market-strip"><div className="page-width strip-inner"><div><span>Safety lab: <strong>{catalog?.scenarios.length ?? "—"} stress cases</strong></span><span>Live feed: <strong>Yahoo research</strong></span><span className="strip-detail">Execution: <strong>Advisory only</strong></span></div><span className="strip-disclaimer"><ShieldCheck size={12}/>Built for 24/7 stock-perpetual risk</span></div></div>
    <header className="site-header"><div className="page-width header-inner"><button className="brand" onClick={() => changeTab("overview")} aria-label="MarketBridge overview"><Mark/><span>Market<span>Bridge</span></span></button><nav className="main-nav" aria-label="Main navigation">{(["overview", "live", "incident", "evaluation", "methodology"] as Tab[]).map((item) => <button key={item} onClick={() => changeTab(item)} className={tab === item ? "active" : ""} aria-current={tab === item ? "page" : undefined}>{item === "overview" ? "Safety lab" : item === "live" ? "Live research" : item === "incident" ? "Real incident" : humanize(item)}</button>)}</nav><div className="header-actions"><span className="demo-badge"><span/>Evidence-aware risk</span><button className="icon-button help-button" aria-label="Read the methodology" onClick={() => changeTab("methodology")}><CircleHelp size={19}/></button></div></div></header>
    <main id="main-content" className="page-width main-content">
      {tab === "overview" && <>
        <div className="page-heading problem-heading"><div><h1>US stocks close.<br/>Their perpetuals keep trading.</h1><p>MarketBridge stops weak off-hours evidence from silently becoming a liquidation price—while still admitting genuine, independently corroborated moves.</p><div className="hero-actions"><button className="button primary" onClick={showBadPrint}><Play size={14} fill="currentColor"/>Watch the failure point</button><button className="text-button" onClick={() => changeTab("incident")}>See the real incident<ArrowRight size={15}/></button></div></div><button className="button secondary" onClick={() => trace && downloadJSON(trace, `marketbridge-${scenarioId}-${symbol.toLowerCase()}.json`)} disabled={!trace}><ArrowDownToLine size={15}/>Export trace</button></div>
        {catalogError ? <ErrorState message={catalogError} retry={retry}/> : !catalog ? <Loading/> : <>
          <div className="scenario-bar"><div className="scenario-label"><FlaskConical size={17}/><span>Safety lab</span><span className="small-label">SYNTHETIC STRESS TEST</span></div><label className="select-wrap scenario-select"><span className="sr-only">Choose a scenario</span><select value={scenarioId} onChange={(event) => selectScenario(event.target.value)}>{catalog.scenarios.map((item, index) => <option key={item.id} value={item.id}>{String(index + 1).padStart(2, "0")} · {item.title}</option>)}</select><ChevronDown size={15}/></label><span className="scenario-bar-hint">Change the evidence. Inspect every decision.</span></div>
          {traceError ? <ErrorState message={traceError} retry={retry}/> : !trace || !current ? <Loading message="Preparing this scenario…"/> : <>
            <div className="summary-grid"><div className="summary-card"><div className="summary-label"><span>MarketBridge reference</span><Activity size={14}/></div><div className="summary-value-row"><strong>{money(current.reference)}</strong><PriceChange value={change(current.reference, trace.initial_price)}/></div><span className="summary-caption">{current.reference === null ? `Last valid: ${money(current.last_valid)}` : `${symbol} · USD · since replay start`}</span></div><div className="summary-card"><div className="summary-label"><span>Independent evidence</span><Layers3 size={14}/></div><div className="summary-value-row"><strong>{current.source_count}<small> {current.source_count === 1 ? "source" : "sources"}</small></strong><span className="mini-bars" aria-hidden="true">{current.sources.map((source) => <i key={source.id} className={source.status === "FRESH" && source.weight > 0 ? "on" : ""}/>)}</span></div><span className="summary-caption">Qualified original source families</span></div><div className="summary-card"><div className="summary-label"><span>Evidence age</span><Clock3 size={14}/></div><div className="summary-value-row"><strong>{metric(current.age_seconds)}<small> seconds</small></strong><span className={`freshness-dot ${current.quality !== "QUALIFIED" ? "stale" : ""}`}/></div><span className="summary-caption">Source time, not connection time</span></div><div className="summary-card"><div className="summary-label"><span>Reference quality</span><ShieldCheck size={14}/></div><div className="summary-quality"><QualityBadge quality={current.quality}/></div><span className="summary-caption">{current.simulation.new_exposure_allowed ? "New paper exposure permitted" : "New paper exposure blocked"}</span></div></div>
            <section className="market-section" aria-labelledby="tracked-title"><div className="section-title-row"><h2 id="tracked-title">Tracked stocks <span>{catalog.symbols.length}</span></h2><div><span className="small-label">USD</span><span className="muted tiny">At replay {elapsed(current.seconds)}</span></div></div><div className="table-scroll"><table className="market-table"><thead><tr><th className="rank-column">#</th><th>Asset</th><th>Reference price</th><th>Replay change</th><th className="hide-mobile">Evidence age</th><th>Quality</th><th className="trend-column">Reference so far</th></tr></thead><tbody>{catalog.symbols.map((item, index) => { const itemTrace = traces![item.symbol], step = itemTrace?.steps[Math.min(cursor, itemTrace.steps.length - 1)]; return <tr key={item.symbol} className={symbol === item.symbol ? "selected" : ""} onClick={() => setSymbol(item.symbol)}><td className="rank-column">{index + 1}</td><td><button className="asset-button" onClick={() => setSymbol(item.symbol)} aria-pressed={symbol === item.symbol}><AssetIcon symbol={item.symbol}/><span><strong>{item.name}</strong><span>{item.symbol}</span></span>{symbol === item.symbol && <span className="selected-indicator"><Check size={10}/></span>}</button></td><td className="price-cell">{money(step?.reference)}</td><td><PriceChange value={change(step?.reference, itemTrace?.initial_price ?? item.base_price)}/></td><td className="hide-mobile muted">{metric(step?.age_seconds, "s")}</td><td>{step && <QualityBadge quality={step.quality}/>}</td><td className="trend-column">{itemTrace && <Sparkline steps={itemTrace.steps.slice(0, cursor + 1)} blue={symbol === item.symbol}/>}</td></tr>; })}</tbody></table></div></section>
            <div className="dashboard-grid"><section className="panel chart-panel" aria-labelledby="chart-title"><div className="chart-heading"><div className="chart-asset"><AssetIcon symbol={symbol} small/><div><h2 id="chart-title">{symbol} reference price</h2><span>{asset?.name} <span className="middot">·</span> Scenario replay</span></div></div><label className="select-wrap symbol-select"><span className="sr-only">Chart symbol</span><select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{catalog.symbols.map((item) => <option key={item.symbol}>{item.symbol}</option>)}</select><ChevronDown size={13}/></label></div><div className="chart-toolbar"><div className="chart-legend">{(["reference", "comparator", "baseline"] as SeriesKey[]).map((key) => <button key={key} className={!series[key] ? "inactive" : ""} aria-pressed={series[key]} onClick={() => setSeries((previous) => ({ ...previous, [key]: !previous[key] }))}><i className={`legend-dot ${key}`}/>{seriesLabels[key]}</button>)}</div><span className="range-label">Model range · uncalibrated</span></div><InteractivePriceChart steps={visibleSteps} current={current} endTime={trace.steps.at(-1)?.timestamp ?? current.timestamp} series={series} onPlay={togglePlayback} playing={playing}/><a className="tradingview-attribution" href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">Charts by TradingView</a><div className="replay-controls"><div className="replay-control-row"><div className="playback-buttons"><button className="play-button" onClick={togglePlayback} aria-label={playing ? "Pause replay" : cursor === lastIndex ? "Replay scenario" : "Play replay"}>{playing ? <Pause size={16} fill="currentColor"/> : <Play size={16} fill="currentColor"/>}</button><button className="icon-button" aria-label="Reset replay" title="Reset replay" onClick={() => { setCursor(0); setPlaying(false); }}><RotateCcw size={17}/></button><button className="icon-button" aria-label="Step forward" title="Step forward" disabled={cursor >= lastIndex} onClick={() => { setPlaying(false); setCursor((previous) => Math.min(previous + 1, lastIndex)); }}><SkipForward size={18}/></button><span className="playback-time"><strong>{elapsed(current.seconds)}</strong><span>/ {elapsed(trace.scenario.duration_seconds)}</span></span></div><div className="speed-controls"><label htmlFor="speed">Speed</label><select id="speed" aria-label="Playback speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>{[1, 2, 4, 8].map((value) => <option key={value} value={value}>{value}×</option>)}</select><span className={`playback-status ${playing ? "playing" : ""}`}><i/>{playing ? "Playing" : cursor === lastIndex ? "Complete" : "Paused"}</span></div></div><input className="timeline-slider" type="range" min={0} max={lastIndex} step={1} value={cursor} aria-label="Replay timeline" aria-valuetext={`${elapsed(current.seconds)} of ${elapsed(trace.scenario.duration_seconds)}`} style={{ "--progress": `${lastIndex ? cursor / lastIndex * 100 : 0}%` } as React.CSSProperties} onChange={(event) => { setPlaying(false); setCursor(Number(event.target.value)); }}/><div className="timeline-footer"><span><span className="timeline-dot"/>Event-by-event playback</span><span>{cursor + 1} / {trace.steps.length} steps</span></div></div></section><EvidencePanel step={current}/></div>
            <Simulator step={current} trace={trace}/>
            <OperatorPayload scenarioId={scenarioId} symbol={symbol} step={current}/>
            <section className="scenario-note"><span className="scenario-note-icon"><BookOpen size={18}/></span><div><h2>{scenario?.title}</h2><p>{scenario?.description}</p><span>Expected behavior: {scenario?.expected_outcome}</span></div><button className="text-button" onClick={() => changeTab("evaluation")}>View test results<ArrowRight size={15}/></button></section>
          </>}
        </>}
      </>}
      {tab === "live" && <LiveView onFallback={() => changeTab("overview")}/>} 
      {tab === "incident" && <IncidentView incident={incident} loading={incidentLoading} error={incidentError} onTryDemo={showBadPrint}/>} 
      {tab === "evaluation" && <EvaluationView evaluation={evaluation} catalog={catalog} loading={evaluationLoading} error={evaluationError} retry={retry} inspect={inspect}/>} 
      {tab === "methodology" && <MethodologyView evaluation={evaluation}/>}
    </main>
    <footer className="page-width footer"><div className="footer-brand"><Mark small/><strong>MarketBridge</strong><span>Evidence-aware risk for 24/7 stock perpetuals.</span></div><div><span>Synthetic safety tests + sourced historical reconstruction</span><span className="footer-divider"/><a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">Charts by TradingView</a><span className="footer-divider"/><span>No real orders</span></div></footer>
  </div>;
}
