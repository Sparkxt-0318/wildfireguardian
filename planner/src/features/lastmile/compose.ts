/**
 * Shared pieces of the message templates: KST time wording, the card's content model and the
 * spoken-script assembly (optional blocks added in a fixed priority order while the script still
 * fits the time budget — deterministic for a given input).
 */
import { parseUtc } from '../../domain/clock';
import type { Verdict } from '../../domain/types';
import { kstStamp } from '../shared/format';
import { spokenSeconds } from './encoding';
import type { MessagePlan } from './plan';
import type { LastMileInput, LmLang, LmText } from './types';

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

/**
 * The arrival shown next to a departure time, from ONE rounding: the arrival rounded UP to the whole
 * minute (never earlier than the model's arrival; the departure is shown as hm() shows it) and the
 * travel minutes as the difference of the two clocks shown — "10:10에 출발하면 10:53쯤 도착(차로 약
 * 43분)" for a 42 min 55 s trip, so the clock and the minutes always agree.
 */
export function arrivalShown(inputIso: string, departS: number, arrivalS: number): { hm: string; min: number } {
  const t0 = parseUtc(inputIso);
  // whole minutes since the epoch (KST is a whole number of minutes ahead of UTC)
  const depMin = Math.floor((t0 + Math.floor(departS) * 1000) / 60000);
  const arrMin = Math.ceil((t0 + arrivalS * 1000) / 60000);
  const k = new Date(arrMin * 60000 + KST_MS);
  return { hm: `${p2(k.getUTCHours())}:${p2(k.getUTCMinutes())}`, min: arrMin - depMin };
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

// ---------------------------------------------------------------- result provenance

/** "이 출발지 결과 없음": the source holds no result for this origin (provenance.computed false). */
const NO_RESULT: LmText = { ko: '이 출발지 결과 없음', en: 'no result for this origin' };

/**
 * Where an origin's result comes from, as the long text's data line and the card's staff line say
 * it: "사전 계산 2026-10-18 08:10 KST" (the precomputed cache's created time) or "API 점검 결과 ·
 * 계산 호스트 Linux x86_64 · 4 vCPU" ("API results · host …", the planner's own name for results
 * of API checks run in this session). A live result never carries the cache's stamp. An origin the
 * source holds no result for is never called computed: "사전 계산 캐시 2026-10-18 08:10 KST · 이
 * 출발지 결과 없음" / "API 점검 · 이 출발지 결과 없음" ("… · no result for this origin").
 */
export function resultSource(input: Pick<LastMileInput, 'provenance'>, lang: LmLang): string {
  const p = input.provenance;
  if (p.source === 'cache') {
    const at = p.cacheCreatedAtIso ? kstStamp(p.cacheCreatedAtIso) : null;
    if (!p.computed) return [lang === 'ko' ? '사전 계산 캐시' : 'Precomputed cache', at].filter(Boolean).join(' ') + ` · ${NO_RESULT[lang]}`;
    return lang === 'ko' ? (at ? `사전 계산 ${at}` : '사전 계산 캐시') : at ? `Precomputed ${at}` : 'Precomputed cache';
  }
  if (!p.computed) return lang === 'ko' ? `API 점검 · ${NO_RESULT.ko}` : `API checks · ${NO_RESULT.en}`;
  return lang === 'ko' ? `API 점검 결과 · 계산 호스트 ${p.host?.ko ?? '미상'}` : `API results · host ${p.host?.en ?? 'unknown'}`;
}

/** The same with the cache file and the evaluated-host status, for the CSV and the panel. */
export function resultSourceFull(input: Pick<LastMileInput, 'provenance' | 'testData'>, lang: LmLang): string {
  const p = input.provenance;
  const head =
    p.source === 'cache'
      ? [lang === 'ko' ? '사전 계산 캐시' : 'Precomputed cache', p.cachePath, p.cacheCreatedAtIso ? kstStamp(p.cacheCreatedAtIso) : null, p.computed ? null : NO_RESULT[lang]].filter(Boolean).join(' · ')
      : resultSource(input, lang);
  return input.testData ? `${head} · ${lang === 'ko' ? '평가 호스트 아님' : 'not the evaluation host'}` : head;
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

/** Optional blocks of a spoken script (the no-car line is required: it is never dropped). */
export type SpokenOptional = 'reason' | 'repeat';

export interface SpokenBlock {
  text: string;
  /** omitted when the script would exceed its time budget; added in SPOKEN_PRIORITY order */
  optional?: SpokenOptional;
  /**
   * Shorter wording of a required block (same facts, fewer words — e.g. without a long place name
   * that the written outputs carry, or the MOCK / test-data marker folded into the data sentence).
   * Used, block by block in order, only while the required blocks alone exceed the budget.
   */
  short?: string;
  /**
   * A last-resort wording (e.g. the greeting without the place name), used the same way only while
   * the required blocks still exceed the budget after every `short`.
   */
  shortest?: string;
}

export const SPOKEN_PRIORITY: readonly SpokenOptional[] = ['reason', 'repeat'];

/**
 * Joins the blocks (one per line): every required block — in its shorter wording, block by block
 * in order, only while the required blocks alone would exceed `maxS`; then, still over, in its
 * shortest wording, block by block — then the optional ones in the fixed priority order while the
 * estimated reading time stays within `maxS`. Deterministic.
 */
export function assembleSpoken(blocks: SpokenBlock[], lang: LmLang, maxS: number): string {
  const used = blocks.map((b) => ({ ...b }));
  const join = (set: Set<SpokenBlock>) =>
    used
      .filter((b) => set.has(b))
      .map((b) => b.text)
      .join('\n');
  const keep = new Set<SpokenBlock>(used.filter((b) => !b.optional));
  for (const level of ['short', 'shortest'] as const) {
    for (const b of used) {
      if (spokenSeconds(join(keep), lang) <= maxS) break;
      const s = b[level];
      if (!b.optional && s) b.text = s;
    }
  }
  for (const pri of SPOKEN_PRIORITY) {
    for (const b of used.filter((x) => x.optional === pri)) {
      const next = new Set(keep);
      next.add(b);
      if (spokenSeconds(join(next), lang) <= maxS) keep.add(b);
    }
  }
  return join(keep);
}

export function pickText(t: LmText, lang: LmLang): string {
  return t[lang] ?? t.ko;
}
