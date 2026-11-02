/**
 * Shared pieces of the message templates: KST time wording, the card's content model and the
 * spoken-script assembly (optional blocks added in a fixed priority order while the script still
 * fits the time budget — deterministic for a given input).
 */
import { parseUtc } from '../../domain/clock';
import type { Verdict } from '../../domain/types';
import { spokenSeconds } from './encoding';
import type { MessagePlan } from './plan';
import type { LmLang, LmText } from './types';

/** One language's templates (./templates/<lang>.ts). Every output is built from fixed text only. */
export interface TemplateSet {
  lang: LmLang;
  sms(p: MessagePlan): string;
  lms(p: MessagePlan): string;
  /** blocks of the loudspeaker script; assembleSpoken() fits them into the time budget */
  broadcastBlocks(p: MessagePlan): SpokenBlock[];
  call(p: MessagePlan): string;
  card(p: MessagePlan): CardContent;
}

const KST_MS = 9 * 3600 * 1000;

export interface KstParts {
  y: number;
  mo: number;
  d: number;
  h: number;
  mi: number;
}

/** KST calendar parts of input time + offset (offset floored to whole seconds, like the planner). */
export function kstParts(inputIso: string, offsetS = 0): KstParts {
  const t = new Date(parseUtc(inputIso) + Math.floor(offsetS) * 1000 + KST_MS);
  return { y: t.getUTCFullYear(), mo: t.getUTCMonth() + 1, d: t.getUTCDate(), h: t.getUTCHours(), mi: t.getUTCMinutes() };
}

const p2 = (n: number) => String(n).padStart(2, '0');

/** "18:40" (KST). */
export function hm(inputIso: string, offsetS = 0): string {
  const p = kstParts(inputIso, offsetS);
  return `${p2(p.h)}:${p2(p.mi)}`;
}

/** "2025-03-24" (KST). */
export function ymd(inputIso: string, offsetS = 0): string {
  const p = kstParts(inputIso, offsetS);
  return `${p.y}-${p2(p.mo)}-${p2(p.d)}`;
}

/** Korean spoken clock: "오후 6시 40분", "새벽 4시", "밤 12시 10분". */
export function koSpokenTime(inputIso: string, offsetS = 0): string {
  const { h, mi } = kstParts(inputIso, offsetS);
  let head: string;
  if (h === 0) head = '밤 12시';
  else if (h <= 5) head = `새벽 ${h}시`;
  else if (h <= 11) head = `오전 ${h}시`;
  else if (h === 12) head = '낮 12시';
  else if (h <= 20) head = `오후 ${h - 12}시`;
  else head = `밤 ${h - 12}시`;
  return mi ? `${head} ${mi}분` : head;
}

/** English spoken clock: "6:40 p.m.", "4 a.m.", "12:10 a.m.". */
export function enSpokenTime(inputIso: string, offsetS = 0): string {
  const { h, mi } = kstParts(inputIso, offsetS);
  const h12 = h % 12 === 0 ? 12 : h % 12;
  const ap = h < 12 ? 'a.m.' : 'p.m.';
  return mi ? `${h12}:${p2(mi)} ${ap}` : `${h12} ${ap}`;
}

/** "2025년 3월 24일 18:00" (KST). */
export function koDate(inputIso: string): string {
  const p = kstParts(inputIso);
  return `${p.y}년 ${p.mo}월 ${p.d}일 ${p2(p.h)}:${p2(p.mi)}`;
}

/** "2025년 3월 24일 오후 6시" (KST, spoken). */
export function koDateSpoken(inputIso: string): string {
  const p = kstParts(inputIso);
  return `${p.y}년 ${p.mo}월 ${p.d}일 ${koSpokenTime(inputIso)}`;
}

/** "25.3.24 18:00" (KST, compact for the Korean SMS). */
export function koSmsDate(inputIso: string): string {
  const p = kstParts(inputIso);
  return `${String(p.y % 100).padStart(2, '0')}.${p.mo}.${p.d} ${p2(p.h)}:${p2(p.mi)}`;
}

/** "2025-03-24 18:00 KST". */
export function enDate(inputIso: string): string {
  return `${ymd(inputIso)} ${hm(inputIso)} KST`;
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "March 24, 2025, 6 p.m." (KST, spoken). */
export function enDateSpoken(inputIso: string): string {
  const p = kstParts(inputIso);
  return `${MONTHS[p.mo - 1]} ${p.d}, ${p.y}, ${enSpokenTime(inputIso)}`;
}

/** Duration wording of the recorded window ("1시간" / "1 hour"; minutes otherwise). */
export function durationText(s: number, lang: LmLang): string {
  if (s > 0 && s % 3600 === 0) {
    const h = s / 3600;
    return lang === 'ko' ? `${h}시간` : `${h} hour${h === 1 ? '' : 's'}`;
  }
  const m = Math.round(s / 60);
  return lang === 'ko' ? `${m}분` : `${m} min`;
}

/** Distance wording for the entry-point note ("120 m", "1.4 km"). */
export function distanceText(m: number): string {
  if (m >= 1000) return `${(m / 1000).toFixed(1)} km`;
  return `${Math.round(m)} m`;
}

// ---------------------------------------------------------------- card content

export type CardLineRole = 'instruction' | 'destination' | 'guide' | 'reason' | 'after' | 'note' | 'status' | 'meaning';

export interface CardLine {
  role: CardLineRole;
  text: string;
}

/** Everything a printed card shows (FieldCard.tsx renders it; nothing is added there). */
export interface CardContent {
  lang: LmLang;
  docTitle: string;
  regionName: string;
  fireInputLabel: string;
  /** "MOCK", "시험 데이터 · 평가 호스트 아님" … */
  badges: string[];
  title: string;
  category: string | null;
  /** icon of the status block: green check only for a leave-by message */
  statusIcon: Verdict;
  statusText: string;
  big: { label: string; time: string; sub: string } | null;
  lines: CardLine[];
  official: string;
  dataLine: string;
  modelLine: string;
  limits: string;
  footer: string;
  meta: string;
}

/** The card as plain text (checks, CSV, screen readers): every visible string in reading order. */
export function cardText(c: CardContent): string {
  return [
    `${c.docTitle} · ${c.regionName} · ${c.fireInputLabel}${c.badges.length ? ` · ${c.badges.join(' · ')}` : ''}`,
    c.category ? `${c.title} (${c.category})` : c.title,
    c.statusText,
    c.big ? `${c.big.label} ${c.big.time} (${c.big.sub})` : null,
    ...c.lines.map((l) => l.text),
    c.official,
    c.dataLine,
    c.modelLine,
    c.limits,
    c.footer,
    c.meta,
  ]
    .filter((x): x is string => Boolean(x))
    .join('\n');
}

// ---------------------------------------------------------------- spoken scripts

export type SpokenOptional = 'reason' | 'repeat' | 'carless';

export interface SpokenBlock {
  text: string;
  /** omitted when the script would exceed its time budget; added in SPOKEN_PRIORITY order */
  optional?: SpokenOptional;
}

export const SPOKEN_PRIORITY: readonly SpokenOptional[] = ['reason', 'repeat', 'carless'];

/**
 * Joins the blocks (one per line) keeping every required block and adding optional ones, in the
 * fixed priority order, while the estimated reading time stays within `maxS`.
 */
export function assembleSpoken(blocks: SpokenBlock[], lang: LmLang, maxS: number): string {
  const keep = new Set<SpokenBlock>(blocks.filter((b) => !b.optional));
  const text = (set: Set<SpokenBlock>) =>
    blocks
      .filter((b) => set.has(b))
      .map((b) => b.text)
      .join('\n');
  for (const pri of SPOKEN_PRIORITY) {
    for (const b of blocks.filter((x) => x.optional === pri)) {
      const next = new Set(keep);
      next.add(b);
      if (spokenSeconds(text(next), lang) <= maxS) keep.add(b);
    }
  }
  return text(keep);
}

export function pickText(t: LmText, lang: LmLang): string {
  return t[lang] ?? t.ko;
}
