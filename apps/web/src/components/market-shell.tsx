"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, BarChart3, Command, Newspaper, PanelsTopLeft, Search, Sparkles, X } from "lucide-react";
import { useMarketData } from "@/components/market-data-provider";
import { money, percent, TRACKED_SYMBOLS } from "@/lib/market";
import type { NasdaqSearchResponse, NasdaqSymbol } from "@/lib/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

const navigation = [
  { href: "/markets/", label: "Live", icon: BarChart3 },
  { href: "/demo/", label: "War Room", icon: Activity },
  { href: "/intelligence/", label: "Intelligence", icon: Newspaper },
  { href: "/providers/", label: "Providers", icon: Sparkles },
  { href: "/terminal/", label: "Terminal", icon: Command },
];

function Brand() {
  return <Link className="mb-brand" href="/" aria-label="MarketBridge home"><PanelsTopLeft className="mb-brand-icon" size={22} strokeWidth={1.8} aria-hidden="true"/><span>MarketBridge</span></Link>;
}

function MarketStrip() {
  const { assets, connection } = useMarketData();
  const tracked = useMemo(() => TRACKED_SYMBOLS.map((symbol) => assets.find((asset) => asset.symbol === symbol)).filter(Boolean), [assets]);
  return <div className="ticker-strip" aria-label="Tracked market strip"><div className="ticker-track">
    {tracked.length ? tracked.map((asset) => asset && <Link key={asset.symbol} href={`/asset/${asset.symbol.toLowerCase()}/`} className="ticker-item"><strong>{asset.symbol}</strong><span>{money(asset.price, asset.currency)}</span><b className={asset.changePct != null && asset.changePct < 0 ? "down" : "up"}>{percent(asset.changePct)}</b></Link>) : <><span className="ticker-item"><strong>NVDA</strong><span>Awaiting free feed</span></span><span className="ticker-item"><strong>TSLA</strong><span>Awaiting free feed</span></span></>}
    <span className={`ticker-state ${connection}`}><i/>{connection === "live" ? "Live" : connection === "delayed" ? "Delayed" : connection === "connecting" ? "Connecting" : "Offline"}</span>
  </div></div>;
}

function GlobalSearch({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { assets } = useMarketData();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [catalogue, setCatalogue] = useState<NasdaqSymbol[]>([]);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const router = useRouter();
  const liveBySymbol = useMemo(() => new Map(assets.map((asset) => [asset.symbol, asset])), [assets]);
  const results = useMemo(() => catalogue.map((item) => ({ ...item, live: liveBySymbol.get(item.symbol) })), [catalogue, liveBySymbol]);
  const openAsset = (index: number) => {
    const asset = results[index];
    if (!asset) return;
    router.push(`/asset/explore/?symbol=${encodeURIComponent(asset.symbol)}`);
    onClose();
  };
  useEffect(() => {
    if (open) {
      setQuery(""); setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        const response = await fetch(`${API_BASE}/v1/symbols?query=${encodeURIComponent(query)}&limit=10`, { signal: controller.signal, cache: "no-store" });
        if (response.ok) setCatalogue(((await response.json()) as NasdaqSearchResponse).items);
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, query ? 140 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [open, query]);
  useEffect(() => { setActiveIndex(0); }, [query]);
  if (!open) return null;
  return <div className="command-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section ref={dialogRef} className="command-dialog" role="dialog" aria-modal="true" aria-label="Search markets" onKeyDown={(event) => {
    if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((index) => results.length ? (index + (event.key === "ArrowDown" ? 1 : -1) + results.length) % results.length : 0); return; }
    if (event.key === "Enter" && document.activeElement === inputRef.current) { event.preventDefault(); openAsset(activeIndex); return; }
    if (event.key === "Tab") {
      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>("input, button:not([disabled])") ?? []);
      if (!focusable.length) return;
      const first = focusable[0]; const last = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  }}><div className="command-input"><Search size={18}/><input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Nasdaq symbols" aria-label="Search Nasdaq symbols" aria-controls="market-search-results" aria-activedescendant={results[activeIndex] ? `market-result-${results[activeIndex].symbol}` : undefined}/><button onClick={onClose} aria-label="Close search"><X size={17}/></button></div><div id="market-search-results" className="command-results" role="listbox">{results.length ? results.map((asset, index) => <button id={`market-result-${asset.symbol}`} key={asset.symbol} className={index === activeIndex ? "active" : ""} role="option" aria-selected={index === activeIndex} onMouseEnter={() => setActiveIndex(index)} onClick={() => openAsset(index)}><span className="symbol-avatar">{asset.symbol.slice(0, 1)}</span><span><strong>{asset.symbol}</strong><small>{asset.name}</small></span><span className="command-enter">{asset.live ? "LIVE" : asset.coverage_state.replaceAll("_", " ")}</span></button>) : <div className="command-empty">{searching ? "Searching Nasdaq…" : query ? "No Nasdaq listing matches this search." : "The Nasdaq catalogue is unavailable."}</div>}</div></section></div>;
}

export default function MarketShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [searchOpen, setSearchOpen] = useState(false);
  const searchButtonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); }
      if (event.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
  const closeSearch = () => { setSearchOpen(false); requestAnimationFrame(() => searchButtonRef.current?.focus()); };
  return <div className="terminal-app"><a className="skip-link" href="#main-content">Skip to content</a><header className="terminal-header"><Brand/><nav className="desktop-nav" aria-label="Primary navigation">{navigation.map(({ href, label }) => <Link key={href} href={href} className={pathname.startsWith(href) ? "active" : ""}>{label}</Link>)}</nav><button ref={searchButtonRef} className="global-search" onClick={() => setSearchOpen(true)} aria-haspopup="dialog" aria-expanded={searchOpen}><Search size={15}/><span>Search markets</span><kbd>⌘K</kbd></button></header><MarketStrip/><main id="main-content" className="terminal-main">{children}</main><nav className="mobile-nav" aria-label="Mobile navigation">{navigation.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={pathname.startsWith(href) ? "active" : ""}><Icon size={18}/><span>{label}</span></Link>)}</nav><GlobalSearch open={searchOpen} onClose={closeSearch}/></div>;
}
