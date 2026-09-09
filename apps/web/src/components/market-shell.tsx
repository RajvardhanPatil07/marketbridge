"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, BarChart3, BriefcaseBusiness, Command, Newspaper, PanelsTopLeft, Search, Sparkles, Star, X } from "lucide-react";
import { useMarketData } from "@/components/market-data-provider";
import { money, percent, TRACKED_SYMBOLS } from "@/lib/market";

const navigation = [
  { href: "/markets/", label: "Markets", icon: BarChart3 }, { href: "/screener/", label: "Screener", icon: Activity },
  { href: "/news/", label: "News", icon: Newspaper }, { href: "/portfolio/", label: "Portfolio", icon: BriefcaseBusiness },
  { href: "/terminal/", label: "Terminal", icon: Command }, { href: "/insights/", label: "Insights", icon: Sparkles },
  { href: "/watchlist/", label: "Watchlist", icon: Star },
];

function Brand() { return <Link className="mb-brand" href="/" aria-label="MarketBridge home"><PanelsTopLeft className="mb-brand-icon" size={22} strokeWidth={1.8} aria-hidden="true"/><span>MarketBridge</span></Link>; }

function MarketStrip() {
  const { assets, connection } = useMarketData();
  const tracked = useMemo(() => TRACKED_SYMBOLS.map((symbol) => assets.find((asset) => asset.symbol === symbol)).filter(Boolean), [assets]);
  return <div className="ticker-strip" aria-label="Tracked market strip"><div className="ticker-track">
    {tracked.length ? tracked.map((asset) => asset && <Link key={asset.symbol} href={`/asset/${asset.symbol.toLowerCase()}/`} className="ticker-item"><strong>{asset.symbol}</strong><span>{money(asset.price, asset.currency)}</span><b className={asset.changePct != null && asset.changePct < 0 ? "down" : "up"}>{percent(asset.changePct)}</b></Link>) : <><span className="ticker-item"><strong>SPX</strong><span>Unavailable</span></span><span className="ticker-item"><strong>NDX</strong><span>Unavailable</span></span><span className="ticker-item"><strong>BTC</strong><span>Unavailable</span></span></>}
    <span className={`ticker-state ${connection}`}><i/>{connection === "live" ? "Live" : connection === "delayed" ? "Delayed" : connection === "connecting" ? "Connecting" : "Offline"}</span>
  </div></div>;
}

function GlobalSearch({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { assets } = useMarketData(); const [query, setQuery] = useState(""); const [activeIndex, setActiveIndex] = useState(0); const inputRef = useRef<HTMLInputElement>(null); const dialogRef = useRef<HTMLElement>(null); const router = useRouter();
  const results = useMemo(() => assets.filter((asset) => `${asset.symbol} ${asset.name}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8), [assets, query]);
  const openAsset = (index: number) => { const asset = results[index]; if (!asset) return; router.push(`/asset/${asset.symbol.toLowerCase()}/`); onClose(); };
  useEffect(() => { if (open) { setQuery(""); setActiveIndex(0); requestAnimationFrame(() => inputRef.current?.focus()); } }, [open]);
  useEffect(() => { setActiveIndex(0); }, [query]);
  if (!open) return null;
  return <div className="command-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section ref={dialogRef} className="command-dialog" role="dialog" aria-modal="true" aria-label="Search markets" onKeyDown={(event) => {
    if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((index) => results.length ? (index + (event.key === "ArrowDown" ? 1 : -1) + results.length) % results.length : 0); return; }
    if (event.key === "Enter" && document.activeElement === inputRef.current) { event.preventDefault(); openAsset(activeIndex); return; }
    if (event.key === "Tab") { const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>("input, button:not([disabled])") ?? []); if (!focusable.length) return; const first = focusable[0]; const last = focusable.at(-1)!; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } }
  }}><div className="command-input"><Search size={18}/><input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search symbol or company" aria-label="Search symbol or company" aria-controls="market-search-results" aria-activedescendant={results[activeIndex] ? `market-result-${results[activeIndex].symbol}` : undefined}/><button onClick={onClose} aria-label="Close search"><X size={17}/></button></div><div id="market-search-results" className="command-results" role="listbox">{results.length ? results.map((asset, index) => <button id={`market-result-${asset.symbol}`} key={asset.symbol} className={index === activeIndex ? "active" : ""} role="option" aria-selected={index === activeIndex} onMouseEnter={() => setActiveIndex(index)} onClick={() => openAsset(index)}><span className="symbol-avatar">{asset.symbol.slice(0, 1)}</span><span><strong>{asset.symbol}</strong><small>{asset.name}</small></span><span className="command-enter">↵</span></button>) : <div className="command-empty">{query ? "No supported asset matches this search." : "Search assets currently provided by MarketBridge."}</div>}</div></section></div>;
}

export default function MarketShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const [searchOpen, setSearchOpen] = useState(false); const searchButtonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { const onKeyDown = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); } if (event.key === "Escape") setSearchOpen(false); }; window.addEventListener("keydown", onKeyDown); return () => window.removeEventListener("keydown", onKeyDown); }, []);
  const closeSearch = () => { setSearchOpen(false); requestAnimationFrame(() => searchButtonRef.current?.focus()); };
  return <div className="terminal-app"><a className="skip-link" href="#main-content">Skip to content</a><header className="terminal-header"><Brand/><nav className="desktop-nav" aria-label="Primary navigation">{navigation.map(({ href, label }) => <Link key={href} href={href} className={pathname.startsWith(href) ? "active" : ""}>{label}</Link>)}</nav><button ref={searchButtonRef} className="global-search" onClick={() => setSearchOpen(true)} aria-haspopup="dialog" aria-expanded={searchOpen}><Search size={15}/><span>Search markets</span><kbd>⌘K</kbd></button></header><MarketStrip/><main id="main-content" className="terminal-main">{children}</main><nav className="mobile-nav" aria-label="Mobile navigation">{navigation.slice(0, 5).map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={pathname.startsWith(href) ? "active" : ""}><Icon size={18}/><span>{label}</span></Link>)}</nav><GlobalSearch open={searchOpen} onClose={closeSearch}/></div>;
}
