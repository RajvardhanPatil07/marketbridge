"use client";

import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import type { ShadowDecision } from "@/lib/types";

export default function EvidenceLineage({ decision }: { decision: ShadowDecision }) {
  const evidence = decision.evidence.slice(0, 6);
  const nodes: Node[] = evidence.map((item, index) => ({
    id: `e-${index}`,
    position: { x: 0, y: index * 78 },
    data: { label: `${item.provider_family} · ${item.venue_family}\n${item.price.toFixed(2)} · ${item.fresh ? "fresh" : "stale"}` },
    className: item.eligible && item.fresh ? "lineage-node evidence healthy" : "lineage-node evidence muted",
  }));
  nodes.push(
    { id: "reference", position: { x: 330, y: 105 }, data: { label: `Reference\n${decision.reference?.toFixed(2) ?? "abstained"}` }, className: "lineage-node reference" },
    { id: "passport", position: { x: 610, y: 35 }, data: { label: `Passport #${decision.passport.sequence}\n${decision.passport.chain_hash.slice(0, 10)}…` }, className: "lineage-node passport" },
    { id: "risk", position: { x: 610, y: 185 }, data: { label: `Risk: ${decision.risk_state}\n${decision.recommended_max_leverage}× leverage` }, className: "lineage-node risk" },
  );
  if (decision.venue_mark) {
    nodes.push({ id: "mark", position: { x: 330, y: 285 }, data: { label: `Venue mark (comparison only)\n${decision.venue_mark.price.toFixed(2)}` }, className: "lineage-node mark" });
  }

  const edgeStyle = { stroke: "#9eabc0", strokeWidth: 1.4 };
  const edges: Edge[] = evidence.map((_, index) => ({
    id: `e-${index}-reference`, source: `e-${index}`, target: "reference", markerEnd: { type: MarkerType.ArrowClosed }, style: edgeStyle,
  }));
  edges.push(
    { id: "reference-passport", source: "reference", target: "passport", markerEnd: { type: MarkerType.ArrowClosed }, style: edgeStyle },
    { id: "reference-risk", source: "reference", target: "risk", markerEnd: { type: MarkerType.ArrowClosed }, style: edgeStyle },
  );
  if (decision.venue_mark) edges.push({ id: "mark-reference", source: "mark", target: "reference", animated: true, label: "compare only", style: { ...edgeStyle, strokeDasharray: "5 5" } });

  return <div className="lineage-canvas" aria-label="Interactive decision evidence graph">
    <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} minZoom={0.55} maxZoom={1.5}>
      <Background gap={18} size={1}/><Controls showInteractive={false}/>
    </ReactFlow>
  </div>;
}
