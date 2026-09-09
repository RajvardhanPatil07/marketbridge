import type { Metadata } from "next";
import { MarketsWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "Stocks" };
export default function StocksPage() { return <MarketsWorkspace category="stocks"/>; }
