import Link from "next/link";
export default function NotFound() { return <div className="route-error"><h1>Market view not found</h1><p>The route or asset is not part of the supported MarketBridge universe.</p><Link href="/markets/">Return to markets</Link></div>; }
