"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { MarketAsset } from "@/lib/market";

const TradingChart = dynamic(() => import("@/components/trading-chart"), { ssr: false, loading: () => <div className="terminal-chart-skeleton" aria-label="Loading chart"/> });

export default function FinancialChart({ asset, compact = false }: { asset: MarketAsset | null; compact?: boolean }) {
  const series = useMemo(() => {
    if (!asset) return [];
    return [
      { key: "reference", label: "MarketBridge reference", color: "#3861fb", area: true, visible: true, data: asset.points.map((point) => ({ time: point.time, value: point.value })) },
      { key: "lower", label: "Lower band", color: "#526170", dashed: true, visible: asset.bandLower != null, data: asset.eventTime && asset.bandLower != null ? [{ time: asset.eventTime, value: asset.bandLower }] : [] },
      { key: "upper", label: "Upper band", color: "#526170", dashed: true, visible: asset.bandUpper != null, data: asset.eventTime && asset.bandUpper != null ? [{ time: asset.eventTime, value: asset.bandUpper }] : [] },
    ];
  }, [asset]);
  if (!asset || asset.points.length < 2) return <div className={`chart-unavailable${compact ? " compact" : ""}`}><span>Chart unavailable</span><small>Waiting for two or more timestamped observations.</small></div>;
  return <div className={compact ? "terminal-chart compact" : "terminal-chart"}><TradingChart series={series} endTime={asset.points.at(-1)?.time ?? asset.eventTime ?? ""} ariaLabel={`${asset.symbol} MarketBridge reference price chart`} height={compact ? 270 : 430} theme="dark"/></div>;
}
