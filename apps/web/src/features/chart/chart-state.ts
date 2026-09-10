import type { ChartRange, ChartType, IndicatorConfig, Resolution, ScaleMode } from "./chart-types";

export type WorkspaceState = { version: 1; range: ChartRange; resolution: Resolution; chartType: ChartType; scaleMode: ScaleMode; adjustment: "raw" | "all"; session: "regular" | "extended" | "all"; indicators: IndicatorConfig[] };
export const DEFAULT_RESOLUTION: Record<ChartRange, Resolution> = { "1D": "1Min", "5D": "5Min", "1M": "30Min", "3M": "1Hour", "6M": "1Day", YTD: "1Day", "1Y": "1Day", "5Y": "1Week", MAX: "1Month" };
export const defaultWorkspace = (): WorkspaceState => ({ version: 1, range: "5D", resolution: "5Min", chartType: "Candlestick", scaleMode: "Regular", adjustment: "raw", session: "regular", indicators: [{ id: "volume", kind: "Volume", length: 20, color: "#4c78ff", visible: true }] });
export function loadWorkspace(symbol: string): WorkspaceState { try { const value = JSON.parse(localStorage.getItem(`marketbridge-chart:v1:${symbol}`) ?? "null"); return value?.version === 1 ? { ...defaultWorkspace(), ...value } : defaultWorkspace(); } catch { return defaultWorkspace(); } }
export function saveWorkspace(symbol: string, state: WorkspaceState) { localStorage.setItem(`marketbridge-chart:v1:${symbol}`, JSON.stringify(state)); }
