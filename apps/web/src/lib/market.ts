import type { LiveObservation, ShadowDecision, ShadowSnapshot, ShadowStatus } from "@/lib/types";

export type ConnectionState = "connecting" | "live" | "delayed" | "offline";
export type MarketAsset = {
  symbol: string; name: string; price: number | null; previousClose: number | null; changePct: number | null;
  currency: string; exchange: string; eventTime: string | null; ageSeconds: number | null;
  points: { time: string; value: number }[]; status: ShadowStatus | "DISPLAY_ONLY"; confidence: number | null;
  bandLower: number | null; bandUpper: number | null; riskState: ShadowDecision["risk_state"] | null;
  divergenceBps: number | null; leverage: number | null; evidenceCount: number; reasons: string[];
  priceSource: "Alpaca IEX" | "Yahoo fallback" | "Qualified reference" | "Unavailable";
  ai: ShadowDecision["ai"] | null;
};

const DISPLAY_NAMES: Record<string, string> = { NVDA: "NVIDIA Corporation", TSLA: "Tesla, Inc.", AAPL: "Apple Inc.", MSFT: "Microsoft Corporation", AMD: "Advanced Micro Devices", QQQ: "Invesco QQQ" };
export const TRACKED_SYMBOLS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMD", "QQQ"] as const;

export const money = (value: number | null, currency = "USD") => value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency, minimumFractionDigits: value >= 1000 ? 0 : 2, maximumFractionDigits: 2 }).format(value);
export const numeric = (value: number | null, digits = 2) => value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
export const percent = (value: number | null) => value == null || !Number.isFinite(value) ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
export const timeAgo = (value: string | null) => {
  if (!value) return "No update";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
};

export function assetsFromSnapshot(snapshot: ShadowSnapshot | null): MarketAsset[] {
  if (!snapshot) return [];
  const observations = new Map((snapshot.yahoo?.observations ?? []).map((item) => [item.symbol, item]));
  const decisions = new Map(snapshot.decisions.map((item) => [item.symbol, item]));
  const symbols = [...new Set([...TRACKED_SYMBOLS, ...observations.keys(), ...decisions.keys()])];
  return symbols.map((symbol) => {
    const observation: LiveObservation | undefined = observations.get(symbol);
    const decision: ShadowDecision | undefined = decisions.get(symbol);
    const directEvidence = decision?.evidence
      .filter((item) => item.source_id.startsWith("alpaca-"))
      .sort((left, right) => new Date(right.event_time).getTime() - new Date(left.event_time).getTime())[0];
    const displayPrice = decision?.reference ?? directEvidence?.price ?? observation?.observed_price ?? decision?.last_valid ?? null;
    const previousClose = observation?.previous_close ?? null;
    const changePct = displayPrice != null && previousClose ? (displayPrice / previousClose - 1) * 100 : observation?.change_pct ?? null;
    const decisionPoints = snapshot.decision_log.filter((item) => item.symbol === symbol && item.reference != null).map((item) => ({ time: item.timestamp, value: item.reference as number }));
    const researchPoints = observation?.points.map((point) => ({ time: point.timestamp, value: point.price })) ?? [];
    return {
      symbol, name: observation?.name ?? DISPLAY_NAMES[symbol] ?? symbol, price: displayPrice, previousClose, changePct,
      currency: observation?.currency ?? "USD", exchange: observation?.exchange ?? "—",
      eventTime: decision?.reference != null ? decision.timestamp : directEvidence?.event_time ?? observation?.event_time ?? decision?.timestamp ?? null,
      ageSeconds: decision?.source_event_age_ms != null ? decision.source_event_age_ms / 1000 : observation?.age_seconds ?? null,
      points: decisionPoints.length > 1 ? decisionPoints : researchPoints, status: decision?.status ?? "DISPLAY_ONLY",
      confidence: decision?.confidence ?? null, bandLower: decision?.band_lower ?? null, bandUpper: decision?.band_upper ?? null,
      riskState: decision?.risk_state ?? null, divergenceBps: decision?.mark_divergence_bps ?? null,
      leverage: decision?.recommended_max_leverage ?? null, evidenceCount: decision?.independent_source_families ?? 0,
      reasons: decision?.reasons ?? observation?.decision.reasons ?? [], ai: decision?.ai ?? null,
      priceSource: decision?.reference != null ? "Qualified reference" : directEvidence ? "Alpaca IEX" : observation ? "Yahoo fallback" : "Unavailable",
    };
  });
}
