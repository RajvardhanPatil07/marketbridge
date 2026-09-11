"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronDown, RefreshCw, Search, TriangleAlert } from "lucide-react";
import { useMarketData } from "@/components/market-data-provider";
import { money, numeric, percent, timeAgo, type MarketAsset } from "@/lib/market";

export function PriceChange({ value, showArrow = false }: { value: number | null; showArrow?: boolean }) {
  if (value == null) return <span className="data-muted">—</span>;
  return <span className={`change ${value < 0 ? "negative" : "positive"}`}>{showArrow && (value < 0 ? <ArrowDown size={11}/> : <ArrowUp size={11}/>)}{percent(value)}</span>;
}

export function AssetMark({ asset, size = "normal" }: { asset: Pick<MarketAsset, "symbol" | "name">; size?: "small" | "normal" }) {
  return <span className={`asset-mark ${size}`} aria-hidden="true">{asset.symbol.slice(0, 1)}</span>;
}

export function Sparkline({ asset }: { asset: MarketAsset }) {
  const values = asset.points.slice(-32).map((point) => point.value).filter(Number.isFinite);
  if (values.length < 2) {
    return <span className="trend-collecting" title="Waiting for a second observed market tick">COLLECTING</span>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, Math.max(Math.abs(values[0]) * 0.0005, 0.01));
  const coordinates = values.map((value, index) => ({
    x: index / (values.length - 1) * 104 + 4,
    y: 29 - (value - min) / range * 24,
  }));
  const points = coordinates.map((point) => `${point.x},${point.y}`).join(" ");
  const area = `M ${coordinates[0].x} 32 L ${points.replaceAll(" ", " L ")} L ${coordinates.at(-1)!.x} 32 Z`;
  const positive = values.at(-1)! >= values[0];
  const gradientId = `spark-${asset.symbol.replace(/[^A-Za-z0-9]/g, "")}`;
  const end = coordinates.at(-1)!;
  return <svg className={`market-sparkline ${positive ? "positive" : "negative"}`} viewBox="0 0 112 34" role="img" aria-label={`${asset.symbol} observed live price trend from ${values.length} ticks`}>
    <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="currentColor" stopOpacity=".26"/><stop offset="100%" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>
    <path d={area} fill={`url(#${gradientId})`}/>
    <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2.35" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke"/>
    <circle cx={end.x} cy={end.y} r="2.2" fill="currentColor"/>
  </svg>;
}

export function DataState({ compact = false }: { compact?: boolean }) {
  const { error, loading, refresh } = useMarketData();
  if (loading) return <div className={`data-state loading ${compact ? "compact" : ""}`} role="status"><span className="skeleton-line"/><span className="skeleton-line short"/><span className="skeleton-line"/></div>;
  if (!error) return null;
  return <div className={`data-state ${compact ? "compact" : ""}`} role="alert"><TriangleAlert size={18}/><div><strong>Market data unavailable</strong><span>{error}</span></div><button onClick={() => void refresh()}><RefreshCw size={13}/>Retry</button></div>;
}

type SortKey = "symbol" | "price" | "previousClose" | "changePct" | "confidence" | "divergenceBps";
export function MarketTable({ limit, showSearch = true }: { limit?: number; showSearch?: boolean }) {
  const { assets, loading } = useMarketData(); const [query, setQuery] = useState(""); const [sort, setSort] = useState<SortKey>("changePct"); const [descending, setDescending] = useState(true);
  const rows = useMemo(() => assets.filter((asset) => `${asset.symbol} ${asset.name}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => {
    const left = sort === "symbol" ? a.symbol : a[sort] ?? -Infinity; const right = sort === "symbol" ? b.symbol : b[sort] ?? -Infinity;
    const result = typeof left === "string" ? left.localeCompare(String(right)) : Number(left) - Number(right); return descending ? -result : result;
  }).slice(0, limit), [assets, query, sort, descending, limit]);
  const changeSort = (next: SortKey) => { if (sort === next) setDescending((value) => !value); else { setSort(next); setDescending(true); } };
  if (loading) return <DataState/>;
  return <div className="market-table-shell">{showSearch && <div className="table-toolbar"><label><Search size={14}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter tracked assets" aria-label="Filter tracked assets"/></label><span>{rows.length} assets</span></div>}<div className="table-scroll"><table className="platform-table market-table-core"><thead><tr><th>#</th><th><button onClick={() => changeSort("symbol")}>Asset<ChevronDown size={11}/></button></th><th><button onClick={() => changeSort("price")}>Current<ChevronDown size={11}/></button></th><th><button onClick={() => changeSort("previousClose")}>Prev close<ChevronDown size={11}/></button></th><th><button onClick={() => changeSort("changePct")}>Change<ChevronDown size={11}/></button></th><th className="secondary-col">Updated</th><th className="secondary-col">Reference state</th><th className="secondary-col"><button onClick={() => changeSort("confidence")}>Confidence<ChevronDown size={11}/></button></th><th>Trend</th></tr></thead><tbody>{rows.map((asset, index) => <tr key={asset.symbol}><td className="rank-cell">{index + 1}</td><td><Link href={`/asset/explore/?symbol=${encodeURIComponent(asset.symbol)}`} className="asset-cell"><AssetMark asset={asset}/><span><strong>{asset.symbol}</strong><small>{asset.name}</small></span></Link></td><td className="numeric-cell"><strong>{money(asset.price, asset.currency)}</strong><small>{asset.priceSource}</small></td><td className="numeric-cell">{money(asset.previousClose, asset.currency)}</td><td className="numeric-cell"><PriceChange value={asset.changePct}/></td><td className="secondary-col numeric-cell">{timeAgo(asset.eventTime)}</td><td className="secondary-col"><span className={`reference-state ${asset.status.toLowerCase()}`}>{asset.status === "DISPLAY_ONLY" ? "DISPLAY QUOTE" : asset.status.replaceAll("_", " ")}</span></td><td className="secondary-col numeric-cell">{asset.confidence == null ? "Not qualified" : `${numeric(asset.confidence, 0)}%`}</td><td><Sparkline asset={asset}/></td></tr>)}</tbody></table></div>{!rows.length && <div className="empty-row">{query ? "No tracked assets match this filter." : "No market observations are available."}</div>}</div>;
}

export function ConnectionSummary() {
  const { snapshot, connection, lastUpdated, refresh } = useMarketData();
  return <div className="connection-summary"><span className={`connection-pill ${connection}`}><i/>{connection}</span><span>{snapshot?.market_health.status.replaceAll("_", " ") ?? "No market health"}</span><span>{timeAgo(lastUpdated)}</span><button onClick={() => void refresh()} aria-label="Refresh market data"><RefreshCw size={13}/></button></div>;
}