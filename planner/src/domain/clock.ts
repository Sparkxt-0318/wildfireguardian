/**
 * Clock formatting. Recorded scenarios show KST wall time = input time (UTC) + offset; KST is
 * UTC+9 all year (no daylight saving). Drawn zones show issued time + offset and a relative T+h:mm.
 */
export type Lang = 'ko' | 'en';

const KST_OFFSET_MS = 9 * 3600 * 1000;

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** Parse an ISO time (or compact 20250324T090000Z) to epoch milliseconds; NaN when invalid. */
export function parseUtc(iso: string): number {
  const compact = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(iso);
  if (compact) {
    const [, y, mo, d, h, mi, s] = compact;
    return Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s));
  }
  return Date.parse(iso);
}

/** UTC ISO → compact form used in file names: 2025-03-24T09:00:00Z → 20250324T090000Z */
export function compactUtc(iso: string): string {
  const t = new Date(parseUtc(iso));
  return (
    `${t.getUTCFullYear()}${pad2(t.getUTCMonth() + 1)}${pad2(t.getUTCDate())}` +
    `T${pad2(t.getUTCHours())}${pad2(t.getUTCMinutes())}${pad2(t.getUTCSeconds())}Z`
  );
}

function kstParts(iso: string, offsetS: number) {
  const ms = parseUtc(iso) + Math.floor(offsetS) * 1000 + KST_OFFSET_MS;
  const d = new Date(ms);
  return {
    y: d.getUTCFullYear(),
    mo: d.getUTCMonth() + 1,
    d: d.getUTCDate(),
    h: d.getUTCHours(),
    mi: d.getUTCMinutes(),
    s: d.getUTCSeconds(),
  };
}

/** "18:10" (or "18:35:43" with seconds) — KST wall time of input time + offset. */
export function kstClock(inputIso: string, offsetS: number, opts: { seconds?: boolean } = {}): string {
  if (!Number.isFinite(parseUtc(inputIso)) || !Number.isFinite(offsetS)) return '—';
  const p = kstParts(inputIso, offsetS);
  return opts.seconds ? `${pad2(p.h)}:${pad2(p.mi)}:${pad2(p.s)}` : `${pad2(p.h)}:${pad2(p.mi)}`;
}

/** "2025-03-24" — KST calendar date of input time + offset. */
export function kstDate(inputIso: string, offsetS = 0): string {
  if (!Number.isFinite(parseUtc(inputIso))) return '—';
  const p = kstParts(inputIso, offsetS);
  return `${p.y}-${pad2(p.mo)}-${pad2(p.d)}`;
}

/** "2025-03-24 18:00 KST" */
export function kstDateTime(inputIso: string, offsetS = 0): string {
  return `${kstDate(inputIso, offsetS)} ${kstClock(inputIso, offsetS)} KST`;
}

/** Elapsed time with sign: "+35분 47초" / "+35 min 47 s"; whole minutes drop the seconds. */
export function formatElapsed(seconds: number, lang: Lang = 'ko'): string {
  if (!Number.isFinite(seconds)) return '—';
  const sign = seconds < 0 ? '−' : '+';
  const total = Math.round(Math.abs(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const parts: string[] = [];
  if (lang === 'ko') {
    if (h) parts.push(`${h}시간`);
    if (m || (!h && !s)) parts.push(`${m}분`);
    if (s) parts.push(`${s}초`);
  } else {
    if (h) parts.push(`${h} h`);
    if (m || (!h && !s)) parts.push(`${m} min`);
    if (s) parts.push(`${s} s`);
  }
  return sign + parts.join(' ');
}

/** Relative scenario clock "T+1:40" (hours:minutes after the input / issued time). */
export function formatRelative(offsetS: number): string {
  if (!Number.isFinite(offsetS)) return '—';
  const sign = offsetS < 0 ? '−' : '+';
  const total = Math.floor(Math.abs(offsetS) / 60);
  return `T${sign}${Math.floor(total / 60)}:${pad2(total % 60)}`;
}

/** Offset as minutes "+10분" / "+10 min" (used for timeline tooltips). */
export function formatOffsetMinutes(offsetS: number, lang: Lang = 'ko'): string {
  const m = offsetS / 60;
  const v = Number.isInteger(m) ? String(m) : m.toFixed(1);
  return lang === 'ko' ? `+${v}분` : `+${v} min`;
}
