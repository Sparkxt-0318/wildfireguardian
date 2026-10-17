/**
 * Geometric status icons (ARCHITECTURE.md §7). Status is always colour + icon + text:
 * - checked_route: green disc with a white check;
 * - model_no_route: black ring with a slash;
 * - unresolved: mid-grey ring, hatched, with a question mark (never green, never "safe").
 * Pattern ids are unique per instance so a hidden icon never breaks another one's fill.
 */
import { useId } from 'react';
import type { Verdict } from '../../domain/types';
import { pick, VERDICT_LABEL, type Lang } from './strings';

export const COLORS = {
  ink: '#0B0B0C',
  paper: '#FFFFFF',
  surface: '#F5F5F7',
  hairline: '#E3E3E6',
  secondary: '#6E6E73',
  accent: '#1A9E55',
  accentHover: '#14824A',
  accentTint: '#E8F6EE',
  unresolved: '#9A9AA0',
} as const;

export function VerdictIcon(props: { verdict: Verdict; size?: number; title?: string; className?: string }) {
  const { verdict, size = 16, title, className } = props;
  const uid = useId().replace(/[^A-Za-z0-9_-]/g, '');
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 20 20',
    className,
    role: title ? 'img' : undefined,
    'aria-hidden': title ? undefined : true,
    'aria-label': title,
    focusable: 'false' as const,
  };
  if (verdict === 'checked_route') {
    return (
      <svg {...common} data-verdict-icon="checked_route">
        <circle cx="10" cy="10" r="9" fill={COLORS.accent} />
        <path d="M5.8 10.4l2.8 2.8 5.6-6" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (verdict === 'model_no_route') {
    return (
      <svg {...common} data-verdict-icon="model_no_route">
        <circle cx="10" cy="10" r="8" fill="#fff" stroke={COLORS.ink} strokeWidth="2" />
        <path d="M4.6 15.4L15.4 4.6" stroke={COLORS.ink} strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }
  const pid = `wfgf-hatch-${uid}`;
  return (
    <svg {...common} data-verdict-icon="unresolved">
      <defs>
        <pattern id={pid} width="3.2" height="3.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="3.2" height="3.2" fill="#fff" />
          <line x1="0" y1="0" x2="0" y2="3.2" stroke={COLORS.unresolved} strokeWidth="1.1" opacity="0.55" />
        </pattern>
      </defs>
      <circle cx="10" cy="10" r="8.2" fill={`url(#${pid})`} stroke={COLORS.unresolved} strokeWidth="1.6" />
      <circle cx="10" cy="9.3" r="4.6" fill="#fff" />
      <path
        d="M8 8.1a2.05 2.05 0 1 1 2.9 1.85c-.55.27-.9.7-.9 1.3v.35"
        fill="none"
        stroke="#4A4A4F"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="14.1" r="1" fill="#4A4A4F" />
    </svg>
  );
}

/** Icon + text, the only allowed way to show a verdict. */
export function VerdictBadge(props: { verdict: Verdict; lang: Lang; size?: number; className?: string }) {
  const { verdict, lang, size = 16, className } = props;
  return (
    <span className={`wfgf-verdict wfgf-verdict--${verdict}${className ? ` ${className}` : ''}`} data-verdict={verdict}>
      <VerdictIcon verdict={verdict} size={size} />
      <span className="wfgf-verdict__text">{pick(VERDICT_LABEL[verdict], lang)}</span>
    </span>
  );
}

/**
 * One cell of a departure-sweep strip. Each state has its own shape, not only a colour:
 * checked = solid green, no route = white with a black slash, unresolved = grey hatch,
 * window closed = empty dotted cell.
 */
export function SweepCellGlyph(props: { verdict: Verdict | 'window_closed'; width?: number; height?: number; title?: string }) {
  const { verdict, width = 14, height = 14, title } = props;
  const uid = useId().replace(/[^A-Za-z0-9_-]/g, '');
  const w = width;
  const h = height;
  const label = title ? { role: 'img' as const, 'aria-label': title } : { 'aria-hidden': true as const };
  if (verdict === 'checked_route') {
    return (
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} {...label} data-sweep={verdict}>
        <rect x="0.5" y="0.5" width={w - 1} height={h - 1} rx="2" fill={COLORS.accent} stroke={COLORS.accent} />
        <path d={`M${w * 0.28} ${h * 0.52}l${w * 0.16} ${h * 0.16} ${w * 0.3} -${h * 0.34}`} fill="none" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (verdict === 'model_no_route') {
    return (
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} {...label} data-sweep={verdict}>
        <rect x="0.75" y="0.75" width={w - 1.5} height={h - 1.5} rx="2" fill="#fff" stroke={COLORS.ink} strokeWidth="1.5" />
        <path d={`M${w * 0.22} ${h * 0.78}L${w * 0.78} ${h * 0.22}`} stroke={COLORS.ink} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (verdict === 'unresolved') {
    const pid = `wfgf-sweephatch-${uid}`;
    return (
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} {...label} data-sweep={verdict}>
        <defs>
          <pattern id={pid} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="3" height="3" fill="#fff" />
            <line x1="0" y1="0" x2="0" y2="3" stroke={COLORS.unresolved} strokeWidth="1.2" />
          </pattern>
        </defs>
        <rect x="0.5" y="0.5" width={w - 1} height={h - 1} rx="2" fill={`url(#${pid})`} stroke={COLORS.unresolved} />
      </svg>
    );
  }
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} {...label} data-sweep="window_closed">
      <rect x="0.5" y="0.5" width={w - 1} height={h - 1} rx="2" fill="#fff" stroke={COLORS.hairline} strokeDasharray="1.5 1.5" />
      <path d={`M${w * 0.3} ${h / 2}H${w * 0.7}`} stroke={COLORS.secondary} strokeWidth="1" />
    </svg>
  );
}

/** Small "MOCK" badge (text, not colour only). */
export function MockBadge(props: { lang: Lang; title?: string }) {
  return (
    <span className="wfgf-mock" title={props.title} data-mock-badge="true">
      MOCK
    </span>
  );
}
