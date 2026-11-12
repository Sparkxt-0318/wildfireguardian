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
import { FORBIDDEN, MODEL_NOT_LIVE, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS, MODEL_NOT_LIVE_SMS, NOT_REAL, DEPARTURE_INSTRUCTION, RESIDENT_119_NOW } from '../strings';
import { clockTimes, maskData } from '../checks';
import { eucKrBytes, gsm7Length, spokenSeconds, SMS_KO_MAX_BYTES, SMS_EN_MAX_GSM7 } from '../encoding';
import { enSpokenTime, hm, koDate, koSpokenTime, enDate, kstParts } from '../compose';
import type { MessagePlan } from '../plan';
import type { LmLang } from '../types';

export const HEAD_CORE_MAX_S = 20;
export const HEAD_FULL_MAX_S = 35;
/**
 * 안전안내문자 limit of the 2025 reform (157 CHARACTERS; 행정안전부예규 제361호 별표 labels "90자"/"157자"). Orders stay
 * at 90 characters. Kept for reference: the no-order message is a STAFF output (Iris/orchestrator scope decision), so
 * it is not sent as a 재난문자 and no 157 limit is enforced on it.
 */
export const STANDARD_MAX_CHARS = 157;
/** Slower reading rate also reported for older listeners (Iris): seconds scale by 3.0 / 2.5. */
export const SLOW_SYLLABLES_PER_S = 2.5;

/**
 * Official order status, supplied explicitly by a named person, with an expiry. Absent, malformed, not yet valid or
 * expired (relative to nowIso) => the no-order output is NOT produced; status is never inferred from silence.
 */
export interface OrderStatusInput {
  status: 'issued' | 'not_issued';
  suppliedBy: string;
  suppliedAtIso: string;
  expiresAtIso: string;
}

/**
 * F-3.1 deadline-field record for this origin (Richard, research/harness-2026-11/F-3.1/deadline_field/postprocess.py):
 * offsets in s after the input time. leaveByS null = model no-route at every departure. issueByS = leaveByS minus
 * ASSUMED alert and door-to-door latencies (sensitivity settings, not measurements); negative = already late.
 * Origin absent from the file => undefined/null here => "not computed". The field has no unresolved state.
 */
export interface IssueOrderBy {
  leaveByS: number | null;
  issueByS?: { low: number; median: number; high: number };
}

/** How a leave-by time is worded (kept variable for a later comprehension test). */
export type TimeStyle = 'clock' | 'clock_and_minutes';

export interface ChannelOptions {
  /** when the outputs are produced (ISO); the data age is measured against it */
  nowIso: string;
  orderStatus?: OrderStatusInput | null;
  issueOrderBy?: IssueOrderBy | null;
  timeStyle?: TimeStyle;
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
  /** the same at the slower 2.5 syllables/s (Korean; English is unchanged) */
  coreSlowS: number;
  fullSlowS: number;
  /** the only exportable form: opener + core + closer, inseparable */
  script: string;
}

export interface ChannelTexts {
  head: HeadScript;
  voice: string;
  familyText: string;
  familyScript: [string, string, string];
  /** staff / village-head only (never resident-facing) */
  staff: { dataAge: string; issueOrderBy: string; noOrder: string | null };
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

// ------------------------------------------------------------------------------------------------ time wording

let STYLE: TimeStyle = 'clock';
/** live data age, spoken (set per build from nowIso; empty for replays) */
let AGE_KO = '';
let AGE_EN = '';

/** Spoken leave-by time, in the selected style (the only place a spoken leave-by time is worded). */
function spokenLeaveBy(p: MessagePlan, lang: LmLang): string {
  const t = lang === 'ko' ? koSpokenTime(iso(p), p.leaveByS!) : enSpokenTime(iso(p), p.leaveByS!);
  if (STYLE === 'clock') return t;
  const m = Math.floor(p.leaveByS! / 60);
  return lang === 'ko' ? `자료 시각부터 ${m}분 뒤인 ${t}` : `${t}, ${m} minutes after the data time`;
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
    o.push(p.input.replay ? (via || test ? `${year(p)}년 기록을 ${via}재현한 ${test}자료입니다.` : `${year(p)}년 기록 재현입니다.`) : `${koSpokenTime(iso(p))} ${via ? '모의 서버 ' : ''}${test}자료이며 실시간이 아닙니다.${AGE_KO}`);
    return { opener: o.join('\n'), closer: OFFICIAL_FIRST.ko };
  }
  if (p.input.replay) o.push(NOT_REAL.en);
  o.push(p.input.replay ? `This is a replay of ${year(p)} records, not live.` : `Data from ${enSpokenTime(iso(p))}, not live.${AGE_EN}`);
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
      b.push({ text: `${spokenLeaveBy(p, 'ko')}까지 차로 출발하십시오.`, short: `${spokenLeaveBy(p, 'ko')}까지 출발하십시오.`, elements: ['time', 'guidance'] });
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
    b.push({ text: `Leave by car by ${spokenLeaveBy(p, 'en')}.`, elements: ['time', 'guidance'] });
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
  const script = [opener, core, closer].join('\n');
  const coreS = spokenSeconds(core, lang);
  const fullS = spokenSeconds(script, lang);
  const slow = lang === 'ko' ? 3.0 / SLOW_SYLLABLES_PER_S : 1;
  return { opener, core, closer, elements, coreS, fullS, coreSlowS: coreS * slow, fullSlowS: fullS * slow, script };
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
        ? `${spokenLeaveBy(p, 'ko')}까지 차로 출발하셔야 합니다${dest ? `. ${dest.ko} 쪽입니다` : ''}.`
        : p.kind === 'no_route'
          ? `${koSpokenTime(iso(p))} 자료로는 차로 나가는 확인된 길이 없습니다.`
          : `${koSpokenTime(iso(p))} 자료로는 대피 길을 확인하지 못했습니다.`;
    const l3 = `차가 없으면 이장에게 알리시고, 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오. ${OFFICIAL_FIRST.ko}`;
    return [l1, l2, l3];
  }
  const l1 = `[Name], this is a wildfire evacuation notice for ${v && /^[\x20-\x7E]+$/.test(v) ? v : 'your village'}. ${replay ? 'It is a replay of records, not a real emergency, ' : ''}from a computer forecast, not live.`;
  const l2 =
    p.kind === 'leave_by' && p.leaveByS !== null
      ? `Leave by car by ${spokenLeaveBy(p, 'en')}${dest && dest.en ? `, toward ${dest.en}` : ''}.`
      : p.kind === 'no_route'
        ? `Data from ${enSpokenTime(iso(p))} shows no checked road out by car.`
        : `Data from ${enSpokenTime(iso(p))} could not check a road out.`;
  const l3 = `No car? Tell the village head, and follow official instructions. In an emergency, report to 119. ${OFFICIAL_FIRST.en}`;
  return [l1, l2, l3];
}

// ------------------------------------------------------------------------------------------------ no order yet

/** True only for an explicit, attributed, currently valid `not_issued` status. */
export function orderNotIssued(o: OrderStatusInput | null | undefined, nowIso: string): boolean {
  if (!o || o.status !== 'not_issued' || !o.suppliedBy || !o.suppliedBy.trim()) return false;
  const now = Date.parse(nowIso), from = Date.parse(o.suppliedAtIso), to = Date.parse(o.expiresAtIso);
  return Number.isFinite(now) && Number.isFinite(from) && Number.isFinite(to) && from <= now && now < to;
}

/** Staff / village-head output (never resident-facing): "no order yet" with the planning frame and data age. */
function noOrder(p: MessagePlan, lang: LmLang, opt: ChannelOptions): string | null {
  const o = opt.orderStatus;
  if (!orderNotIssued(o, opt.nowIso)) return null;
  const v = villageName(p, lang);
  const age = dataAge(p, opt.nowIso, lang);
  if (lang === 'ko') {
    const body =
      p.kind === 'leave_by' && p.leaveByS !== null
        ? `모델 계산으로는 ${hm(iso(p), p.leaveByS)}까지 출발해야 하는 곳입니다.`
        : p.kind === 'no_route'
          ? '모델 계산으로는 확인된 대피 길이 없는 곳입니다.'
          : '모델 계산으로 확인하지 못한 곳입니다.';
    return [
      `[이장·담당자용 · ${longTag(p, 'ko')}${MODEL_NOT_LIVE.ko}]`,
      `${v ?? '이 마을'}: 아직 공식 대피 명령은 없습니다(명령 상태 입력: ${o!.suppliedBy}, ${koDate(o!.suppliedAtIso)}).`,
      body,
      '명령이 없다고 위험이 없는 것은 아닙니다.',
      age,
      OFFICIAL_FIRST.ko,
    ].join('\n');
  }
  const body =
    p.kind === 'leave_by' && p.leaveByS !== null
      ? `Model: this place must leave by ${hm(iso(p), p.leaveByS)}.`
      : p.kind === 'no_route'
        ? 'Model: no checked road out.'
        : 'Model: not checked.';
  return [
    `[For village head / staff · ${longTag(p, 'en')}${MODEL_NOT_LIVE.en}]`,
    `${v && /^[\x20-\x7E]+$/.test(v) ? v : 'This village'}: no official order yet (order status from ${o!.suppliedBy}, ${enDate(o!.suppliedAtIso)}).`,
    body,
    'No order yet is not an all-clear.',
    age,
    OFFICIAL_FIRST.en,
  ].join('\n');
}

/** Tag naming the replay and every marker. */
function longTag(p: MessagePlan, lang: LmLang): string {
  const parts = lang === 'ko'
    ? [p.input.replay ? '기록재현' : '', p.input.mock ? 'MOCK' : '', p.input.testData ? '시험자료' : '']
    : [p.input.replay ? 'REPLAY' : '', p.input.mock ? 'MOCK' : '', p.input.testData ? 'TEST' : ''];
  const t = parts.filter(Boolean).join(lang === 'ko' ? '·' : ' ');
  return t ? `${t} · ` : '';
}

// ------------------------------------------------------------------------------------------------ staff fields

export function dataAge(p: MessagePlan, nowIso: string, lang: LmLang): string {
  const t0 = iso(p);
  if (p.input.replay) return lang === 'ko' ? `자료 시각 ${koDate(t0)} · ${year(p)}년 기록 재현 자료` : `Data time ${enDate(t0)} · replay of ${year(p)} records`;
  const ageMin = Math.floor((Date.parse(nowIso) - Date.parse(t0)) / 60000);
  if (!Number.isFinite(ageMin) || ageMin < 0) return lang === 'ko' ? `자료 시각 ${koDate(t0)} · 자료 나이 확인 불가` : `Data time ${enDate(t0)} · data age unknown`;
  return lang === 'ko' ? `자료 시각 ${koDate(t0)} · ${ageMin}분 전 자료` : `Data time ${enDate(t0)} · ${ageMin} min old`;
}

export function issueOrderByText(p: MessagePlan, v: IssueOrderBy | null | undefined, lang: LmLang): string {
  const head = lang === 'ko' ? '공식 명령 발령 시한(모델 계산, 전달 지연은 가정값)' : 'Issue order by (model; delivery latencies are assumptions)';
  const none = lang === 'ko' ? `${head}: 산출되지 않음` : `${head}: not computed`;
  if (!v) return none;
  if (v.leaveByS === null) {
    // the field's model no-route; shown only when the planner agrees (never a time)
    if (p.kind !== 'no_route') return lang === 'ko' ? `${head}: 플래너 결과와 불일치 — 산출되지 않음` : `${head}: disagrees with the planner — not computed`;
    return lang === 'ko' ? `${head}: 모델상 확인된 경로 없음 — 시한 없음, 명령을 미루지 마십시오` : `${head}: no checked route in the model — no deadline; do not delay the order`;
  }
  if (p.kind !== 'leave_by' || !v.issueByS) return lang === 'ko' ? `${head}: 플래너 결과와 불일치 — 산출되지 않음` : `${head}: disagrees with the planner — not computed`;
  const show = (x: number) => (x < 0 ? (lang === 'ko' ? '이미 지남' : 'already past') : hm(iso(p), x));
  const { low, median, high } = v.issueByS;
  return lang === 'ko'
    ? `${head}: 지연 짧음 ${show(low)} · 중간 ${show(median)} · 김 ${show(high)}`
    : `${head}: short latency ${show(low)} · median ${show(median)} · long ${show(high)}`;
}

// ------------------------------------------------------------------------------------------------ assembly + checks

export function buildChannels(p: MessagePlan, opt: ChannelOptions): ChannelSet {
  const text = {} as Record<LmLang, ChannelTexts>;
  STYLE = opt.timeStyle ?? 'clock';
  const ageMin = Math.floor((Date.parse(opt.nowIso) - Date.parse(iso(p))) / 60000);
  const liveAge = !p.input.replay && Number.isFinite(ageMin) && ageMin >= 0;
  AGE_KO = liveAge ? ` ${ageMin}분 전 자료입니다.` : '';
  AGE_EN = liveAge ? ` The data is ${ageMin} minutes old.` : '';
  for (const lang of ['ko', 'en'] as LmLang[]) {
    text[lang] = {
      head: headScript(p, lang),
      voice: voice(p, lang),
      familyText: familyText(p, lang),
      familyScript: familyScript(p, lang),
      staff: { dataAge: dataAge(p, opt.nowIso, lang), issueOrderBy: issueOrderByText(p, opt.issueOrderBy, lang), noOrder: noOrder(p, lang, opt) },
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
      ['head', t.head.script],
      ['voice', t.voice],
      ['familyText', t.familyText],
      ['familyScript', t.familyScript.join('\n')],
      ['staff', `${t.staff.dataAge}\n${t.staff.issueOrderBy}`],
      ...(t.staff.noOrder !== null ? ([['staff.noOrder', t.staff.noOrder]] as [string, string][]) : []),
    ];
    for (const [name, s] of outs) {
      const id = `${lang}.${name}`;
      const masked = maskData(s, names).toLowerCase();
      for (const w of FORBIDDEN[lang]) if (masked.includes(w.toLowerCase())) v.push(`${id}: forbidden word "${w}"`);
      if (!name.startsWith('staff') && RESIDENT_119_NOW[lang].test(s)) v.push(`${id}: tells residents to call 119 now`);
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
    if (t.staff.noOrder !== null && !t.staff.noOrder.includes(MODEL_NOT_LIVE[lang])) v.push(`${lang}.staff.noOrder: missing planning-only frame`);
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
 * Staff list of replies that need follow-up (key 2, and unknown keys — flagged). SYNTHETIC households only in this
 * repository; in practice the list would be held by the 읍·면사무소 staff and the 이장 who run the call system.
 * Two sections, in the planner's own order so the kit and the planner never disagree:
 *  - topSection: places that need a human decision, not a time — model no-route, then unresolved (including origins
 *    with no plan), then partial; within each, planner urgency rank, then reply time, then contact;
 *  - byDeadline: leave_by places, ascending by T; ties by urgency rank, reply time, contact.
 */
export function transportNeedList(replies: Reply[], plans: Record<string, MessagePlan>): { topSection: NeedRow[]; byDeadline: NeedRow[] } {
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
  const KIND_ORDER: Record<string, number> = { no_route: 0, unresolved: 1, partial: 2, leave_by: 3 };
  const tie = (a: NeedRow, b: NeedRow) =>
    (a.urgencyRank ?? inf) - (b.urgencyRank ?? inf) || a.receivedAtIso.localeCompare(b.receivedAtIso) || a.contact.localeCompare(b.contact);
  const top = rows.filter((r) => r.checkFirst).sort((a, b) => KIND_ORDER[a.kind]! - KIND_ORDER[b.kind]! || tie(a, b));
  const dated = rows.filter((r) => !r.checkFirst).sort((a, b) => a.leaveByS! - b.leaveByS! || tie(a, b));
  return { topSection: top, byDeadline: dated };
}
