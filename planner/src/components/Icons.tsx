/**
 * Geometric inline SVG icons (no clip-art). Status icons:
 *   checked_route  → check in a circle (green)
 *   model_no_route → slashed circle (ink)
 *   unresolved     → question mark in a circle (mid grey)
 */
import type { CSSProperties, ReactElement, ReactNode } from 'react';
import type { Verdict } from '../domain/types';

interface IconProps {
  size?: number;
  color?: string;
  className?: string;
  style?: CSSProperties;
  title?: string;
}

function Svg({ size = 16, className, style, title, children, viewBox = '0 0 16 16' }: IconProps & { children: ReactNode; viewBox?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      className={className}
      style={style}
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  );
}

export function CheckIcon({ color = 'currentColor', ...p }: IconProps) {
  return (
    <Svg {...p}>
      <circle cx="8" cy="8" r="7" fill="none" stroke={color} strokeWidth="1.5" />
      <path d="M4.8 8.2 7 10.3l4.2-4.6" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export function NoRouteIcon({ color = 'currentColor', ...p }: IconProps) {
  return (
    <Svg {...p}>
      <circle cx="8" cy="8" r="7" fill="none" stroke={color} strokeWidth="1.5" />
      <path d="M3.3 12.7 12.7 3.3" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </Svg>
  );
}

export function UnresolvedIcon({ color = 'currentColor', ...p }: IconProps) {
  return (
    <Svg {...p}>
      <circle cx="8" cy="8" r="7" fill="none" stroke={color} strokeWidth="1.5" />
      <path d="M6.1 6.1a1.95 1.95 0 1 1 2.75 1.78c-.55.25-.85.7-.85 1.3v.35" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="8" cy="11.6" r="0.9" fill={color} />
    </Svg>
  );
}

/** Not checked: the recorded destination window cannot be met from this departure. */
export function WindowIcon({ color = 'currentColor', ...p }: IconProps) {
  return (
    <Svg {...p}>
      <circle cx="8" cy="8" r="7" fill="none" stroke={color} strokeWidth="1.3" strokeDasharray="2.2 2" />
      <path d="M5 8h6" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </Svg>
  );
}

export function VerdictIcon({ verdict, ...p }: IconProps & { verdict: Verdict }): ReactElement {
  if (verdict === 'checked_route') return <CheckIcon {...p} />;
  if (verdict === 'model_no_route') return <NoRouteIcon {...p} />;
  return <UnresolvedIcon {...p} />;
}

export function PlayIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M5 3.5v9l7.5-4.5z" fill={p.color ?? 'currentColor'} />
    </Svg>
  );
}

export function PauseIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <rect x="4" y="3.5" width="2.6" height="9" rx="0.6" fill={p.color ?? 'currentColor'} />
      <rect x="9.4" y="3.5" width="2.6" height="9" rx="0.6" fill={p.color ?? 'currentColor'} />
    </Svg>
  );
}

export function SearchIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <circle cx="7" cy="7" r="4.6" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" />
      <path d="m10.5 10.5 3.2 3.2" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" />
    </Svg>
  );
}

export function CloseIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="m4 4 8 8M12 4l-8 8" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" />
    </Svg>
  );
}

export function RefreshIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M13 8a5 5 0 1 1-1.5-3.55" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" />
      <path d="M12.2 2.2v2.6H9.6" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export function DocumentIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M4 1.8h5.2L12 4.6v9.6H4z" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M6 8h4M6 10.6h4" stroke={p.color ?? 'currentColor'} strokeWidth="1.3" strokeLinecap="round" />
    </Svg>
  );
}

export function ExportIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M8 2v7.5M5 6.5 8 9.5l3-3" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3 10.5v3h10v-3" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export function InfoIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <circle cx="8" cy="8" r="6.6" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.4" />
      <path d="M8 7.2v4" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="8" cy="4.9" r="0.9" fill={p.color ?? 'currentColor'} />
    </Svg>
  );
}

export function ChevronIcon({ dir = 'right', ...p }: IconProps & { dir?: 'left' | 'right' | 'down' | 'up' }) {
  const rot = { right: 0, down: 90, left: 180, up: 270 }[dir];
  return (
    <Svg {...p} style={{ ...(p.style ?? {}), transform: `rotate(${rot}deg)` }}>
      <path d="m6 3.5 4.5 4.5L6 12.5" fill="none" stroke={p.color ?? 'currentColor'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** Product mark: a road line under a flame-free arc (geometric). */
export function ProductMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
      <rect x="0.5" y="0.5" width="27" height="27" rx="8" fill="#0B0B0C" />
      <path d="M7 19.5c3.2-6.4 10.8-6.4 14 0" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
      <circle cx="14" cy="10" r="2.6" fill="#1A9E55" />
    </svg>
  );
}

/** Map legend glyphs. */
export function OriginGlyph({ kind }: { kind: 'village' | 'facility' | 'not_checkable' | 'shelter' | 'research' }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      {kind === 'village' && <circle cx="8" cy="8" r="5" fill="#FFFFFF" stroke="#0B0B0C" strokeWidth="1.8" />}
      {kind === 'facility' && <rect x="3" y="3" width="10" height="10" rx="3" fill="#FFFFFF" stroke="#0B0B0C" strokeWidth="1.8" />}
      {kind === 'not_checkable' && <circle cx="8" cy="8" r="5" fill="none" stroke="#9A9AA0" strokeWidth="1.6" strokeDasharray="2 1.6" />}
      {kind === 'shelter' && <circle cx="8" cy="8" r="5" fill="#FFFFFF" stroke="#1A9E55" strokeWidth="2.4" />}
      {kind === 'research' && <path d="M8 2.6 13.4 8 8 13.4 2.6 8z" fill="#FFFFFF" stroke="#0B0B0C" strokeWidth="1.7" strokeLinejoin="round" />}
    </svg>
  );
}
