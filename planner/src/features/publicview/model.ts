/**
 * P-PROTO — public-facing prototype on REPLAYED data only (research/harness-2026-11/P-PROTO/DESIGN.md).
 *
 * Pure model: the last-mile kit's fail-closed MessagePlan → one card per saved place. Adds no data and no
 * computation. Iris's safeguards against a replayed "leave by" being read as a live instruction:
 *  - no bare clock time anywhere: every card that shows a time carries, inside the same card, the replay date and a
 *    replay mark next to the time (so a cropped screenshot of one card still says it is a replay);
 *  - data age on a replay is the replay date and input time, never "x minutes old";
 *  - no green / all-clear state exists; unresolved, partial and no-route never show a time or a destination;
 *  - hand-off is destination only (no waypoints), as text and as a GPX file whose file name, track name and
 *    description carry the replay label; no geo: link.
 * Nothing here is fit for live use; comprehension is untested.
 */
import { hm, kstParts, ymd } from '../lastmile/compose';
import { messagePlan, type MessagePlan } from '../lastmile/plan';
import type { LastMileInput, LmLang, LmText } from '../lastmile/types';

export type Tone = 'leave' | 'stop' | 'unknown';
export type Icon = 'clock' | 'stop' | 'question';

export interface PublicCard {
  originId: string;
  place: LmText;
  kind: MessagePlan['kind'];
  tone: Tone;
  icon: Icon;
  /** the status in words (never colour alone) */
  words: LmText;
  /** leave-by clock time with the day marked when it crosses midnight; null unless kind is leave_by */
  time: LmText | null;
  /** fixed one-outbound-trip line (Iris): non-null exactly when `time` is */
  oneTrip: LmText | null;
  /** replay date + mark, shown next to the time and in every card */
  replayStamp: LmText;
  /** data age: the replay date and input time (never minutes for a replay) */
  dataAge: LmText;
  /** what to do now (official first) */
  guidance: LmText;
  /** destination hand-off (leave_by with a named, non-varying destination and known coordinates) */
  handoff: Handoff | null;
}

export interface Handoff {
  name: LmText;
  lat: number;
  lon: number;
  text: LmText;
  gpxFileName: string;
  gpx: string;
}

export const REPLAY_MARK: LmText = { ko: '기록 재현 · 실제 상황 아님', en: 'REPLAY · not a real situation' };
export const BANNER: LmText = {
  ko: '2025년 산불 기록 재현입니다 · 실제 상황이 아닙니다 · 실시간 대피에 쓰지 마십시오',
  en: 'Replay of 2025 wildfire records · not a real situation · do not use for live evacuation',
};
export const OFFICIAL_SLOT: LmText = {
  ko: '공식 대피 명령, 재난문자, 이장·읍·면사무소 안내가 이 화면보다 항상 우선합니다. 이 재현 화면은 당시의 공식 명령을 보여 주지 않습니다.',
  en: 'Official evacuation orders, emergency texts and the village head or town office always come before this screen. This replay does not show the official orders of the time.',
};
export const QUESTION: LmText = { ko: '대피해야 하나요? 언제까지?', en: 'Do I need to leave, and by when?' };
export const DEVICE_NOTE: LmText = {
  ko: '저장한 장소는 이 기기 안에만 남습니다. 이 화면은 자기 파일 말고는 아무 곳에도 연결하지 않습니다.',
  en: 'Saved places stay on this device. This page connects to nothing but its own files.',
};

const iso = (p: MessagePlan) => p.input.scenario.inputTimeIso;
const p2 = (n: number) => String(n).padStart(2, '0');

function stamp(input: LastMileInput): LmText {
  const t = input.scenario.inputTimeIso;
  const k = kstParts(t);
  const d = `${k.y}-${p2(k.mo)}-${p2(k.d)}`;
  return { ko: `${d} ${REPLAY_MARK.ko} · 모델 추정`, en: `${d} ${REPLAY_MARK.en} · model estimate` };
}

function age(input: LastMileInput): LmText {
  const t = input.scenario.inputTimeIso;
  return { ko: `자료: ${ymd(t)} ${hm(t)} 기록 (재현)`, en: `Data: records of ${ymd(t)} ${hm(t)} KST (replay)` };
}

function dayMarked(p: MessagePlan, offsetS: number): LmText {
  const a = kstParts(iso(p)), b = kstParts(iso(p), offsetS);
  const d = Math.round((Date.UTC(b.y, b.mo - 1, b.d) - Date.UTC(a.y, a.mo - 1, a.d)) / 86400000);
  const t = hm(iso(p), offsetS);
  if (d === 0) return { ko: t, en: t };
  if (d === 1) return { ko: `다음날 ${t}`, en: `${t} (next day)` };
  const day = ymd(iso(p), offsetS);
  return { ko: `${day} ${t}`, en: `${t} (${day})` };
}

function placeName(input: LastMileInput): LmText {
  return input.origin.name ?? input.origin.display;
}

function xml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Destination-only hand-off; the replay label is inside the file name, the track name and the description. */
export function handoffFor(p: MessagePlan, coords: (destinationId: string) => { lat: number; lon: number } | null): Handoff | null {
  if (p.kind !== 'leave_by' || !p.destination || p.destinationVaries || !p.destination.name || p.leaveByS === null) return null;
  const c = coords(p.destination.id);
  if (!c || !Number.isFinite(c.lat) || !Number.isFinite(c.lon)) return null;
  const st = stamp(p.input);
  const t = dayMarked(p, p.leaveByS);
  const name = p.destination.name;
  const text: LmText = {
    ko: `[${st.ko}] ${placeName(p.input).ko} → ${name.ko} (${c.lat.toFixed(5)}, ${c.lon.toFixed(5)}) · 모델상 ${t.ko}까지 차로 출발 · 공식 안내가 우선합니다`,
    en: `[${st.en}] ${placeName(p.input).en} → ${name.en || name.ko} (${c.lat.toFixed(5)}, ${c.lon.toFixed(5)}) · model: leave by car by ${t.en} · official guidance comes first`,
  };
  const label = `REPLAY ${ymd(iso(p))} NOT REAL - ${name.en || name.ko}`;
  const gpx =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<gpx version="1.1" creator="WildfireGuardian replay prototype" xmlns="http://www.topografix.com/GPX/1/1">\n' +
    `  <metadata><name>${xml(label)}</name><desc>${xml(text.en)} | ${xml(text.ko)}</desc></metadata>\n` +
    `  <wpt lat="${c.lat.toFixed(6)}" lon="${c.lon.toFixed(6)}"><name>${xml(label)}</name><desc>${xml(BANNER.en)}</desc></wpt>\n` +
    '</gpx>\n';
  return { name, lat: c.lat, lon: c.lon, text, gpxFileName: `REPLAY-${ymd(iso(p))}-NOT-REAL-${p.destination.id.replace(/[^A-Za-z0-9]+/g, '_')}.gpx`, gpx };
}

/**
 * Iris: on every card that shows a time — the result covers one outbound trip; the way back was not checked. Korean by
 * Sofia ("빠져나가는"); both languages say the same thing (not checked), as Iris asked.
 */
export const ONE_TRIP: LmText = {
  ko: '이 결과는 한 번 빠져나가는 길만 확인한 것입니다. 돌아오는 길은 확인하지 않았습니다.',
  en: 'This result checks one trip out only. The way back was not checked.',
};

/** What the calculation does not include, in plain words, none implying a size or likelihood (Iris, Sofia). */
export const NOT_IN_MODEL: { title: LmText; items: LmText[] } = {
  title: { ko: '계산에 넣지 않은 것', en: 'Not included in this calculation' },
  items: [
    { ko: '연기(시야)', en: 'smoke (visibility)' },
    { ko: '좁은 길', en: 'narrow roads' },
    { ko: '차량 정체', en: 'queues of cars' },
    { ko: '불티로 인한 차량 화재', en: 'embers setting cars alight' },
    { ko: '돌아오는 길', en: 'the way back' },
  ],
};

/** The uniform step between the departure times in the sweep (minutes), or null when there is none. */
export function sweepStepMin(input: LastMileInput): number | null {
  const o = [...new Set((input.plan?.sweep ?? []).map((c) => c.offsetS))].sort((a, b) => a - b);
  if (o.length < 2) return null;
  const d = new Set(o.slice(1).map((v, i) => v - o[i]!));
  if (d.size !== 1) return null;
  const s = [...d][0]!;
  return s > 0 && s % 60 === 0 ? s / 60 : null;
}

export type AfterWords = 'horizon' | 'none_checked' | 'gap';

/**
 * The descriptive leave-by sentence, one per AfterKind (Iris: what the model found, not an instruction; Korean by
 * Sofia). Only the departure times in the sweep were computed, every `stepMin` minutes (the clause is omitted when the
 * step is not uniform). "No checked road" (확인된 길 없음) covers both a model no-route and an unresolved check, never "no
 * road" or "closed". Each must be true of the sweep it describes (property test in tests/planner/pproto.test.ts):
 * - horizon: no departure after T was requested (only window-closed times or none): later ones were not checked;
 * - none_checked: no requested departure after T has a checked road;
 * - gap: the next requested departure after T has no checked road; `nextMin` = its distance from T in minutes (shown
 *   only when it equals the step). A later checked road is never mentioned, so the sentence cannot be read as "leaving
 *   later is also fine".
 */
export function leaveByWords(after: AfterWords, stepMin: number | null, nextMin: number | null = null): LmText {
  const koStep = stepMin ? `${stepMin}분 간격으로 ` : '';
  const enStep = stepMin ? ` (every ${stepMin} minutes)` : '';
  const ko = `모델 계산: 이 시각까지 ${koStep}계산한 출발 시각마다 차로 나갈 수 있는 확인된 길이 있습니다.`;
  const en = `Model: at each departure time computed up to this time${enStep}, there is a checked road out by car.`;
  const next = after === 'gap' && stepMin !== null && nextMin === stepMin ? nextMin : null;
  const tail: Record<AfterWords, LmText> = {
    horizon: { ko: '그 뒤 출발은 확인하지 않았습니다.', en: 'Later departures were not checked.' },
    none_checked: { ko: '그 뒤의 출발 시각은 계산한 시각 모두 확인된 길이 없습니다.', en: 'Every later departure time computed has no checked road.' },
    gap: next
      ? { ko: `바로 다음 계산 시각(${next}분 뒤)에 출발하면 확인된 길이 없습니다.`, en: `Leaving at the next computed time (${next} minutes later) has no checked road.` }
      : { ko: '바로 다음 계산 시각에 출발하면 확인된 길이 없습니다.', en: 'Leaving at the next computed time has no checked road.' },
  };
  return { ko: `${ko} ${tail[after].ko}`, en: `${en} ${tail[after].en}` };
}

/** Minutes from T to the next requested (not window-closed) departure time, or null. */
export function nextRequestedMin(input: LastMileInput, leaveByS: number): number | null {
  const n = (input.plan?.sweep ?? []).filter((c) => c.verdict !== 'window_closed' && c.offsetS > leaveByS).sort((a, b) => a.offsetS - b.offsetS)[0];
  return n && (n.offsetS - leaveByS) % 60 === 0 ? (n.offsetS - leaveByS) / 60 : null;
}

export function cardFor(input: LastMileInput, coords: (destinationId: string) => { lat: number; lon: number } | null = () => null): PublicCard {
  const p = messagePlan(input, null);
  const base = { originId: input.origin.id, place: placeName(input), kind: p.kind, replayStamp: stamp(input), dataAge: age(input) };
  if (p.kind === 'leave_by' && p.leaveByS !== null && p.after !== null) {
    const t = dayMarked(p, p.leaveByS);
    return {
      ...base,
      tone: 'leave',
      icon: 'clock',
      // Iris: descriptive mood — what the model found, not an instruction
      words: leaveByWords(p.after, sweepStepMin(input), nextRequestedMin(input, p.leaveByS)),
      time: t,
      oneTrip: ONE_TRIP,
      guidance: { ko: '공식 대피 명령이 우선합니다. 차가 없으면 이장에게 바로 알리십시오.', en: 'Official evacuation orders come first. No car? Tell the village head now.' },
      handoff: handoffFor(p, coords),
    };
  }
  if (p.kind === 'no_route') {
    return {
      ...base,
      tone: 'stop',
      icon: 'stop',
      words: { ko: '모델 계산: 차로 나가는 확인된 길 없음', en: 'Model: no checked road out by car' },
      time: null,
      oneTrip: null,
      guidance: { ko: '이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.', en: 'Follow official instructions of the village head and town office. In an emergency, report to 119.' },
      handoff: null,
    };
  }
  return {
    ...base,
    tone: 'unknown',
    icon: 'question',
    words: { ko: '확인하지 못함 — 길이 있다는 뜻도, 없다는 뜻도 아닙니다', en: 'Not checked — this means neither that a road exists nor that none does' },
    time: null,
    oneTrip: null,
    guidance: { ko: '공식 대피 안내를 따르십시오.', en: 'Follow official evacuation guidance.' },
    handoff: null,
  };
}

/**
 * Examples shown when nothing is saved: one leave_by, one no_route and one unresolved (fixed rule: the first by
 * origin id of each kind), labelled as examples, so the first thing a visitor learns is that the tool often has no
 * answer. Missing kinds are skipped.
 */
export function exampleIds(inputs: LastMileInput[]): string[] {
  const sorted = [...inputs].sort((a, b) => a.origin.id.localeCompare(b.origin.id));
  const pick = (k: MessagePlan['kind'][]) => sorted.find((i) => k.includes(messagePlan(i, null).kind))?.origin.id ?? null;
  return [pick(['leave_by']), pick(['no_route']), pick(['unresolved', 'partial'])].filter((x): x is string => x !== null);
}

export function pick(t: LmText, lang: LmLang): string {
  return t[lang] || t.ko;
}

/**
 * Places by URL (?scenario=<cache index path>&place=<origin id>). Both parameters are UNTRUSTED: the scenario must equal
 * one of the committed cache index paths exactly (it is matched, never fetched as given) and the place must be an origin
 * of that scenario; anything else yields nulls (the page then shows its empty state).
 */
export function parseLink(search: string, entryPaths: string[]): { scenario: string | null; place: string | null } {
  let q: URLSearchParams;
  try {
    q = new URLSearchParams(search);
  } catch {
    return { scenario: null, place: null };
  }
  const sc = q.get('scenario');
  const scenario = sc !== null && entryPaths.includes(sc) ? sc : null;
  const pl = q.get('place');
  const place = scenario && pl !== null && /^[A-Za-z0-9:/._-]{1,120}$/.test(pl) ? pl : null;
  return { scenario, place };
}

/** The place id only if it is an origin of the loaded scenario. */
export function validPlace(place: string | null, inputs: LastMileInput[]): string | null {
  return place !== null && inputs.some((i) => i.origin.id === place) ? place : null;
}

/** A shareable link for a place (sharing it reveals the chosen place). */
export function linkFor(scenario: string, place: string): string {
  return `?${new URLSearchParams({ scenario, place }).toString()}`;
}
