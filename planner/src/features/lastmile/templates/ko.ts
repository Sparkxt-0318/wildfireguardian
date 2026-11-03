/**
 * Korean source templates (현장 전달 문구). Plain, polite Korean for older listeners: short
 * sentences in 하십시오체, concrete clock times ("오후 6시 40분"), no jargon in spoken text
 * ("모델" is said as "컴퓨터 예측 계산"; the planner's labels 확인된 경로 / 모델상 경로 없음 / 미확인
 * stay in writing).
 *
 * Audiences: the SMS, the village broadcast and the family call script reach residents and
 * families, so they never tell people to call 119 now — they say "follow the official instructions
 * of the 이장 and the 읍·면사무소; in an emergency, report to 119". The long text and the card are
 * written for the 이장 / facility staff and address each audience by name. A recorded replay says so
 * first in every SMS and long text, and the broadcast opens with "이 방송은 실제 상황이 아닙니다."
 *
 * Every inserted name or time is followed only by particles that do not depend on the last syllable
 * (까지, 에, 의, 에서, 입니다), so a place name never breaks the grammar. Names are never invented:
 * an unnamed destination is "지도 자료에 이름이 없는 학교" in writing (its id only in the card's staff
 * footer) and "이름 없는 학교" when spoken.
 */
import { kstStamp } from '../../shared/format';
import { FOOTER_APP } from '../../shared/strings';
import { ENTRY_LIMIT_M } from '../../../domain/plan';
import {
  arrivalShown,
  durationText,
  distanceText,
  hm,
  kstParts,
  koDate,
  koDateSpoken,
  koSmsDate,
  koSpokenTime,
  resultSource,
  type CardContent,
  type CardLine,
  type SpokenBlock,
  type TemplateSet,
} from '../compose';
import { groupExitLabels, type LmReason } from '../explanation';
import { bigLabelKind, ENTRY_SPOKEN_MIN_M, type MessagePlan, type PlannedDestination } from '../plan';
import { MODEL_NOT_LIVE, MODEL_NOT_LIVE_SMS, MODEL_NOT_LIVE_SPOKEN, MODEL_PLAN_SPOKEN, MODEL_SMS, NOT_REAL, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS } from '../strings';

const iso = (p: MessagePlan) => p.input.scenario.inputTimeIso;

function year(p: MessagePlan): number {
  return p.input.region.fireYear ?? kstParts(iso(p)).y;
}

/** 마을 / 시설 — both end in a final consonant (이 마을은, 이 시설은). */
function placeWord(p: MessagePlan): string {
  return p.input.origin.kind === 'facility' ? '시설' : '마을';
}

const facility = (p: MessagePlan) => p.input.origin.kind === 'facility';

/** "구암리(마을)" — the category is left out when the name already says it. */
function withCategory(name: string, category: string): string {
  const n = name.replace(/\s+/g, '');
  const c = category.replace(/\s+/g, '');
  if (n.includes(c) || (c.endsWith('회관') && n.includes('회관')) || (c === '학교' && /학교|분교/.test(n))) return name;
  return `${name}(${category})`;
}

function originWritten(p: MessagePlan): string {
  const o = p.input.origin;
  return o.name ? withCategory(o.name.ko, o.category.ko) : o.display.ko;
}

/** Written destination: the OSM name, or "지도 자료에 이름이 없는 학교" (no ids for residents). */
function destWritten(d: PlannedDestination): string {
  return d.name ? withCategory(d.name.ko, d.category.ko) : `지도 자료에 이름이 없는 ${d.category.ko}`;
}

/** Spoken destination: the name, or "이름 없는 학교". */
function destSpoken(d: PlannedDestination): string {
  return d.name ? d.name.ko : `이름 없는 ${d.category.ko}`;
}

function kOfN(k: number, n: number): string {
  return k >= n ? `산불 예측 시나리오 ${n}가지 모두에서` : `산불 예측 시나리오 ${n}가지 중 ${k}가지에서`;
}

type Exits = Extract<LmReason, { kind: 'all_exits_blocked' }>;

/** At most `max` names (3 in the long text, 2 on the card), then "외"; one place's roads are merged. */
function exitNames(r: Exits, max: number): string {
  const names = groupExitLabels(r.exits).map((e) => e.ko);
  return names.length > max ? `${names.slice(0, max).join('·')} 외` : names.join('·');
}

/** Each road on its own: "길마다 … 최소 k가지에서" never reads as one scenario blocking every road. */
function exitMembers(r: Exits): string {
  if (r.roads === 1) return r.kMin >= r.n ? `산불 예측 시나리오 ${r.n}가지 모두에서` : `산불 예측 시나리오 ${r.n}가지 중 ${r.kMin}가지에서`;
  return r.kMin >= r.n ? `길마다 산불 예측 시나리오 ${r.n}가지 모두에서` : `길마다 산불 예측 시나리오 ${r.n}가지 중 최소 ${r.kMin}가지에서`;
}

/**
 * The exits of the explanation file are the roads where the area reachable by car from the entry
 * point WITHOUT meeting flames ends (tools/explain_deadlines README §4) — not the roads out of the
 * village: the first roads out of the entry point are open in most recorded cases.
 */
function exitsWritten(p: MessagePlan, r: Exits, max: number): string {
  const area = `이 ${placeWord(p)}에서 불길을 만나지 않고 차로 갈 수 있는 구역을 벗어나는 길`;
  const when = r.atStart ? '자료 시각에 이미 불길에 막혀 있습니다' : `자료 시각부터 ${durationText(p.input.scenario.horizonS, 'ko')} 안에 불길에 막힙니다`;
  if (r.roads === 1) return `이유: ${area}은 1곳(${exitNames(r, max)})뿐이며, ${when}(${exitMembers(r)}).`;
  // several roads with one label: "길 2곳(둘 다 구계리 부근 도로)이 …"
  if (r.exits.length === 1) return `이유: ${area} ${r.roads}곳(${r.roads === 2 ? '둘 다' : '모두'} ${r.exits[0]!.text.ko})이 ${when}(${exitMembers(r)}).`;
  return `이유: ${area} ${r.roads}곳(${exitNames(r, max)})이 모두 ${when}(${exitMembers(r)}).`;
}

/** Spoken (optional broadcast block): "the exits of the area one can reach avoiding the flames". */
function exitsSpoken(p: MessagePlan, r: Exits): string {
  const area = '이곳에서 불길을 피해 갈 수 있는 구역의 출구';
  const when = r.atStart ? '이미 불길에 막혀 있습니다' : `${durationText(p.input.scenario.horizonS, 'ko')} 안에 불길에 막힙니다`;
  return r.roads === 1 ? `산불 예측에서는 ${area} 1곳이 ${when}.` : `산불 예측에서는 ${area} ${r.roads}곳이 모두 ${when}.`;
}

/** First line of the SMS: date + what the data is ("[25.3.26 02:00 기록재현]"). */
function smsTag(p: MessagePlan): string {
  // both markers in as many bytes as "기록재현" (8): the tag never pushes the SMS over 90 bytes
  const word = p.input.mock && p.input.testData ? 'MOCK시험' : p.input.mock ? 'MOCK' : p.input.testData ? '시험자료' : p.input.replay ? '기록재현' : '계획자료';
  return `[${koSmsDate(iso(p))} ${word}]`;
}

/** First line of the long text. */
function lmsTag(p: MessagePlan): string {
  const parts = [p.input.mock ? 'MOCK' : null, p.input.testData ? '시험 데이터' : null, p.input.replay ? `${year(p)}년 기록 재현 · 실제 상황 아님` : '계획 자료 · 실시간 아님'];
  return `[${parts.filter(Boolean).join(' · ')}]`;
}

/** Who acts on a model_no_route result, by audience. */
function noRouteStaff(p: MessagePlan): string {
  return `${facility(p) ? '시설 담당자' : '이장'}: 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따르십시오.`;
}
function noRouteResidents(p: MessagePlan): string {
  return facility(p)
    ? '이용자·가족: 시설과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.'
    : '주민: 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.';
}
/** The model_no_route reason in writing (long text, card), or null. */
function noRouteReasonWritten(p: MessagePlan, max: number): string | null {
  const r = p.reason;
  const range = durationText(p.input.scenario.horizonS, 'ko');
  if (!r) return null;
  if (r.kind === 'all_exits_blocked') return exitsWritten(p, r, max);
  if (r.kind === 'entry_in_flame') return `이유: 산불 예측 시나리오상 이 ${placeWord(p)}의 진입 지점(가장 가까운 도로 지점)이 출발 시각에 이미 불길 안에 있습니다.`;
  // the file's claim covers the candidate shelters the planner tried, never every possible destination
  if (r.kind === 'no_route_flames') return `이유: 점검한 어느 출발 시각에도, 점검한 도착지(후보 대피소) 중 산불 예측 시나리오상 불길을 피하는 길로 ${range} 자료 범위 안에 도착해 머물 수 있는 곳이 없습니다.`;
  if (r.kind === 'no_route_time_window') return `이유: 점검한 어느 출발 시각에도, 불길이 없더라도 점검한 도착지(후보 대피소) 중 ${range} 자료 범위 안에 도착해 머물 수 있는 곳이 없습니다.`;
  return null;
}

/** The model_no_route reason, spoken (optional broadcast block; a call-script line), or null. */
function noRouteReasonSpoken(p: MessagePlan): string | null {
  const r = p.reason;
  const range = durationText(p.input.scenario.horizonS, 'ko');
  if (!r) return null;
  if (r.kind === 'all_exits_blocked') return exitsSpoken(p, r);
  if (r.kind === 'entry_in_flame') return '산불 예측에서는 이곳의 진입 지점이 이미 불길 안에 있습니다.';
  if (r.kind === 'no_route_flames') return `산불 예측에서는 점검한 도착지 중 불길을 피하는 길로 ${range} 안에 닿을 수 있는 곳이 없습니다.`;
  if (r.kind === 'no_route_time_window') return `불길이 없더라도 점검한 도착지 중 ${range} 안에 닿을 수 있는 곳이 없습니다.`;
  return null;
}
function noRouteSpoken(p: MessagePlan): string {
  return `${facility(p) ? '시설과' : '이장과'} 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.`;
}

const PARTIAL_TEXT = '출발 시각에 따라 모델 결과가 달라, 출발 시각을 하나로 안내하지 않습니다.';

/** Said wherever the time is the end of the checked range, not a fire deadline. */
const NOT_FIRE_KO = '이 시각은 불길 때문에 정한 것이 아닙니다.';

/** What limits T, in writing (long text). Never implies a fire deadline unless the explanation says so. */
function afterWritten(p: MessagePlan, T: string, card: boolean): CardLine {
  const r = p.reason;
  const t0 = iso(p);
  const range = durationText(p.input.scenario.horizonS, 'ko');
  // the explanation proves only that the NEXT checked departure fails, so the lines say exactly that
  const N = hm(t0, p.nextOffsetS ?? p.leaveByS ?? 0);
  if (r && (r.kind === 'flame_on_route' || r.kind === 'dwell_at_destination')) {
    const F = hm(t0, r.flameS);
    const tail = card ? '' : r.kind === 'flame_on_route' ? ` 다음 점검 시각인 ${N}에 출발하면 그곳에서 불길과 만날 수 있습니다.` : ` 다음 점검 시각인 ${N}에 출발하면 도착 뒤 머무는 동안 불길과 만날 수 있습니다.`;
    return {
      role: 'reason',
      text: r.kind === 'flame_on_route' ? `이유: ${kOfN(r.k, r.n)}는 ${r.road.text.ko}에 ${F}쯤 불길이 닿습니다.${tail}` : `이유: ${kOfN(r.k, r.n)}는 도착지 부근(${r.road.text.ko})에 ${F}쯤 불길이 닿습니다.${tail}`,
    };
  }
  if (r && r.kind === 'no_flame_avoiding_route') {
    return { role: 'reason', text: `이유: 다음 점검 시각인 ${N}에 출발하면 점검한 도착지(후보 대피소) 중 산불 예측 시나리오상 불길을 피하는 길로 제시간에 도착해 머물 수 있는 곳이 없습니다.` };
  }
  if (r && r.kind === 'time_window') {
    // only what is established: at the next checked time no destination checked fits the window even
    // without fire (the file), and no later departure has a checked route (the planner's sweep)
    return {
      role: 'after',
      text: `다음 점검 시각인 ${N}에 출발하면 불길이 없더라도 점검한 도착지 중 ${range} 자료 범위 안에 도착해 머물 수 있는 곳이 없습니다. ${T}보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다. ${NOT_FIRE_KO}`,
    };
  }
  if (p.after === 'horizon') {
    return card
      ? { role: 'after', text: `그 뒤 출발은 점검하지 않았습니다(자료 범위 ${range}). ${NOT_FIRE_KO}` }
      : { role: 'after', text: `모델이 점검한 마지막 출발 시각이 ${T}입니다. 그보다 늦은 출발은 점검하지 않았습니다(자료 범위: 자료 시각부터 ${range}). ${NOT_FIRE_KO}` };
  }
  if (p.after === 'gap') return { role: 'after', text: `${T} 이후에는 확인되지 않은 출발 시각이 있어, 이 안내는 ${T}까지의 출발만 다룹니다.` };
  return { role: 'after', text: `${T}보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.` };
}

/** The same, spoken (optional block of the broadcast; a line of the call script). */
function afterSpoken(p: MessagePlan): string {
  const r = p.reason;
  const t0 = iso(p);
  if (r && r.kind === 'flame_on_route') return `${kOfN(r.k, r.n)}는 ${r.road.text.ko}에 ${koSpokenTime(t0, r.flameS)}쯤 불길이 닿습니다.`;
  if (r && r.kind === 'dwell_at_destination') return `${kOfN(r.k, r.n)}는 도착지 부근에 ${koSpokenTime(t0, r.flameS)}쯤 불길이 닿습니다.`;
  if (r && r.kind === 'no_flame_avoiding_route') {
    return `다음 점검 시각인 ${koSpokenTime(t0, p.nextOffsetS ?? p.leaveByS ?? 0)}에 출발하면 점검한 도착지 중 산불 예측상 불길을 피하는 길로 제시간에 닿을 수 있는 곳이 없습니다.`;
  }
  if (r && r.kind === 'time_window') return `그보다 늦게 출발하는 길은 확인되지 않았습니다. ${NOT_FIRE_KO}`;
  if (p.after === 'horizon') return `그 뒤 출발은 점검하지 않았습니다. ${NOT_FIRE_KO}`;
  if (p.after === 'gap') return '그 뒤에는 확인되지 않은 출발 시각이 있습니다.';
  return '그보다 늦게 출발하는 길은 확인되지 않았습니다.';
}

function entryNote(p: MessagePlan): string {
  const dist = p.input.origin.entryDistanceM;
  return dist !== null && dist >= 1
    ? `시각은 ${placeWord(p)}에서 ${distanceText(dist)} 떨어진 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.`
    : '시각은 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.';
}

function carlessWritten(p: MessagePlan): string {
  return facility(p) ? '이용자를 옮길 차가 부족하면 읍·면사무소에 바로 알리십시오.' : '차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.';
}

/** Body lines of the long text (LMS) and of the non-leave-by card. */
function bodyLines(p: MessagePlan, target: 'lms' | 'card'): CardLine[] {
  const out: CardLine[] = [];
  const t0 = iso(p);
  if (p.kind === 'leave_by' && p.leaveByS !== null) {
    const T = hm(t0, p.leaveByS);
    out.push({ role: 'instruction', text: `${T}(${koSpokenTime(t0, p.leaveByS)})까지 차로 출발하십시오. 이 시각까지 기다리지 마십시오.` });
    const d = p.destination;
    if (d) {
      if (p.destinationVaries) {
        out.push({ role: 'destination', text: `도착지는 출발 시각에 따라 다릅니다. ${T}에 출발할 때 모델이 점검한 도착지: ${destWritten(d)}.` });
      } else if (d.arrivalS !== null && d.arrivalS > p.leaveByS) {
        const a = arrivalShown(t0, p.leaveByS, d.arrivalS);
        out.push({ role: 'destination', text: `모델이 점검한 도착지: ${destWritten(d)}. ${T}에 출발하면 ${a.hm}쯤 도착합니다(차로 약 ${a.min}분, 교통 정체 미반영).` });
      } else {
        out.push({ role: 'destination', text: `모델이 점검한 도착지: ${destWritten(d)}.` });
      }
    }
    out.push(afterWritten(p, T, false));
    out.push({ role: 'guide', text: '실제 대피 장소와 길은 공식 안내를 따르십시오.' });
    out.push({ role: 'note', text: carlessWritten(p) });
    out.push({ role: 'note', text: entryNote(p) });
    return out;
  }
  if (p.kind === 'no_route') {
    if (target === 'lms') out.push({ role: 'status', text: '모델상 확인된 차량 경로가 없습니다.' });
    out.push({ role: 'instruction', text: noRouteStaff(p) });
    out.push({ role: 'instruction', text: noRouteResidents(p) });
    const why = noRouteReasonWritten(p, target === 'card' ? 2 : 3);
    if (why) out.push({ role: 'reason', text: why });
    if (target === 'card') out.push({ role: 'meaning', text: '모델상 경로 없음: 점검한 모든 출발 시각과 도착지에서 확인된 경로가 없었다는 뜻입니다.' });
    return out;
  }
  if (p.kind === 'partial') {
    if (target === 'lms') out.push({ role: 'status', text: PARTIAL_TEXT });
    out.push({ role: 'instruction', text: '공식 대피 안내를 따르십시오.' });
    if (target === 'card') out.push({ role: 'note', text: '출발 시각별 결과는 사전 대피계획서에서 확인하십시오.' });
    return out;
  }
  // unresolved
  if (target === 'lms') out.push({ role: 'status', text: '모델로 차량 경로를 확인하지 못했습니다(미확인).' });
  out.push({ role: 'meaning', text: '미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.' });
  out.push({ role: 'instruction', text: '공식 대피 안내를 따르십시오.' });
  const note = p.input.plan?.note ?? (p.input.plan ? null : 'not_computed');
  if (note === 'not_checkable') out.push({ role: 'note', text: `이 ${placeWord(p)}은 ${ENTRY_LIMIT_M / 1000} km 안에 점검할 수 있는 도로 지점이 없어 점검하지 않았습니다.` });
  else if (note === 'rejected') out.push({ role: 'note', text: '계산 요청이 거부되어 점검하지 못했습니다.' });
  else if (note === 'not_computed') out.push({ role: 'note', text: '이 출발지는 아직 계산하지 않았습니다.' });
  return out;
}

/**
 * The card's leave-by lines: the same facts as the long text in fewer words (the card shows the
 * time in large type above them), so one A5 page holds them at 14 pt.
 */
function leaveByCardLines(p: MessagePlan): CardLine[] {
  const out: CardLine[] = [];
  const t0 = iso(p);
  if (p.leaveByS === null) return out;
  const T = hm(t0, p.leaveByS);
  out.push({ role: 'instruction', text: '이 시각까지 기다리지 말고 미리 차로 출발하십시오.' });
  const d = p.destination;
  if (d) {
    if (p.destinationVaries) out.push({ role: 'destination', text: `도착지는 출발 시각에 따라 다릅니다. ${T} 출발 때 모델이 점검한 도착지: ${destWritten(d)}` });
    else if (d.arrivalS !== null && d.arrivalS > p.leaveByS) {
      const a = arrivalShown(t0, p.leaveByS, d.arrivalS);
      out.push({ role: 'destination', text: `모델이 점검한 도착지: ${destWritten(d)} · ${T} 출발 시 ${a.hm}쯤 도착(차로 약 ${a.min}분, 교통 정체 미반영)` });
    } else out.push({ role: 'destination', text: `모델이 점검한 도착지: ${destWritten(d)}` });
  }
  out.push(afterWritten(p, T, true));
  out.push({ role: 'guide', text: `실제 대피 장소와 길은 공식 안내를 따르십시오. ${carlessWritten(p)}` });
  return out;
}

/** Card limitations; a leave-by card starts with what its times refer to (the entry point). */
function cardLimits(p: MessagePlan): string {
  const base = '차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전';
  if (p.kind !== 'leave_by') return base;
  const dist = p.input.origin.entryDistanceM;
  const entry =
    dist !== null && dist >= 1
      ? `시각은 ${placeWord(p)}에서 ${distanceText(dist)} 떨어진 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외`
      : '시각은 가장 가까운 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외';
  return `${entry} · ${base}`;
}

function closingNotes(p: MessagePlan): string[] {
  const out: string[] = [];
  if (p.input.replay) out.push(`${year(p)}년 실제 산불 기록을 재현한 시나리오입니다.`);
  if (p.input.mock) out.push('MOCK: 모의 서버가 기록 결과를 재생한 자료입니다.');
  if (p.input.testData) out.push(testDataNote(p));
  return out;
}

/**
 * Why the result is marked test data (per origin: a cache made elsewhere, or a live result's host).
 * Names only the hosts that are not the evaluated host (provenance.testHost).
 */
function testDataNote(p: MessagePlan): string {
  const v = p.input.provenance;
  if (v.source === 'cache') return v.computed ? '시험 데이터: 평가 호스트가 아닌 장비에서 계산한 결과입니다.' : '시험 데이터: 평가 호스트가 아닌 장비에서 만든 캐시입니다.';
  if (!v.host) return '시험 데이터: 계산 호스트를 알 수 없어 평가 호스트의 결과로 보지 않습니다.';
  const other = v.testHost === undefined ? v.host : v.testHost;
  if (!other) return '시험 데이터: 일부 결과의 계산 호스트를 알 수 없어 평가 호스트의 결과로 보지 않습니다.';
  return other.ko === v.host.ko
    ? `시험 데이터: 평가 호스트가 아닌 장비(${other.ko})에서 API로 계산한 결과입니다.`
    : `시험 데이터: 평가 호스트가 아닌 장비(${other.ko})에서 API로 계산한 결과가 섞여 있습니다.`;
}

const STATUS: Record<MessagePlan['kind'], string> = {
  leave_by: '모델로 확인된 차량 경로 있음',
  no_route: '모델상 확인된 차량 경로 없음',
  unresolved: '미확인: 모델로 확인하지 못함',
  partial: '부분 확인: 출발 시각마다 결과가 다름',
};

/**
 * "{lead}2025년 3월 26일 새벽 2시 (산불) 기록을 재현한 모델 기반 계획 정보입니다." (+ MOCK / test
 * notes); not a replay: "… 자료로 만든 모델 기반 계획 정보이며, 실시간 정보가 아닙니다."
 */
function dataSentence(p: MessagePlan, lead: string, fire: boolean): string {
  const t0 = iso(p);
  const core = p.input.replay
    ? `${lead}${koDateSpoken(t0)} ${fire ? '산불 ' : ''}기록을 재현한 ${MODEL_PLAN_SPOKEN.ko}입니다.`
    : `${lead}${koDateSpoken(t0)} 자료로 만든 ${MODEL_NOT_LIVE_SPOKEN.ko}.`;
  return core + (p.input.mock ? ' 모의 서버 자료입니다.' : '') + (p.input.testData ? ' 시험용 계산 자료입니다.' : '');
}

/**
 * The broadcast's data sentence. With a MOCK / test-data marker it has a shorter wording that
 * keeps every marker inside the sentence ("…기록을 모의 서버로 재현한 시험용 모델 기반 계획
 * 정보입니다."), so a marker never pushes a real origin's broadcast over its time budget.
 */
function dataBlock(p: MessagePlan): SpokenBlock {
  const text = dataSentence(p, '', false);
  if (!p.input.replay || (!p.input.mock && !p.input.testData)) return { text };
  const via = p.input.mock ? '모의 서버로 ' : '';
  const test = p.input.testData ? '시험용 ' : '';
  return { text, short: `${koDateSpoken(iso(p))} 기록을 ${via}재현한 ${test}${MODEL_PLAN_SPOKEN.ko}입니다.` };
}

export const KO: TemplateSet = {
  lang: 'ko',

  sms(p) {
    const lines: string[] = [smsTag(p)];
    const notLive = MODEL_NOT_LIVE_SMS.ko;
    const m = MODEL_SMS.ko;
    if (p.kind === 'leave_by' && p.leaveByS !== null) lines.push(`${m}상 ${hm(iso(p), p.leaveByS)}까지 차로 출발`, `${OFFICIAL_FIRST_SMS.ko}·${notLive}`);
    else if (p.kind === 'no_route') lines.push(`${m}상 경로 없음·${notLive}`, `${OFFICIAL_FIRST_SMS.ko}, 위급 시 119`);
    else if (p.kind === 'partial') lines.push(`${m} 부분 확인·${notLive}`, `${OFFICIAL_FIRST_SMS.ko}·공식안내 따르십시오`);
    else lines.push(`${m} 경로 미확인·${notLive}`, `${OFFICIAL_FIRST_SMS.ko}·공식안내 따르십시오`);
    return lines.join('\n');
  },

  lms(p) {
    return [
      lmsTag(p),
      `산불 대피 계획 정보 · ${originWritten(p)}`,
      `자료 기준: ${koDate(iso(p))} (한국 시각) · ${resultSource(p.input, 'ko')}`,
      '',
      ...bodyLines(p, 'lms').map((l) => `■ ${l.text}`),
      '',
      OFFICIAL_FIRST.ko,
      MODEL_NOT_LIVE.ko,
      ...closingNotes(p),
      FOOTER_APP.ko,
    ].join('\n');
  },

  broadcastBlocks(p) {
    const t0 = iso(p);
    const o = p.input.origin;
    const blocks: SpokenBlock[] = [];
    if (p.input.replay) blocks.push({ text: NOT_REAL.ko });
    // a long place name is the last thing dropped (the written outputs carry it)
    blocks.push(
      o.name && o.kind === 'facility'
        ? { text: `${o.name.ko} 직원과 이용자 여러분께 알려 드립니다.`, short: `${o.name.ko} 여러분께 알려 드립니다.`, shortest: '여러분께 알려 드립니다.' }
        : o.name
          ? { text: `${o.name.ko} 주민 여러분께 알려 드립니다.`, shortest: '주민 여러분께 알려 드립니다.' }
          : { text: '주민 여러분께 알려 드립니다.' },
    );
    blocks.push(dataBlock(p));
    const repeat: SpokenBlock | null = p.input.replay ? { optional: 'repeat', text: `다시 알려 드립니다. 실제 상황이 아닌 ${year(p)}년 기록 재현입니다.` } : null;
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = koSpokenTime(t0, p.leaveByS);
      blocks.push({
        text:
          p.destination && !p.destinationVaries
            ? `${S}까지 차로 출발하십시오. ${destSpoken(p.destination)}까지 가는 길이 컴퓨터 예측 계산으로 확인되었습니다.`
            : `${S}까지 차로 출발하십시오. 그때까지 출발하는 길이 컴퓨터 예측 계산으로 확인되었습니다.`,
        short: `${S}까지 차로 출발하십시오. 그때까지 출발하는 길이 컴퓨터 예측으로 확인되었습니다.`,
      });
      const dist = o.entryDistanceM;
      if (dist !== null && dist > ENTRY_SPOKEN_MIN_M) {
        blocks.push({ text: `시각은 ${placeWord(p)}에서 ${distanceText(dist)} 떨어진 도로 기준입니다.`, short: `시각은 ${distanceText(dist)} 떨어진 도로 기준입니다.` });
      }
      blocks.push({ text: o.kind === 'facility' ? '차가 부족하면 읍·면사무소에 바로 알리십시오.' : '차가 없는 분은 이장에게 바로 알리십시오.' });
      blocks.push({ text: '대피 장소는 공식 안내를 따르십시오.' });
      blocks.push({ optional: 'reason', text: afterSpoken(p) });
      blocks.push(repeat ?? { optional: 'repeat', text: `다시 알려 드립니다. ${S}까지 출발하십시오.` });
    } else if (p.kind === 'no_route') {
      blocks.push({ text: `컴퓨터 예측 계산으로는 이곳에서 차로 나가는 확인된 길이 없습니다. ${noRouteSpoken(p)}` });
      const why = noRouteReasonSpoken(p);
      if (why) blocks.push({ optional: 'reason', text: why });
      blocks.push(repeat ?? { optional: 'repeat', text: `다시 알려 드립니다. ${noRouteSpoken(p)}` });
    } else if (p.kind === 'partial') {
      blocks.push({ text: '출발 시각에 따라 컴퓨터 예측 계산 결과가 달라, 출발 시각을 하나로 알려 드리지 않습니다. 공식 대피 안내를 따르십시오.' });
      blocks.push(repeat ?? { optional: 'repeat', text: '다시 알려 드립니다. 공식 대피 안내를 따르십시오.' });
    } else {
      blocks.push({ text: '컴퓨터 예측 계산으로는 이곳의 차량 대피 길을 확인하지 못했습니다. 길이 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따르십시오.' });
      blocks.push(repeat ?? { optional: 'repeat', text: '다시 알려 드립니다. 공식 대피 안내를 따르십시오.' });
    }
    blocks.push({ text: OFFICIAL_FIRST.ko });
    return blocks;
  },

  call(p) {
    const t0 = iso(p);
    const o = p.input.origin;
    const place = placeWord(p);
    const lines: string[] = [];
    lines.push(`[통화 전 확인] ${OFFICIAL_FIRST.ko} 아래 내용은 ${MODEL_NOT_LIVE_SPOKEN.ko}. [ ] 안은 직접 채워 말하십시오.`);
    if (p.kind === 'no_route') lines.push(`[통화 전 확인] ${facility(p) ? '시설' : '이장'}이 119와 읍·면사무소에 먼저 연락했는지 확인하십시오.`);
    if (o.name && o.kind === 'facility') {
      lines.push(`안녕하세요. ${o.name.ko}의 [직원 이름]입니다. [어르신 성함] 보호자님께 산불 대피 계획을 알려 드리려고 전화드렸습니다.`);
    } else if (o.name && o.kind === 'village') {
      lines.push(`안녕하세요. [소속·이름]입니다. ${o.name.ko}에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.`);
    } else {
      lines.push('안녕하세요. [소속·이름]입니다. [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.');
    }
    lines.push(dataSentence(p, p.input.replay ? '지금 드리는 내용은 실제 상황이 아니라, ' : '지금 드리는 내용은 ', true));
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = koSpokenTime(t0, p.leaveByS);
      const dist = o.entryDistanceM;
      const from = dist !== null && dist > ENTRY_SPOKEN_MIN_M ? `${place}에서 ${distanceText(dist)} 떨어진 도로에서` : `${place} 근처 도로에서`;
      lines.push(
        p.destination && !p.destinationVaries
          ? `컴퓨터 예측 계산(모델)으로는 ${from} ${S}까지 차로 출발하면 ${destSpoken(p.destination)}까지 가는 경로가 확인되었습니다.`
          : `컴퓨터 예측 계산(모델)으로는 ${from} ${S}까지 차로 출발하는 경로가 확인되었습니다. 도착지는 출발 시각에 따라 다릅니다.`,
      );
      lines.push(afterSpoken(p));
      if (o.kind === 'village') lines.push('어르신께서 차가 없거나 혼자 움직이기 어려우시면 이장이나 읍·면사무소에 바로 알려 주십시오.');
    } else if (p.kind === 'no_route') {
      lines.push(`컴퓨터 예측 계산(모델)으로는 ${place}에서 차로 나가는 확인된 경로가 없었습니다. 이런 결과라면 ${facility(p) ? '시설' : '이장'}은 바로 119와 읍·면사무소에 연락해 공식 지시를 따라야 합니다.`);
      const why = noRouteReasonSpoken(p);
      if (why) lines.push(why);
      // what the family itself is told (as in the broadcast): follow official instructions; 119 in an emergency
      lines.push(noRouteSpoken(p));
    } else if (p.kind === 'partial') {
      lines.push('출발 시각에 따라 컴퓨터 예측 계산 결과가 달라, 출발 시각을 하나로 알려 드리지 않습니다. 공식 대피 안내를 따라야 합니다.');
    } else {
      lines.push(`컴퓨터 예측 계산(모델)으로는 ${place}의 차량 대피 경로를 확인하지 못했습니다(미확인). 경로가 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따라야 합니다.`);
    }
    lines.push(`${OFFICIAL_FIRST.ko} 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.`);
    lines.push('궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.');
    return lines.join('\n');
  },

  card(p): CardContent {
    const t0 = iso(p);
    const o = p.input.origin;
    const badges: string[] = [];
    if (p.input.replay) badges.push('실제 상황 아님');
    if (p.input.mock) badges.push('MOCK');
    if (p.input.testData) badges.push('시험 데이터 · 평가 호스트 아님');
    const d = p.destination;
    return {
      lang: 'ko',
      docTitle: '산불 대피 계획 카드',
      regionName: p.input.region.name.ko,
      fireInputLabel: p.input.fireInputLabel.ko,
      badges,
      title: o.name ? o.name.ko : o.display.ko,
      category: o.name ? o.category.ko : null,
      statusIcon: p.kind === 'leave_by' ? 'checked_route' : p.kind === 'no_route' ? 'model_no_route' : 'unresolved',
      statusText: STATUS[p.kind],
      big:
        p.kind === 'leave_by' && p.leaveByS !== null
          ? { label: bigLabelKind(p) === 'last_checked' ? '점검한 마지막 출발' : '출발 마감', time: hm(t0, p.leaveByS), sub: `${koSpokenTime(t0, p.leaveByS)} · 한국 시각` }
          : null,
      lines: p.kind === 'leave_by' ? leaveByCardLines(p) : bodyLines(p, 'card'),
      official: OFFICIAL_FIRST.ko,
      dataLine: `자료 기준: ${koDate(t0)} (한국 시각)${p.input.replay ? ` · ${year(p)}년 실제 산불 기록을 재현한 시나리오` : ''}`,
      modelLine: MODEL_NOT_LIVE.ko,
      limits: cardLimits(p),
      footer: FOOTER_APP.ko,
      meta: [
        `시나리오 ${p.input.scenario.scenarioSetId}`,
        `작성 ${kstStamp(p.input.generatedAtIso)}`,
        // per origin: the cache's created time, or this session's API checks and their compute host — never mixed up
        resultSource(p.input, 'ko'),
        p.kind === 'leave_by' && d && !d.name ? `도착지 ID ${d.id}` : null,
      ]
        .filter(Boolean)
        .join(' · '),
    };
  },
};
