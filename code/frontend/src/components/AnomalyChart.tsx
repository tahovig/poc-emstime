import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { ChartData } from "../api/types";
import "./AnomalyChart.css";

interface Props {
  chart: ChartData;
}

const CHART_HEIGHT = 320;

// Validated with the dataviz skill's palette validator (all-pairs, since
// this is a scatter chart): with the existing value-line blue (#1d4ed8) and
// generic-anomaly red (#dc2626) already on the chart, only 3 more hues clear
// colorblind-safety here -- a 4th collides with something every time. So the
// 4th fault type (tq_corruption) reuses dropout's hue as a hollow marker
// (stroke only, no fill) instead of getting its own color -- the skill's own
// prescribed mitigation for a shared-hue pair: secondary encoding (fill
// style) rather than color alone.
const FAULT_TYPE_STYLE: Record<string, { stroke: string; fill: string }> = {
  dropout: { stroke: "#e87ba4", fill: "#e87ba4" },
  timestamp_jitter: { stroke: "#eda100", fill: "#eda100" },
  clock_step: { stroke: "#008300", fill: "#008300" },
  tq_corruption: { stroke: "#e87ba4", fill: "transparent" },
};
const FAULT_TYPES = Object.keys(FAULT_TYPE_STYLE);

// "Other" is every flagged row outside a real fault window -- background
// noise from contamination (~1% of all rows, by construction). Smaller and
// lower-opacity than the fault-type dots so it visually recedes instead of
// competing with them.
const OTHER_STYLE = { stroke: "rgba(220, 38, 38, 0.55)", fill: "rgba(220, 38, 38, 0.55)" };

// Anomaly dot hit radius in CSS px -- generous enough to hover reliably
// without needing pixel-perfect aim at a 6px dot.
const HOVER_HIT_RADIUS = 10;

function formatTimestamp(ms: number): string {
  const d = new Date(ms);
  const pad = (n: number, len = 2) => String(n).padStart(len, "0");
  // Millisecond precision matters here -- these are sub-second PMU-style
  // timestamps, not wall-clock UI timestamps.
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`
  );
}

// Canvas-rendered (uPlot), not SVG: the whole point of server-side
// decimation (downsample.py) is to keep the browser fast even though the
// backing dataset can be 10M+ rows -- a canvas renderer keeps that true at
// the render layer too, instead of quietly reintroducing a DOM-per-point
// cost here.
export default function AnomalyChart({ chart }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    const tooltip = tooltipRef.current;
    if (!container || !tooltip) return;

    const xs = chart.timestamps.map((ms) => ms / 1000); // uPlot's time axis expects seconds
    const faultWindowRanges = chart.fault_windows.map(
      (w) => [w.start_ms / 1000, w.end_ms / 1000] as const,
    );

    // categorize(idx): which fault type (if any) a flagged row belongs to --
    // "other" for a flagged row outside every real fault window, null for a
    // row that isn't flagged at all. Single source of truth shared by both
    // the per-series data split below and the hover tooltip, instead of two
    // independent timestamp-range scans.
    const categorize = (idx: number): string | null => {
      if (!chart.anomaly[idx]) return null;
      const ts = chart.timestamps[idx];
      const window = chart.fault_windows.find((w) => ts >= w.start_ms && ts <= w.end_ms);
      return window ? window.fault_type : "other";
    };
    const categories = chart.timestamps.map((_, i) => categorize(i));

    const faultTypeYs = FAULT_TYPES.map((type) =>
      chart.values.map((v, i) => (categories[i] === type ? v : null)),
    );
    const otherYs = chart.values.map((v, i) => (categories[i] === "other" ? v : null));

    const hideTooltip = () => {
      tooltip.style.display = "none";
    };

    const opts: uPlot.Options = {
      width: container.clientWidth,
      height: CHART_HEIGHT,
      scales: { x: { time: true } },
      series: [
        {},
        { label: "value", stroke: "#1d4ed8", width: 1, points: { show: false } },
        ...FAULT_TYPES.map((type) => {
          const style = FAULT_TYPE_STYLE[type];
          return {
            label: type,
            stroke: style.stroke,
            width: 0,
            points: { show: true, size: 8, stroke: style.stroke, fill: style.fill },
          };
        }),
        {
          label: "other",
          stroke: OTHER_STYLE.stroke,
          width: 0,
          points: { show: true, size: 5, stroke: OTHER_STYLE.stroke, fill: OTHER_STYLE.fill },
        },
      ],
      cursor: {
        points: { show: false }, // we draw our own hover affordance via the tooltip
      },
      hooks: {
        draw: [
          (u) => {
            if (faultWindowRanges.length === 0) return;
            const ctx = u.ctx;
            ctx.save();
            ctx.fillStyle = "rgba(220, 38, 38, 0.08)";
            for (const [start, end] of faultWindowRanges) {
              const x0 = u.valToPos(start, "x", true);
              const x1 = u.valToPos(end, "x", true);
              ctx.fillRect(x0, u.bbox.top, Math.max(x1 - x0, 1), u.bbox.height);
            }
            ctx.restore();
          },
        ],
        setCursor: [
          (u) => {
            const { left, top, idx } = u.cursor;
            if (left == null || top == null || left < 0 || top < 0 || idx == null) {
              hideTooltip();
              return;
            }

            // toCanvasPixels=false: cursor.left/top are CSS-pixel coordinates
            // relative to the plotting area, and valToPos must be asked for
            // the same space (its `true` variant returns device/canvas
            // pixels, which don't match cursor coordinates 1:1 whenever
            // devicePixelRatio != 1).
            //
            // u.cursor.idx is uPlot's nearest-X row across ALL rows,
            // anomalous or not -- when an anomalous row sits close in x to a
            // differently-categorized (or non-anomalous) neighbor, idx can
            // snap to the wrong one, permanently hiding the tooltip for a
            // dot that's clearly visible. Search a small window around idx
            // for the nearest actually-anomalous row within the hit radius
            // instead of trusting idx alone.
            const SEARCH_RADIUS = 8;
            const lo = Math.max(0, idx - SEARCH_RADIUS);
            const hi = Math.min(chart.anomaly.length - 1, idx + SEARCH_RADIUS);
            let bestIdx = -1;
            let bestDistSq = HOVER_HIT_RADIUS * HOVER_HIT_RADIUS;
            for (let i = lo; i <= hi; i++) {
              if (!chart.anomaly[i]) continue;
              const px = u.valToPos(xs[i], "x", false);
              const py = u.valToPos(chart.values[i], "y", false);
              const dx = left - px;
              const dy = top - py;
              const distSq = dx * dx + dy * dy;
              if (distSq <= bestDistSq) {
                bestDistSq = distSq;
                bestIdx = i;
              }
            }

            if (bestIdx < 0) {
              hideTooltip();
              return;
            }

            const pointX = u.valToPos(xs[bestIdx], "x", false);
            const pointY = u.valToPos(chart.values[bestIdx], "y", false);
            const ts = chart.timestamps[bestIdx];
            const category = categories[bestIdx];

            tooltip.replaceChildren();
            const timeEl = document.createElement("div");
            timeEl.className = "anomaly-tooltip__time";
            timeEl.textContent = formatTimestamp(ts);
            tooltip.appendChild(timeEl);

            const valueEl = document.createElement("div");
            valueEl.textContent = `value: ${chart.values[bestIdx].toFixed(3)}`;
            tooltip.appendChild(valueEl);

            if (category && category !== "other") {
              const faultEl = document.createElement("div");
              faultEl.className = "anomaly-tooltip__fault";
              faultEl.textContent = `fault: ${category}`;
              tooltip.appendChild(faultEl);
            }

            tooltip.style.display = "block";

            const overRect = u.over.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            const offsetX = overRect.left - containerRect.left;
            const offsetY = overRect.top - containerRect.top;

            const tooltipWidth = tooltip.offsetWidth;
            const tooltipHeight = tooltip.offsetHeight;

            let tooltipLeft = offsetX + pointX + 10;
            if (tooltipLeft + tooltipWidth > container.clientWidth) {
              tooltipLeft = offsetX + pointX - tooltipWidth - 10;
            }

            let tooltipTop = offsetY + pointY - tooltipHeight - 12;
            if (tooltipTop < 0) {
              tooltipTop = offsetY + pointY + 12;
            }

            tooltip.style.left = `${tooltipLeft}px`;
            tooltip.style.top = `${tooltipTop}px`;
          },
        ],
      },
    };

    const data: uPlot.AlignedData = [xs, chart.values, ...faultTypeYs, otherYs];
    plotRef.current = new uPlot(opts, data, container);

    const handleResize = () => {
      plotRef.current?.setSize({ width: container.clientWidth, height: CHART_HEIGHT });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      hideTooltip();
      plotRef.current?.destroy();
      plotRef.current = null;
    };
  }, [chart]);

  return (
    <div>
      <div ref={containerRef} className="anomaly-chart">
        <div ref={tooltipRef} className="anomaly-tooltip" />
      </div>
      <p className="anomaly-chart__note">
        Showing {chart.timestamps.length.toLocaleString()} of {chart.n_rows_full.toLocaleString()} rows (decimated
        for display) — {chart.n_anomalies_full.toLocaleString()} anomalies detected, {chart.fault_windows.length}{" "}
        fault window(s) shaded.
      </p>
    </div>
  );
}
