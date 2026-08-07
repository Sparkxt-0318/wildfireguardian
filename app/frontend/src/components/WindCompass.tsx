// Wind compass — hand-rolled SVG per the dataviz method.
// Form: a single current value + direction → stat-tile treatment with a
// directional dial, NOT a chart with axes. Identity is carried by the one
// series hue (--viz-series blue); all text wears ink tokens, never the hue.
// The dial ring/ticks are recessive hairlines. The value uses proportional
// figures (no tabular-nums on a display-size number).

import type { WeatherStatus } from "../api/client";
import { useI18n } from "../i18n";
import { WindArrows } from "../svg/WindArrows";

/**
 * `wind_dir_deg` follows the meteorological convention (direction the wind
 * comes FROM, degrees clockwise from north). The arrow shows where the wind
 * is BLOWING TOWARD (dir + 180°) — that is the question a resident actually
 * has ("is it blowing at us?") — and is labelled as such. The speed shown is
 * exactly the API's `wind_speed_ms`.
 */
export function WindCompass({ weather }: { weather: WeatherStatus }) {
  const { t } = useI18n();
  const towardDeg = (weather.wind_dir_deg + 180) % 360;

  const C = 100; // center
  const R = 78; // dial radius
  const rad = ((towardDeg - 90) * Math.PI) / 180;
  const tipX = C + Math.cos(rad) * (R - 16);
  const tipY = C + Math.sin(rad) * (R - 16);
  const tailX = C - Math.cos(rad) * (R - 42);
  const tailY = C - Math.sin(rad) * (R - 42);

  // cardinal tick positions
  const ticks = [0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
    const a = ((deg - 90) * Math.PI) / 180;
    return {
      major: deg % 90 === 0,
      x1: C + Math.cos(a) * (R - 8),
      y1: C + Math.sin(a) * (R - 8),
      x2: C + Math.cos(a) * R,
      y2: C + Math.sin(a) * R,
    };
  });

  const labels = [
    { text: t("dir_n"), x: C, y: C - R + 26 },
    { text: t("dir_e"), x: C + R - 26, y: C },
    { text: t("dir_s"), x: C, y: C + R - 26 },
    { text: t("dir_w"), x: C - R + 26, y: C },
  ];

  return (
    <section className="viz-card" aria-label={t("wind_compass_title")}>
      <h3 className="viz-title">{t("wind_compass_title")}</h3>
      <p className="viz-sub">{t("wind_toward_label")}</p>
      <div className="row" style={{ gap: 16, alignItems: "center" }}>
        <svg
          width="150"
          height="150"
          viewBox="0 0 200 200"
          role="img"
          aria-label={`${t("wx_wind")} ${weather.wind_speed_ms} ${t("unit_ms")}`}
        >
          {/* recessive dial: hairline ring + ticks */}
          <circle
            cx={C}
            cy={C}
            r={R}
            fill="var(--surface)"
            stroke="var(--viz-grid)"
            strokeWidth="1"
          />
          {ticks.map((tk, i) => (
            <line
              key={i}
              x1={tk.x1}
              y1={tk.y1}
              x2={tk.x2}
              y2={tk.y2}
              stroke={tk.major ? "var(--viz-axis)" : "var(--viz-grid)"}
              strokeWidth={tk.major ? 2 : 1}
            />
          ))}
          {labels.map((l) => (
            <text
              key={l.text}
              x={l.x}
              y={l.y}
              textAnchor="middle"
              dominantBaseline="central"
              className="viz-label-text"
              fill="var(--ink-secondary)"
            >
              {l.text}
            </text>
          ))}
          {/* the wind arrow — series hue, thick, with surface-ringed hub */}
          <line
            x1={tailX}
            y1={tailY}
            x2={tipX}
            y2={tipY}
            stroke="var(--viz-series)"
            strokeWidth="6"
            strokeLinecap="round"
          />
          <g
            transform={`rotate(${towardDeg} ${C} ${C}) translate(${C} ${C - R + 16})`}
          >
            <path
              d="M0 -14 L11 8 L0 3 L-11 8 Z"
              fill="var(--viz-series)"
              stroke="var(--surface)"
              strokeWidth="2"
            />
          </g>
          <circle
            cx={C}
            cy={C}
            r="7"
            fill="var(--viz-series)"
            stroke="var(--surface)"
            strokeWidth="2"
          />
        </svg>
        <div>
          <div className="viz-value">
            {weather.wind_speed_ms}
            <span className="viz-unit"> {t("unit_ms")}</span>
          </div>
          <p
            style={{
              margin: "8px 0 0",
              fontSize: "var(--fs-small)",
              color: "var(--ink-secondary)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <WindArrows size={40} rotateDeg={towardDeg} />
            {weather.wind_toward_user
              ? t("wx_wind_toward")
              : t("wx_wind_not_toward")}
          </p>
        </div>
      </div>
    </section>
  );
}
