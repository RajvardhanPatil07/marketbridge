import type { DisplaySnapshot, LiveObservation, ShadowDecision, ShadowLiveBar, ShadowSnapshot, ShadowStatus } from "@/lib/types";

export type ConnectionState = "connecting" | "live" | "delayed" | "offline";
export type MarketAsset = {
  symbol: string; name: string; price: number | null; previousClose: number | null; changePct: number | null;
  currency: string; exchange: string; eventTime: string | null; ageSeconds: number | null;
  bid?: number | null; ask?: number | null; dayVolume?: number | null;
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
    const latestLiveBar = snapshot.live_bars?.[symbol]?.reduce<ShadowLiveBar | undefined>((latest, bar) => !latest || Date.parse(bar.timestamp) > Date.parse(latest.timestamp) ? bar : latest, undefined);
    const displayCandidates = [
      directEvidence && { price: directEvidence.price, eventTime: directEvidence.event_time, ageSeconds: directEvidence.age_seconds, source: "Alpaca IEX" as const },
      latestLiveBar && { price: latestLiveBar.close, eventTime: latestLiveBar.timestamp, ageSeconds: Math.max(0, (Date.now() - Date.parse(latestLiveBar.timestamp)) / 1000), source: "Alpaca IEX" as const },
      observation && { price: observation.observed_price, eventTime: observation.event_time, ageSeconds: observation.age_seconds, source: "Yahoo fallback" as const },
    ].filter((candidate): candidate is NonNullable<typeof candidate> => Boolean(candidate))
      .sort((left, right) => Date.parse(right.eventTime) - Date.parse(left.eventTime));
    const freshestDisplay = displayCandidates[0];
    const displayPrice = decision?.reference ?? freshestDisplay?.price ?? decision?.last_valid ?? null;
    const previousClose = observation?.previous_close ?? null;
    const changePct = displayPrice != null && previousClose ? (displayPrice / previousClose - 1) * 100 : observation?.change_pct ?? null;
    const decisionPoints = snapshot.decision_log.filter((item) => item.symbol === symbol && item.reference != null).map((item) => ({ time: item.timestamp, value: item.reference as number }));
    const researchPoints = observation?.points.map((point) => ({ time: point.timestamp, value: point.price })) ?? [];
    return {
      symbol, name: observation?.name ?? DISPLAY_NAMES[symbol] ?? symbol, price: displayPrice, previousClose, changePct,
      currency: observation?.currency ?? "USD", exchange: observation?.exchange ?? "—",
      eventTime: decision?.reference != null ? decision.timestamp : freshestDisplay?.eventTime ?? decision?.timestamp ?? null,
      ageSeconds: decision?.reference != null && decision.source_event_age_ms != null ? decision.source_event_age_ms / 1000 : freshestDisplay?.ageSeconds ?? null,
      points: decisionPoints.length > 1 ? decisionPoints : researchPoints, status: decision?.status ?? "DISPLAY_ONLY",
      confidence: decision?.confidence ?? null, bandLower: decision?.band_lower ?? null, bandUpper: decision?.band_upper ?? null,
      riskState: decision?.risk_state ?? null, divergenceBps: decision?.mark_divergence_bps ?? null,
      leverage: decision?.recommended_max_leverage ?? null, evidenceCount: decision?.independent_source_families ?? 0,
      reasons: decision?.reasons ?? observation?.decision.reasons ?? [], ai: decision?.ai ?? null,
      priceSource: decision?.reference != null ? "Qualified reference" : freshestDisplay?.source ?? "Unavailable",
    };
  });
}

export function mergeDisplaySnapshots(assets: MarketAsset[], snapshots: DisplaySnapshot[]): MarketAsset[] {
  const current = new Map(assets.map((asset) => [asset.symbol, asset]));
  for (const snapshot of snapshots) {
    const existing = current.get(snapshot.symbol);
    const hasOracleReference = existing?.priceSource === "Qualified reference";
    const price = hasOracleReference ? existing.price : snapshot.price ?? existing?.price ?? null;
    const previousClose = snapshot.previous_close ?? existing?.previousClose ?? null;
    current.set(snapshot.symbol, {
      symbol: snapshot.symbol, name: existing && existing.name !== snapshot.symbol ? existing.name : snapshot.name, price, previousClose,
      changePct: hasOracleReference && price != null && previousClose ? (price / previousClose - 1) * 100 : snapshot.change_pct ?? existing?.changePct ?? null,
      currency: snapshot.currency, exchange: existing?.exchange === "—" || !existing ? snapshot.exchange : existing.exchange,
      eventTime: hasOracleReference ? existing.eventTime : snapshot.event_time ?? existing?.eventTime ?? null,
      ageSeconds: hasOracleReference ? existing.ageSeconds : snapshot.event_time ? Math.max(0, (Date.now() - Date.parse(snapshot.event_time)) / 1000) : existing?.ageSeconds ?? null,
      bid: snapshot.bid ?? existing?.bid ?? null, ask: snapshot.ask ?? existing?.ask ?? null,
      dayVolume: snapshot.day_volume ?? existing?.dayVolume ?? null,
      points: (() => {
        const points = [...(existing?.points ?? [])];
        if (snapshot.price != null && snapshot.event_time) {
          const duplicate = points.some((point) => point.time === snapshot.event_time);
          if (!duplicate) points.push({ time: snapshot.event_time, value: snapshot.price });
        }
        return points
          .sort((left, right) => Date.parse(left.time) - Date.parse(right.time))
          .slice(-32);
      })(), status: existing?.status ?? "DISPLAY_ONLY", confidence: existing?.confidence ?? null,
      bandLower: existing?.bandLower ?? null, bandUpper: existing?.bandUpper ?? null, riskState: existing?.riskState ?? null,
      divergenceBps: existing?.divergenceBps ?? null, leverage: existing?.leverage ?? null,
      evidenceCount: existing?.evidenceCount ?? 0, reasons: existing?.reasons ?? ["DISPLAY_SNAPSHOT_ONLY"],
      priceSource: hasOracleReference ? "Qualified reference" : snapshot.price != null ? "Alpaca IEX" : existing?.priceSource ?? "Unavailable",
      ai: existing?.ai ?? null,
    });
  }
  return [...current.values()].sort((left, right) => left.symbol.localeCompare(right.symbol));
}