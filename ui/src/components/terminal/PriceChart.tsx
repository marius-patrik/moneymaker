import { useEffect, useRef, useState } from "react";
import {
  createChart, CandlestickSeries, HistogramSeries, LineSeries,
  CrosshairMode, type IChartApi, type ISeriesApi, type Time,
} from "lightweight-charts";
import { useTheme } from "@/lib/useTheme";
import { fmt } from "@/lib/utils";
import type { Candle, IndicatorSeries } from "@/lib/api";

export type ChartKind = "candles" | "line";
export type DrawTool = "none" | "hline" | "trend";

export interface Drawing {
  id: string;
  kind: "hline" | "trend";
  /** hline uses one point; trend uses two. */
  points: { time: number; price: number }[];
  color: string;
}

/** Resolve a CSS custom property to a concrete colour the canvas can use. */
function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `hsl(${v})` : fallback;
}

interface Hover {
  open: number; high: number; low: number; close: number;
  volume: number; time: number;
}

/**
 * TradingView's own charting library.
 *
 * Recharts draws a picture of the data; this is an instrument you can
 * interrogate — crosshair with an OHLC readout, scroll to zoom, drag to pan,
 * and a price scale you can stretch. Candles carry each period's range and
 * direction, which a line drops.
 */
/** Distinct, theme-neutral colours so overlays stay apart from the candles. */
const OVERLAY_COLORS = ["#f59e0b", "#38bdf8", "#a78bfa", "#f472b6"];

export function PriceChart({
  candles, kind = "candles", height = 380, onHover, overlays = [],
  drawings = [], tool = "none", onDraw, onDrawingsChange,
}: {
  candles: Candle[];
  kind?: ChartKind;
  height?: number;
  onHover?: (h: Hover | null) => void;
  /** Indicator series drawn over the price pane. */
  overlays?: IndicatorSeries[];
  /** User-drawn levels and trendlines. */
  drawings?: Drawing[];
  tool?: DrawTool;
  onDraw?: (d: Drawing) => void;
  onDrawingsChange?: (d: Drawing[]) => void;
}) {
  const overlayRefs = useRef<ISeriesApi<"Line">[]>([]);
  const drawRefs = useRef<ISeriesApi<"Line">[]>([]);
  const pendingRef = useRef<{ time: number; price: number } | null>(null);
  const holder = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const priceRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const { theme } = useTheme();

  // Rebuild on theme or series-type change: colours are baked into the
  // chart at construction, and the series type cannot be swapped in place.
  useEffect(() => {
    if (!holder.current) return;

    const text = cssVar("--muted-foreground", "#888");
    const grid = cssVar("--border", "#222");
    const up = cssVar("--profit", "#26a69a");
    const down = cssVar("--loss", "#ef5350");

    const chart = createChart(holder.current, {
      height,
      layout: {
        background: { color: "transparent" },
        textColor: text,
        fontFamily: '"JetBrains Mono Variable", monospace',
        fontSize: 10,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: grid, style: 1 },
        horzLines: { color: grid, style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: text, width: 1, style: 3, labelBackgroundColor: grid },
        horzLine: { color: text, width: 1, style: 3, labelBackgroundColor: grid },
      },
      rightPriceScale: { borderColor: grid, scaleMargins: { top: 0.08, bottom: 0.26 } },
      timeScale: { borderColor: grid, timeVisible: true, secondsVisible: false },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });

    const price = kind === "candles"
      ? chart.addSeries(CandlestickSeries, {
          upColor: up, downColor: down, borderVisible: false,
          wickUpColor: up, wickDownColor: down,
        })
      : chart.addSeries(LineSeries, { color: up, lineWidth: 2 });

    // Volume shares the pane, pinned to the lower quarter.
    const vol = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    chartRef.current = chart;
    priceRef.current = price;
    volRef.current = vol;

    const ro = new ResizeObserver(() => {
      if (holder.current) chart.applyOptions({ width: holder.current.clientWidth });
    });
    ro.observe(holder.current);

    return () => {
      ro.disconnect(); chart.remove();
      chartRef.current = null; overlayRefs.current = [];
    };
  }, [kind, height, theme]);

  // Overlays are rebuilt wholesale: the set changes rarely and reconciling
  // series identity is more machinery than the saving is worth.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    for (const s of overlayRefs.current) {
      try { chart.removeSeries(s); } catch { /* chart already torn down */ }
    }
    overlayRefs.current = [];

    overlays.filter((o) => o.pane === "price").forEach((o, i) => {
      const series = chart.addSeries(LineSeries, {
        color: OVERLAY_COLORS[i % OVERLAY_COLORS.length],
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      series.setData(o.points.map((p) => ({ time: p.time as Time, value: p.value })));
      overlayRefs.current.push(series);
    });
  }, [overlays, candles, kind, theme]);

  // Feed data.
  useEffect(() => {
    const price = priceRef.current, vol = volRef.current, chart = chartRef.current;
    if (!price || !vol || !chart || candles.length === 0) return;

    const up = cssVar("--profit", "#26a69a");
    const down = cssVar("--loss", "#ef5350");

    if (kind === "candles") {
      (price as ISeriesApi<"Candlestick">).setData(candles.map((c) => ({
        time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close,
      })));
    } else {
      (price as ISeriesApi<"Line">).setData(candles.map((c) => ({
        time: c.time as Time, value: c.close,
      })));
    }

    const hasVolume = candles.some((c) => c.volume > 0);
    vol.applyOptions({ visible: hasVolume });
    if (hasVolume) {
      vol.setData(candles.map((c) => ({
        time: c.time as Time,
        value: c.volume,
        color: c.close >= c.open ? `${up}33` : `${down}33`,
      })));
    }

    chart.timeScale().fitContent();
  }, [candles, kind]);

  // Drawings. Rebuilt wholesale like overlays — the set is small and edited
  // by hand, so reconciling identity would cost more than it saves.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    for (const s of drawRefs.current) {
      try { chart.removeSeries(s); } catch { /* chart gone */ }
    }
    drawRefs.current = [];
    if (candles.length === 0) return;

    const first = candles[0].time, last = candles[candles.length - 1].time;
    for (const d of drawings) {
      const series = chart.addSeries(LineSeries, {
        color: d.color, lineWidth: 1, lineStyle: d.kind === "hline" ? 2 : 0,
        priceLineVisible: false, lastValueVisible: d.kind === "hline",
        crosshairMarkerVisible: false,
      });
      // A horizontal level spans the whole visible range; a trendline runs
      // between the two points that defined it.
      const pts = d.kind === "hline"
        // A level has no time of its own — it spans whatever is visible.
        ? [{ time: first as Time, value: d.points[0].price },
           { time: last as Time, value: d.points[0].price }]
        : d.points
            .slice()
            .sort((a, b) => a.time - b.time)
            .map((p) => ({ time: p.time as Time, value: p.price }));
      series.setData(pts);
      drawRefs.current.push(series);
    }
  }, [drawings, candles, kind, theme]);

  // Placing a drawing: one click for a level, two for a trendline.
  useEffect(() => {
    const chart = chartRef.current, price = priceRef.current;
    if (!chart || !price || tool === "none" || !onDraw) {
      pendingRef.current = null;
      return;
    }

    const handler = (param: Parameters<Parameters<IChartApi["subscribeClick"]>[0]>[0]) => {
      if (!param.time || !param.point) return;
      const value = price.coordinateToPrice(param.point.y);
      if (value == null) return;
      const point = { time: Number(param.time), price: Number(value) };

      if (tool === "hline") {
        onDraw({ id: `d${Date.now()}`, kind: "hline", points: [point], color: "#eab308" });
        return;
      }
      if (!pendingRef.current) {
        pendingRef.current = point;   // first click anchors the line
        return;
      }
      onDraw({
        id: `d${Date.now()}`, kind: "trend",
        points: [pendingRef.current, point], color: "#38bdf8",
      });
      pendingRef.current = null;
    };

    chart.subscribeClick(handler);
    return () => chart.unsubscribeClick(handler);
  }, [tool, onDraw, candles]);

  // Crosshair readout, so the numbers under the cursor are legible.
  useEffect(() => {
    const chart = chartRef.current, price = priceRef.current;
    if (!chart || !price || !onHover) return;

    const handler = (param: Parameters<Parameters<IChartApi["subscribeCrosshairMove"]>[0]>[0]) => {
      if (!param.time || !param.point) { onHover(null); return; }
      const bar = candles.find((c) => c.time === param.time);
      onHover(bar ? { ...bar, time: bar.time } : null);
    };
    chart.subscribeCrosshairMove(handler);
    return () => chart.unsubscribeCrosshairMove(handler);
  }, [candles, onHover]);

  return <div ref={holder} className="w-full" style={{ height }} />;
}

/** OHLC strip that follows the crosshair. */
export function OhlcReadout({ hover, fallback }: { hover: Hover | null; fallback?: Candle }) {
  const b = hover ?? fallback;
  if (!b) return null;
  const up = b.close >= b.open;
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[11px] tabular-nums">
      {([["O", b.open], ["H", b.high], ["L", b.low], ["C", b.close]] as const).map(([k, v]) => (
        <span key={k} className="text-muted-foreground">
          {k} <span className={up ? "text-profit" : "text-loss"}>{fmt(v)}</span>
        </span>
      ))}
      {b.volume > 0 && (
        <span className="text-muted-foreground">
          V <span className="text-foreground">{Math.round(b.volume).toLocaleString()}</span>
        </span>
      )}
    </div>
  );
}
