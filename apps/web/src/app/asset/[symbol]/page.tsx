import type { Metadata } from "next";
import { AssetWorkspace } from "@/components/market-workspaces";
import { TRACKED_SYMBOLS } from "@/lib/market";
export const dynamicParams = false;
export function generateStaticParams() { return TRACKED_SYMBOLS.map((symbol) => ({ symbol: symbol.toLowerCase() })); }
export async function generateMetadata({ params }: { params: Promise<{ symbol: string }> }): Promise<Metadata> { const { symbol } = await params; return { title: symbol.toUpperCase() }; }
export default async function AssetPage({ params }: { params: Promise<{ symbol: string }> }) { const { symbol } = await params; return <AssetWorkspace symbol={symbol}/>; }
