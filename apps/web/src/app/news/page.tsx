import type { Metadata } from "next";
import { NewsWorkspace } from "@/components/market-workspaces";
export const metadata: Metadata = { title: "News" };
export default function NewsPage() { return <NewsWorkspace/>; }
