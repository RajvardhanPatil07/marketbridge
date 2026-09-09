import type { Metadata } from "next";
import { InsightsWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "Insights" };
export default function InsightsPage() { return <InsightsWorkspace/>; }
