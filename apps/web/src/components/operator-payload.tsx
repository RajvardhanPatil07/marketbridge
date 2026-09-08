"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Clipboard, Code2 } from "lucide-react";
import type { OperatorDecision, Step } from "@/lib/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

export default function OperatorPayload({ scenarioId, symbol, step }: { scenarioId: string; symbol: string; step: Step }) {
  const [payload, setPayload] = useState<(OperatorDecision & Record<string, unknown>) | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/v1/operator/decision/${encodeURIComponent(scenarioId)}?symbol=${encodeURIComponent(symbol)}&second=${step.seconds}`, { signal: controller.signal, headers: { Accept: "application/json" } })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Operator endpoint unavailable")))
      .then(setPayload)
      .catch(() => { if (!controller.signal.aborted) setPayload(null); });
    return () => controller.abort();
  }, [scenarioId, step.seconds, symbol]);
  const preview = useMemo(() => payload ? JSON.stringify({
    symbol: payload.symbol,
    reference: payload.reference,
    status: payload.status,
    independent_source_families: payload.independent_source_families,
    new_exposure_allowed: payload.new_exposure_allowed,
    advisory_exposure_multiplier: payload.advisory_exposure_multiplier,
    reasons: payload.reasons,
  }, null, 2) : "Loading the risk decision…", [payload]);
  async function copyPayload() {
    if (!payload) return;
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }
  return <section className="panel operator-payload" aria-labelledby="operator-payload-title">
    <div className="panel-heading"><div><span className="mode-label"><Code2 size={13}/>Integration-ready output</span><h2 id="operator-payload-title">The risk engine gets a decision, not another chart.</h2><p>A read-only payload that can drive exposure, leverage, and publication policy.</p></div><button className="button secondary compact" onClick={copyPayload} disabled={!payload}>{copied ? <Check size={14}/> : <Clipboard size={14}/>} {copied ? "Copied" : "Copy JSON"}</button></div>
    <pre aria-live="polite">{preview}</pre>
    <div className="payload-footer"><span>GET /v1/operator/decision/{scenarioId}</span><span>Advisory only · no trade execution</span></div>
  </section>;
}
