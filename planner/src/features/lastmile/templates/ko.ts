/**
 * Korean source templates (현장 전달 문구). Plain, polite Korean for older listeners: short
 * sentences, 합쇼체 for notices, concrete clock times ("오후 6시 40분"), no jargon (the planner's
 * own labels: 확인된 경로 / 모델상 경로 없음 / 미확인).
 *
 * Every inserted name is followed only by particles that do not depend on the last syllable
 * (까지, 에, 의, 에서), so a place name never breaks the grammar. Names are never invented: an
 * unnamed place keeps the planner's descriptor ("이름 없는 마을 · node 1") in writing and is
 * left out of spoken greetings.
 */
import { kstStamp } from '../../shared/format';
import { FOOTER_APP } from '../../shared/strings';
import { ENTRY_LIMIT_M } from '../../../domain/plan';
import {
  durationText,
  distanceText,
  hm,
  kstParts,
  koDate,
  koDateSpoken,
  koSmsDate,
  koSpokenTime,
  type CardContent,
  type CardLine,
  type SpokenBlock,
  type TemplateSet,
} from '../compose';
import type { LmReason } from '../explanation';
import type { MessagePlan, PlannedDestination } from '../plan';
import { MODEL_NOT_LIVE, MODEL_NOT_LIVE_SMS, MODEL_NOT_LIVE_SPOKEN, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS } from '../strings';

const iso = (p: MessagePlan) => p.input.scenario.inputTimeIso;

function year(p: MessagePlan): number {
  return p.input.region.fireYear ?? kstParts(iso(p)).y;
}

/** 마을 / 시설 / 출발 지점 — all end in a final consonant (이 마을은, 이 시설은, 이 출발 지점은). */
function placeWord(p: MessagePlan): string {
  const k = p.input.origin.kind;
  return k === 'facility' ? '시설' : k === 'research' ? '출발 지점' : '마을';
}

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

function destWritten(d: PlannedDestination): string {
  return d.name ? withCategory(d.name.ko, d.category.ko) : d.display.ko;
}

/** Spoken destination: the name, or "이름 없는 학교" (an id is not read aloud). */
function destSpoken(d: PlannedDestination): string {
  return d.name ? d.name.ko : `이름 없는 ${d.category.ko}`;
}

function kOfN(k: number, n: number): string {
  return k >= n ? `산불 예측 시나리오 ${n}가지 모두에서` : `산불 예측 시나리오 ${n}가지 중 ${k}가지에서`;
}

function exitNames(r: Extract<LmReason, { kind: 'all_exits_blocked' }>): string {
  const names = r.exits.map((e) => e.text.ko);
  return names.length > 3 ? `${names.slice(0, 3).join('·')} 외 ${names.length - 3}곳` : names.join('·');
}

function membersNote(r: Extract<LmReason, { kind: 'all_exits_blocked' }>): string {
  return r.kMin >= r.n ? `예측 시나리오 ${r.n}가지 모두` : `예측 시나리오 ${r.n}가지 중 최소 ${r.kMin}가지`;
}

function smsTail(p: MessagePlan): string {
  const word = p.input.mock ? 'MOCK' : p.input.testData ? '시험' : p.input.replay ? '재현' : '자료';
  return `${koSmsDate(iso(p))} ${word}`;
}

/** Body lines shared by the long text (LMS) and the card. */
function bodyLines(p: MessagePlan, target: 'lms' | 'card'): CardLine[] {
  const out: CardLine[] = [];
  const t0 = iso(p);
  const place = placeWord(p);
  if (p.kind === 'leave_by' && p.leaveByS !== null) {
    const T = hm(t0, p.leaveByS);
    out.push({ role: 'instruction', text: `${T}(${koSpokenTime(t0, p.leaveByS)})까지 차로 출발하십시오. 마감 시각까지 기다리지 마십시오.` });
    const d = p.destination;
    if (d) {
      if (p.destinationVaries) {
        out.push({ role: 'destination', text: `도착지는 출발 시각에 따라 다릅니다. ${T}에 출발할 때 모델이 점검한 도착지: ${destWritten(d)}.` });
      } else if (d.arrivalS !== null && d.arrivalS >= p.leaveByS) {
        const min = Math.max(1, Math.round((d.arrivalS - p.leaveByS) / 60));
        out.push({
          role: 'destination',
          text: `모델이 점검한 도착지: ${destWritten(d)}. ${T}에 출발하면 ${hm(t0, d.arrivalS)}쯤 도착합니다(차로 약 ${min}분, 교통 정체 미반영).`,
        });
      } else {
        out.push({ role: 'destination', text: `모델이 점검한 도착지: ${destWritten(d)}.` });
      }
    }
    const r = p.reason;
    if (r && (r.kind === 'flame_on_route' || r.kind === 'dwell_at_destination')) {
      const F = hm(t0, r.flameS);
      out.push({
        role: 'reason',
        text:
          r.kind === 'flame_on_route'
            ? `이유: ${kOfN(r.k, r.n)} ${r.road.text.ko}에 ${F}쯤 불길이 닿습니다. ${T}보다 늦게 출발하면 그곳에서 불길과 만날 수 있습니다.`
            : `이유: ${kOfN(r.k, r.n)} 도착지 부근(${r.road.text.ko})에 ${F}쯤 불길이 닿습니다. ${T}보다 늦게 출발하면 도착 뒤 머무는 동안 불길과 만날 수 있습니다.`,
      });
    } else if (p.after === 'horizon') {
      out.push({ role: 'after', text: `${T}보다 늦은 출발은 이 자료로 점검하지 않았습니다(자료 시각부터 ${durationText(p.input.scenario.horizonS, 'ko')}까지만 점검).` });
    } else if (p.after === 'gap') {
      out.push({ role: 'after', text: `${T} 이후에는 확인되지 않은 출발 시각이 있어, 이 안내는 ${T}까지의 출발만 다룹니다.` });
    } else {
      out.push({ role: 'after', text: `${T}보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.` });
    }
    out.push({ role: 'guide', text: '실제 대피 장소와 길은 공식 안내를 따르십시오.' });
    out.push({
      role: 'note',
      text:
        p.input.origin.kind === 'facility'
          ? '이용자를 옮길 차가 부족하면 읍·면사무소에 바로 알리십시오.'
          : '차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.',
    });
    const dist = p.input.origin.entryDistanceM;
    out.push({
      role: 'note',
      text:
        dist !== null && dist >= 1 && p.input.origin.kind !== 'research'
          ? `시각은 ${place}에서 ${distanceText(dist)} 떨어진 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.`
          : '시각은 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.',
    });
    return out;
  }
  if (p.kind === 'no_route') {
    out.push({ role: 'status', text: '모델상 확인된 차량 경로가 없습니다.' });
    out.push({ role: 'instruction', text: '지금 바로 119 또는 읍·면사무소에 연락하고 공식 지시를 따르십시오.' });
    const r = p.reason;
    if (r && r.kind === 'all_exits_blocked') {
      out.push({
        role: 'reason',
        text: `이유: 산불 예측에서는 ${place}에서 나가는 도로 ${r.exits.length}곳(${exitNames(r)}) 모두에 자료 시각부터 ${durationText(p.input.scenario.horizonS, 'ko')} 안에 불길이 닿습니다(${membersNote(r)}).`,
      });
    }
    if (target === 'card') out.push({ role: 'meaning', text: '모델상 경로 없음: 점검한 모든 출발 시각과 도착지에서 확인된 경로가 없었다는 뜻입니다.' });
    return out;
  }
  if (p.kind === 'partial') {
    out.push({ role: 'status', text: `출발 시각에 따라 모델 결과가 다르고, 자료 시각(${hm(t0)})에 바로 출발하는 경로는 확인되지 않았습니다.` });
    out.push({ role: 'instruction', text: '공식 대피 안내를 따르십시오.' });
    if (target === 'card') out.push({ role: 'note', text: '출발 시각별 결과는 사전 대피계획서에서 확인하십시오.' });
    return out;
  }
  // unresolved
  out.push({ role: 'status', text: '모델로 차량 경로를 확인하지 못했습니다(미확인).' });
  out.push({ role: 'meaning', text: '미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.' });
  out.push({ role: 'instruction', text: '공식 대피 안내를 따르십시오.' });
  const note = p.input.plan?.note ?? (p.input.plan ? null : 'not_computed');
  if (note === 'not_checkable') out.push({ role: 'note', text: `이 ${place}은 ${ENTRY_LIMIT_M / 1000} km 안에 점검할 수 있는 도로 지점이 없어 점검하지 않았습니다.` });
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
  out.push({ role: 'instruction', text: '마감 시각까지 기다리지 말고 미리 차로 출발하십시오.' });
  const d = p.destination;
  if (d) {
    if (p.destinationVaries) out.push({ role: 'destination', text: `도착지는 출발 시각에 따라 다릅니다. ${T} 출발 때 모델이 점검한 도착지: ${destWritten(d)}` });
    else if (d.arrivalS !== null && d.arrivalS >= p.leaveByS) {
      const min = Math.max(1, Math.round((d.arrivalS - p.leaveByS) / 60));
      out.push({ role: 'destination', text: `모델이 점검한 도착지: ${destWritten(d)} · ${T} 출발 시 ${hm(t0, d.arrivalS)}쯤 도착(차로 약 ${min}분, 교통 정체 미반영)` });
    } else out.push({ role: 'destination', text: `모델이 점검한 도착지: ${destWritten(d)}` });
  }
  const r = p.reason;
  if (r && (r.kind === 'flame_on_route' || r.kind === 'dwell_at_destination')) {
    const F = hm(t0, r.flameS);
    // the large leave-by time above says "not later"; the card states where and when flames reach
    out.push({
      role: 'reason',
      text:
        r.kind === 'flame_on_route'
          ? `이유: ${kOfN(r.k, r.n)} ${r.road.text.ko}에 ${F}쯤 불길이 닿습니다.`
          : `이유: ${kOfN(r.k, r.n)} 도착지 부근(${r.road.text.ko})에 ${F}쯤 불길이 닿습니다.`,
    });
  } else if (p.after === 'horizon') {
    out.push({ role: 'after', text: `${T} 이후 출발은 점검하지 않았습니다(자료 시각부터 ${durationText(p.input.scenario.horizonS, 'ko')}까지만 점검).` });
  } else if (p.after === 'gap') {
    out.push({ role: 'after', text: `${T} 이후에는 확인되지 않은 출발 시각이 있어 ${T}까지만 안내합니다.` });
  } else {
    out.push({ role: 'after', text: `${T} 이후 출발은 모델로 확인된 경로가 없습니다.` });
  }
  out.push({
    role: 'guide',
    text:
      '실제 대피 장소와 길은 공식 안내를 따르십시오. ' +
      (p.input.origin.kind === 'facility' ? '이용자를 옮길 차가 부족하면 읍·면사무소에 바로 알리십시오.' : '차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.'),
  });
  return out;
}

/** Card limitations; a leave-by card starts with what its times refer to (the entry point). */
function cardLimits(p: MessagePlan): string {
  const base = '차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전';
  if (p.kind !== 'leave_by') return base;
  const dist = p.input.origin.entryDistanceM;
  const entry =
    dist !== null && dist >= 1 && p.input.origin.kind !== 'research'
      ? `시각은 ${placeWord(p)}에서 ${distanceText(dist)} 떨어진 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외`
      : '시각은 가장 가까운 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외';
  return `${entry} · ${base}`;
}

function closingNotes(p: MessagePlan): string[] {
  const out: string[] = [];
  if (p.input.replay) out.push(`${year(p)}년 실제 산불 기록을 재현한 시나리오입니다.`);
  if (p.input.mock) out.push('MOCK: 모의 서버가 기록 결과를 재생한 자료입니다.');
  if (p.input.testData) out.push('시험 데이터: 평가 호스트가 아닌 장비에서 계산한 결과입니다.');
  return out;
}

const STATUS: Record<MessagePlan['kind'], string> = {
  leave_by: '모델로 확인된 차량 경로 있음',
  no_route: '모델상 확인된 차량 경로 없음',
  unresolved: '미확인: 모델로 확인하지 못함',
  partial: '부분 확인: 자료 시각 출발은 미확인',
};

function spokenReason(p: MessagePlan): SpokenBlock | null {
  const t0 = iso(p);
  const r = p.reason;
  if (r && r.kind === 'flame_on_route') return { optional: 'reason', text: `${kOfN(r.k, r.n)} ${r.road.text.ko}에 ${koSpokenTime(t0, r.flameS)}쯤 불길이 닿습니다.` };
  if (r && r.kind === 'dwell_at_destination') return { optional: 'reason', text: `${kOfN(r.k, r.n)} 도착지 부근에 ${koSpokenTime(t0, r.flameS)}쯤 불길이 닿습니다.` };
  if (r && r.kind === 'all_exits_blocked') {
    return { optional: 'reason', text: `산불 예측에서는 이곳에서 나가는 도로 ${r.exits.length}곳 모두에 ${durationText(p.input.scenario.horizonS, 'ko')} 안에 불길이 닿습니다.` };
  }
  if (p.kind === 'leave_by') {
    if (p.after === 'horizon') return { optional: 'reason', text: '그보다 늦은 출발은 이 자료로 점검하지 않았습니다.' };
    if (p.after === 'gap') return { optional: 'reason', text: '그 뒤에는 확인되지 않은 출발 시각이 있습니다.' };
    return { optional: 'reason', text: '그보다 늦게 출발하는 길은 확인되지 않았습니다.' };
  }
  return null;
}

export const KO: TemplateSet = {
  lang: 'ko',

  sms(p) {
    const lines: string[] = [];
    if (p.kind === 'leave_by' && p.leaveByS !== null) lines.push('모델로 확인된 경로 있음', `${hm(iso(p), p.leaveByS)}까지 출발`);
    else if (p.kind === 'no_route') lines.push('모델상 경로 없음', '즉시 119·읍면사무소 연락');
    else if (p.kind === 'partial') lines.push('부분 확인(모델)', '공식 대피 안내를 따르세요');
    else lines.push('경로 미확인(모델)', '공식 대피 안내를 따르세요');
    lines.push(`${OFFICIAL_FIRST_SMS.ko}·${MODEL_NOT_LIVE_SMS.ko}`, smsTail(p));
    return lines.join('\n');
  },

  lms(p) {
    const tag = [p.input.replay ? `${year(p)}년 기록 재현` : '계획 자료', p.input.mock ? 'MOCK' : null, p.input.testData ? '시험 데이터' : null].filter(Boolean).join(' · ');
    return [
      `[산불 대피 계획 정보 · ${tag}]`,
      originWritten(p),
      `자료 기준: ${koDate(iso(p))} (한국 시각)`,
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
    blocks.push({
      text:
        o.name && o.kind === 'facility'
          ? `${o.name.ko} 직원과 이용자 여러분께 알려 드립니다.`
          : o.name && o.kind === 'village'
            ? `${o.name.ko} 주민 여러분께 알려 드립니다.`
            : '주민 여러분께 알려 드립니다.',
    });
    blocks.push({
      text:
        `이 안내는 ${koDateSpoken(t0)} ${p.input.replay ? '기록을 재현한' : '자료로 만든'} ${MODEL_NOT_LIVE_SPOKEN.ko}.` +
        (p.input.mock ? ' 모의 서버 자료입니다.' : '') +
        (p.input.testData ? ' 시험용 계산 자료입니다.' : ''),
    });
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = koSpokenTime(t0, p.leaveByS);
      blocks.push({
        text:
          p.destination && !p.destinationVaries
            ? `${S}까지 차로 출발하십시오. ${destSpoken(p.destination)}까지 가는 길이 모델로 확인되었습니다.`
            : `${S}까지 차로 출발하십시오. 그때까지 출발하는 길이 모델로 확인되었습니다.`,
      });
      const why = spokenReason(p);
      if (why) blocks.push(why);
      blocks.push({ text: '실제 대피 장소는 공식 안내를 따르십시오.' });
      blocks.push({
        optional: 'carless',
        text: o.kind === 'facility' ? '차가 부족하면 읍·면사무소에 바로 알리십시오.' : '차가 없는 분은 이장이나 읍·면사무소에 바로 알리십시오.',
      });
      blocks.push({ optional: 'repeat', text: `다시 알려 드립니다. ${S}까지 출발하십시오.` });
    } else if (p.kind === 'no_route') {
      blocks.push({ text: '모델로 계산한 결과, 이곳에서 차로 나가는 확인된 길이 없습니다. 지금 바로 119나 읍·면사무소에 연락하고, 공식 지시를 따르십시오.' });
      const why = spokenReason(p);
      if (why) blocks.push(why);
      blocks.push({ optional: 'repeat', text: '다시 알려 드립니다. 지금 바로 119나 읍·면사무소에 연락하십시오.' });
    } else if (p.kind === 'partial') {
      blocks.push({ text: '모델 결과가 출발 시각마다 다르고, 자료 시각에 바로 출발하는 길은 확인되지 않았습니다. 공식 대피 안내를 따르십시오.' });
      blocks.push({ optional: 'repeat', text: '다시 알려 드립니다. 공식 대피 안내를 따르십시오.' });
    } else {
      blocks.push({ text: '모델로는 이곳의 차량 대피 길을 확인하지 못했습니다. 길이 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따르십시오.' });
      blocks.push({ optional: 'repeat', text: '다시 알려 드립니다. 공식 대피 안내를 따르십시오.' });
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
    if (p.kind === 'no_route') lines.push('[통화 전 확인] 119와 읍·면사무소에 먼저 연락했는지 확인하십시오.');
    if (o.name && o.kind === 'facility') {
      lines.push(`안녕하세요. ${o.name.ko}의 [직원 이름]입니다. [어르신 성함] 보호자님께 산불 대피 계획을 알려 드리려고 전화드렸습니다.`);
    } else if (o.name && o.kind === 'village') {
      lines.push(`안녕하세요. [소속·이름]입니다. ${o.name.ko}에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.`);
    } else {
      lines.push('안녕하세요. [소속·이름]입니다. [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.');
    }
    lines.push(
      `지금 드리는 내용은 ${koDateSpoken(t0)} ${p.input.replay ? '산불 기록을 재현한' : '자료로 만든'} ${MODEL_NOT_LIVE_SPOKEN.ko}.` +
        (p.input.mock ? ' 모의 서버 자료입니다.' : '') +
        (p.input.testData ? ' 시험용 계산 자료입니다.' : ''),
    );
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = koSpokenTime(t0, p.leaveByS);
      lines.push(
        p.destination && !p.destinationVaries
          ? `모델 계산으로는 ${place} 근처 도로에서 ${S}까지 차로 출발하면 ${destSpoken(p.destination)}까지 가는 경로가 확인되었습니다.`
          : `모델 계산으로는 ${place} 근처 도로에서 ${S}까지 차로 출발하는 경로가 확인되었습니다. 도착지는 출발 시각에 따라 다릅니다.`,
      );
      const r = p.reason;
      if (r && r.kind === 'flame_on_route') lines.push(`이유는 ${kOfN(r.k, r.n)} ${r.road.text.ko}에 ${koSpokenTime(t0, r.flameS)}쯤 불길이 닿기 때문입니다.`);
      else if (r && r.kind === 'dwell_at_destination') lines.push(`이유는 ${kOfN(r.k, r.n)} 도착지 부근에 ${koSpokenTime(t0, r.flameS)}쯤 불길이 닿기 때문입니다.`);
      else if (p.after === 'horizon') lines.push('그보다 늦은 출발은 이 자료로 점검하지 않았습니다.');
      else if (p.after === 'gap') lines.push('그 뒤에는 확인되지 않은 출발 시각이 있습니다.');
      else lines.push('그보다 늦게 출발하는 경로는 확인되지 않았습니다.');
    } else if (p.kind === 'no_route') {
      lines.push(`모델 계산으로는 ${place}에서 차로 나가는 확인된 경로가 없었습니다. 그래서 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따라야 합니다.`);
      const r = p.reason;
      if (r && r.kind === 'all_exits_blocked') {
        lines.push(`산불 예측에서는 ${place}에서 나가는 도로 ${r.exits.length}곳 모두에 ${durationText(p.input.scenario.horizonS, 'ko')} 안에 불길이 닿습니다.`);
      }
    } else if (p.kind === 'partial') {
      lines.push('모델 결과가 출발 시각에 따라 다르고, 자료 시각에 바로 출발하는 경로는 확인되지 않았습니다. 공식 대피 안내를 따라야 합니다.');
    } else {
      lines.push(`모델 계산으로는 ${place}의 차량 대피 경로를 확인하지 못했습니다(미확인). 경로가 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따라야 합니다.`);
    }
    lines.push(`${OFFICIAL_FIRST.ko} 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.`);
    lines.push('궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.');
    return lines.join('\n');
  },

  card(p): CardContent {
    const t0 = iso(p);
    const o = p.input.origin;
    const badges: string[] = [];
    if (p.input.mock) badges.push('MOCK');
    if (p.input.testData) badges.push('시험 데이터 · 평가 호스트 아님');
    const cache = p.input.provenance.cacheCreatedAtIso;
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
          ? { label: '출발 마감', time: hm(t0, p.leaveByS), sub: `${koSpokenTime(t0, p.leaveByS)} · 한국 시각` }
          : null,
      lines: p.kind === 'leave_by' ? leaveByCardLines(p) : bodyLines(p, 'card').filter((l) => l.role !== 'status'),
      official: OFFICIAL_FIRST.ko,
      dataLine: `자료 기준: ${koDate(t0)} (한국 시각)${p.input.replay ? ` · ${year(p)}년 실제 산불 기록을 재현한 시나리오` : ''}`,
      modelLine: MODEL_NOT_LIVE.ko,
      limits: cardLimits(p),
      footer: FOOTER_APP.ko,
      meta: [`작성 ${kstStamp(p.input.generatedAtIso)}`, `시나리오 ${p.input.scenario.scenarioSetId}`, cache ? `사전 계산 ${kstStamp(cache)}` : null]
        .filter(Boolean)
        .join(' · '),
    };
  },
};
