"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { assetsFromSnapshot, mergeDisplaySnapshots, type ConnectionState, type MarketAsset } from "@/lib/market";
import type { DisplaySnapshot, DisplaySnapshotsResponse, ShadowSnapshot } from "@/lib/types";

type MarketDataContextValue = { assets: MarketAsset[]; snapshot: ShadowSnapshot | null; connection: ConnectionState; error: string | null; loading: boolean; lastUpdated: string | null; refresh: () => Promise<void> };
const MarketDataContext = createContext<MarketDataContextValue | null>(null);
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");
const friendlyError = (status?: number) => status === 401 || status === 403 ? "Market data access is not authorized." : status === 429 ? "Market data is rate limited. Updates will resume automatically." : "The market-data service is unavailable. Existing research tools remain accessible.";

export function MarketDataProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState<ShadowSnapshot | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [displaySnapshots, setDisplaySnapshots] = useState<DisplaySnapshot[]>([]);
  const fallbackStarted = useRef(false);
  const accept = useCallback((next: ShadowSnapshot) => {
    setSnapshot(next); setError(null); setLoading(false);
    setConnection(next.yahoo?.provider_status === "AVAILABLE" ? "live" : "delayed");
  }, []);
  const loadSnapshot = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/shadow/snapshot`, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) throw Object.assign(new Error(), { status: response.status });
      accept(await response.json() as ShadowSnapshot);
    } catch (cause) {
      const status = typeof cause === "object" && cause && "status" in cause ? Number(cause.status) : undefined;
      setError(friendlyError(status)); setConnection("offline"); setLoading(false);
    }
  }, [accept]);
  const loadDisplaySnapshots = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/market/snapshots`, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return;
      setDisplaySnapshots(((await response.json()) as DisplaySnapshotsResponse).items);
    } catch { /* preserve the last verified display snapshot */ }
  }, []);
  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/shadow/refresh`, { method: "POST", headers: { Accept: "application/json" } });
      if (!response.ok) throw Object.assign(new Error(), { status: response.status });
      await Promise.all([loadSnapshot(), loadDisplaySnapshots()]);
    } catch (cause) {
      const status = typeof cause === "object" && cause && "status" in cause ? Number(cause.status) : undefined;
      setError(friendlyError(status));
    }
  }, [loadDisplaySnapshots, loadSnapshot]);

  useEffect(() => {
    void Promise.all([loadSnapshot(), loadDisplaySnapshots()]);
    const displayTimer = window.setInterval(() => void loadDisplaySnapshots(), 30_000);
    const wsOrigin = API_BASE ? API_BASE.replace(/^http/, "ws") : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
    let source: EventSource | null = null; let socket: WebSocket | null = null; let closed = false;
    const startFallback = () => {
      if (closed || fallbackStarted.current) return;
      fallbackStarted.current = true; source = new EventSource(`${API_BASE}/v1/shadow/stream`);
      source.onmessage = (event) => accept(JSON.parse(event.data) as ShadowSnapshot);
      source.onerror = () => setConnection((state) => state === "live" ? "delayed" : "offline");
    };
    try {
      socket = new WebSocket(`${wsOrigin}/v1/shadow/ws`); socket.onopen = () => setConnection("live");
      socket.onmessage = (event) => { const message = JSON.parse(event.data) as { type: string; data?: ShadowSnapshot }; if (message.type === "shadow_snapshot" && message.data) accept(message.data); };
      socket.onerror = startFallback; socket.onclose = startFallback;
    } catch { startFallback(); }
    return () => { closed = true; window.clearInterval(displayTimer); socket?.close(); source?.close(); fallbackStarted.current = false; };
  }, [accept, loadDisplaySnapshots, loadSnapshot]);

  const value = useMemo<MarketDataContextValue>(() => ({ assets: mergeDisplaySnapshots(assetsFromSnapshot(snapshot), displaySnapshots), snapshot, connection, error, loading, lastUpdated: snapshot?.decisions[0]?.timestamp ?? snapshot?.yahoo?.fetched_at ?? null, refresh }), [snapshot, displaySnapshots, connection, error, loading, refresh]);
  return <MarketDataContext.Provider value={value}>{children}</MarketDataContext.Provider>;
}

export function useMarketData() { const value = useContext(MarketDataContext); if (!value) throw new Error("useMarketData must be used inside MarketDataProvider"); return value; }
