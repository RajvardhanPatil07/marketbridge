import type { Metadata } from "next";
import { MarketsWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "ETFs" };
export default function EtfsPage() { return <MarketsWorkspace category="etfs"/>; }
