"use client";

import { useSearchParams } from "next/navigation";
import { AssetWorkspace } from "@/components/market-workspaces";

export default function CatalogAssetPage() {
  const symbol = (useSearchParams().get("symbol") ?? "").trim().toUpperCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,11}$/.test(symbol)) {
    return <div className="workspace"><div className="integration-empty"><div><strong>Select a Nasdaq symbol</strong><p>Open global search with ⌘K and choose a listing.</p></div></div></div>;
  }
  return <AssetWorkspace symbol={symbol}/>;
}
