import type { Metadata } from "next";
import { TerminalWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "Terminal" };
export default function TerminalPage() { return <TerminalWorkspace/>; }
