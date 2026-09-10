import type { Metadata } from "next";
import { ProviderMesh } from "@/components/v1-experience";

export const metadata: Metadata = { title: "Provider Mesh" };
export default function ProvidersPage() { return <ProviderMesh/>; }
