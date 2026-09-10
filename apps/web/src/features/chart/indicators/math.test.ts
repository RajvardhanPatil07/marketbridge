import { describe, expect, it } from "vitest";
import { bollinger, ema, macd, rsi, sma } from "./math";

describe("deterministic indicator mathematics", () => {
  it("calculates simple and exponential moving averages", () => {
    expect(sma([1, 2, 3, 4, 5], 3)).toEqual([null, null, 2, 3, 4]);
    expect(ema([1, 2, 3, 4, 5], 3)).toEqual([null, null, 2, 3, 4]);
  });

  it("calculates population Bollinger bands", () => {
    const result = bollinger([1, 2, 3], 3, 2);
    expect(result.middle[2]).toBe(2);
    expect(result.upper[2]).toBeCloseTo(3.632993, 5);
    expect(result.lower[2]).toBeCloseTo(0.367006, 5);
  });

  it("keeps RSI bounded and MACD aligned with its input", () => {
    const values = Array.from({ length: 60 }, (_, index) => 100 + index * 0.5 + Math.sin(index));
    const relativeStrength = rsi(values, 14).filter((value): value is number => value != null);
    expect(relativeStrength.every((value) => value >= 0 && value <= 100)).toBe(true);
    const result = macd(values);
    expect(result.line).toHaveLength(values.length);
    expect(result.signal).toHaveLength(values.length);
    expect(result.histogram).toHaveLength(values.length);
  });
});
