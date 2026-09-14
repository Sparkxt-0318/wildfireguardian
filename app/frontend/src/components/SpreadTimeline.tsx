// Spread-ETA bar — hand-rolled SVG per the dataviz method.
// Form: one ratio against a limit → a METER, not a bar chart. The filled
// span (0 → ETA) is "time you have" in the current danger-status hue; the
// unfilled track is a pale tint of the SAME hue (meter rule). Status color
// never stands alone: the card pairs it with the clock icon and the value
// in words. The scale is 0–3 h — the GO-decision horizon of the triage
// engine (spec §6) — with the marker clamped at the right edge and the true
// server value always printed. Shows ONLY when the API sent `eta_minutes`.

import type { Situation } from "../api/client";
import { useI18n } from "../i18n";
import { formatMinutes } from "../lib/format";
import { IconClock } from "./Icons";

const W = 340;
const H = 96;
const PAD_L = 12;
const PAD_R = 12;
const BAR_Y = 40;
const BAR_H = 22;
const SCALE_MAX_MIN = 180; // triage GO horizon (spec §6), axis limit only

const LEVEL_COLOR: Record<string, { fill: string; tint: string }> = {
  SAFE: { fill: "var(--safe)", tint: "var(--safe-tint)" },
  WATCH: { fill: "var(--watch)", tint: "var(--watch-tint)" },
  GO: { fill: "var(--go)", tint: "var(--go-tint)" },
};

export function SpreadTimeline({ situation }: { situation: Situation }) {
  const { t, lang } = useI18n();
  const eta = situation.eta_minutes;
  // Not on a predicted pathway — nothing to show. A non-positive ETA is the
  // same case wearing a number: "the fire arrives in 0 minutes" is never
  // information a resident can act on, and beside a CAUTION status it reads as
  // a contradiction. The gateway sends null for this now (spread.py), and this
  // screen refuses to print a countdown of zero even if one ever arrives.
  if (eta === null || eta <= 0) return null;

  const colors = LEVEL_COLOR[situation.danger.level] ?? LEVEL_COLOR.GO;
  const clamped = Math.max(0, Math.min(eta, SCALE_MAX_MIN));
  const trackW = W - PAD_L - PAD_R;
  const fillW = (trackW * clamped) / SCALE_MAX_MIN;

  const hourTicks = [0, 60, 120, 180];
  const tickLabel = (m: number) => {
    if (m === 0) return "0";
    const h = m / 60;
    const overflow = m === SCALE_MAX_MIN && eta > SCALE_MAX_MIN ? "+" : "";
    return lang === "ko" ? `${h}시간${overflow}` : `${h} h${overflow}`;
  };

  return (
    <section className="viz-card" aria-label={t("eta_bar_title")}>
      <div className="row" style={{ gap: 10 }}>
        <span style={{ color: colors.fill, display: "inline-flex" }}>
          <IconClock size={32} />
        </span>
        <h3 className="viz-title" style={{ margin: 0 }}>
          {t("eta_bar_title")}
        </h3>
      </div>
      <div className="viz-value" style={{ margin: "6px 0 2px" }}>
        {formatMinutes(eta, lang)}
      </div>
      <p className="viz-sub">{t("eta_bar_sub")}</p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", display: "block" }}
        role="img"
        aria-label={`${t("eta_bar_title")}: ${formatMinutes(eta, lang)}`}
      >
        {/* pale same-hue track */}
        <rect
          x={PAD_L}
          y={BAR_Y}
          width={trackW}
          height={BAR_H}
          rx="4"
          fill={colors.tint}
        />
        {/* filled span 0 → ETA: rounded data-end, square baseline (left) */}
        {fillW > 0 && (
          <path
            d={`M${PAD_L} ${BAR_Y} H${PAD_L + Math.max(fillW - 4, 0)} q4 0 4 4 v${BAR_H - 8} q0 4 -4 4 H${PAD_L} Z`}
            fill={colors.fill}
          />
        )}
        {/* ETA marker with 2px surface ring */}
        <line
          x1={PAD_L + fillW}
          x2={PAD_L + fillW}
          y1={BAR_Y - 8}
          y2={BAR_Y + BAR_H + 8}
          stroke="var(--surface)"
          strokeWidth="6"
        />
        <line
          x1={PAD_L + fillW}
          x2={PAD_L + fillW}
          y1={BAR_Y - 8}
          y2={BAR_Y + BAR_H + 8}
          stroke="var(--ink)"
          strokeWidth="2.5"
        />
        {/* hour ticks — recessive axis text */}
        {hourTicks.map((m) => {
          const tx = PAD_L + (trackW * m) / SCALE_MAX_MIN;
          return (
            <g key={m}>
              <line
                x1={tx}
                x2={tx}
                y1={BAR_Y + BAR_H + 2}
                y2={BAR_Y + BAR_H + 8}
                stroke="var(--viz-axis)"
                strokeWidth="1"
              />
              <text
                x={tx}
                y={BAR_Y + BAR_H + 24}
                textAnchor={m === 0 ? "start" : m === 180 ? "end" : "middle"}
                className="viz-axis-text"
              >
                {tickLabel(m)}
              </text>
            </g>
          );
        })}
      </svg>
    </section>
  );
}
