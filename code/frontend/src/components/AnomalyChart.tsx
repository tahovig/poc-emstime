import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { ChartData } from "../api/types";
import "./AnomalyChart.css";

interface Props {
  chart: ChartData;
}

const CHART_HEIGHT = 320;

// Canvas-rendered (uPlot), not SVG: the whole point of server-side
// decimation (downsample.py) is to keep the browser fast even though the
// backing dataset can be 10M+ rows -- a canvas renderer keeps that true at
// the render layer too, instead of quietly reintroducing a DOM-per-point
// cost here.
export default function AnomalyChart({ chart }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const xs = chart.timestamps.map((ms) => ms / 1000); // uPlot's time axis expects seconds
    const anomalyYs = chart.values.map((v, i) => (chart.anomaly[i] ? v : null));
    const faultWindowRanges = chart.fault_windows.map(
      (w) => [w.start_ms / 1000, w.end_ms / 1000] as const,
    );

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
      plotRef.current?.destroy();
      plotRef.current = null;
    };
  }, [chart]);

  return (
    <div>
      <div ref={containerRef} className="anomaly-chart" />
      <p className="anomaly-chart__note">
        Showing {chart.timestamps.length.toLocaleString()} of {chart.n_rows_full.toLocaleString()} rows (decimated
        for display) — {chart.n_anomalies_full.toLocaleString()} anomalies detected, {chart.fault_windows.length}{" "}
        fault window(s) shaded.
      </p>
    </div>
  );
}
