import type { Metadata } from "next";
import { MarketsWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "Markets" };
export default function MarketsPage() { return <MarketsWorkspace/>; }
