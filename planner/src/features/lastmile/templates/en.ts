/**
 * English templates — a translation of the Korean source (./ko.ts), same structure, same facts and
 * the same audiences (no "call 119 now" in the SMS, broadcast or family call script). The SMS uses
 * only the GSM 03.38 alphabet (no "·", no dashes); the long text avoids characters outside EUC-KR so
 * it can also be sent as a Korean LMS.
 */
import { kstStamp } from '../../shared/format';
import { FOOTER_APP } from '../../shared/strings';
import { ENTRY_LIMIT_M } from '../../../domain/plan';
import {
  durationText,
  distanceText,
  enDate,
  enDateSpoken,
  enSpokenTime,
  hm,
  kstParts,
  ymd,
  type CardContent,
  type CardLine,
  type SpokenBlock,
  type TemplateSet,
} from '../compose';
import { groupExitLabels, type LmReason } from '../explanation';
import { bigLabelKind, ENTRY_SPOKEN_MIN_M, type MessagePlan, type PlannedDestination } from '../plan';
import { MODEL_NOT_LIVE, MODEL_NOT_LIVE_SMS, MODEL_NOT_LIVE_SPOKEN, MODEL_PLAN_SPOKEN, MODEL_SMS, NOT_REAL, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS } from '../strings';

const iso = (p: MessagePlan) => p.input.scenario.inputTimeIso;

/** The planner's footer with a plain hyphen (the em dash is outside EUC-KR / GSM-7). */
const FOOTER_PLAIN = FOOTER_APP.en.replace(/\s*—\s*/g, ' - ');

/** "1-hour" (adjective form of the recorded range). */
function rangeAdj(p: MessagePlan): string {
  return durationText(p.input.scenario.horizonS, 'en').replace(/ hours?$/, '-hour').replace(/ min$/, '-minute');
}

function year(p: MessagePlan): number {
  return p.input.region.fireYear ?? kstParts(iso(p)).y;
}

const facility = (p: MessagePlan) => p.input.origin.kind === 'facility';

function placeWord(p: MessagePlan): string {
  return facility(p) ? 'facility' : 'village';
}

function withCategory(name: string, category: string): string {
  return name.toLowerCase().includes(category.toLowerCase()) ? name : `${name} (${category})`;
}

function originWritten(p: MessagePlan): string {
  const o = p.input.origin;
  return o.name ? withCategory(o.name.en, o.category.en) : o.display.en;
}

/** Written destination: the OSM name, or "a school with no name in the map data" (no ids for residents). */
function destWritten(d: PlannedDestination): string {
  return d.name ? withCategory(d.name.en, d.category.en) : `a ${d.category.en.toLowerCase()} with no name in the map data`;
}

function destSpoken(d: PlannedDestination): string {
  return d.name ? d.name.en : `an unnamed ${d.category.en.toLowerCase()}`;
}

function kOfN(k: number, n: number): string {
  return k >= n ? `all ${n} fire scenarios from the forecast` : `${k} of ${n} fire scenarios from the forecast`;
}

/** Ends a sentence once ("by 6:40 p.m." already ends with a period). */
function sentence(s: string): string {
  return s.endsWith('.') ? s : `${s}.`;
}

/** A Latin-script name exists (OSM name:en); otherwise spoken text stays generic. */
function latin(name: string): boolean {
  return !/[ㄱ-ㆎ가-힣]/.test(name);
}

type Exits = Extract<LmReason, { kind: 'all_exits_blocked' }>;

/** At most `max` names (3 in the long text, 2 on the card), then "and others"; one place's roads are merged. */
function exitNames(r: Exits, max: number): string {
  const names = groupExitLabels(r.exits).map((e) => e.en);
  return names.length > max ? `${names.slice(0, max).join(', ')} and others` : names.join(', ');
}

/**
 * The exits of the explanation file are the roads where the area reachable by car from the entry
 * point WITHOUT meeting flames ends (tools/explain_deadlines README §4) — not the roads out of the
 * village (see ko.ts).
 */
function exitsWritten(p: MessagePlan, r: Exits, max: number): string {
  const range = durationText(p.input.scenario.horizonS, 'en');
  const area = `leading out of the area reachable by car from this ${placeWord(p)} without meeting flames`;
  const when = r.atStart ? 'already blocked by flames at the data time' : `blocked by flames within ${range} of the data time`;
  const members = r.kMin >= r.n ? `in all ${r.n} fire scenarios from the forecast` : `in at least ${r.kMin} of ${r.n} fire scenarios from the forecast`;
  if (r.roads === 1) return `Why: the only road ${area} (${exitNames(r, max)}) is ${when} (${members}).`;
  if (r.exits.length === 1) {
    // several roads with one label: "(both near Gugye-ri)"
    const l = r.exits[0]!;
    // "a road about 800 m from this village" → "(both about 800 m from this village)"
    const what = l.source === 'unnamed' ? 'unnamed' : l.text.en.replace(/^(a|the) road /, '');
    return `Why: the ${r.roads} roads ${area} (${r.roads === 2 ? 'both' : 'all'} ${what}) are ${when} (on each road, ${members}).`;
  }
  return `Why: ${r.roads === 2 ? 'both roads' : `all ${r.roads} roads`} ${area} (${exitNames(r, max)}) are ${when} (on each road, ${members}).`;
}

function exitsSpoken(p: MessagePlan, r: Exits): string {
  const area = 'leading out of the area reachable from here without meeting flames';
  const when = r.atStart ? 'already blocked by flames' : `blocked by flames within ${durationText(p.input.scenario.horizonS, 'en')}`;
  return r.roads === 1 ? `In the forecast, the only road ${area} is ${when}.` : `In the forecast, ${r.roads === 2 ? 'both roads' : `all ${r.roads} roads`} ${area} are ${when}.`;
}

/** The model_no_route reason in writing (long text, card), or null. */
function noRouteReasonWritten(p: MessagePlan, max: number): string | null {
  const r = p.reason;
  if (!r) return null;
  if (r.kind === 'all_exits_blocked') return exitsWritten(p, r, max);
  if (r.kind === 'entry_in_flame') return `Why: in the fire scenarios from the forecast, the entry point of this ${placeWord(p)} (the nearest road point) is already in flames at departure.`;
  // the file's claim covers the candidate shelters the planner tried, never every possible destination
  if (r.kind === 'no_route_flames') return `Why: from every departure time checked, none of the destinations checked (candidate shelters) can be reached and the stay finished within the ${rangeAdj(p)} data range on a road that avoids the flames in the fire scenarios from the forecast.`;
  if (r.kind === 'no_route_time_window') return `Why: from every departure time checked, none of the destinations checked (candidate shelters) can be reached and the stay finished within the ${rangeAdj(p)} data range, even without fire.`;
  return null;
}

/** The model_no_route reason, spoken (optional broadcast block; a call-script line), or null. */
function noRouteReasonSpoken(p: MessagePlan): string | null {
  const r = p.reason;
  const range = durationText(p.input.scenario.horizonS, 'en');
  if (!r) return null;
  if (r.kind === 'all_exits_blocked') return exitsSpoken(p, r);
  if (r.kind === 'entry_in_flame') return 'In the forecast, the road entry point here is already in flames.';
  if (r.kind === 'no_route_flames') return `In the forecast, no route that avoids the flames reaches any of the destinations checked within ${range}.`;
  if (r.kind === 'no_route_time_window') return `Even without fire, none of the destinations checked can be reached within ${range}.`;
  return null;
}

/** First line of the SMS: what the data is and its time. */
function smsTag(p: MessagePlan): string {
  const t = `${ymd(iso(p))} ${hm(iso(p))} KST`;
  if (!p.input.replay) return `Planning data of ${t}, ${MODEL_NOT_LIVE_SMS.en}`;
  const pre = p.input.mock ? 'MOCK ' : p.input.testData ? 'TEST ' : '';
  return `${pre}REPLAY of ${t} data, ${MODEL_NOT_LIVE_SMS.en}`;
}

/** First line of the long text. */
function lmsTag(p: MessagePlan): string {
  const parts = [p.input.mock ? 'MOCK' : null, p.input.testData ? 'TEST DATA' : null, p.input.replay ? `REPLAY of recorded ${year(p)} data - not a real emergency` : 'Planning data - not live'];
  return `[${parts.filter(Boolean).join(' - ')}]`;
}

function noRouteStaff(p: MessagePlan): string {
  return `${facility(p) ? 'Facility staff' : 'Village head'}: call 119 and the eup/myeon office now and follow official instructions.`;
}
function noRouteResidents(p: MessagePlan): string {
  return facility(p)
    ? 'Residents and families: follow official instructions from the facility and the eup/myeon office. In an emergency, call 119.'
    : 'Residents: follow official instructions from the village head and the eup/myeon office. In an emergency, call 119.';
}
function noRouteSpoken(p: MessagePlan): string {
  return `Follow official instructions from ${facility(p) ? 'the facility' : 'the village head'} and the eup/myeon office. In an emergency, call 119.`;
}

const PARTIAL_TEXT = 'Model results differ by departure time, so no single departure time is given.';

/** Said wherever the time is the end of the checked range, not a fire deadline. */
const NOT_FIRE_EN = 'this time was not set by fire.';

/** What limits T, in writing. Never implies a fire deadline unless the explanation says so. */
function afterWritten(p: MessagePlan, T: string, card: boolean): CardLine {
  const r = p.reason;
  const t0 = iso(p);
  const range = durationText(p.input.scenario.horizonS, 'en');
  // the explanation proves only that the NEXT checked departure fails, so the lines say exactly that
  const N = hm(t0, p.nextOffsetS ?? p.leaveByS ?? 0);
  if (r && (r.kind === 'flame_on_route' || r.kind === 'dwell_at_destination')) {
    const F = hm(t0, r.flameS);
    if (r.kind === 'flame_on_route') {
      return {
        role: 'reason',
        text: card ? `Why: in ${kOfN(r.k, r.n)}, flames reach ${r.road.text.en} around ${F}.` : `Why: in ${kOfN(r.k, r.n)}, flames reach ${r.road.text.en} around ${F} KST. If you leave at the next checked time, ${N}, you may meet the fire there.`,
      };
    }
    return {
      role: 'reason',
      text: card
        ? `Why: in ${kOfN(r.k, r.n)}, flames reach the destination area (${r.road.text.en}) around ${F}.`
        : `Why: in ${kOfN(r.k, r.n)}, flames reach the destination area (${r.road.text.en}) around ${F} KST. If you leave at the next checked time, ${N}, you may meet the fire while staying there.`,
    };
  }
  if (r && r.kind === 'no_flame_avoiding_route') {
    return {
      role: 'reason',
      text: card
        ? `Why: at the next checked time, ${N}, no destination checked can be reached and the stay finished in time on a road that avoids the flames in the fire scenarios from the forecast.`
        : `Why: leaving at the next checked time, ${N}, none of the destinations checked (candidate shelters) can be reached and the stay finished in time on a road that avoids the flames in the fire scenarios from the forecast.`,
    };
  }
  if (r && r.kind === 'time_window') {
    // only what is established (see ko.ts): the next checked time fails for every destination checked, later times have no checked route
    return {
      role: 'after',
      text: card
        ? `At the next checked time, ${N}, even without fire no destination checked can be reached and the stay finished within the ${rangeAdj(p)} range; no checked route after ${T}; ${NOT_FIRE_EN}`
        : `Leaving at the next checked time, ${N}, none of the destinations checked can be reached and the stay finished within the ${rangeAdj(p)} data range, even without fire; departures after ${T} have no checked route in the model; ${NOT_FIRE_EN}`,
    };
  }
  if (p.after === 'horizon') {
    return card
      ? { role: 'after', text: `Later departures were not checked (data range ${range}); ${NOT_FIRE_EN}` }
      : { role: 'after', text: `${T} KST is the last departure time the model checked. Later departures were not checked (data range: ${range} from the data time); ${NOT_FIRE_EN}` };
  }
  if (p.after === 'gap') {
    return card
      ? { role: 'after', text: `Some departure times after ${T} were not checked; this card covers up to ${T}.` }
      : { role: 'after', text: `Some departure times after ${T} could not be checked, so this message covers departures up to ${T} only.` };
  }
  return { role: 'after', text: card ? `No checked route for departures after ${T}.` : `Departures after ${T} have no checked route in the model.` };
}

function afterSpoken(p: MessagePlan): string {
  const r = p.reason;
  const t0 = iso(p);
  if (r && r.kind === 'flame_on_route') return latin(r.road.text.en) ? sentence(`In ${kOfN(r.k, r.n)}, flames reach ${r.road.text.en} around ${enSpokenTime(t0, r.flameS)}`) : sentence(`In ${kOfN(r.k, r.n)}, flames reach a road on the way around ${enSpokenTime(t0, r.flameS)}`);
  if (r && r.kind === 'dwell_at_destination') return sentence(`In ${kOfN(r.k, r.n)}, flames reach the destination area around ${enSpokenTime(t0, r.flameS)}`);
  if (r && r.kind === 'no_flame_avoiding_route') {
    return `Leaving at the next checked time, ${enSpokenTime(t0, p.nextOffsetS ?? p.leaveByS ?? 0)}, none of the destinations checked can be reached in time on a road that avoids the flames in the forecast.`;
  }
  if (r && r.kind === 'time_window') return `Later departures have no checked route; ${NOT_FIRE_EN}`;
  if (p.after === 'horizon') return `Later departures were not checked; ${NOT_FIRE_EN}`;
  if (p.after === 'gap') return 'Some later departure times were not checked.';
  return 'Later departures have no checked route.';
}

function entryNote(p: MessagePlan): string {
  const dist = p.input.origin.entryDistanceM;
  return dist !== null && dist >= 1
    ? `Times refer to the nearest road point (entry point), ${distanceText(dist)} from the ${placeWord(p)}. Time to get ready and board is not included.`
    : 'Times refer to the nearest road point (entry point). Time to get ready and board is not included.';
}

function carlessWritten(p: MessagePlan): string {
  return facility(p) ? 'If the facility lacks vehicles to move its residents, tell the eup/myeon office now.' : 'If you have no car or cannot move on your own, tell the village head or the eup/myeon office now.';
}

function bodyLines(p: MessagePlan, target: 'lms' | 'card'): CardLine[] {
  const out: CardLine[] = [];
  const t0 = iso(p);
  if (p.kind === 'leave_by' && p.leaveByS !== null) {
    const T = hm(t0, p.leaveByS);
    out.push({ role: 'instruction', text: `Leave by car no later than ${T} KST (${enSpokenTime(t0, p.leaveByS)}). Do not wait until that time.` });
    const d = p.destination;
    if (d) {
      if (p.destinationVaries) {
        out.push({ role: 'destination', text: `The destination depends on the departure time. Destination the model checked for leaving at ${T}: ${destWritten(d)}.` });
      } else if (d.arrivalS !== null && d.arrivalS >= p.leaveByS) {
        const min = Math.max(1, Math.round((d.arrivalS - p.leaveByS) / 60));
        out.push({ role: 'destination', text: `Destination the model checked: ${destWritten(d)}. Leaving at ${T}, arrival around ${hm(t0, d.arrivalS)} KST (about ${min} min by car; traffic not included).` });
      } else {
        out.push({ role: 'destination', text: `Destination the model checked: ${destWritten(d)}.` });
      }
    }
    out.push(afterWritten(p, T, false));
    out.push({ role: 'guide', text: 'Follow official guidance on where to go and which roads to use.' });
    out.push({ role: 'note', text: carlessWritten(p) });
    out.push({ role: 'note', text: entryNote(p) });
    return out;
  }
  if (p.kind === 'no_route') {
    if (target === 'lms') out.push({ role: 'status', text: 'No checked vehicle route in the model.' });
    out.push({ role: 'instruction', text: noRouteStaff(p) });
    out.push({ role: 'instruction', text: noRouteResidents(p) });
    const why = noRouteReasonWritten(p, target === 'card' ? 2 : 3);
    if (why) out.push({ role: 'reason', text: why });
    if (target === 'card') out.push({ role: 'meaning', text: '"No route in the model": no checked route at any departure time or destination checked.' });
    return out;
  }
  if (p.kind === 'partial') {
    if (target === 'lms') out.push({ role: 'status', text: PARTIAL_TEXT });
    out.push({ role: 'instruction', text: 'Follow official evacuation guidance.' });
    if (target === 'card') out.push({ role: 'note', text: 'See the pre-season plan sheet for the result at each departure time.' });
    return out;
  }
  if (target === 'lms') out.push({ role: 'status', text: 'The model could not check a vehicle route (unresolved).' });
  out.push({ role: 'meaning', text: 'Unresolved means neither that a route exists nor that it does not.' });
  out.push({ role: 'instruction', text: 'Follow official evacuation guidance.' });
  const note = p.input.plan?.note ?? (p.input.plan ? null : 'not_computed');
  if (note === 'not_checkable') out.push({ role: 'note', text: `This ${placeWord(p)} has no checkable road point within ${ENTRY_LIMIT_M / 1000} km, so it was not checked.` });
  else if (note === 'rejected') out.push({ role: 'note', text: 'The check request was refused, so it was not checked.' });
  else if (note === 'not_computed') out.push({ role: 'note', text: 'This origin has not been computed yet.' });
  return out;
}

/** The card's leave-by lines: the long text's facts in fewer words (see ko.ts). */
function leaveByCardLines(p: MessagePlan): CardLine[] {
  const out: CardLine[] = [];
  const t0 = iso(p);
  if (p.leaveByS === null) return out;
  const T = hm(t0, p.leaveByS);
  out.push({ role: 'instruction', text: 'Do not wait until this time: leave by car early.' });
  const d = p.destination;
  if (d) {
    if (p.destinationVaries) out.push({ role: 'destination', text: `The destination depends on the departure time; for ${T}: ${destWritten(d)}` });
    else if (d.arrivalS !== null && d.arrivalS >= p.leaveByS) {
      const min = Math.max(1, Math.round((d.arrivalS - p.leaveByS) / 60));
      out.push({ role: 'destination', text: `Model-checked destination: ${destWritten(d)}; leave ${T}, arrive around ${hm(t0, d.arrivalS)} (about ${min} min by car; traffic not included)` });
    } else out.push({ role: 'destination', text: `Model-checked destination: ${destWritten(d)}` });
  }
  out.push(afterWritten(p, T, true));
  out.push({
    role: 'guide',
    text: 'Follow official guidance on where to go. ' + (facility(p) ? 'Not enough vehicles? Tell the eup/myeon office now.' : 'No car or need help? Tell the village head or eup/myeon office now.'),
  });
  return out;
}

/** Card limitations; a leave-by card starts with what its times refer to (the entry point). */
function cardLimits(p: MessagePlan): string {
  const base = 'Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents';
  if (p.kind !== 'leave_by') return base;
  const dist = p.input.origin.entryDistanceM;
  const entry = dist !== null && dist >= 1 ? `Times at the road entry point ${distanceText(dist)} away; boarding time not included` : 'Times at the nearest road entry point; boarding time not included';
  return `${entry} · ${base}`;
}

function closingNotes(p: MessagePlan): string[] {
  const out: string[] = [];
  if (p.input.replay) out.push(`Replay of recorded ${year(p)} wildfire scenarios.`);
  if (p.input.mock) out.push('MOCK: recorded results replayed by the mock server.');
  if (p.input.testData) out.push('Test data: computed on a host other than the evaluation host.');
  return out;
}

const STATUS: Record<MessagePlan['kind'], string> = {
  leave_by: 'Checked vehicle route in the model',
  no_route: 'No checked vehicle route in the model',
  unresolved: 'Unresolved: the model could not check a route',
  partial: 'Partly checked: results differ by departure time',
};

/** "…model-based planning information from a replay of recorded wildfire data, <date> Korea time." */
function dataSentence(p: MessagePlan, lead: string): string {
  const t0 = iso(p);
  const core = p.input.replay
    ? `${lead}${MODEL_PLAN_SPOKEN.en} from a replay of recorded wildfire data, ${enDateSpoken(t0)} Korea time.`
    : `${lead}${MODEL_NOT_LIVE_SPOKEN.en} from planning data, ${enDateSpoken(t0)} Korea time. It is not live information.`;
  return core + (p.input.mock ? ' This is mock server data.' : '') + (p.input.testData ? ' These are test results.' : '');
}

export const EN: TemplateSet = {
  lang: 'en',

  sms(p) {
    const lines: string[] = [smsTag(p)];
    if (p.kind === 'leave_by' && p.leaveByS !== null) lines.push(`${MODEL_SMS.en}: leave by car no later than ${hm(iso(p), p.leaveByS)} KST.`, OFFICIAL_FIRST_SMS.en);
    else if (p.kind === 'no_route') lines.push(`${MODEL_SMS.en}: no checked route.`, `${OFFICIAL_FIRST_SMS.en} In an emergency, call 119.`);
    else if (p.kind === 'partial') lines.push(`${MODEL_SMS.en}: partly checked.`, `${OFFICIAL_FIRST_SMS.en} Follow official guidance.`);
    else lines.push(`${MODEL_SMS.en}: route not checked (unresolved).`, `${OFFICIAL_FIRST_SMS.en} Follow official guidance.`);
    return lines.join('\n');
  },

  lms(p) {
    return [
      lmsTag(p),
      `Wildfire evacuation plan information - ${originWritten(p)}`,
      `Data time: ${enDate(iso(p))}`,
      '',
      ...bodyLines(p, 'lms').map((l) => `- ${l.text}`),
      '',
      OFFICIAL_FIRST.en,
      MODEL_NOT_LIVE.en,
      ...closingNotes(p),
      FOOTER_PLAIN,
    ].join('\n');
  },

  broadcastBlocks(p) {
    const t0 = iso(p);
    const o = p.input.origin;
    const blocks: SpokenBlock[] = [];
    if (p.input.replay) blocks.push({ text: NOT_REAL.en });
    blocks.push(
      o.kind === 'facility'
        ? o.name && latin(o.name.en)
          ? { text: `Attention, staff and residents of ${o.name.en}.`, short: `Attention, ${o.name.en}.` }
          : { text: 'Attention, staff and residents of this facility.' }
        : { text: o.name && latin(o.name.en) ? `Attention, residents of ${o.name.en}.` : 'Attention, residents.' },
    );
    blocks.push({ text: dataSentence(p, 'This is ') });
    const repeat: SpokenBlock | null = p.input.replay ? { optional: 'repeat', text: `Again: this is not a real emergency; it is a replay of recorded ${year(p)} data.` } : null;
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = enSpokenTime(t0, p.leaveByS);
      blocks.push({
        text:
          p.destination && !p.destinationVaries && (p.destination.name === null || latin(p.destination.name.en))
            ? `${sentence(`Leave by car no later than ${S}`)} The computer forecast checked a route to ${destSpoken(p.destination)} for departures up to then.`
            : `${sentence(`Leave by car no later than ${S}`)} The computer forecast checked routes for departures up to then.`,
        short: `${sentence(`Leave by car no later than ${S}`)} The computer forecast checked routes for departures up to then.`,
      });
      const dist = o.entryDistanceM;
      if (dist !== null && dist > ENTRY_SPOKEN_MIN_M) blocks.push({ text: `Times are for the road ${distanceText(dist)} from the ${placeWord(p)}.`, short: `Times are for the road ${distanceText(dist)} away.` });
      blocks.push({ text: o.kind === 'facility' ? 'If vehicles are short, tell the eup/myeon office now.' : 'If you have no car, tell the village head now.' });
      blocks.push({ text: 'Follow official guidance on where to go.' });
      blocks.push({ optional: 'reason', text: afterSpoken(p) });
      blocks.push(repeat ?? { optional: 'repeat', text: sentence(`Again: leave no later than ${S}`) });
    } else if (p.kind === 'no_route') {
      blocks.push({ text: `In the computer forecast, there is no checked vehicle route from here. ${noRouteSpoken(p)}` });
      const why = noRouteReasonSpoken(p);
      if (why) blocks.push({ optional: 'reason', text: why });
      blocks.push(repeat ?? { optional: 'repeat', text: `Again: ${noRouteSpoken(p)}` });
    } else if (p.kind === 'partial') {
      blocks.push({ text: 'Computer forecast results differ by departure time, so no single departure time is given. Follow official evacuation guidance.' });
      blocks.push(repeat ?? { optional: 'repeat', text: 'Again: follow official evacuation guidance.' });
    } else {
      blocks.push({ text: 'The computer forecast could not check a vehicle route from here. This means neither that a route exists nor that it does not. Follow official evacuation guidance.' });
      blocks.push(repeat ?? { optional: 'repeat', text: 'Again: follow official evacuation guidance.' });
    }
    blocks.push({ text: OFFICIAL_FIRST.en });
    return blocks;
  },

  call(p) {
    const t0 = iso(p);
    const o = p.input.origin;
    const place = placeWord(p);
    const lines: string[] = [];
    lines.push(`[Before the call] ${OFFICIAL_FIRST.en} What follows is ${MODEL_NOT_LIVE_SPOKEN.en}, not live information. Fill in the [brackets] yourself.`);
    if (p.kind === 'no_route') lines.push(`[Before the call] Check that the ${facility(p) ? 'facility' : 'village head'} has contacted 119 and the eup/myeon office first.`);
    if (o.name && o.kind === 'facility') {
      lines.push(`Hello, this is [staff name] from ${o.name.en}. I am calling the family of [resident name] about the wildfire evacuation plan.`);
    } else if (o.name && o.kind === 'village') {
      lines.push(`Hello, this is [your name and role]. I am calling the family of [resident name], who lives in ${o.name.en}, about the wildfire evacuation plan.`);
    } else {
      lines.push('Hello, this is [your name and role]. I am calling the family of [resident name] about the wildfire evacuation plan.');
    }
    lines.push(dataSentence(p, p.input.replay ? 'This is not a real emergency: it is ' : 'This is '));
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = enSpokenTime(t0, p.leaveByS);
      const dist = o.entryDistanceM;
      const from = dist !== null && dist > ENTRY_SPOKEN_MIN_M ? `the road ${distanceText(dist)} from the ${place}` : `the road near the ${place}`;
      lines.push(
        p.destination && !p.destinationVaries
          ? `In the computer forecast (the model), leaving by car from ${from} no later than ${S} gives a checked route to ${destSpoken(p.destination)}.`
          : `In the computer forecast (the model), leaving by car from ${from} no later than ${S} gives a checked route. The destination depends on the departure time.`,
      );
      lines.push(afterSpoken(p));
      if (o.kind === 'village') lines.push('If [resident name] has no car or cannot move alone, please tell the village head or the eup/myeon office right away.');
    } else if (p.kind === 'no_route') {
      lines.push(
        `In the computer forecast (the model), there was no checked vehicle route from the ${place}. With a result like this, the ${facility(p) ? 'facility' : 'village head'} must call 119 and the eup/myeon office right away and follow official instructions.`,
      );
      const why = noRouteReasonSpoken(p);
      if (why) lines.push(why);
      // what the family itself is told (as in the broadcast): follow official instructions; 119 in an emergency
      lines.push(noRouteSpoken(p));
    } else if (p.kind === 'partial') {
      lines.push('Computer forecast results differ by departure time, so no single departure time is given. Official evacuation guidance must be followed.');
    } else {
      lines.push(`The computer forecast (the model) could not check a vehicle route from the ${place} (unresolved). This means neither that a route exists nor that it does not. Official evacuation guidance must be followed.`);
    }
    lines.push(`${OFFICIAL_FIRST.en} The actual place and time of any move may change with official guidance.`);
    lines.push('If you have questions, please call [phone number]. Thank you.');
    return lines.join('\n');
  },

  card(p): CardContent {
    const t0 = iso(p);
    const o = p.input.origin;
    const badges: string[] = [];
    if (p.input.replay) badges.push('Not a real emergency');
    if (p.input.mock) badges.push('MOCK');
    if (p.input.testData) badges.push('Test data · not the evaluation host');
    const cache = p.input.provenance.cacheCreatedAtIso;
    const d = p.destination;
    return {
      lang: 'en',
      docTitle: 'Evacuation plan card',
      regionName: p.input.region.name.en,
      fireInputLabel: p.input.fireInputLabel.en,
      badges,
      title: o.name ? o.name.en : o.display.en,
      category: o.name ? o.category.en : null,
      statusIcon: p.kind === 'leave_by' ? 'checked_route' : p.kind === 'no_route' ? 'model_no_route' : 'unresolved',
      statusText: STATUS[p.kind],
      big:
        p.kind === 'leave_by' && p.leaveByS !== null
          ? { label: bigLabelKind(p) === 'last_checked' ? 'Checked up to' : 'Leave by', time: hm(t0, p.leaveByS), sub: `${enSpokenTime(t0, p.leaveByS)} KST` }
          : null,
      lines: p.kind === 'leave_by' ? leaveByCardLines(p) : bodyLines(p, 'card'),
      official: OFFICIAL_FIRST.en,
      dataLine: `Data time: ${enDate(t0)}${p.input.replay ? ` · Replay of recorded ${year(p)} wildfire scenarios` : ''}`,
      modelLine: MODEL_NOT_LIVE.en,
      limits: cardLimits(p),
      footer: FOOTER_APP.en,
      meta: [
        `Scenario ${p.input.scenario.scenarioSetId}`,
        `Prepared ${kstStamp(p.input.generatedAtIso)}`,
        cache ? `Precomputed ${kstStamp(cache)}` : null,
        p.kind === 'leave_by' && d && !d.name ? `Dest. ID ${d.id}` : null,
      ]
        .filter(Boolean)
        .join(' · '),
    };
  },
};
