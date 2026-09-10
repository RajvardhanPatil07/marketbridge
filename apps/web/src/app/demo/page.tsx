import type { Metadata } from "next";
import { WarRoom } from "@/components/v1-experience";

export const metadata: Metadata = { title: "War Room Demo" };
export default function DemoPage() { return <WarRoom/>; }
