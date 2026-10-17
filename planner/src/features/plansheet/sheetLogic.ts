/**
 * Pure helpers of the plan sheet (unit-tested in tests/planner/features.plansheet.test.ts).
 */
import type { Verdict } from '../../domain/types';
import { clockAt, formatExposure, kstClock } from '../shared/format';
import { ALT_PLAN_TEXT, attemptReasonText, NOTE_LABEL, pick, RAW_STATUS_LABEL, VERDICT_LABEL, type Lang } from '../shared/strings';
import { SHEET } from './strings';
import type { PlanSheetData, PlanSheetScenario } from './types';

export const DEFAULT_LIMITS = { peakKwM2: 10, doseKjM2: 100 } as const;

export function fill(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

/** Scenario row label "S1"… in sheet order. */
export function scenarioTag(index: number): string {
  return `S${index + 1}`;
}

/** A route may be drawn only for a checked_route scenario with a geometry. */
export function drawableRoute(s: PlanSheetScenario) {
  return s.bestVerdict === 'checked_route' && s.route && s.route.geometry?.coordinates?.length >= 2 ? s.route : null;
}

/** The travel-only comparison is drawn only next to a checked route, and only with a geometry. */
export function drawableTravelOnly(s: PlanSheetScenario) {
  return s.travelOnlyRoute && s.travelOnlyRoute.geometry?.coordinates?.length >= 2 ? s.travelOnlyRoute : null;
}

export interface AltPlanItem {
  index: number;
  tag: string;
  scenarioSetId: string;
  inputTimeIso: string;
  /** drawn zones: issue time of the zone forecast (row label) */
  issuedAtIso: string | null;
  verdict: Exclude<Verdict, 'checked_route'>;
  text: string;
  reason: string | null;
}

/** Reason of an unresolved scenario row: the MOCK raw status instead of "기타 (OTHER)". */
export function scenarioReasonText(s: Pick<PlanSheetScenario, 'reasonCode' | 'rawStatus'>, lang: Lang, opts: { short?: boolean } = {}): string | null {
  const text = attemptReasonText(s.reasonCode, s.rawStatus ?? null, lang);
  // short: the MOCK label without its raw status token (the alternative-plan line keeps the code)
  return opts.short && text && s.rawStatus && RAW_STATUS_LABEL[s.rawStatus] && (!s.reasonCode || s.reasonCode === 'OTHER') ? pick(RAW_STATUS_LABEL[s.rawStatus]!, lang) : text;
}

/**
 * What each departure time of an unresolved scenario says, as runs of equal results:
 * "04:00 모델상 경로 없음; 04:10–04:40 미확인 · <reason>". Checked and "시간창 밖" cells are left out.
 */
export function sweepReasonRuns(s: PlanSheetScenario, lang: Lang): string[] {
  return sweepRuns(s, lang).runs;
}

function sweepRuns(s: PlanSheetScenario, lang: Lang): { runs: string[]; cellReasons: boolean } {
  const cells = [...s.sweep].sort((a, b) => a.offsetS - b.offsetS);
  const runs: { from: number; to: number; label: string }[] = [];
  let any = false;
  let cellReasons = false;
  for (const c of cells) {
    if (c.verdict !== 'model_no_route' && c.verdict !== 'unresolved') {
      runs.push({ from: c.offsetS, to: c.offsetS, label: '' });
      continue;
    }
    let label = pick(VERDICT_LABEL[c.verdict], lang);
    if (c.verdict === 'model_no_route') any = true;
    if (c.verdict === 'unresolved') {
      const r = attemptReasonText(c.reasonCode ?? null, c.rawStatus ?? null, lang);
      if (r) {
        any = true;
        cellReasons = true;
        label += ` · ${r}`;
      }
    }
    const last = runs[runs.length - 1];
    if (last && last.label === label) last.to = c.offsetS;
    else runs.push({ from: c.offsetS, to: c.offsetS, label });
  }
  // nothing but reason-less unresolved cells: the scenario note / reason code says it
  if (!any) return { runs: [], cellReasons };
  return {
    runs: runs.filter((r) => r.label).map((r) => `${kstClock(s.inputTimeIso, r.from)}${r.to !== r.from ? `–${kstClock(s.inputTimeIso, r.to)}` : ''} ${r.label}`),
    cellReasons,
  };
}

/**
 * Scenarios that need an alternative plan: exactly those whose best verdict is NOT checked_route.
 * model_no_route → "차량 대피 경로를 확인하지 못함: …"; unresolved → "판단 불가 — 안전으로 간주하지 말 것"
 * with what every departure time said (recorded no-route offsets included).
 */
export function alternativePlanItems(sheet: Pick<PlanSheetData, 'scenarios'>, lang: Lang): AltPlanItem[] {
  const out: AltPlanItem[] = [];
  sheet.scenarios.forEach((s, index) => {
    if (s.bestVerdict === 'checked_route') return;
    const verdict = s.bestVerdict;
    const reasons: string[] = [];
    if (verdict === 'unresolved') {
      if (s.note) reasons.push(pick(NOTE_LABEL[s.note], lang));
      const { runs, cellReasons } = sweepRuns(s, lang);
      if (runs.length) reasons.push(runs.join('; '));
      // cells without their own reason: the scenario's reason code (MOCK status instead of OTHER)
      if (!cellReasons) {
        const r = scenarioReasonText(s, lang);
        if (r) reasons.push(r);
      }
    }
    out.push({
      index,
      tag: scenarioTag(index),
      scenarioSetId: s.scenarioSetId,
      inputTimeIso: s.inputTimeIso,
      issuedAtIso: s.issuedAtIso ?? null,
      verdict,
      text: pick(ALT_PLAN_TEXT[verdict], lang),
      reason: reasons.length ? reasons.join(' · ') : null,
    });
  });
  return out;
}

export interface PartialCheckedItem {
  index: number;
  tag: string;
  scenarioSetId: string;
  /** "18:30" — the departure deadline */
  deadline: string;
  /** "18:10" or null when even the first departure time is not a checked route */
  contiguous: string | null;
}

/**
 * Checked scenarios whose earlier departure times are not all checked routes (contiguous basis
 * differs from the deadline, or is null): "departure before the deadline" is NOT covered for them,
 * so the sheet must not claim that no alternative plan is needed. Same rule as deadlineCell's sub.
 */
export function partialCheckedScenarios(sheet: Pick<PlanSheetData, 'scenarios'>): PartialCheckedItem[] {
  const out: PartialCheckedItem[] = [];
  sheet.scenarios.forEach((s, index) => {
    if (s.bestVerdict !== 'checked_route' || s.latestSafeDepartureS === null) return;
    if (s.contiguousSafeDepartureS === s.latestSafeDepartureS) return;
    const base = { inputTimeIso: s.inputTimeIso, issuedAtIso: s.issuedAtIso ?? null };
    out.push({
      index,
      tag: scenarioTag(index),
      scenarioSetId: s.scenarioSetId,
      deadline: clockAt(base, s.latestSafeDepartureS),
      contiguous: s.contiguousSafeDepartureS === null ? null : clockAt(base, s.contiguousSafeDepartureS),
    });
  });
  return out;
}

/** The caveat line of a partially checked scenario (ko/en). */
export function partialCheckedText(item: PartialCheckedItem, lang: Lang): string {
  return fill(pick(SHEET.altCaveat, lang), { tag: item.tag, deadline: item.deadline, time: item.contiguous ?? pick(SHEET.altNoneWord, lang) });
}

export interface ExposureSummary {
  members: number;
  maxPeak: number | null;
  maxDose: number | null;
  anyContact: boolean | null;
  limits: { peakKwM2: number; doseKjM2: number };
}

/** Max over the hazard scenarios (members) of the shown route; null fields when nothing is known. */
export function exposureSummary(s: PlanSheetScenario): ExposureSummary | null {
  if (s.bestVerdict !== 'checked_route' || s.exposure.length === 0) return null;
  let maxPeak: number | null = null;
  let maxDose: number | null = null;
  let anyContact: boolean | null = null;
  for (const e of s.exposure) {
    if (e.peakKwM2 !== null && Number.isFinite(e.peakKwM2)) maxPeak = maxPeak === null ? e.peakKwM2 : Math.max(maxPeak, e.peakKwM2);
    if (e.doseKjM2 !== null && Number.isFinite(e.doseKjM2)) maxDose = maxDose === null ? e.doseKjM2 : Math.max(maxDose, e.doseKjM2);
    if (e.contact !== null) anyContact = (anyContact ?? false) || e.contact;
  }
  return { members: s.exposure.length, maxPeak, maxDose, anyContact, limits: s.limits ?? DEFAULT_LIMITS };
}

export function exposureText(sum: ExposureSummary, lang: Lang): string {
  return fill(pick(SHEET.exposureLine, lang), { peak: formatExposure(sum.maxPeak), dose: formatExposure(sum.maxDose) });
}

export interface DeadlineCell {
  main: string;
  sub: string | null;
}

/** "18:50" + "연속 확인 기준 18:30" (or "동일"/"없음"); "—" when there is no checked departure. */
export function deadlineCell(s: PlanSheetScenario, lang: Lang): DeadlineCell {
  const base = { inputTimeIso: s.inputTimeIso, issuedAtIso: s.issuedAtIso ?? null };
  if (s.bestVerdict !== 'checked_route' || s.latestSafeDepartureS === null) return { main: '—', sub: null };
  const main = clockAt(base, s.latestSafeDepartureS);
  let sub: string;
  if (s.contiguousSafeDepartureS === null) sub = pick(SHEET.contiguousNone, lang);
  else if (s.contiguousSafeDepartureS === s.latestSafeDepartureS) sub = pick(SHEET.contiguousSame, lang);
  else sub = fill(pick(SHEET.contiguous, lang), { time: clockAt(base, s.contiguousSafeDepartureS) });
  return { main, sub };
}

export function arrivalCell(s: PlanSheetScenario): string {
  if (s.bestVerdict !== 'checked_route' || !s.shelter) return '—';
  return clockAt({ inputTimeIso: s.inputTimeIso, issuedAtIso: s.issuedAtIso ?? null }, s.shelter.arrivalS);
}

/** Longitude/latitude bounds of everything drawn on the sheet map ([w, s, e, n]); null if nothing. */
export function sheetBounds(sheet: PlanSheetData): [number, number, number, number] | null {
  const pts: [number, number][] = [];
  if (Number.isFinite(sheet.origin.lon) && Number.isFinite(sheet.origin.lat)) pts.push([sheet.origin.lon, sheet.origin.lat]);
  for (const s of sheet.scenarios) {
    const r = drawableRoute(s);
    if (r) for (const c of r.geometry.coordinates) pts.push([c[0]!, c[1]!]);
    const t = r ? drawableTravelOnly(s) : null;
    if (t) for (const c of t.geometry.coordinates) pts.push([c[0]!, c[1]!]);
    if (r && s.shelter) pts.push([s.shelter.lon, s.shelter.lat]);
  }
  if (pts.length === 0) return null;
  let w = Infinity;
  let so = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  for (const [x, y] of pts) {
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    w = Math.min(w, x);
    e = Math.max(e, x);
    so = Math.min(so, y);
    n = Math.max(n, y);
  }
  return Number.isFinite(w) ? [w, so, e, n] : null;
}

/** Unique checked shelters drawn on the map. */
export function sheetShelters(sheet: PlanSheetData): { id: string; lon: number; lat: number; tags: string[] }[] {
  const by = new Map<string, { id: string; lon: number; lat: number; tags: string[] }>();
  sheet.scenarios.forEach((s, i) => {
    if (!drawableRoute(s) || !s.shelter) return;
    const cur = by.get(s.shelter.id);
    if (cur) cur.tags.push(scenarioTag(i));
    else by.set(s.shelter.id, { id: s.shelter.id, lon: s.shelter.lon, lat: s.shelter.lat, tags: [scenarioTag(i)] });
  });
  return [...by.values()];
}

/** Stable key of the map content (cache key for rendered map images). */
export function sheetMapKey(sheet: PlanSheetData, w: number, h: number): string {
  const parts: string[] = [sheet.region.id, sheet.origin.id, String(w), String(h)];
  for (const s of sheet.scenarios) {
    const r = drawableRoute(s);
    const t = r ? drawableTravelOnly(s) : null;
    const rc = r?.geometry.coordinates;
    const tc = t?.geometry.coordinates;
    parts.push(
      s.scenarioSetId,
      rc ? `${rc.length}:${rc[0]}:${rc[rc.length - 1]}` : '-',
      tc ? `${tc.length}:${tc[0]}:${tc[tc.length - 1]}` : '-',
      s.shelter?.id ?? '-',
    );
  }
  return parts.join('|');
}
