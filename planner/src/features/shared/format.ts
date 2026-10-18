/**
 * Pure formatting helpers for the feature modules. Times are seconds after the scenario's input
 * time (UTC); the wall clock is KST (UTC+9, no daylight saving) — see src/domain/clock.ts.
 */
import { formatRelative, kstClock, kstDate, kstDateTime, parseUtc } from '../../domain/clock';
import type { Lang } from '../../domain/clock';

export { kstClock, kstDate, kstDateTime, formatRelative, parseUtc };

/**
 * Clock settings of a scenario row. Offsets are always seconds after the INPUT time (the API's
 * journey clock), so the wall clock is input time + offset. Drawn zones add the relative
 * "T+h:mm" after the zone forecast's issue time (issued_at ≤ input_time).
 */
export interface ClockBase {
  inputTimeIso: string;
  /** drawn zones: the zones' issued time (adds "T+h:mm" counted from it) */
  issuedAtIso?: string | null;
}

/** "18:50" (recorded) or "18:50 (T+0:50)" (drawn zones, relative to the issue time). "—" for null. */
export function clockAt(base: ClockBase, offsetS: number | null | undefined, opts: { seconds?: boolean } = {}): string {
  if (offsetS === null || offsetS === undefined || !Number.isFinite(offsetS)) return '—';
  const wall = kstClock(base.inputTimeIso, offsetS, opts);
  if (!base.issuedAtIso) return wall;
  const sinceIssue = (parseUtc(base.inputTimeIso) - parseUtc(base.issuedAtIso)) / 1000 + offsetS;
  return Number.isFinite(sinceIssue) ? `${wall} (${formatRelative(sinceIssue)})` : wall;
}

/** "2025-03-24 18:50" KST for CSV cells (no "KST" suffix: the column header says KST). */
export function kstDateClock(iso: string, offsetS: number | null | undefined): string {
  if (offsetS === null || offsetS === undefined || !Number.isFinite(offsetS) || !Number.isFinite(parseUtc(iso))) return '';
  return `${kstDate(iso, offsetS)} ${kstClock(iso, offsetS)}`;
}

/** ISO instant → "2026-10-17 18:31 KST" (generation / cache times). */
export function kstStamp(iso: string | null | undefined): string {
  if (!iso || !Number.isFinite(parseUtc(iso))) return '—';
  return kstDateTime(iso, 0);
}

/**
 * Heat flux / dose value for display. Never rounds a positive value to 0: values below 0.001 are
 * shown as "< 0.001"; otherwise up to 3 significant digits (min 1 decimal for values < 10).
 */
export function formatExposure(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  if (v === 0) return '0';
  if (v < 0.001) return '< 0.001';
  if (v >= 100) return String(Math.round(v));
  return String(Number(v.toPrecision(3)));
}

export function formatDistanceM(m: number | null | undefined, lang: Lang): string {
  if (m === null || m === undefined || !Number.isFinite(m)) return '—';
  if (m >= 1000) return `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)} km`;
  return lang === 'ko' ? `${Math.round(m)} m` : `${Math.round(m)} m`;
}

/** "7.2 s" compute time; null → "—". */
export function formatSeconds(s: number | null | undefined): string {
  if (s === null || s === undefined || !Number.isFinite(s)) return '—';
  return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`;
}

/** Duration in minutes "35분" / "35 min" (arrival − departure). */
export function formatMinutes(seconds: number | null | undefined, lang: Lang): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—';
  const m = Math.round(seconds / 60);
  return lang === 'ko' ? `${m}분` : `${m} min`;
}

export function formatCoord(lon: number, lat: number): string {
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return '—';
  return `${lat.toFixed(5)}°N ${lon.toFixed(5)}°E`;
}

/** Smallest positive gap between sorted offsets, in minutes (sweep step for captions); null if < 2 offsets. */
export function sweepStepMin(offsetsS: number[]): number | null {
  const xs = [...new Set(offsetsS.filter((x) => Number.isFinite(x)))].sort((a, b) => a - b);
  let best: number | null = null;
  for (let i = 1; i < xs.length; i += 1) {
    const d = xs[i]! - xs[i - 1]!;
    if (d > 0 && (best === null || d < best)) best = d;
  }
  return best === null ? null : Math.round(best / 60);
}

/** Short id for file names: "osm:node/415158323" → "osm-node-415158323". */
export function slug(s: string): string {
  return s.replace(/[^A-Za-z0-9가-힣._-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 80) || 'x';
}
