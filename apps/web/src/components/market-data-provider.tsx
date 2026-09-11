"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { assetsFromSnapshot, mergeDisplaySnapshots, type ConnectionState, type MarketAsset } from "@/lib/market";
import type { DisplaySnapshot, DisplaySnapshotsResponse, ShadowSnapshot } from "@/lib/types";

type MarketDataContextValue = { assets: MarketAsset[]; snapshot: ShadowSnapshot | null; connection: ConnectionState; error: string | null; loading: boolean; lastUpdated: string | null; refresh: () => Promise<void> };
const MarketDataContext = createContext<MarketDataContextValue | null>(null);
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const friendlyError = (status?: number) => status === 401 || status === 403 ? "Market data access is not authorized." : status === 429 ? "Market data is rate limited. Updates will resume automatically." : "The market-data service is unavailable. The synthetic War Room remains available.";

function sanitizeSnapshot(next: ShadowSnapshot): ShadowSnapshot {
  return { ...next, providers: next.providers.filter((provider) => provider.id !== "databento") };
}

function providerConnection(next: ShadowSnapshot): ConnectionState {
  const live = next.providers.some((provider) => ["alpaca", "hyperliquid", "twelve-data"].includes(provider.id) && ["AVAILABLE", "LIMITED", "AUTHENTICATED"].includes(provider.status));
  if (live) return "live";
  if (next.decisions.length || next.yahoo?.observations?.length) return "delayed";
  return "offline";
}

export function MarketDataProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState<ShadowSnapshot | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [displaySnapshots, setDisplaySnapshots] = useState<DisplaySnapshot[]>([]);
  const fallbackStarted = useRef(false);
  const alpacaConfigured = snapshot?.configuration.alpaca.credentials_configured ?? false;

  const accept = useCallback((incoming: ShadowSnapshot) => {
    const next = sanitizeSnapshot(incoming);
    setSnapshot(next); setError(null); setLoading(false); setConnection(providerConnection(next));
  }, []);

  const loadSnapshot = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/shadow/snapshot`, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) throw Object.assign(new Error(), { status: response.status });
      const next = await response.json() as ShadowSnapshot;
      accept(next);
      return next;
    } catch (cause) {
      const status = typeof cause === "object" && cause && "status" in cause ? Number(cause.status) : undefined;
      setError(friendlyError(status)); setConnection("offline"); setLoading(false);
      return null;
    }
  }, [accept]);

  const loadDisplaySnapshots = useCallback(async () => {
    if (!alpacaConfigured) {
      setDisplaySnapshots([]);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/v1/market/snapshots`, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return;
      const incoming = ((await response.json()) as DisplaySnapshotsResponse).items;
      setDisplaySnapshots((previous) => {
        const combined = [...previous, ...incoming];
        const bySymbol = new Map<string, DisplaySnapshot[]>();
        for (const item of combined) {
          const items = bySymbol.get(item.symbol) ?? [];
          const duplicate = items.some((candidate) =>
            candidate.event_time === item.event_time && candidate.price === item.price
          );
          if (!duplicate) items.push(item);
          bySymbol.set(item.symbol, items.slice(-32));
        }
        return [...bySymbol.values()].flat();
      });
    } catch { /* preserve the last verified display snapshot */ }
  }, [alpacaConfigured]);

  const refresh = useCallback(async () => {
    await loadSnapshot();
    await loadDisplaySnapshots();
  }, [loadDisplaySnapshots, loadSnapshot]);

  useEffect(() => {
    void loadSnapshot();
    const wsOrigin = API_BASE ? API_BASE.replace(/^http/, "ws") : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
    let source: EventSource | null = null; let socket: WebSocket | null = null; let closed = false;
    const startFallback = () => {
      if (closed || fallbackStarted.current) return;
      fallbackStarted.current = true; source = new EventSource(`${API_BASE}/v1/shadow/stream`);
      source.onmessage = (event) => accept(JSON.parse(event.data) as ShadowSnapshot);
      source.onerror = () => setConnection((state) => state === "live" ? "delayed" : "offline");
    };
    try {
      socket = new WebSocket(`${wsOrigin}/v1/shadow/ws`); socket.onopen = () => setConnection((state) => state === "connecting" ? "delayed" : state);
      socket.onmessage = (event) => { const message = JSON.parse(event.data) as { type: string; data?: ShadowSnapshot }; if (message.type === "shadow_snapshot" && message.data) accept(message.data); };
      socket.onerror = startFallback; socket.onclose = startFallback;
    } catch { startFallback(); }
    return () => { closed = true; socket?.close(); source?.close(); fallbackStarted.current = false; };
  }, [accept, loadSnapshot]);

  useEffect(() => {
    if (!alpacaConfigured) {
      setDisplaySnapshots([]);
      return;
    }
    void loadDisplaySnapshots();
    const timer = window.setInterval(() => void loadDisplaySnapshots(), 30_000);
    return () => window.clearInterval(timer);
  }, [alpacaConfigured, loadDisplaySnapshots]);

  const value = useMemo<MarketDataContextValue>(() => ({ assets: mergeDisplaySnapshots(assetsFromSnapshot(snapshot), displaySnapshots), snapshot, connection, error, loading, lastUpdated: snapshot?.decisions[0]?.timestamp ?? snapshot?.yahoo?.fetched_at ?? null, refresh }), [snapshot, displaySnapshots, connection, error, loading, refresh]);
  return <MarketDataContext.Provider value={value}>{children}</MarketDataContext.Provider>;
}

export function useMarketData() { const value = useContext(MarketDataContext); if (!value) throw new Error("useMarketData must be used inside MarketDataProvider"); return value; }