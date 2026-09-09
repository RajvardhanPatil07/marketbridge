import type { Metadata } from "next";
import { ScreenerWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "Screener" };
export default function ScreenerPage() { return <ScreenerWorkspace/>; }
