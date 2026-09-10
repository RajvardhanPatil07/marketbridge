"use client";

import { Activity, Radio, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import styles from "./kalshi-pulse.module.css";

const API_BASE = process.env.NEXT_PUBLIC_MARKETBRIDGE_API_BASE?.replace(/\/$/, "") ?? "";
const REFRESH_MS = 120_000;

type PulseMarket = {
  ticker: string;
  title: string;
  yes_label: string;
  probability: number | null;
  probability_change_pp: number | null;
  spread_pp: number | null;
  volume_24h: number;
  quality: "HIGH" | "MEDIUM" | "LOW";
  relevance: "DIRECT" | "RELATED";
};

type KalshiPulse = {
  status: "AVAILABLE" | "NO_RELEVANT_MARKETS" | "DEGRADED" | "UNAVAILABLE" | "RATE_LIMITED" | "UPSTREAM_ERROR";
  cached: boolean;
  api_key_required: false;
  cost: "FREE_PUBLIC_REST";
  markets: PulseMarket[];
  summary: { matched: number; high_quality: number; largest_move_pp: number | null };
  message: string | null;
};

function signed(value: number | null) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)} pp`;
}

function probability(value: number | null) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export default function KalshiPulsePanel({ symbol }: { symbol: string }) {
  const [pulse, setPulse] = useState<KalshiPulse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch(`${API_BASE}/v1/kalshi/pulse?symbol=${encodeURIComponent(symbol)}`, {
          headers: { Accept: "application/json" }, cache: "no-store", signal: controller.signal,
        });
        if (!response.ok) throw new Error(`Kalshi pulse request failed (${response.status})`);
        setPulse(await response.json() as KalshiPulse);
        setError(null);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Kalshi pulse is unavailable");
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [symbol]);

  const message = error ?? pulse?.message;
  return <section className={styles.panel} aria-live="polite">
    <header className={styles.header}>
      <div className={styles.title}><Radio size={15}/><div><h2>Kalshi Event Information Pulse</h2><p>Market-implied event probabilities related to {symbol}</p></div></div>
      <span className={styles.badge}>FREE PUBLIC REST</span>
    </header>
    <div className={styles.summary}>
      <div><span>Relevant markets</span><strong>{pulse?.summary.matched ?? "—"}</strong></div>
      <div><span>High-quality signals</span><strong>{pulse?.summary.high_quality ?? "—"}</strong></div>
      <div><span>Largest move</span><strong>{signed(pulse?.summary.largest_move_pp ?? null)}</strong></div>
      <div><span>Mode</span><strong>Advisory</strong></div>
    </div>
    {pulse?.markets.length ? <div className={styles.body}>{pulse.markets.map((market) => {
      const changeClass = (market.probability_change_pp ?? 0) >= 0 ? styles.positive : styles.negative;
      return <article className={styles.market} key={market.ticker}>
        <div className={styles.marketCopy}><strong title={market.title}>{market.title}</strong><span>{market.yes_label} · {market.relevance.toLowerCase()} relevance · {market.volume_24h.toLocaleString()} contracts/24h</span></div>
        <div className={styles.marketPrice}><strong>{probability(market.probability)}</strong><b className={changeClass}>{signed(market.probability_change_pp)}</b><i className={styles.quality}>{market.quality}</i></div>
      </article>;
    })}</div> : <div className={styles.quiet}>{message ?? "Scanning Kalshi's open event markets…"}</div>}
    <footer className={styles.boundary}><ShieldCheck size={13}/><span>Event context only. Never counted as direct {symbol} price evidence or executable arbitrage.</span>{pulse?.cached ? <Activity size={11} aria-label="Cached response"/> : null}</footer>
  </section>;
}
