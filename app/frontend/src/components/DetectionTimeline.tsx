// Detection-count timeline — hand-rolled SVG line chart per the dataviz method.
// Form: trend over time, single series → 2px line + ~10% area wash in the one
// series hue. No legend box (single series — the title names it). Gridlines
// are solid hairlines. Labels selective: the endpoint (and the peak when it
// isn't the endpoint) — never a number on every point. Values are exactly the
// API's history points; a visually-hidden table is the WCAG table-view twin.

import type { HistoryPoint } from "../api/client";
import { useI18n } from "../i18n";
import { formatClock } from "../lib/format";

const W = 340;
const H = 170;
const PAD_L = 44; // room for y ticks
const PAD_R = 34; // room for endpoint label
const PAD_T = 14;
const PAD_B = 30; // x-axis band INSIDE the container (anti-pattern guard)

function niceMax(maxValue: number): number {
  if (maxValue <= 5) return 5;
  const pow = 10 ** Math.floor(Math.log10(maxValue));
  for (const m of [1, 2, 5, 10]) {
    if (maxValue <= m * pow) return m * pow;
  }
  return 10 * pow;
}

export function DetectionTimeline({ history }: { history: HistoryPoint[] }) {
  const { t, lang } = useI18n();
  if (history.length < 2) return null;

  const yMax = niceMax(Math.max(...history.map((p) => p.detections)));
  const x = (i: number) =>
    PAD_L + ((W - PAD_L - PAD_R) * i) / (history.length - 1);
  const y = (v: number) => PAD_T + (H - PAD_T - PAD_B) * (1 - v / yMax);

  const linePath = history
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(p.detections).toFixed(1)}`)
    .join(" ");
  const areaPath =
    `${linePath} L${x(history.length - 1).toFixed(1)} ${(H - PAD_B).toFixed(1)}` +
    ` L${x(0).toFixed(1)} ${(H - PAD_B).toFixed(1)} Z`;

  const last = history[history.length - 1];
  const peakIdx = history.reduce(
    (best, p, i) => (p.detections > history[best].detections ? i : best),
    0,
  );
  const showPeak =
    peakIdx !== history.length - 1 &&
    history[peakIdx].detections !== last.detections;

  const gridValues = [yMax / 2, yMax];

  return (
    <section className="viz-card" aria-label={t("timeline_title")}>
      <h3 className="viz-title">{t("timeline_title")}</h3>
      <p className="viz-sub">{t("timeline_sub")}</p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", display: "block" }}
        role="img"
        aria-label={`${t("timeline_title")}: ${last.detections}`}
      >
        {/* solid hairline grid, one shade off the surface */}
        {gridValues.map((v) => (
          <g key={v}>
            <line
              x1={PAD_L}
              x2={W - PAD_R}
              y1={y(v)}
              y2={y(v)}
              stroke="var(--viz-grid)"
              strokeWidth="1"
            />
            <text
              x={PAD_L - 6}
              y={y(v)}
              textAnchor="end"
              dominantBaseline="central"
              className="viz-axis-text"
            >
              {v}
            </text>
          </g>
        ))}
        {/* baseline */}
        <line
          x1={PAD_L}
          x2={W - PAD_R}
          y1={H - PAD_B}
          y2={H - PAD_B}
          stroke="var(--viz-axis)"
          strokeWidth="1"
        />
        <text
          x={PAD_L - 6}
          y={H - PAD_B}
          textAnchor="end"
          dominantBaseline="central"
          className="viz-axis-text"
        >
          0
        </text>
        {/* area wash ~10% + 2px line */}
        <path d={areaPath} fill="var(--viz-series)" opacity="0.1" />
        <path
          d={linePath}
          fill="none"
          stroke="var(--viz-series)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* peak label (selective, only when it isn't the endpoint) */}
        {showPeak && (
          <g>
            <circle
              cx={x(peakIdx)}
              cy={y(history[peakIdx].detections)}
              r="4.5"
              fill="var(--viz-series)"
              stroke="var(--surface)"
              strokeWidth="2"
            />
            <text
              x={x(peakIdx)}
              y={y(history[peakIdx].detections) - 9}
              textAnchor="middle"
              className="viz-label-text"
            >
              {history[peakIdx].detections}
            </text>
          </g>
        )}
        {/* endpoint dot (≥8px with 2px surface ring) + endpoint label */}
        <circle
          cx={x(history.length - 1)}
          cy={y(last.detections)}
          r="5"
          fill="var(--viz-series)"
          stroke="var(--surface)"
          strokeWidth="2"
        />
        <text
          x={Math.min(x(history.length - 1) + 8, W - 2)}
          y={y(last.detections)}
          textAnchor="start"
          dominantBaseline="central"
          className="viz-label-text"
        >
          {last.detections}
        </text>
        {/* x-axis band: first + last time, local clock */}
        <text
          x={PAD_L}
          y={H - 8}
          textAnchor="start"
          className="viz-axis-text"
        >
          {formatClock(history[0].t_utc, lang)}
        </text>
        <text
          x={W - PAD_R}
          y={H - 8}
          textAnchor="end"
          className="viz-axis-text"
        >
          {formatClock(last.t_utc, lang)}
        </text>
      </svg>
      {/* table-view twin (screen readers / WCAG) */}
      <table className="sr-only">
        <caption>{t("timeline_title")}</caption>
        <thead>
          <tr>
            <th>{t("updated_label")}</th>
            <th>{t("fire_detections")}</th>
          </tr>
        </thead>
        <tbody>
          {history.map((p) => (
            <tr key={p.t_utc}>
              <td>{formatClock(p.t_utc, lang)}</td>
              <td>{p.detections}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
