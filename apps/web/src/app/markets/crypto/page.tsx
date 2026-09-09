import type { Metadata } from "next";
import { MarketsWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "Crypto" };
export default function CryptoPage() { return <MarketsWorkspace category="crypto"/>; }
