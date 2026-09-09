import type { Metadata } from "next";
import Dashboard from "@/components/dashboard";
export const metadata: Metadata = { title: "Risk Lab" };
export default function RiskLabPage() { return <div className="embedded-risk-lab"><Dashboard/></div>; }
