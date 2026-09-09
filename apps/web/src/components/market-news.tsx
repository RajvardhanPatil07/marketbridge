"use client";

import { CircleAlert, ExternalLink, Newspaper, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { MarketNewsArticle, MarketNewsFeed } from "@/lib/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

function published(value: string) {
  if (!value) return "Publication time unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Publication time unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
  }).format(date);
}

function sentiment(article: MarketNewsArticle) {
  if (article.sentiment_score == null) return { label: "Unscored", tone: "neutral" };
  if (article.sentiment_score > 0.1) return { label: "Positive", tone: "positive" };
  if (article.sentiment_score < -0.1) return { label: "Negative", tone: "negative" };
  return { label: "Neutral", tone: "neutral" };
}

export default function MarketNews({ symbol }: { symbol?: string }) {
  const [feed, setFeed] = useState<MarketNewsFeed | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
    try {
      const response = await fetch(`${API_BASE}/v1/news${query}`, {
        signal, headers: { Accept: "application/json" }, cache: "no-store",
      });
      if (!response.ok) throw new Error(`News request failed (${response.status})`);
      setFeed(await response.json() as MarketNewsFeed);
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError("The financial-news service is unavailable.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (loading && !feed) return <div className="news-state"><RefreshCw className="news-spinner" size={18}/><span>Loading financial news…</span></div>;
  if (error) return <div className="news-state news-error"><CircleAlert size={18}/><span>{error}</span><button onClick={() => void load()}>Retry</button></div>;
  if (!feed?.configured) return <div className="news-state"><CircleAlert size={18}/><div><strong>Marketaux is not configured</strong><p>Add <code>MARKETAUX_API_TOKEN</code> to the backend environment, then restart MarketBridge.</p></div></div>;
  if (feed.status !== "AVAILABLE" && feed.status !== "DEGRADED" && !feed.articles.length) return <div className="news-state news-error"><CircleAlert size={18}/><div><strong>Marketaux feed unavailable</strong><p>{feed.message}</p></div><button onClick={() => void load()}>Retry</button></div>;
  if (!feed.articles.length) return <div className="news-state"><Newspaper size={18}/><div><strong>No matching coverage</strong><p>No recent Marketaux articles mention {symbol ?? "the tracked US symbols"}.</p></div></div>;

  return <div className="news-feed">
    {feed.status === "DEGRADED" && <div className="news-warning"><CircleAlert size={13}/>{feed.message ?? "Showing cached news."}</div>}
    {feed.articles.map((article) => {
      const score = sentiment(article);
      return <article className="news-card" key={article.id}>
        <div className="news-source"><span>{article.source}</span><time dateTime={article.published_at}>{published(article.published_at)}</time></div>
        <a href={article.url} target="_blank" rel="noreferrer"><h3>{article.title}</h3><ExternalLink size={13}/></a>
        {article.description && <p>{article.description}</p>}
        <div className="news-meta"><span className={`news-sentiment ${score.tone}`}>{score.label}</span>{article.symbols.map((item) => <span className="news-symbol" key={item}>{item}</span>)}</div>
      </article>;
    })}
    <footer className="news-provider">Market data decisions remain independent of news sentiment · Source: Marketaux{feed.cached ? " · cached" : ""}</footer>
  </div>;
}
