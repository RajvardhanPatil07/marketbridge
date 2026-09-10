"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AreaSeries, BarSeries, BaselineSeries, CandlestickSeries, ColorType, createChart, HistogramSeries, LineSeries, LineStyle, PriceScaleMode, type IChartApi, type IPriceLine, type ISeriesApi, type Time, type UTCTimestamp } from "lightweight-charts";
import { money, percent, timeAgo, type MarketAsset } from "@/lib/market";
import { useMarketData } from "@/components/market-data-provider";
import ChartToolbar from "./ChartToolbar";
import ChartDrawingTools from "./ChartDrawingTools";
import { defaultWorkspace, DEFAULT_RESOLUTION, loadWorkspace, saveWorkspace, type WorkspaceState } from "./chart-state";
import type { BarsResponse, ChartRange, ChartType, IndicatorConfig, IndicatorKind, MarketBar, Resolution } from "./chart-types";
import { bollinger, ema, heikinAshi, macd, points, rsi, sma } from "./indicators/math";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const timestamp = (value: string) => Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
const scaleModes = { Regular: PriceScaleMode.Normal, Logarithmic: PriceScaleMode.Logarithmic, Percentage: PriceScaleMode.Percentage, "Indexed to 100": PriceScaleMode.IndexedTo100 } as const;
type AnySeries = ISeriesApi<"Candlestick"> | ISeriesApi<"Bar"> | ISeriesApi<"Line"> | ISeriesApi<"Area"> | ISeriesApi<"Baseline"> | ISeriesApi<"Histogram">;

function mergeBars(current: MarketBar[], incoming: MarketBar[]) { const map = new Map(current.map((bar) => [bar.timestamp, bar])); incoming.forEach((bar) => map.set(bar.timestamp, bar)); return [...map.values()].sort((a, b) => a.timestamp.localeCompare(b.timestamp)); }

export default function MarketChart({ asset }: { asset: MarketAsset }) {
  const { snapshot } = useMarketData();
  const containerRef = useRef<HTMLDivElement>(null); const shellRef = useRef<HTMLDivElement>(null); const chartRef = useRef<IChartApi | null>(null); const mainRef = useRef<AnySeries | null>(null); const livePriceLineRef = useRef<IPriceLine | null>(null); const studyRefs = useRef<AnySeries[]>([]); const barsRef = useRef<MarketBar[]>([]); const requestRef = useRef<AbortController | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceState>(defaultWorkspace); const [bars, setBars] = useState<MarketBar[]>([]); const [meta, setMeta] = useState<BarsResponse | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null); const [crosshair, setCrosshair] = useState<MarketBar | null>(null); const [fullscreenActive, setFullscreenActive] = useState(false);

  useEffect(() => setWorkspace(loadWorkspace(asset.symbol)), [asset.symbol]);
  useEffect(() => saveWorkspace(asset.symbol, workspace), [asset.symbol, workspace]);
  const updateWorkspace = useCallback((next: Partial<WorkspaceState>) => setWorkspace((value) => ({ ...value, ...next })), []);

  const load = useCallback(async (range: ChartRange, resolution: Resolution, prepend = false, end?: string) => {
    if (!prepend) requestRef.current?.abort(); const controller = new AbortController(); if (!prepend) requestRef.current = controller;
    setLoading(true); setError(null);
    const params = new URLSearchParams({ range, resolution, feed: "iex", adjustment: workspace.adjustment, session: workspace.session });
    if (end) { const before = new Date(end); const start = new Date(before); start.setUTCFullYear(start.getUTCFullYear() - 10); params.set("start", start.toISOString()); params.set("end", before.toISOString()); }
    try { const response = await fetch(`${API_BASE}/v1/market/bars/${encodeURIComponent(asset.symbol)}?${params}`, { signal: controller.signal, cache: "no-store" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail?.message ?? "Historical market data is unavailable"); const typed = payload as BarsResponse; setMeta(typed); setBars((current) => prepend ? mergeBars(current, typed.bars) : typed.bars); }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Historical market data is unavailable"); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }, [asset.symbol, workspace.adjustment, workspace.session]);
  useEffect(() => { void load(workspace.range, workspace.resolution); return () => requestRef.current?.abort(); }, [load, workspace.range, workspace.resolution]);

  useEffect(() => { const container = containerRef.current; if (!container) return; const chart = createChart(container, { autoSize: true, height: 470, layout: { background: { type: ColorType.Solid, color: "#0d1116" }, textColor: "#788492", attributionLogo: true, fontFamily: "var(--font-mono), monospace" }, grid: { vertLines: { color: "#171d24" }, horzLines: { color: "#202730", style: LineStyle.Dashed } }, timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#252c35", rightOffset: 6 }, rightPriceScale: { borderColor: "#252c35" } }); chartRef.current = chart; chart.subscribeCrosshairMove((param) => { if (!param.time) return setCrosshair(null); setCrosshair(barsRef.current.find((bar) => timestamp(bar.timestamp) === param.time) ?? null); }); return () => { chart.remove(); chartRef.current = null; mainRef.current = null; studyRefs.current = []; }; }, []);

  const pointTail = asset.points.at(-1); const pointsSignature = `${asset.points.length}:${pointTail?.time ?? ""}:${pointTail?.value ?? ""}`;
  useEffect(() => { const chart = chartRef.current; if (!chart) return; if (mainRef.current) chart.removeSeries(mainRef.current); livePriceLineRef.current = null; studyRefs.current.forEach((series) => chart.removeSeries(series)); studyRefs.current = []; barsRef.current = bars; const displayed = workspace.chartType === "Heikin Ashi" ? heikinAshi(bars) : bars; let main: AnySeries;
    if (workspace.chartType === "Candlestick" || workspace.chartType === "Heikin Ashi") { main = chart.addSeries(CandlestickSeries, { upColor: "#16c784", downColor: "#ea3943", wickUpColor: "#16c784", wickDownColor: "#ea3943", borderVisible: false }); main.setData(displayed.map((bar) => ({ time: timestamp(bar.timestamp), open: bar.open, high: bar.high, low: bar.low, close: bar.close }))); }
    else if (workspace.chartType === "OHLC Bars") { main = chart.addSeries(BarSeries, { upColor: "#16c784", downColor: "#ea3943" }); main.setData(displayed.map((bar) => ({ time: timestamp(bar.timestamp), open: bar.open, high: bar.high, low: bar.low, close: bar.close }))); }
    else if (workspace.chartType === "Area") { main = chart.addSeries(AreaSeries, { lineColor: "#3861fb", topColor: "#3861fb44", bottomColor: "#3861fb05" }); main.setData(displayed.map((bar) => ({ time: timestamp(bar.timestamp), value: bar.close }))); }
    else if (workspace.chartType === "Baseline") { main = chart.addSeries(BaselineSeries, { baseValue: { type: "price", price: displayed[0]?.close ?? 0 }, topLineColor: "#16c784", bottomLineColor: "#ea3943" }); main.setData(displayed.map((bar) => ({ time: timestamp(bar.timestamp), value: bar.close }))); }
    else { main = chart.addSeries(LineSeries, { color: "#3861fb", lineWidth: 2 }); main.setData(displayed.map((bar) => ({ time: timestamp(bar.timestamp), value: bar.close }))); }
    mainRef.current = main; if (asset.price != null) livePriceLineRef.current = main.createPriceLine({ price: asset.price, color: "#3861fb", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "LIVE" }); const closes = bars.map((bar) => bar.close);
    const addLine = (data: { time: string; value: number }[], color: string, pane = 0) => { const series = chart.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane); series.setData(data.map((point) => ({ time: timestamp(point.time), value: point.value }))); studyRefs.current.push(series); };
    workspace.indicators.filter((item) => item.visible).forEach((item) => { if (item.kind === "SMA") addLine(points(bars, sma(closes, item.length)), item.color); if (item.kind === "EMA") addLine(points(bars, ema(closes, item.length)), item.color); if (item.kind === "Bollinger Bands") { const result = bollinger(closes, item.length); addLine(points(bars, result.middle), item.color); addLine(points(bars, result.upper), "#8faaff"); addLine(points(bars, result.lower), "#8faaff"); } if (item.kind === "Volume") { const series = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", priceLineVisible: false, lastValueVisible: false }, 1); series.setData(bars.map((bar) => ({ time: timestamp(bar.timestamp), value: bar.volume, color: bar.close >= bar.open ? "#16c78466" : "#ea394366" }))); studyRefs.current.push(series); } if (item.kind === "RSI") addLine(points(bars, rsi(closes, item.length)), item.color, 2); if (item.kind === "MACD") { const result = macd(closes); addLine(points(bars, result.line), item.color, 2); addLine(points(bars, result.signal), "#d29922", 2); } });
    if (workspace.range === "1D" && asset.points.length) addLine(asset.points, "#7da2ff"); chart.priceScale("right").applyOptions({ mode: scaleModes[workspace.scaleMode] }); chart.timeScale().fitContent();
  }, [bars, pointsSignature, workspace.chartType, workspace.indicators, workspace.range, workspace.scaleMode]);

  useEffect(() => {
    if (asset.price == null || !livePriceLineRef.current) return;
    livePriceLineRef.current.applyOptions({ price: asset.price });
  }, [asset.price]);

  useEffect(() => {
    if (workspace.adjustment !== "raw" || !meta || !bars.length) return;
    const reconcile = async () => {
      try {
        const response = await fetch(`${API_BASE}/v1/market/bars/${asset.symbol}?range=1D&resolution=${workspace.resolution}&feed=${meta.feed}&adjustment=raw&session=${workspace.session}`, { cache: "no-store" });
        if (!response.ok) return;
        const payload = await response.json() as BarsResponse; const incoming = payload.bars.slice(-3); const latest = incoming.at(-1); const series = mainRef.current;
        if (!latest || !series) return;
        const known = barsRef.current.at(-1); const merged = mergeBars(barsRef.current, incoming); barsRef.current = merged;
        if (!known || incoming.length > 1 && timestamp(latest.timestamp) - timestamp(known.timestamp) > 2 * 86_400) { setBars(merged); return; }
        if (workspace.chartType === "Candlestick" || workspace.chartType === "OHLC Bars") (series as ISeriesApi<"Candlestick">).update({ time: timestamp(latest.timestamp), open: latest.open, high: latest.high, low: latest.low, close: latest.close });
        else if (workspace.chartType === "Heikin Ashi") { const transformed = heikinAshi(merged).at(-1)!; (series as ISeriesApi<"Candlestick">).update({ time: timestamp(transformed.timestamp), open: transformed.open, high: transformed.high, low: transformed.low, close: transformed.close }); }
        else (series as ISeriesApi<"Line">).update({ time: timestamp(latest.timestamp), value: latest.close });
      } catch { /* retain the last verified bar and expose provider state */ }
    };
    const timer = window.setInterval(() => void reconcile(), 30_000); return () => clearInterval(timer);
  }, [asset.symbol, bars.length, meta, workspace.adjustment, workspace.chartType, workspace.resolution, workspace.session]);

  useEffect(() => {
    if (workspace.adjustment !== "raw" || workspace.resolution !== "1Min") return;
    const live = snapshot?.live_bars?.[asset.symbol]?.at(-1); const series = mainRef.current;
    if (!live || !series) return;
    barsRef.current = mergeBars(barsRef.current, [live]);
    if (workspace.chartType === "Candlestick" || workspace.chartType === "OHLC Bars") (series as ISeriesApi<"Candlestick">).update({ time: timestamp(live.timestamp), open: live.open, high: live.high, low: live.low, close: live.close });
    else if (workspace.chartType === "Heikin Ashi") { const transformed = heikinAshi(barsRef.current).at(-1)!; (series as ISeriesApi<"Candlestick">).update({ time: timestamp(transformed.timestamp), open: transformed.open, high: transformed.high, low: transformed.low, close: transformed.close }); }
    else (series as ISeriesApi<"Line">).update({ time: timestamp(live.timestamp), value: live.close });
  }, [asset.symbol, snapshot?.live_bars, workspace.adjustment, workspace.chartType, workspace.resolution]);

  const addIndicator = (kind: IndicatorKind) => setWorkspace((state) => ({ ...state, indicators: [...state.indicators, { id: `${kind}-${Date.now()}`, kind, length: kind === "EMA" ? 20 : kind === "RSI" ? 14 : 20, color: "#79a1ff", visible: true }] }));
  const screenshot = () => { const canvas = chartRef.current?.takeScreenshot(); if (!canvas) return; const link = document.createElement("a"); link.download = `${asset.symbol}-${workspace.range}.png`; link.href = canvas.toDataURL("image/png"); link.click(); };
  const zoomIn = () => { const scale = chartRef.current?.timeScale(); const range = scale?.getVisibleLogicalRange(); if (!scale || !range) return; const inset = (range.to - range.from) * .12; scale.setVisibleLogicalRange({ from: range.from + inset, to: range.to - inset }); };
  const fullscreen = useCallback(async () => {
    if (document.fullscreenElement) { await document.exitFullscreen(); return; }
    await shellRef.current?.requestFullscreen();
  }, []);
  useEffect(() => { const syncFullscreen = () => setFullscreenActive(Boolean(document.fullscreenElement)); document.addEventListener("fullscreenchange", syncFullscreen); return () => document.removeEventListener("fullscreenchange", syncFullscreen); }, []);
  useEffect(() => { const key = (event: KeyboardEvent) => { if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return; if (event.key.toLowerCase() === "f") void fullscreen(); if (event.key.toLowerCase() === "c") updateWorkspace({ chartType: "Candlestick" }); if (event.key.toLowerCase() === "l") updateWorkspace({ chartType: "Line" }); if (event.key === "1") updateWorkspace({ resolution: "1Min" }); if (event.key === "5") updateWorkspace({ resolution: "5Min" }); if (event.key.toLowerCase() === "d") updateWorkspace({ resolution: "1Day" }); }; window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key); }, [fullscreen, updateWorkspace]);
  return <div className="market-chart-shell" ref={shellRef}><ChartToolbar range={workspace.range} resolution={workspace.resolution} chartType={workspace.chartType} scaleMode={workspace.scaleMode} fullscreen={fullscreenActive} onRange={(range) => updateWorkspace({ range, resolution: DEFAULT_RESOLUTION[range] })} onResolution={(resolution) => updateWorkspace({ resolution })} onChartType={(chartType: ChartType) => updateWorkspace({ chartType })} onScale={(scaleMode) => updateWorkspace({ scaleMode })} onIndicator={addIndicator} onScreenshot={screenshot} onFullscreen={fullscreen} onReset={() => setWorkspace(defaultWorkspace())}/><div className="market-chart-status"><strong>{asset.symbol}</strong><span className="market-chart-live-price"><b>{money(asset.price, asset.currency)}</b><i className={(asset.changePct ?? 0) >= 0 ? "positive" : "negative"}>{percent(asset.changePct)}</i><small>{asset.priceSource} · {timeAgo(asset.eventTime)}</small></span><span>{meta ? `ALPACA ${meta.feed.toUpperCase()}` : "PROVIDER UNAVAILABLE"}</span><span className={meta?.status === "AVAILABLE" ? "ok" : "limited"}>{meta?.status ?? "OFFLINE"}</span><span>{workspace.session.toUpperCase()} · {workspace.resolution} · {workspace.adjustment.toUpperCase()}</span><span className="oracle-boundary">DISPLAY BARS ≠ ORACLE EVIDENCE</span></div>{crosshair && <div className="market-chart-legend"><b>{new Date(crosshair.timestamp).toLocaleString()}</b><span>O {crosshair.open.toFixed(2)}</span><span>H {crosshair.high.toFixed(2)}</span><span>L {crosshair.low.toFixed(2)}</span><span>C {crosshair.close.toFixed(2)}</span><span>V {crosshair.volume.toLocaleString()}</span><span>VWAP {crosshair.vwap?.toFixed(2) ?? "—"}</span><span>REF {asset.price?.toFixed(2) ?? "—"}</span><span>RISK {asset.riskState ?? "—"}</span></div>}<div className="market-chart-canvas" ref={containerRef}/><ChartDrawingTools symbol={asset.symbol} onZoom={zoomIn}/>{loading && !bars.length && <div className="market-chart-loading">Loading verified historical bars…</div>}{error && !bars.length && <div className="market-chart-error"><strong>Historical chart unavailable</strong><span>{error}</span><small>No candles were fabricated. Configure server-side Alpaca credentials to enable chart history.</small></div>}{meta?.has_more_history && workspace.range === "MAX" && <button className="load-history" disabled={loading} onClick={() => void load("MAX", workspace.resolution, true, meta.next_end ?? undefined)}>{loading ? "Loading…" : "Load older history"}</button>}<div className="indicator-chips">{workspace.indicators.map((item: IndicatorConfig) => <button key={item.id} onClick={() => setWorkspace((state) => ({ ...state, indicators: state.indicators.filter((value) => value.id !== item.id) }))}>{item.kind} {item.kind !== "Volume" && item.length} ×</button>)}</div></div>;
}
