import { Suspense } from "react";
import CatalogAssetPage from "@/components/catalog-asset-page";

export default function ExploreAssetPage() {
  return <Suspense fallback={<div className="workspace">Loading Nasdaq listing…</div>}><CatalogAssetPage/></Suspense>;
}
