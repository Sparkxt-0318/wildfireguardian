/**
 * The one method diagram of the About panel: a vertical flow of seven steps from the recorded
 * forecast to the departure deadline. Plain inline SVG, geometric glyphs, ink + one accent.
 */
import { useId } from 'react';
import type { Verdict } from '../../domain/types';
import { pick, VERDICT_LABEL, type Lang } from '../shared/strings';
import { COLORS } from '../shared/VerdictIcon';
import { METHOD_STEPS } from './strings';

const W = 600;
const ROW = 64;
const GAP = 16;
const CARD_X = 56;
const RAIL_X = 22;
const GLYPH_X = CARD_X + 18;
const TEXT_X = CARD_X + 64;

function Glyph({ i, x, y, hatchId }: { i: number; x: number; y: number; hatchId: string }) {
  const t = `translate(${x} ${y})`;
  const ink = COLORS.ink;
  switch (i) {
    case 0: {
      const ops = [0.06, 0.14, 0.32, 0.14, 0.32, 0.58, 0.32, 0.58, 0.86];
      return (
        <g transform={t}>
          {ops.map((o, k) => (
            <rect key={k} x={(k % 3) * 9.5} y={Math.floor(k / 3) * 9.5} width="8" height="8" rx="1.2" fill={ink} opacity={o} />
          ))}
        </g>
      );
    }
    case 1:
      return (
        <g transform={t} fill="#fff" stroke={ink} strokeWidth="1.4" strokeLinejoin="round">
          {[0, 1, 2, 3].map((k) => (
            <path key={k} d={`M1 ${8 + k * 4.5}L14 ${2 + k * 4.5}L27 ${8 + k * 4.5}L14 ${14 + k * 4.5}Z`} />
          ))}
        </g>
      );
    case 2:
      return (
        <g transform={t} stroke={ink} strokeLinecap="round">
          <path d="M3 24L9 14M9 14L19 18M19 18L25 5M9 14L12 4M19 18L26 25" strokeWidth="1.2" opacity="0.35" />
          <path d="M3 24L9 14L19 18L25 5" strokeWidth="2" fill="none" />
          {[
            [3, 24],
            [9, 14],
            [19, 18],
            [25, 5],
            [12, 4],
            [26, 25],
          ].map(([cx, cy], k) => (
            <circle key={k} cx={cx} cy={cy} r={k < 4 ? 2.6 : 2} fill={k < 4 ? ink : '#fff'} strokeWidth="1.2" />
          ))}
        </g>
      );
    case 3:
      return (
        <g transform={t} stroke={ink} strokeLinecap="round" fill="none">
          <path d="M2 9V5H26V9" strokeWidth="1.2" opacity="0.6" />
          <path d="M2 19H21" strokeWidth="2" />
          <circle cx="2.5" cy="19" r="2.4" fill={ink} stroke="none" />
          <circle cx="11" cy="19" r="2" fill="#fff" strokeWidth="1.4" />
          <rect x="21" y="15" width="7" height="8" rx="1.2" fill="#fff" strokeWidth="1.4" />
        </g>
      );
    case 4:
      return (
        <g transform={t} stroke={ink} strokeLinecap="round" fill="none" strokeWidth="1.5">
          <path d="M2 14H10M10 14L22 4M10 14H22M10 14L22 24" />
          <circle cx="24.5" cy="4" r="2.5" fill={COLORS.accent} stroke="none" />
          <circle cx="24.5" cy="14" r="2.5" fill="#fff" />
          <circle cx="24.5" cy="24" r="2.5" fill={`url(#${hatchId})`} stroke={COLORS.unresolved} />
        </g>
      );
    case 5:
      return (
        <g transform={t} stroke={ink} strokeLinecap="round">
          <path d="M1 22H27" strokeWidth="1.4" />
          {[2, 7, 12, 17, 22].map((cx, k) => (
            <rect key={k} x={cx - 1.6} y={8} width="3.2" height="10" rx="1" fill={ink} stroke="none" opacity={0.25 + k * 0.15} />
          ))}
          <path d="M22 4L26 7L22 10" strokeWidth="1.4" fill="none" />
          <path d="M2 7H25" strokeWidth="1" opacity="0.4" />
        </g>
      );
    default:
      return (
        <g transform={t} fill="none" strokeLinecap="round">
          <circle cx="14" cy="14" r="11" stroke={COLORS.accentHover} strokeWidth="1.8" fill="#fff" />
          <path d="M14 7.5V14L18.5 17" stroke={COLORS.accentHover} strokeWidth="2" />
        </g>
      );
  }
}

/** Approximate rendered width (px) of a label, for laying out the verdict row. */
function textWidth(s: string, fontPx: number): number {
  let w = 0;
  for (const ch of s) {
    const c = ch.codePointAt(0) ?? 0;
    if (c >= 0xac00 && c <= 0xd7a3) w += fontPx * 0.98;
    else if (ch === ' ') w += fontPx * 0.28;
    else if (/[A-Z]/.test(ch)) w += fontPx * 0.66;
    else w += fontPx * 0.53;
  }
  return w;
}

function MiniVerdict({ verdict, x, y, hatchId }: { verdict: Verdict; x: number; y: number; hatchId: string }) {
  const cx = x + 7;
  const cy = y;
  if (verdict === 'checked_route') {
    return (
      <g>
        <circle cx={cx} cy={cy} r="7" fill={COLORS.accent} />
        <path d={`M${cx - 3.3} ${cy + 0.3}l2.2 2.2 4.4-4.6`} fill="none" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    );
  }
  if (verdict === 'model_no_route') {
    return (
      <g>
        <circle cx={cx} cy={cy} r="6.2" fill="#fff" stroke={COLORS.ink} strokeWidth="1.6" />
        <path d={`M${cx - 4.2} ${cy + 4.2}L${cx + 4.2} ${cy - 4.2}`} stroke={COLORS.ink} strokeWidth="1.6" strokeLinecap="round" />
      </g>
    );
  }
  return (
    <g>
      <circle cx={cx} cy={cy} r="6.4" fill={`url(#${hatchId})`} stroke={COLORS.unresolved} strokeWidth="1.3" />
      <circle cx={cx} cy={cy - 0.4} r="3.7" fill="#fff" />
      <path
        d={`M${cx - 1.55} ${cy - 1.3}a1.6 1.6 0 1 1 2.25 1.45c-.42.2-.7.55-.7 1v.25`}
        fill="none"
        stroke="#4A4A4F"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
      <circle cx={cx} cy={cy + 3.1} r="0.75" fill="#4A4A4F" />
    </g>
  );
}

export function MethodDiagram({ lang }: { lang: Lang }) {
  const uid = useId().replace(/[^A-Za-z0-9_-]/g, '');
  const hatchId = `wfgf-mhatch-${uid}`;
  const titleId = `wfgf-mtitle-${uid}`;
  const descId = `wfgf-mdesc-${uid}`;
  const n = METHOD_STEPS.length;
  const H = n * ROW + (n - 1) * GAP + 2;
  const desc = METHOD_STEPS.map((s, i) => `${i + 1}. ${pick(s.title, lang)}${s.sub ? ` (${pick(s.sub, lang)})` : ''}`).join(' → ');
  const verdicts: Verdict[] = ['checked_route', 'model_no_route', 'unresolved'];

  let vx = TEXT_X;
  const verdictPos = verdicts.map((v) => {
    const label = pick(VERDICT_LABEL[v], lang);
    const pos = { v, x: vx, label };
    vx += 14 + 6 + textWidth(label, 13) + 18;
    return pos;
  });

  return (
    <svg
      className="wfgf-method"
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      role="img"
      aria-labelledby={`${titleId} ${descId}`}
      style={{ maxWidth: W, display: 'block' }}
    >
      <title id={titleId}>{lang === 'ko' ? '방법 개요' : 'Method overview'}</title>
      <desc id={descId}>{desc}</desc>
      <defs>
        <pattern id={hatchId} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="3" height="3" fill="#fff" />
          <line x1="0" y1="0" x2="0" y2="3" stroke={COLORS.unresolved} strokeWidth="1.1" />
        </pattern>
      </defs>
      {METHOD_STEPS.map((step, i) => {
        const y = 1 + i * (ROW + GAP);
        const last = i === n - 1;
        const cy = y + ROW / 2;
        return (
          <g key={i}>
            {i < n - 1 && (
              <g>
                <line x1={RAIL_X} y1={cy + 15} x2={RAIL_X} y2={cy + ROW + GAP - 15} stroke={COLORS.hairline} strokeWidth="1.5" />
                <path
                  d={`M${RAIL_X - 4} ${cy + ROW / 2 + GAP / 2 - 2}l4 4 4-4`}
                  fill="none"
                  stroke={COLORS.secondary}
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </g>
            )}
            <circle
              cx={RAIL_X}
              cy={cy}
              r="14"
              fill={last ? COLORS.accent : '#fff'}
              stroke={last ? COLORS.accent : COLORS.ink}
              strokeWidth="1.5"
            />
            <text
              x={RAIL_X}
              y={cy + 4.5}
              textAnchor="middle"
              fontSize="13"
              fontWeight="700"
              fill={last ? '#fff' : COLORS.ink}
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {i + 1}
            </text>
            <rect
              x={CARD_X}
              y={y}
              width={W - CARD_X - 1}
              height={ROW}
              rx="12"
              fill={last ? COLORS.accentTint : COLORS.surface}
              stroke={last ? COLORS.accent : 'none'}
              strokeWidth="1"
            />
            <Glyph i={i} x={GLYPH_X} y={y + (ROW - 28) / 2} hatchId={hatchId} />
            <text x={TEXT_X} y={step.sub || i === 4 ? y + 26 : y + 37} fontSize="15" fontWeight="650" fill={COLORS.ink}>
              {pick(step.title, lang)}
            </text>
            {step.sub && (
              <text x={TEXT_X} y={y + 46} fontSize="12.5" fill={COLORS.secondary}>
                {pick(step.sub, lang)}
              </text>
            )}
            {i === 4 &&
              verdictPos.map((p) => (
                <g key={p.v}>
                  <MiniVerdict verdict={p.v} x={p.x} y={y + 43} hatchId={hatchId} />
                  <text x={p.x + 20} y={y + 47.5} fontSize="13" fontWeight="600" fill={p.v === 'checked_route' ? COLORS.accentHover : p.v === 'model_no_route' ? COLORS.ink : '#55555A'}>
                    {p.label}
                  </text>
                </g>
              ))}
          </g>
        );
      })}
    </svg>
  );
}
