import type { Metadata } from "next";
import { IntelligenceWorkspace } from "@/components/v1-experience";

export const metadata: Metadata = { title: "Market Intelligence" };
export default function IntelligencePage() { return <IntelligenceWorkspace/>; }
