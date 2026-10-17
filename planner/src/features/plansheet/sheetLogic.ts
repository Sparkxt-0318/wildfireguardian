/**
 * Pure helpers of the plan sheet (unit-tested in tests/planner/features.plansheet.test.ts).
 */
import type { Verdict } from '../../domain/types';
import { clockAt, formatExposure } from '../shared/format';
import { ALT_PLAN_TEXT, NOTE_LABEL, pick, reasonText, type Lang } from '../shared/strings';
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

/**
 * Scenarios that need an alternative plan: exactly those whose best verdict is NOT checked_route.
 * model_no_route → "차량 대피 경로를 확인하지 못함: …"; unresolved → "판단 불가 — 안전으로 간주하지 말 것".
 */
export function alternativePlanItems(sheet: Pick<PlanSheetData, 'scenarios'>, lang: Lang): AltPlanItem[] {
  const out: AltPlanItem[] = [];
  sheet.scenarios.forEach((s, index) => {
    if (s.bestVerdict === 'checked_route') return;
    const verdict = s.bestVerdict;
    const reasons: string[] = [];
    if (verdict === 'unresolved') {
      if (s.note) reasons.push(pick(NOTE_LABEL[s.note], lang));
      const r = reasonText(s.reasonCode, lang);
      if (r) reasons.push(r);
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
