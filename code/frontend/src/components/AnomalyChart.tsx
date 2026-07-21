import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { ChartData } from "../api/types";
import "./AnomalyChart.css";

interface Props {
  chart: ChartData;
}

const CHART_HEIGHT = 320;

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
    const anomalyYs = chart.values.map((v, i) => (chart.anomaly[i] ? v : null));
    const faultWindowRanges = chart.fault_windows.map(
      (w) => [w.start_ms / 1000, w.end_ms / 1000] as const,
    );

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
        {
          label: "anomaly",
          stroke: "#dc2626",
          width: 0,
          points: { show: true, size: 6, stroke: "#dc2626", fill: "#dc2626" },
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
            if (left == null || top == null || left < 0 || top < 0 || idx == null || !chart.anomaly[idx]) {
              hideTooltip();
              return;
            }

            // toCanvasPixels=false: cursor.left/top are CSS-pixel coordinates
            // relative to the plotting area, and valToPos must be asked for
            // the same space (its `true` variant returns device/canvas
            // pixels, which don't match cursor coordinates 1:1 whenever
            // devicePixelRatio != 1).
            const pointX = u.valToPos(xs[idx], "x", false);
            const pointY = u.valToPos(chart.values[idx], "y", false);
            const dx = left - pointX;
            const dy = top - pointY;
            if (dx * dx + dy * dy > HOVER_HIT_RADIUS * HOVER_HIT_RADIUS) {
              hideTooltip();
              return;
            }

            const ts = chart.timestamps[idx];
            const faultWindow = chart.fault_windows.find((w) => ts >= w.start_ms && ts <= w.end_ms);

            tooltip.replaceChildren();
            const timeEl = document.createElement("div");
            timeEl.className = "anomaly-tooltip__time";
            timeEl.textContent = formatTimestamp(ts);
            tooltip.appendChild(timeEl);

            const valueEl = document.createElement("div");
            valueEl.textContent = `value: ${chart.values[idx].toFixed(3)}`;
            tooltip.appendChild(valueEl);

            if (faultWindow) {
              const faultEl = document.createElement("div");
              faultEl.className = "anomaly-tooltip__fault";
              faultEl.textContent = `fault: ${faultWindow.fault_type}`;
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

    const data: uPlot.AlignedData = [xs, chart.values, anomalyYs];
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
