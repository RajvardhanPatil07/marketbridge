import type { MarketBar } from "../chart-types";

export type Point = { time: string; value: number };

export function sma(values: number[], length: number): (number | null)[] {
  const out: (number | null)[] = Array(values.length).fill(null); let sum = 0;
  for (let index = 0; index < values.length; index += 1) {
    sum += values[index]; if (index >= length) sum -= values[index - length];
    if (index >= length - 1) out[index] = sum / length;
  }
  return out;
}

export function ema(values: number[], length: number): (number | null)[] {
  const out: (number | null)[] = Array(values.length).fill(null);
  if (values.length < length || length < 1) return out;
  let current = values.slice(0, length).reduce((sum, value) => sum + value, 0) / length;
  out[length - 1] = current; const alpha = 2 / (length + 1);
  for (let index = length; index < values.length; index += 1) { current = values[index] * alpha + current * (1 - alpha); out[index] = current; }
  return out;
}

export function bollinger(values: number[], length = 20, deviations = 2) {
  const middle = sma(values, length); const upper = [...middle]; const lower = [...middle];
  for (let index = length - 1; index < values.length; index += 1) {
    const mean = middle[index]!; const variance = values.slice(index - length + 1, index + 1).reduce((sum, value) => sum + (value - mean) ** 2, 0) / length;
    upper[index] = mean + Math.sqrt(variance) * deviations; lower[index] = mean - Math.sqrt(variance) * deviations;
  }
  return { middle, upper, lower };
}

export function rsi(values: number[], length = 14): (number | null)[] {
  const out: (number | null)[] = Array(values.length).fill(null); if (values.length <= length) return out;
  let gain = 0; let loss = 0;
  for (let index = 1; index <= length; index += 1) { const change = values[index] - values[index - 1]; gain += Math.max(change, 0); loss += Math.max(-change, 0); }
  gain /= length; loss /= length; out[length] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let index = length + 1; index < values.length; index += 1) { const change = values[index] - values[index - 1]; gain = (gain * (length - 1) + Math.max(change, 0)) / length; loss = (loss * (length - 1) + Math.max(-change, 0)) / length; out[index] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss); }
  return out;
}

export function macd(values: number[], fast = 12, slow = 26, signalLength = 9) {
  const fastLine = ema(values, fast); const slowLine = ema(values, slow);
  const line = values.map((_, index) => fastLine[index] == null || slowLine[index] == null ? null : fastLine[index]! - slowLine[index]!);
  const valid = line.filter((value): value is number => value != null); const validSignal = ema(valid, signalLength); let cursor = 0;
  const signal = line.map((value) => value == null ? null : validSignal[cursor++]);
  return { line, signal, histogram: line.map((value, index) => value == null || signal[index] == null ? null : value - signal[index]!) };
}

export function heikinAshi(bars: MarketBar[]): MarketBar[] {
  let previousOpen = 0; let previousClose = 0;
  return bars.map((bar, index) => { const close = (bar.open + bar.high + bar.low + bar.close) / 4; const open = index ? (previousOpen + previousClose) / 2 : (bar.open + bar.close) / 2; const transformed = { ...bar, open, close, high: Math.max(bar.high, open, close), low: Math.min(bar.low, open, close) }; previousOpen = open; previousClose = close; return transformed; });
}

export function points(bars: MarketBar[], values: (number | null)[]): Point[] { return bars.flatMap((bar, index) => values[index] == null ? [] : [{ time: bar.timestamp, value: values[index]! }]); }
