/**
 * W-KIT — channel-ready message outputs built on the last-mile kit (research/harness-2026-11/W-KIT/DESIGN.md).
 *
 * Deterministic templates over the kit's own MessagePlan (../plan.ts); no model, no network. Planning aid only:
 * every output says it is model-based and not live, a recorded replay says it is not a real situation, and
 * `unresolved` never carries a departure time, a destination or reassurance. Each output fails closed on its own
 * (checkChannels): a violating output is withheld, the others stay usable.
 *
 * Outputs per origin (Korean source, English translation pending native review):
 *  - head: village-head script — a ≤ 20 s CORE carrying the five warning elements (source, hazard, location, time,
 *    guidance) between a fixed framing OPENER (not-real / data time / markers) and CLOSER (official orders first),
 *    counted separately (the framing alone is ≈ 12–13 s, so a 20 s script with framing is infeasible).
 *  - voice: automatic voice call (ARS) with key-press replies; key 2 = "needs help to leave", passed to the 이장 and
 *    읍·면사무소 — never a promise of transport (the kit's FORBIDDEN list bans pickup / rescue words).
 *  - familyText (≤ 90 bytes EUC-KR / ≤ 160 GSM-7) and familyScript (exactly three lines).
 *  - noOrder: only when the order status supplied by officials is `not_issued`: "no order yet — …", so silence is never
 *    read as safety.
 *  - staff: data-age line and the issue-order-by field (officials only; never a time unless one was computed).
 */
import { FORBIDDEN, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS, MODEL_NOT_LIVE_SMS, NOT_REAL, DEPARTURE_INSTRUCTION, RESIDENT_119_NOW } from '../strings';
import { clockTimes, maskData } from '../checks';
import { eucKrBytes, gsm7Length, spokenSeconds, SMS_KO_MAX_BYTES, SMS_EN_MAX_GSM7 } from '../encoding';
import { enSpokenTime, hm, koDate, koSpokenTime, enDate, kstParts } from '../compose';
import type { MessagePlan } from '../plan';
import type { LmLang } from '../types';

export const HEAD_CORE_MAX_S = 20;
export const HEAD_FULL_MAX_S = 35;
/** Standard (non-urgent) text limit relayed from the August 2025 reform; unit pending source check (code points). */
export const STANDARD_MAX_CHARS = 157;

export type OrderStatus = 'issued' | 'not_issued' | null;

/** F-3.1 issue-order-by value for this origin (offset s after the input time), or why there is none. */
export type IssueOrderBy = { offsetS: number } | { status: 'unresolved' | 'no_route' | 'not_computed' } | null;

export interface ChannelOptions {
  /** when the outputs are produced (ISO); the data age is measured against it */
  nowIso: string;
  orderStatus?: OrderStatus;
  issueOrderBy?: IssueOrderBy;
}

export type Element = 'source' | 'hazard' | 'location' | 'time' | 'guidance';
export const ELEMENTS: readonly Element[] = ['source', 'hazard', 'location', 'time', 'guidance'];

export interface TaggedBlock {
  text: string;
  elements: Element[];
  /** dropped (last first) only while the core exceeds its budget */
  optional?: boolean;
  /** same elements in fewer words (e.g. without a long place name), used only while still over budget */
  short?: string;
}

export interface HeadScript {
  opener: string;
  core: string;
  closer: string;
  /** elements present in the core as assembled */
  elements: Element[];
  coreS: number;
  fullS: number;
}

export interface ChannelTexts {
  head: HeadScript;
  voice: string;
  familyText: string;
  familyScript: [string, string, string];
  noOrder: string | null;
  staff: { dataAge: string; issueOrderBy: string };
}

export interface ChannelSet {
  originId: string;
  kind: MessagePlan['kind'];
  /** the single destination any output may name (null: none may) */
  destinationName: Record<LmLang, string> | null;
  text: Record<LmLang, ChannelTexts>;
  violations: string[];
}

const iso = (p: MessagePlan) => p.input.scenario.inputTimeIso;
const year = (p: MessagePlan) => kstParts(iso(p)).y;

function villageName(p: MessagePlan, lang: LmLang): string | null {
  const n = p.input.origin.name;
  return n ? n[lang] ?? null : null;
}

/** The one destination outputs may name: leave_by with a destination that does not vary, and a real name. */
export function namedDestination(p: MessagePlan): Record<LmLang, string> | null {
  if (p.kind !== 'leave_by' || !p.destination || p.destinationVaries || !p.destination.name) return null;
  const ko = p.destination.name.ko;
  const en = p.destination.name.en;
  return ko ? { ko, en: en && /^[\x20-\x7E]+$/.test(en) ? en : '' } : null;
}

// ------------------------------------------------------------------------------------------------ head script

function assemble(blocks: TaggedBlock[], lang: LmLang, maxS: number): TaggedBlock[] {
  const keep = blocks.map((b) => ({ ...b }));
  const len = () => spokenSeconds(keep.map((b) => b.text).join('\n'), lang);
  for (let i = keep.length - 1; i >= 0 && len() > maxS; i--) if (keep[i]!.optional) keep.splice(i, 1);
  // shorten from the end backwards, so the place name in the first block is the last thing dropped
  for (const b of [...keep].reverse()) {
    if (len() <= maxS) break;
    if (b.short) b.text = b.short;
  }
  return keep;
}

function framing(p: MessagePlan, lang: LmLang): { opener: string; closer: string } {
  const o: string[] = [];
  if (lang === 'ko') {
    if (p.input.replay) o.push(NOT_REAL.ko);
    const via = p.input.mock ? '모의 서버로 ' : '';
    const test = p.input.testData ? '시험용 ' : '';
    o.push(p.input.replay ? (via || test ? `${year(p)}년 기록을 ${via}재현한 ${test}자료입니다.` : `${year(p)}년 기록 재현입니다.`) : `${koSpokenTime(iso(p))} ${via ? '모의 서버 ' : ''}${test}자료이며 실시간이 아닙니다.`);
    return { opener: o.join('\n'), closer: OFFICIAL_FIRST.ko };
  }
  if (p.input.replay) o.push(NOT_REAL.en);
  o.push(p.input.replay ? `This is a replay of ${year(p)} records, not live.` : `Data from ${enSpokenTime(iso(p))}, not live.`);
  if (p.input.mock) o.push('Mock server data.');
  if (p.input.testData) o.push('Test computation data.');
  return { opener: o.join('\n'), closer: OFFICIAL_FIRST.en };
}

function headCoreBlocks(p: MessagePlan, lang: LmLang): TaggedBlock[] {
  const v = villageName(p, lang);
  const dest = namedDestination(p);
  const facility = p.input.origin.kind === 'facility';
  if (lang === 'ko') {
    const who = facility ? `${v ?? '이 시설'} 안내입니다.` : `${v ?? '이 마을'} 이장입니다.`;
    const b: TaggedBlock[] = [{ text: `${who} 산불 대피 안내입니다.`, short: `${facility ? '시설' : '이장'} 안내입니다. 이곳 산불 대피 안내입니다.`, elements: ['source', 'location', 'hazard'] }];
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      b.push({ text: `${koSpokenTime(iso(p), p.leaveByS)}까지 차로 출발하십시오.`, short: `${koSpokenTime(iso(p), p.leaveByS)}까지 출발하십시오.`, elements: ['time', 'guidance'] });
      if (dest) b.push({ text: `${dest.ko} 쪽입니다.`, elements: ['location'], optional: true });
      b.push({ text: facility ? '차가 부족하면 읍·면사무소에 알리십시오.' : '차가 없으면 이장에게 알리십시오.', short: facility ? '차가 부족하면 면사무소에 알리십시오.' : '차가 없으면 이장에게.', elements: ['guidance'] });
    } else if (p.kind === 'no_route') {
      b.push({ text: `${koSpokenTime(iso(p))} 자료로는 차로 나가는 확인된 길이 없습니다.`, short: `${koSpokenTime(iso(p))} 자료로는 확인된 길이 없습니다.`, elements: ['time'] });
      b.push({ text: '공식 지시를 따르고, 위급하면 119에 신고하십시오.', short: '공식 지시를 따르십시오. 위급하면 119입니다.', elements: ['guidance'] });
    } else {
      b.push({ text: `${koSpokenTime(iso(p))} 자료로는 대피 길을 확인하지 못했습니다.`, short: `${koSpokenTime(iso(p))} 자료로는 확인하지 못했습니다.`, elements: ['time'] });
      b.push({ text: '공식 대피 안내를 따르십시오.', elements: ['guidance'] });
    }
    return b;
  }
  const who = facility ? 'This is your facility.' : 'This is your village head.';
  const b: TaggedBlock[] = [{ text: `${who} Wildfire evacuation notice${v && /^[\x20-\x7E]+$/.test(v) ? ` for ${v}` : ' for this village'}.`, short: `${who} Wildfire evacuation notice for this place.`, elements: ['source', 'location', 'hazard'] }];
  if (p.kind === 'leave_by' && p.leaveByS !== null) {
    b.push({ text: `Leave by car by ${enSpokenTime(iso(p), p.leaveByS)}.`, elements: ['time', 'guidance'] });
    if (dest && dest.en) b.push({ text: `Go toward ${dest.en}.`, elements: ['location'], optional: true });
    b.push({ text: facility ? 'Short of cars? Tell the town office.' : 'No car? Tell the village head.', elements: ['guidance'] });
  } else if (p.kind === 'no_route') {
    b.push({ text: `Data from ${enSpokenTime(iso(p))} shows no checked road out.`, elements: ['time'] });
    b.push({ text: 'Follow official instructions. In an emergency, report to 119.', elements: ['guidance'] });
  } else {
    b.push({ text: `Data from ${enSpokenTime(iso(p))} could not check a road out.`, elements: ['time'] });
    b.push({ text: 'Follow official evacuation guidance.', elements: ['guidance'] });
  }
  return b;
}

export function headScript(p: MessagePlan, lang: LmLang): HeadScript {
  const { opener, closer } = framing(p, lang);
  const blocks = assemble(headCoreBlocks(p, lang), lang, HEAD_CORE_MAX_S);
  const core = blocks.map((b) => b.text).join('\n');
  const elements = ELEMENTS.filter((e) => blocks.some((b) => b.elements.includes(e)));
  return { opener, core, closer, elements, coreS: spokenSeconds(core, lang), fullS: spokenSeconds([opener, core, closer].join('\n'), lang) };
}

// ------------------------------------------------------------------------------------------------ voice call (ARS)

export type ReplyCode = 'leaving' | 'acknowledged' | 'needs_help' | 'repeat' | 'unknown';

/** What a key press means for this origin's message kind. */
export function replyCode(kind: MessagePlan['kind'], key: string): ReplyCode {
  if (key === '1') return kind === 'leave_by' ? 'leaving' : 'acknowledged';
  if (key === '2') return 'needs_help';
  if (key === '3') return 'repeat';
  return 'unknown';
}

function voice(p: MessagePlan, lang: LmLang): string {
  const h = headScript(p, lang);
  const leave = p.kind === 'leave_by';
  if (lang === 'ko') {
    return [
      h.opener,
      '산불 대피 안내 자동 전화입니다.',
      h.core,
      `${leave ? '지금 출발하시면' : '안내를 들으셨으면'} 1번, 차가 없거나 혼자 이동이 어려우면 2번, 다시 들으시려면 3번을 누르십시오.`,
      '2번을 누르시면 이장과 읍·면사무소에 전달됩니다.',
      h.closer,
    ].join('\n');
  }
  return [
    h.opener,
    'This is an automated wildfire evacuation call.',
    h.core,
    `Press 1 ${leave ? 'if you are leaving now' : 'if you heard this notice'}, 2 if you have no car or cannot leave on your own, 3 to hear this again.`,
    'If you press 2, your answer is passed to the village head and the town office.',
    h.closer,
  ].join('\n');
}

// ------------------------------------------------------------------------------------------------ family relay

function tag(p: MessagePlan, lang: LmLang): string {
  const m = p.input.mock, t = p.input.testData;
  if (lang === 'ko') return m && t ? '[MOCK시험]' : m ? '[MOCK]' : t ? '[시험자료]' : p.input.replay ? '[기록재현]' : '';
  return [p.input.replay ? 'REPLAY' : '', m ? 'MOCK' : '', t ? 'TEST' : ''].filter(Boolean).join(' ');
}

function familyText(p: MessagePlan, lang: LmLang): string {
  const full = familyTextWith(p, lang, villageName(p, lang));
  const fits = lang === 'ko' ? eucKrBytes(full).bytes <= SMS_KO_MAX_BYTES : gsm7Length(full).chars <= SMS_EN_MAX_GSM7;
  return fits ? full : familyTextWith(p, lang, null);
}

function familyTextWith(p: MessagePlan, lang: LmLang, v: string | null): string {
  if (lang === 'ko') {
    const head = `${tag(p, 'ko')}${v ?? '마을'} 산불`;
    const body = p.kind === 'leave_by' && p.leaveByS !== null ? `모델상 ${hm(iso(p), p.leaveByS)}까지 차로 출발` : p.kind === 'no_route' ? '모델상 경로 없음, 위급 시 119' : '모델 미확인, 공식안내 따름';
    return `${head}\n${body}\n${OFFICIAL_FIRST_SMS.ko}·${MODEL_NOT_LIVE_SMS.ko}`;
  }
  const head = `${tag(p, 'en')} ${v && /^[\x20-\x7E]+$/.test(v) ? v : 'Village'} wildfire`.trim();
  const body = p.kind === 'leave_by' && p.leaveByS !== null ? `Model: leave by car by ${hm(iso(p), p.leaveByS)}` : p.kind === 'no_route' ? 'Model: no route. Emergency: 119' : 'Model: not checked. Follow official guidance';
  return `${head}\n${body}\n${OFFICIAL_FIRST_SMS.en} ${MODEL_NOT_LIVE_SMS.en}`;
}

function familyScript(p: MessagePlan, lang: LmLang): [string, string, string] {
  const v = villageName(p, lang);
  const dest = namedDestination(p);
  const replay = p.input.replay;
  if (lang === 'ko') {
    const l1 = `[이름]님, ${v ?? '마을'} 산불 대피 안내입니다. ${replay ? '실제 상황이 아니라 기록 재현이며, ' : ''}컴퓨터 예측 계산 자료입니다.`;
    const l2 =
      p.kind === 'leave_by' && p.leaveByS !== null
        ? `${koSpokenTime(iso(p), p.leaveByS)}까지 차로 출발하셔야 합니다${dest ? `. ${dest.ko} 쪽입니다` : ''}.`
        : p.kind === 'no_route'
          ? `${koSpokenTime(iso(p))} 자료로는 차로 나가는 확인된 길이 없습니다.`
          : `${koSpokenTime(iso(p))} 자료로는 대피 길을 확인하지 못했습니다.`;
    const l3 = `차가 없으면 이장에게 알리시고, 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오. ${OFFICIAL_FIRST.ko}`;
    return [l1, l2, l3];
  }
  const l1 = `[Name], this is a wildfire evacuation notice for ${v && /^[\x20-\x7E]+$/.test(v) ? v : 'your village'}. ${replay ? 'It is a replay of records, not a real emergency, ' : ''}from a computer forecast, not live.`;
  const l2 =
    p.kind === 'leave_by' && p.leaveByS !== null
      ? `Leave by car by ${enSpokenTime(iso(p), p.leaveByS)}${dest && dest.en ? `, toward ${dest.en}` : ''}.`
      : p.kind === 'no_route'
        ? `Data from ${enSpokenTime(iso(p))} shows no checked road out by car.`
        : `Data from ${enSpokenTime(iso(p))} could not check a road out.`;
  const l3 = `No car? Tell the village head, and follow official instructions. In an emergency, report to 119. ${OFFICIAL_FIRST.en}`;
  return [l1, l2, l3];
}

// ------------------------------------------------------------------------------------------------ no order yet

function noOrder(p: MessagePlan, lang: LmLang, status: OrderStatus): string | null {
  if (status !== 'not_issued') return null;
  const fits = (t: string) => [...t].length <= STANDARD_MAX_CHARS;
  const full = noOrderWith(p, lang, villageName(p, lang), false);
  if (fits(full)) return full;
  const unnamed = noOrderWith(p, lang, null, false);
  return fits(unnamed) ? unnamed : noOrderWith(p, lang, null, true);
}

/** Standard-text tag: the replay note AND every marker (room for all of them, unlike the 90-byte text). */
function longTag(p: MessagePlan, lang: LmLang): string {
  const parts = lang === 'ko'
    ? [p.input.replay ? '기록재현' : '', p.input.mock ? 'MOCK' : '', p.input.testData ? '시험자료' : '']
    : [p.input.replay ? 'REPLAY' : '', p.input.mock ? 'MOCK' : '', p.input.testData ? 'TEST' : ''];
  const t = parts.filter(Boolean).join(lang === 'ko' ? '·' : ' ');
  return t ? (lang === 'ko' ? `[${t}]` : `${t} `) : '';
}

function noOrderWith(p: MessagePlan, lang: LmLang, v: string | null, shortFirst: boolean): string {
  if (lang === 'ko') {
    const lead = `${longTag(p, 'ko')}${v ?? '마을'} 산불: 아직 공식 대피 명령은 없습니다.`;
    const body =
      p.kind === 'leave_by' && p.leaveByS !== null
        ? `컴퓨터 예측으로는 ${hm(iso(p), p.leaveByS)}까지 출발해야 합니다.`
        : p.kind === 'no_route'
          ? '컴퓨터 예측으로는 확인된 대피 길이 없습니다.'
          : '컴퓨터 예측으로는 확인하지 못했습니다.';
    return `${lead} ${body} 명령이 없다고 위험이 없는 것은 아닙니다. ${shortFirst ? OFFICIAL_FIRST_SMS.ko + '.' : OFFICIAL_FIRST.ko}`;
  }
  const lead = `${longTag(p, 'en')}${v && /^[\x20-\x7E]+$/.test(v) ? v : 'Village'} wildfire: no official order yet.`;
  const body =
    p.kind === 'leave_by' && p.leaveByS !== null
      ? `Forecast: leave by ${hm(iso(p), p.leaveByS)}.`
      : p.kind === 'no_route'
        ? 'Forecast: no checked road out.'
        : 'Forecast: not checked.';
  return `${lead} ${body} No order yet is not an all-clear. ${shortFirst ? OFFICIAL_FIRST_SMS.en : OFFICIAL_FIRST.en}`;
}

// ------------------------------------------------------------------------------------------------ staff fields

export function dataAge(p: MessagePlan, nowIso: string, lang: LmLang): string {
  const t0 = iso(p);
  if (p.input.replay) return lang === 'ko' ? `자료 시각 ${koDate(t0)} · ${year(p)}년 기록 재현 자료` : `Data time ${enDate(t0)} · replay of ${year(p)} records`;
  const ageMin = Math.floor((Date.parse(nowIso) - Date.parse(t0)) / 60000);
  if (!Number.isFinite(ageMin) || ageMin < 0) return lang === 'ko' ? `자료 시각 ${koDate(t0)} · 자료 나이 확인 불가` : `Data time ${enDate(t0)} · data age unknown`;
  return lang === 'ko' ? `자료 시각 ${koDate(t0)} · ${ageMin}분 전 자료` : `Data time ${enDate(t0)} · ${ageMin} min old`;
}

export function issueOrderByText(p: MessagePlan, v: IssueOrderBy | undefined, lang: LmLang): string {
  if (v && 'offsetS' in v && Number.isFinite(v.offsetS) && p.kind === 'leave_by') {
    return lang === 'ko' ? `공식 명령 발령 시한(모델 계산): ${hm(iso(p), v.offsetS)}` : `Issue order by (model): ${hm(iso(p), v.offsetS)}`;
  }
  return lang === 'ko' ? '공식 명령 발령 시한(모델 계산): 산출되지 않음' : 'Issue order by (model): not computed';
}

// ------------------------------------------------------------------------------------------------ assembly + checks

export function buildChannels(p: MessagePlan, opt: ChannelOptions): ChannelSet {
  const text = {} as Record<LmLang, ChannelTexts>;
  for (const lang of ['ko', 'en'] as LmLang[]) {
    text[lang] = {
      head: headScript(p, lang),
      voice: voice(p, lang),
      familyText: familyText(p, lang),
      familyScript: familyScript(p, lang),
      noOrder: noOrder(p, lang, opt.orderStatus ?? null),
      staff: { dataAge: dataAge(p, opt.nowIso, lang), issueOrderBy: issueOrderByText(p, opt.issueOrderBy, lang) },
    };
  }
  const set: ChannelSet = { originId: p.input.origin.id, kind: p.kind, destinationName: namedDestination(p), text, violations: [] };
  set.violations = checkChannels(p, set);
  return set;
}

/** Names from data, masked before the word checks (a village called 안전마을 must not trip "안전"). */
function inserted(p: MessagePlan): string[] {
  const out: string[] = [];
  for (const t of [p.input.origin.name, p.destination?.name]) if (t) for (const s of [t.ko, t.en]) if (s) out.push(s);
  return out.sort((a, b) => b.length - a.length);
}

/** Every rule violation of every output, each prefixed with its output (e.g. "ko.head.core: …"). */
export function checkChannels(p: MessagePlan, set: ChannelSet): string[] {
  const v: string[] = [];
  const names = inserted(p);
  const dataHm = hm(iso(p));
  for (const lang of ['ko', 'en'] as LmLang[]) {
    const t = set.text[lang];
    const outs: [string, string][] = [
      ['head', [t.head.opener, t.head.core, t.head.closer].join('\n')],
      ['voice', t.voice],
      ['familyText', t.familyText],
      ['familyScript', t.familyScript.join('\n')],
      ...(t.noOrder !== null ? ([['noOrder', t.noOrder]] as [string, string][]) : []),
      ['staff', `${t.staff.dataAge}\n${t.staff.issueOrderBy}`],
    ];
    for (const [name, s] of outs) {
      const id = `${lang}.${name}`;
      const masked = maskData(s, names).toLowerCase();
      for (const w of FORBIDDEN[lang]) if (masked.includes(w.toLowerCase())) v.push(`${id}: forbidden word "${w}"`);
      if (name !== 'staff' && RESIDENT_119_NOW[lang].test(s)) v.push(`${id}: tells residents to call 119 now`);
      if (p.kind !== 'leave_by' && DEPARTURE_INSTRUCTION[lang].test(maskData(s, names))) v.push(`${id}: departure instruction without a checked window`);
      if (p.kind !== 'leave_by') {
        const extra = clockTimes(maskData(s, names)).filter((c) => c !== dataHm);
        if (extra.length) v.push(`${id}: clock time ${extra.join(',')} without a checked window`);
      }
      if (name !== 'staff' && !s.includes(OFFICIAL_FIRST[lang]) && !s.includes(OFFICIAL_FIRST_SMS[lang])) v.push(`${id}: missing official-orders-first`);
      const markerInstead = lang === 'ko' && name === 'familyText' && (p.input.mock || p.input.testData) && /MOCK|시험자료/.test(s);
      if (p.input.replay && name !== 'staff' && !markerInstead && !(lang === 'ko' ? /재현/.test(s) : /replay/i.test(s))) v.push(`${id}: missing replay note`);
      // destination consistency: only the plan's own destination, and only when it may be named. The allowed name
      // and the origin's name are masked first (a destination name may be a substring of the allowed one).
      const allowed = [set.destinationName?.[lang], p.input.origin.name?.[lang]].filter((n): n is string => !!n).sort((a, b) => b.length - a.length);
      const rest = maskData(s, allowed);
      const dests = Object.values(p.input.destinations)
        .flatMap((d) => (d.name ? [d.name[lang]] : []))
        .filter((n): n is string => !!n && n.length > 1);
      for (const d of new Set(dests)) if (rest.includes(d)) v.push(`${id}: names destination "${d}" the plan does not allow`);
    }
    if (t.head.coreS > HEAD_CORE_MAX_S) v.push(`${lang}.head.core: ${t.head.coreS.toFixed(1)} s > ${HEAD_CORE_MAX_S} s`);
    if (t.head.fullS > HEAD_FULL_MAX_S) v.push(`${lang}.head: ${t.head.fullS.toFixed(1)} s > ${HEAD_FULL_MAX_S} s`);
    const missing = ELEMENTS.filter((e) => !t.head.elements.includes(e));
    if (missing.length) v.push(`${lang}.head.core: missing elements ${missing.join(',')}`);
    if (lang === 'ko') {
      const b = eucKrBytes(t.familyText);
      if (b.unencodable.length) v.push(`ko.familyText: unencodable ${b.unencodable.join('')}`);
      if (b.bytes > SMS_KO_MAX_BYTES) v.push(`ko.familyText: ${b.bytes} bytes > ${SMS_KO_MAX_BYTES}`);
    } else {
      const g = gsm7Length(t.familyText);
      if (g.nonGsm.length) v.push(`en.familyText: not GSM-7 ${g.nonGsm.join('')}`);
      if (g.chars > SMS_EN_MAX_GSM7) v.push(`en.familyText: ${g.chars} > ${SMS_EN_MAX_GSM7}`);
    }
    if (t.noOrder !== null && [...t.noOrder].length > STANDARD_MAX_CHARS) v.push(`${lang}.noOrder: ${[...t.noOrder].length} chars > ${STANDARD_MAX_CHARS}`);
    if (t.familyScript.length !== 3) v.push(`${lang}.familyScript: not three lines`);
  }
  return v;
}

// ------------------------------------------------------------------------------------------------ transport-need list

export interface Reply {
  originId: string;
  /** opaque household / contact label from the call system (never shown to residents) */
  contact: string;
  key: string;
  receivedAtIso: string;
}

export interface NeedRow {
  originId: string;
  contact: string;
  code: ReplyCode;
  kind: MessagePlan['kind'];
  /** leave-by offset (s) — only for kind leave_by */
  leaveByS: number | null;
  /** "no checked leave-by — check first" for no_route / unresolved / partial / unknown origin */
  checkFirst: boolean;
  urgencyRank: number | null;
  receivedAtIso: string;
}

/**
 * Staff list of replies that need follow-up (key 2, and unknown keys — flagged), ordered: origins WITHOUT a checked
 * leave-by first (no_route, unresolved, partial, or an origin with no plan), then leave_by ascending by T; ties by the
 * planner's urgency rank, then reply time, then contact. Unresolved is never treated as "later".
 */
export function transportNeedList(replies: Reply[], plans: Record<string, MessagePlan>): NeedRow[] {
  const rows: NeedRow[] = [];
  for (const r of replies) {
    const p = plans[r.originId];
    const kind = p?.kind ?? 'unresolved';
    const code = replyCode(kind, r.key.trim());
    if (code !== 'needs_help' && code !== 'unknown') continue;
    const leaveByS = p && p.kind === 'leave_by' ? p.leaveByS : null;
    rows.push({ originId: r.originId, contact: r.contact, code, kind, leaveByS, checkFirst: leaveByS === null, urgencyRank: p?.input.urgencyRank ?? null, receivedAtIso: r.receivedAtIso });
  }
  const inf = Number.POSITIVE_INFINITY;
  return rows.sort(
    (a, b) =>
      Number(b.checkFirst) - Number(a.checkFirst) ||
      (a.leaveByS ?? -inf) - (b.leaveByS ?? -inf) ||
      (a.urgencyRank ?? inf) - (b.urgencyRank ?? inf) ||
      a.receivedAtIso.localeCompare(b.receivedAtIso) ||
      a.contact.localeCompare(b.contact),
  );
}
