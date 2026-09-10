"use client";

import type { MarketAsset } from "@/lib/market";
import MarketChart from "@/features/chart/MarketChart";

export default function FinancialChart({ asset, compact = false }: { asset: MarketAsset | null; compact?: boolean }) {
  if (!asset) return <div className={`chart-unavailable${compact ? " compact" : ""}`}><span>Chart unavailable</span><small>Waiting for a supported market symbol.</small></div>;
  return <div className={compact ? "terminal-chart compact" : "terminal-chart"}><MarketChart asset={asset}/></div>;
}
