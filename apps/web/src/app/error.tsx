"use client";
import { RotateCcw, TriangleAlert } from "lucide-react";
export default function ErrorBoundary({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <div className="route-error" role="alert"><TriangleAlert size={22}/><h1>This market view could not load</h1><p>Try the request again. If the issue persists, the backend market-data service may be unavailable.</p><button onClick={reset}><RotateCcw size={14}/>Try again</button></div>; }
