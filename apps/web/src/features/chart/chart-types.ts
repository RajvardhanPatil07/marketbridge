export const RANGES = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"] as const;
export const RESOLUTIONS = ["1Min", "2Min", "5Min", "10Min", "15Min", "30Min", "1Hour", "2Hour", "4Hour", "1Day", "1Week", "1Month"] as const;
export const CHART_TYPES = ["Candlestick", "OHLC Bars", "Line", "Area", "Baseline", "Heikin Ashi"] as const;
export type ChartRange = typeof RANGES[number];
export type Resolution = typeof RESOLUTIONS[number];
export type ChartType = typeof CHART_TYPES[number];
export type ScaleMode = "Regular" | "Logarithmic" | "Percentage" | "Indexed to 100";

export type MarketBar = {
  timestamp: string; open: number; high: number; low: number; close: number;
  volume: number; vwap: number | null; trade_count: number | null;
};

export type BarsResponse = {
  symbol: string; provider: "alpaca"; feed: string; resolution: Resolution;
  adjustment: "raw" | "all"; currency: string; timezone: string; start: string; end: string;
  session: "regular" | "extended" | "all"; status: "AVAILABLE" | "DELAYED";
  is_delayed: boolean; entitlement: string; cached: boolean; pages: number;
  bars: MarketBar[]; has_more_history: boolean; next_end: string | null;
  data_role: "DISPLAY_ONLY_NOT_ORACLE_EVIDENCE";
};

export type IndicatorKind = "SMA" | "EMA" | "Bollinger Bands" | "Volume" | "RSI" | "MACD";
export type IndicatorConfig = { id: string; kind: IndicatorKind; length: number; color: string; visible: boolean };
