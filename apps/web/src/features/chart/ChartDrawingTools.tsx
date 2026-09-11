"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Brush, Crosshair, Eye, EyeOff, Lock, Minus, MousePointer2, Redo2, Ruler, Square, Trash2, Type, Unlock, Waypoints, ZoomIn } from "lucide-react";

type Tool = "cursor" | "trend" | "horizontal" | "vertical" | "fibonacci" | "rectangle" | "brush" | "text" | "measure";
type Point = { x: number; y: number };
type Drawing = { id: string; tool: Exclude<Tool, "cursor">; start: Point; end: Point; points?: Point[]; text?: string };

const tools: { value: Tool; label: string; icon: typeof Crosshair }[] = [
  { value: "cursor", label: "Cursor", icon: MousePointer2 },
  { value: "trend", label: "Trend line", icon: Waypoints },
  { value: "horizontal", label: "Horizontal line", icon: Minus },
  { value: "vertical", label: "Vertical line", icon: Crosshair },
  { value: "fibonacci", label: "Fibonacci retracement", icon: Redo2 },
  { value: "rectangle", label: "Rectangle", icon: Square },
  { value: "brush", label: "Brush", icon: Brush },
  { value: "text", label: "Text note", icon: Type },
  { value: "measure", label: "Measure", icon: Ruler },
];

const point = (event: ReactPointerEvent<SVGSVGElement>): Point => {
  const bounds = event.currentTarget.getBoundingClientRect();
  return { x: ((event.clientX - bounds.left) / bounds.width) * 1000, y: ((event.clientY - bounds.top) / bounds.height) * 1000 };
};

function DrawingShape({ drawing }: { drawing: Drawing }) {
  const common = { stroke: "#b8c9ff", strokeWidth: 2.25, vectorEffect: "non-scaling-stroke" as const, fill: "none", strokeLinecap: "round" as const };
  if (drawing.tool === "horizontal") return <line {...common} x1={0} y1={drawing.start.y} x2={1000} y2={drawing.start.y}/>;
  if (drawing.tool === "vertical") return <line {...common} x1={drawing.start.x} y1={0} x2={drawing.start.x} y2={1000}/>;
  if (drawing.tool === "rectangle") return <rect {...common} x={Math.min(drawing.start.x, drawing.end.x)} y={Math.min(drawing.start.y, drawing.end.y)} width={Math.abs(drawing.end.x - drawing.start.x)} height={Math.abs(drawing.end.y - drawing.start.y)} fill="#3861fb12"/>;
  if (drawing.tool === "brush") return <polyline {...common} points={(drawing.points ?? []).map((item) => `${item.x},${item.y}`).join(" ")} strokeLinecap="round" strokeLinejoin="round"/>;
  if (drawing.tool === "text") return <text x={drawing.start.x} y={drawing.start.y} fill="#f0f3f6" fontSize="18" fontFamily="var(--font-sans), sans-serif">{drawing.text}</text>;
  if (drawing.tool === "fibonacci") {
    const top = Math.min(drawing.start.y, drawing.end.y); const height = Math.abs(drawing.end.y - drawing.start.y);
    return <g>{[0, .236, .382, .5, .618, 1].map((level) => <g key={level}><line {...common} x1={drawing.start.x} y1={top + height * level} x2={drawing.end.x} y2={top + height * level}/><text x={drawing.end.x + 5} y={top + height * level - 4} fill="#8faaff" fontSize="12">{level.toFixed(3)}</text></g>)}</g>;
  }
  return <g><line {...common} x1={drawing.start.x} y1={drawing.start.y} x2={drawing.end.x} y2={drawing.end.y} strokeDasharray={drawing.tool === "measure" ? "5 4" : undefined}/>{drawing.tool === "measure" && <text x={(drawing.start.x + drawing.end.x) / 2} y={(drawing.start.y + drawing.end.y) / 2 - 8} fill="#f0f3f6" fontSize="13">{Math.round(Math.hypot(drawing.end.x - drawing.start.x, drawing.end.y - drawing.start.y))} px</text>}</g>;
}

export default function ChartDrawingTools({ symbol, onZoom }: { symbol: string; onZoom(): void }) {
  const storageKey = `marketbridge-drawings:v1:${symbol}`;
  const [active, setActive] = useState<Tool>("cursor");
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [draft, setDraft] = useState<Drawing | null>(null);
  const [locked, setLocked] = useState(false);
  const [hidden, setHidden] = useState(false);
  const drawingRef = useRef(false);

  useEffect(() => {
    try { setDrawings(JSON.parse(localStorage.getItem(storageKey) ?? "[]")); } catch { setDrawings([]); }
  }, [storageKey]);
  useEffect(() => { localStorage.setItem(storageKey, JSON.stringify(drawings)); }, [drawings, storageKey]);

  const visibleDrawings = useMemo(() => hidden ? [] : draft ? [...drawings, draft] : drawings, [draft, drawings, hidden]);
  const begin = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (active === "cursor" || locked) return;
    const start = point(event); drawingRef.current = true; event.currentTarget.setPointerCapture(event.pointerId);
    if (active === "horizontal" || active === "vertical") {
      setDrawings((items) => [...items, { id: crypto.randomUUID(), tool: active, start, end: start }]); drawingRef.current = false; return;
    }
    if (active === "text") {
      const text = window.prompt("Text note"); if (text?.trim()) setDrawings((items) => [...items, { id: crypto.randomUUID(), tool: "text", start, end: start, text: text.trim() }]); drawingRef.current = false; return;
    }
    setDraft({ id: crypto.randomUUID(), tool: active, start, end: start, points: active === "brush" ? [start] : undefined });
  };
  const move = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!drawingRef.current) return; const end = point(event);
    setDraft((value) => value ? { ...value, end, points: value.tool === "brush" ? [...(value.points ?? []), end] : value.points } : value);
  };
  const finish = () => {
    if (!drawingRef.current) return; drawingRef.current = false;
    setDraft((value) => { if (value) setDrawings((items) => [...items, value]); return null; });
  };

  return <><div className="chart-drawing-toolbar" role="toolbar" aria-label="Drawing tools">
    {tools.map(({ value, label, icon: Icon }) => <button key={value} type="button" className={active === value ? "active" : ""} title={label} aria-label={label} aria-pressed={active === value} onClick={() => setActive(value)}><Icon size={16}/></button>)}
    <span/>
    <button type="button" title="Zoom in" aria-label="Zoom in" onClick={onZoom}><ZoomIn size={16}/></button>
    <button type="button" title={locked ? "Unlock drawings" : "Lock drawings"} aria-label={locked ? "Unlock drawings" : "Lock drawings"} aria-pressed={locked} onClick={() => setLocked((value) => !value)}>{locked ? <Lock size={16}/> : <Unlock size={16}/>}</button>
    <button type="button" title={hidden ? "Show drawings" : "Hide drawings"} aria-label={hidden ? "Show drawings" : "Hide drawings"} aria-pressed={hidden} onClick={() => setHidden((value) => !value)}>{hidden ? <Eye size={16}/> : <EyeOff size={16}/>}</button>
    <button type="button" title="Remove last drawing" aria-label="Remove last drawing" disabled={!drawings.length} onClick={() => setDrawings((items) => items.slice(0, -1))}><Redo2 className="undo-icon" size={16}/></button>
    <button type="button" title="Remove all drawings" aria-label="Remove all drawings" disabled={!drawings.length} onClick={() => setDrawings([])}><Trash2 size={16}/></button>
  </div><svg className={`chart-drawing-layer ${active === "cursor" || locked ? "passive" : "drawing"}`} viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Chart drawings" onPointerDown={begin} onPointerMove={move} onPointerUp={finish} onPointerCancel={finish}>{visibleDrawings.map((drawing) => <DrawingShape key={drawing.id} drawing={drawing}/>)}</svg></>;
}