/**
 * English templates — a translation of the Korean source (./ko.ts), same structure and the same
 * facts. The SMS uses only the GSM 03.38 alphabet (no "·", no dashes); the long text avoids
 * characters outside EUC-KR so it can also be sent as a Korean LMS.
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
import type { LmReason } from '../explanation';
import type { MessagePlan, PlannedDestination } from '../plan';
import { MODEL_NOT_LIVE, MODEL_NOT_LIVE_SMS, MODEL_NOT_LIVE_SPOKEN, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS } from '../strings';

const iso = (p: MessagePlan) => p.input.scenario.inputTimeIso;

/** The planner's footer with a plain hyphen (the em dash is outside EUC-KR / GSM-7). */
const FOOTER_PLAIN = FOOTER_APP.en.replace(/\s*—\s*/g, ' - ');

function year(p: MessagePlan): number {
  return p.input.region.fireYear ?? kstParts(iso(p)).y;
}

function placeWord(p: MessagePlan): string {
  const k = p.input.origin.kind;
  return k === 'facility' ? 'facility' : k === 'research' ? 'start point' : 'village';
}

function withCategory(name: string, category: string): string {
  return name.toLowerCase().includes(category.toLowerCase()) ? name : `${name} (${category})`;
}

function originWritten(p: MessagePlan): string {
  const o = p.input.origin;
  return o.name ? withCategory(o.name.en, o.category.en) : o.display.en;
}

function destWritten(d: PlannedDestination): string {
  return d.name ? withCategory(d.name.en, d.category.en) : d.display.en;
}

function destSpoken(d: PlannedDestination): string {
  return d.name ? d.name.en : `an unnamed ${d.category.en.toLowerCase()}`;
}

function kOfN(k: number, n: number): string {
  return k >= n ? `all ${n} fire scenarios from the forecast` : `${k} of ${n} fire scenarios from the forecast`;
}

function exitNames(r: Extract<LmReason, { kind: 'all_exits_blocked' }>): string {
  const names = r.exits.map((e) => e.text.en);
  return names.length > 3 ? `${names.slice(0, 3).join(', ')} and ${names.length - 3} more` : names.join(', ');
}

function membersNote(r: Extract<LmReason, { kind: 'all_exits_blocked' }>): string {
  return r.kMin >= r.n ? `in all ${r.n} scenarios` : `in at least ${r.kMin} of ${r.n} scenarios`;
}

function smsTail(p: MessagePlan): string {
  const t = `${ymd(iso(p))} ${hm(iso(p))} KST`;
  if (p.input.mock) return `MOCK replay, ${t}`;
  if (p.input.testData) return `TEST replay, ${t}`;
  return p.input.replay ? `Replay of ${t} data` : `Data: ${t}`;
}

/** Ends a sentence once ("by 6:40 p.m." already ends with a period). */
function sentence(s: string): string {
  return s.endsWith('.') ? s : `${s}.`;
}

/** A Latin-script name exists (OSM name:en); otherwise spoken greetings stay generic. */
function latin(name: string): boolean {
  return !/[\u3131-\u318e\uac00-\ud7a3]/.test(name);
}

function bodyLines(p: MessagePlan, target: 'lms' | 'card'): CardLine[] {
  const out: CardLine[] = [];
  const t0 = iso(p);
  const place = placeWord(p);
  if (p.kind === 'leave_by' && p.leaveByS !== null) {
    const T = hm(t0, p.leaveByS);
    out.push({ role: 'instruction', text: `Leave by car no later than ${T} KST (${enSpokenTime(t0, p.leaveByS)}). Do not wait until the last minute.` });
    const d = p.destination;
    if (d) {
      if (p.destinationVaries) {
        out.push({ role: 'destination', text: `The destination depends on the departure time. Destination the model checked for leaving at ${T}: ${destWritten(d)}.` });
      } else if (d.arrivalS !== null && d.arrivalS >= p.leaveByS) {
        const min = Math.max(1, Math.round((d.arrivalS - p.leaveByS) / 60));
        out.push({
          role: 'destination',
          text: `Destination the model checked: ${destWritten(d)}. Leaving at ${T}, arrival around ${hm(t0, d.arrivalS)} KST (about ${min} min by car; traffic not included).`,
        });
      } else {
        out.push({ role: 'destination', text: `Destination the model checked: ${destWritten(d)}.` });
      }
    }
    const r = p.reason;
    if (r && (r.kind === 'flame_on_route' || r.kind === 'dwell_at_destination')) {
      const F = hm(t0, r.flameS);
      out.push({
        role: 'reason',
        text:
          r.kind === 'flame_on_route'
            ? `Why: in ${kOfN(r.k, r.n)}, flames reach ${r.road.text.en} around ${F} KST. If you leave after ${T}, you may meet the fire there.`
            : `Why: in ${kOfN(r.k, r.n)}, flames reach the destination area (${r.road.text.en}) around ${F} KST. If you leave after ${T}, you may meet the fire while staying there.`,
      });
    } else if (p.after === 'horizon') {
      out.push({ role: 'after', text: `Departures after ${T} were not checked with this data (it covers ${durationText(p.input.scenario.horizonS, 'en')} from the data time).` });
    } else if (p.after === 'gap') {
      out.push({ role: 'after', text: `Some departure times after ${T} could not be checked, so this message covers departures up to ${T} only.` });
    } else {
      out.push({ role: 'after', text: `Departures after ${T} have no checked route in the model.` });
    }
    out.push({ role: 'guide', text: 'Follow official guidance on where to go and which roads to use.' });
    out.push({
      role: 'note',
      text:
        p.input.origin.kind === 'facility'
          ? 'If the facility lacks vehicles to move its residents, tell the eup/myeon office now.'
          : 'If you have no car or cannot move on your own, tell the village head or the eup/myeon office now.',
    });
    const dist = p.input.origin.entryDistanceM;
    out.push({
      role: 'note',
      text:
        dist !== null && dist >= 1 && p.input.origin.kind !== 'research'
          ? `Times refer to the nearest road point (entry point), ${distanceText(dist)} from the ${place}. Time to get ready and board is not included.`
          : 'Times refer to the nearest road point (entry point). Time to get ready and board is not included.',
    });
    return out;
  }
  if (p.kind === 'no_route') {
    out.push({ role: 'status', text: 'No checked vehicle route in the model.' });
    out.push({ role: 'instruction', text: 'Call 119 or the eup/myeon office now and follow official instructions.' });
    const r = p.reason;
    if (r && r.kind === 'all_exits_blocked') {
      out.push({
        role: 'reason',
        text: `Why: in the fire forecast, all ${r.exits.length} roads leaving the ${place} (${exitNames(r)}) meet flames within ${durationText(p.input.scenario.horizonS, 'en')} of the data time (${membersNote(r)}).`,
      });
    }
    if (target === 'card') out.push({ role: 'meaning', text: '"No route in the model" means no checked route for any departure time or destination that was checked.' });
    return out;
  }
  if (p.kind === 'partial') {
    out.push({ role: 'status', text: `Model results differ by departure time, and leaving at the data time (${hm(t0)} KST) was not checked.` });
    out.push({ role: 'instruction', text: 'Follow official evacuation guidance.' });
    if (target === 'card') out.push({ role: 'note', text: 'See the pre-season plan sheet for the result at each departure time.' });
    return out;
  }
  out.push({ role: 'status', text: 'The model could not check a vehicle route (unresolved).' });
  out.push({ role: 'meaning', text: 'Unresolved means neither that a route exists nor that it does not.' });
  out.push({ role: 'instruction', text: 'Follow official evacuation guidance.' });
  const note = p.input.plan?.note ?? (p.input.plan ? null : 'not_computed');
  if (note === 'not_checkable') out.push({ role: 'note', text: `This ${place} has no checkable road point within ${ENTRY_LIMIT_M / 1000} km, so it was not checked.` });
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
  out.push({ role: 'instruction', text: 'Do not wait for the deadline: leave by car early.' });
  const d = p.destination;
  if (d) {
    if (p.destinationVaries) out.push({ role: 'destination', text: `The destination depends on the departure time; for ${T}: ${destWritten(d)}` });
    else if (d.arrivalS !== null && d.arrivalS >= p.leaveByS) {
      const min = Math.max(1, Math.round((d.arrivalS - p.leaveByS) / 60));
      out.push({ role: 'destination', text: `Model-checked destination: ${destWritten(d)}; leave ${T}, arrive around ${hm(t0, d.arrivalS)} (about ${min} min by car; traffic not included)` });
    } else out.push({ role: 'destination', text: `Model-checked destination: ${destWritten(d)}` });
  }
  const r = p.reason;
  if (r && (r.kind === 'flame_on_route' || r.kind === 'dwell_at_destination')) {
    const F = hm(t0, r.flameS);
    out.push({
      role: 'reason',
      text:
        r.kind === 'flame_on_route'
          ? `Why: in ${kOfN(r.k, r.n)}, flames reach ${r.road.text.en} around ${F}.`
          : `Why: in ${kOfN(r.k, r.n)}, flames reach the destination area (${r.road.text.en}) around ${F}.`,
    });
  } else if (p.after === 'horizon') {
    out.push({ role: 'after', text: `Departures after ${T} were not checked (the data covers ${durationText(p.input.scenario.horizonS, 'en')}).` });
  } else if (p.after === 'gap') {
    out.push({ role: 'after', text: `Some departure times after ${T} were not checked; this card covers up to ${T}.` });
  } else {
    out.push({ role: 'after', text: `No checked route for departures after ${T}.` });
  }
  out.push({
    role: 'guide',
    text:
      'Follow official guidance on where to go. ' +
      (p.input.origin.kind === 'facility' ? 'Not enough vehicles? Tell the eup/myeon office now.' : 'No car, or cannot move alone? Tell the village head or eup/myeon office now.'),
  });
  return out;
}

/** Card limitations; a leave-by card starts with what its times refer to (the entry point). */
function cardLimits(p: MessagePlan): string {
  const base = 'Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents';
  if (p.kind !== 'leave_by') return base;
  const dist = p.input.origin.entryDistanceM;
  const entry =
    dist !== null && dist >= 1 && p.input.origin.kind !== 'research'
      ? `Times at the road entry point ${distanceText(dist)} away; boarding time not included`
      : 'Times at the nearest road entry point; boarding time not included';
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
  partial: 'Partly checked: leaving at the data time was not checked',
};

function spokenReason(p: MessagePlan): SpokenBlock | null {
  const t0 = iso(p);
  const r = p.reason;
  if (r && r.kind === 'flame_on_route') return { optional: 'reason', text: `In ${kOfN(r.k, r.n)}, flames reach ${r.road.text.en} around ${enSpokenTime(t0, r.flameS)}` };
  if (r && r.kind === 'dwell_at_destination') return { optional: 'reason', text: `In ${kOfN(r.k, r.n)}, flames reach the destination area around ${enSpokenTime(t0, r.flameS)}` };
  if (r && r.kind === 'all_exits_blocked') {
    return { optional: 'reason', text: `In the fire forecast, all ${r.exits.length} roads leaving this place meet flames within ${durationText(p.input.scenario.horizonS, 'en')}.` };
  }
  if (p.kind === 'leave_by') {
    if (p.after === 'horizon') return { optional: 'reason', text: 'Later departures were not checked with this data.' };
    if (p.after === 'gap') return { optional: 'reason', text: 'Some later departure times were not checked.' };
    return { optional: 'reason', text: 'Later departures have no checked route.' };
  }
  return null;
}

export const EN: TemplateSet = {
  lang: 'en',

  sms(p) {
    const lines: string[] = [];
    if (p.kind === 'leave_by' && p.leaveByS !== null) lines.push('Model: checked route found.', `Leave by ${hm(iso(p), p.leaveByS)} KST.`);
    else if (p.kind === 'no_route') lines.push('No route in the model.', 'Call 119 or the eup/myeon office now.');
    else if (p.kind === 'partial') lines.push('Partly checked in the model.', 'Follow official evacuation guidance.');
    else lines.push('Unresolved: route not checked.', 'Follow official evacuation guidance.');
    lines.push(OFFICIAL_FIRST_SMS.en, MODEL_NOT_LIVE_SMS.en, smsTail(p));
    return lines.join('\n');
  },

  lms(p) {
    const tag = [p.input.replay ? `${year(p)} recorded replay` : 'planning data', p.input.mock ? 'MOCK' : null, p.input.testData ? 'TEST DATA' : null].filter(Boolean).join(', ');
    return [
      `[Wildfire evacuation plan information - ${tag}]`,
      originWritten(p),
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
    blocks.push({
      text:
        o.kind === 'facility'
          ? o.name && latin(o.name.en)
            ? `Attention, staff and residents of ${o.name.en}.`
            : 'Attention, staff and residents of this facility.'
          : o.name && o.kind === 'village' && latin(o.name.en)
            ? `Attention, residents of ${o.name.en}.`
            : 'Attention, residents.',
    });
    blocks.push({
      text:
        `This is ${MODEL_NOT_LIVE_SPOKEN.en} from ${p.input.replay ? 'a replay of recorded wildfire data' : 'planning data'}, ${enDateSpoken(t0)} Korea time. It is not live information.` +
        (p.input.mock ? ' This is mock server data.' : '') +
        (p.input.testData ? ' These are test results.' : ''),
    });
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = enSpokenTime(t0, p.leaveByS);
      blocks.push({
        text:
          p.destination && !p.destinationVaries
            ? `${sentence(`Leave by car by ${S}`)} The model checked a route to ${destSpoken(p.destination)} for departures up to then.`
            : `${sentence(`Leave by car by ${S}`)} The model checked routes for departures up to then.`,
      });
      const why = spokenReason(p);
      if (why) blocks.push(why);
      blocks.push({ text: 'Follow official guidance on where to go.' });
      blocks.push({
        optional: 'carless',
        text: o.kind === 'facility' ? 'If vehicles are short, tell the eup/myeon office now.' : 'If you have no car, tell the village head or the eup/myeon office now.',
      });
      blocks.push({ optional: 'repeat', text: sentence(`Again: leave by ${S}`) });
    } else if (p.kind === 'no_route') {
      blocks.push({ text: 'In the model, there is no checked vehicle route from here. Call 119 or the eup/myeon office now, and follow official instructions.' });
      const why = spokenReason(p);
      if (why) blocks.push(why);
      blocks.push({ optional: 'repeat', text: 'Again: call 119 or the eup/myeon office now.' });
    } else if (p.kind === 'partial') {
      blocks.push({ text: 'Model results differ by departure time, and leaving at the data time was not checked. Follow official evacuation guidance.' });
      blocks.push({ optional: 'repeat', text: 'Again: follow official evacuation guidance.' });
    } else {
      blocks.push({ text: 'The model could not check a vehicle route from here. This means neither that a route exists nor that it does not. Follow official evacuation guidance.' });
      blocks.push({ optional: 'repeat', text: 'Again: follow official evacuation guidance.' });
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
    if (p.kind === 'no_route') lines.push('[Before the call] Check that 119 and the eup/myeon office have been contacted first.');
    if (o.name && o.kind === 'facility') {
      lines.push(`Hello, this is [staff name] from ${o.name.en}. I am calling the family of [resident name] about the wildfire evacuation plan.`);
    } else if (o.name && o.kind === 'village') {
      lines.push(`Hello, this is [your name and role]. I am calling the family of [resident name], who lives in ${o.name.en}, about the wildfire evacuation plan.`);
    } else {
      lines.push('Hello, this is [your name and role]. I am calling the family of [resident name] about the wildfire evacuation plan.');
    }
    lines.push(
      `This is ${MODEL_NOT_LIVE_SPOKEN.en} from ${p.input.replay ? 'a replay of recorded wildfire data' : 'planning data'}, ${enDateSpoken(t0)} Korea time. It is not live information.` +
        (p.input.mock ? ' This is mock server data.' : '') +
        (p.input.testData ? ' These are test results.' : ''),
    );
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      const S = enSpokenTime(t0, p.leaveByS);
      lines.push(
        p.destination && !p.destinationVaries
          ? `In the model, leaving by car from the road near the ${place} by ${S} gives a checked route to ${destSpoken(p.destination)}.`
          : `In the model, leaving by car from the road near the ${place} by ${S} gives a checked route. The destination depends on the departure time.`,
      );
      const r = p.reason;
      if (r && r.kind === 'flame_on_route') lines.push(`The reason: in ${kOfN(r.k, r.n)}, flames reach ${r.road.text.en} around ${enSpokenTime(t0, r.flameS)}`);
      else if (r && r.kind === 'dwell_at_destination') lines.push(`The reason: in ${kOfN(r.k, r.n)}, flames reach the destination area around ${enSpokenTime(t0, r.flameS)}`);
      else if (p.after === 'horizon') lines.push('Later departures were not checked with this data.');
      else if (p.after === 'gap') lines.push('Some later departure times were not checked.');
      else lines.push('Later departures have no checked route.');
    } else if (p.kind === 'no_route') {
      lines.push(`In the model, there was no checked vehicle route from the ${place}. So 119 and the eup/myeon office must be contacted now, and official instructions followed.`);
      const r = p.reason;
      if (r && r.kind === 'all_exits_blocked') {
        lines.push(`In the fire forecast, all ${r.exits.length} roads leaving the ${place} meet flames within ${durationText(p.input.scenario.horizonS, 'en')}.`);
      }
    } else if (p.kind === 'partial') {
      lines.push('Model results differ by departure time, and leaving at the data time was not checked. Official evacuation guidance must be followed.');
    } else {
      lines.push(`The model could not check a vehicle route from the ${place} (unresolved). This means neither that a route exists nor that it does not. Official evacuation guidance must be followed.`);
    }
    lines.push(`${OFFICIAL_FIRST.en} The actual place and time of any move may change with official guidance.`);
    lines.push('If you have questions, please call [phone number]. Thank you.');
    return lines.join('\n');
  },

  card(p): CardContent {
    const t0 = iso(p);
    const o = p.input.origin;
    const badges: string[] = [];
    if (p.input.mock) badges.push('MOCK');
    if (p.input.testData) badges.push('Test data · not the evaluation host');
    const cache = p.input.provenance.cacheCreatedAtIso;
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
      big: p.kind === 'leave_by' && p.leaveByS !== null ? { label: 'Leave by', time: hm(t0, p.leaveByS), sub: `${enSpokenTime(t0, p.leaveByS)} KST` } : null,
      lines: p.kind === 'leave_by' ? leaveByCardLines(p) : bodyLines(p, 'card').filter((l) => l.role !== 'status'),
      official: OFFICIAL_FIRST.en,
      dataLine: `Data time: ${enDate(t0)}${p.input.replay ? ` · Replay of recorded ${year(p)} wildfire scenarios` : ''}`,
      modelLine: MODEL_NOT_LIVE.en,
      limits: cardLimits(p),
      footer: FOOTER_APP.en,
      meta: [`Prepared ${kstStamp(p.input.generatedAtIso)}`, `Scenario ${p.input.scenario.scenarioSetId}`, cache ? `Precomputed ${kstStamp(cache)}` : null]
        .filter(Boolean)
        .join(' · '),
    };
  },
};
