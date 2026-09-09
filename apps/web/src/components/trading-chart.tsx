"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  ColorType,
  CrosshairMode,
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

export type ChartSeries = {
  key: string;
  label: string;
  color: string;
  data: { time: string; value: number | null }[];
  area?: boolean;
  dashed?: boolean;
  visible?: boolean;
};

function epoch(value: string): UTCTimestamp {
  return Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
}

export default function TradingChart({
  series,
  endTime,
  ariaLabel,
  height = 310,
  theme = "light",
}: {
  series: ChartSeries[];
  endTime?: string;
  ariaLabel: string;
  height?: number;
  theme?: "light" | "dark";
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Map<string, ISeriesApi<"Line" | "Area">>>(new Map());

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = createChart(container, {
      autoSize: true,
      height,
      layout: {
        background: { type: ColorType.Solid, color: theme === "dark" ? "#0d1116" : "#ffffff" },
        textColor: theme === "dark" ? "#74808c" : "#7b879b",
        fontFamily: "Geist, Inter, system-ui, sans-serif",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: theme === "dark" ? "#171d24" : "#f3f5f8" },
        horzLines: { color: theme === "dark" ? "#202730" : "#edf0f5", style: LineStyle.Dashed },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: theme === "dark" ? "#242a32" : "#e4e8ef", scaleMargins: { top: 0.12, bottom: 0.12 } },
      timeScale: {
        borderColor: theme === "dark" ? "#242a32" : "#e4e8ef",
        timeVisible: true,
        secondsVisible: true,
        rightOffsetPixels: 8,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });
    chartRef.current = chart;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current.clear();
    };
  }, [height, theme]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const activeKeys = new Set(series.map((item) => item.key));
    for (const [key, api] of seriesRef.current) {
      if (!activeKeys.has(key)) {
        chart.removeSeries(api);
        seriesRef.current.delete(key);
      }
    }
    for (const item of series) {
      let api = seriesRef.current.get(item.key);
      if (!api) {
        api = item.area
          ? chart.addSeries(AreaSeries, {
              lineColor: item.color,
              topColor: `${item.color}24`,
              bottomColor: `${item.color}03`,
              lineWidth: 3,
              title: item.label,
              priceLineVisible: false,
            })
          : chart.addSeries(LineSeries, {
              color: item.color,
              lineWidth: item.key.includes("bound") ? 1 : 2,
              lineStyle: item.dashed ? LineStyle.Dashed : LineStyle.Solid,
              title: item.label,
              priceLineVisible: false,
            });
        seriesRef.current.set(item.key, api);
      }
      api.applyOptions({ visible: item.visible !== false });
      const data: ({ time: Time; value: number } | { time: Time })[] = item.data.map((point) =>
        point.value == null ? { time: epoch(point.time) } : { time: epoch(point.time), value: point.value }
      );
      if (endTime && (!data.length || data[data.length - 1].time !== epoch(endTime))) {
        data.push({ time: epoch(endTime) });
      }
      api.setData(data);
    }
    chart.timeScale().fitContent();
  }, [series, endTime]);

  return <div className="trading-chart" role="img" aria-label={ariaLabel} ref={containerRef}/>;
}
