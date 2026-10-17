/**
 * Pure client-side exports (no DOM, no I/O). Unit-tested in tests/planner/features.exports.test.ts.
 *
 * - routeToGeoJSON: FeatureCollection with the route LineString (times_s per vertex), origin and
 *   shelter points, verdict / arrival / provenance properties and the fire-input label.
 * - routeToKML: KML 2.2 document with styles, Placemarks and ExtendedData ("MOCK" in the name when mock).
 * - dispatchListCSV: one row per origin, UTF-8 with BOM (Excel), RFC 4180 quoting, CRLF.
 *
 * Honesty: only a checked_route is ever emitted as a route (ExportRefusedError otherwise); a
 * travel-time-only route is only emitted with role "travel_only_comparison", its own verdict and
 * its full-policy grade, and is never called an evacuation route.
 */
import type { FeatureCollection } from 'geojson';
import { compactUtc, parseUtc } from '../../domain/clock';
import { compareUrgency, type UrgencyItem } from '../../domain/plan';
import type { OriginPlan, Verdict } from '../../domain/types';
import { kstDateClock, kstStamp, slug } from '../shared/format';
import { ALT_PLAN_TEXT, FOOTER_APP, NOTE_LABEL, pick, reasonText, VERDICT_LABEL, type Lang } from '../shared/strings';
import type { ExportInput, ExportOrigin, ExportProvenance, ExportRoute } from './types';

export const EXPORT_SCHEMA = 'wfg.planner.export/1';

export type RefusalCode = 'NO_CHECKED_ROUTE' | 'INVALID_GEOMETRY' | 'POLICY_NOT_FULL' | 'ROLE_POLICY_MISMATCH' | 'NO_ROUTE_SELECTED';

export class ExportRefusedError extends Error {
  readonly code: RefusalCode;
  constructor(code: RefusalCode, message: string) {
    super(message);
    this.name = 'ExportRefusedError';
    this.code = code;
  }
}

/** Throws ExportRefusedError unless the route may be exported in its role. */
export function assertExportable(route: ExportRoute | null | undefined): asserts route is ExportRoute {
  if (!route) throw new ExportRefusedError('NO_ROUTE_SELECTED', 'no route selected');
  if (route.verdict !== 'checked_route') {
    throw new ExportRefusedError(
      'NO_CHECKED_ROUTE',
      `only checked routes are exported; this result is ${route.verdict} (model_no_route and unresolved are never drawn as routes)`,
    );
  }
  if (route.role === 'evacuation_route' && route.policy !== 'full') {
    throw new ExportRefusedError(
      'POLICY_NOT_FULL',
      `an evacuation route must come from the full policy; ${route.policy} routes are exported only as role "travel_only_comparison"`,
    );
  }
  if (route.role === 'travel_only_comparison' && route.policy !== 'travel_only') {
    throw new ExportRefusedError('ROLE_POLICY_MISMATCH', `role travel_only_comparison requires policy travel_only, got ${route.policy}`);
  }
  const n = route.coordinates?.length ?? 0;
  if (n < 2 || route.coordinates.some((c) => !Array.isArray(c) || !Number.isFinite(c[0]) || !Number.isFinite(c[1]))) {
    throw new ExportRefusedError('INVALID_GEOMETRY', 'route geometry needs at least two finite [lon, lat] vertices');
  }
  if (!Array.isArray(route.timesS) || route.timesS.length !== n || route.timesS.some((t) => !Number.isFinite(t))) {
    throw new ExportRefusedError('INVALID_GEOMETRY', 'times_s must give one finite time per vertex');
  }
}

/** True when assertExportable would pass. */
export function isExportable(route: ExportRoute | null | undefined): boolean {
  try {
    assertExportable(route);
    return true;
  } catch {
    return false;
  }
}

const r7 = (x: number) => Math.round(x * 1e7) / 1e7;

/** Offsets are seconds after the input time (the API's journey clock) in every mode. */
function clockBase(input: ExportInput): string {
  return input.scenario.inputTimeIso;
}

function provenanceObject(p: ExportProvenance): Record<string, unknown> {
  return {
    checkpoint: p.checkpoint,
    package: p.packageName ?? 'wfg_latest',
    package_version: p.packageVersion,
    kit: p.kit,
    api_mode: p.apiMode,
    cache_api_mode: p.cacheApiMode ?? null,
    api_version: p.apiVersion,
    git_commit: p.gitCommit,
    cache_created_at: p.cacheCreatedAtIso,
    scenario_set_id: p.scenarioSetId,
    scenario_ids: p.scenarioIds ?? [],
    input_hashes: p.inputHashes ?? {},
    graph_id: p.graphId ?? null,
    host: p.hostLabel ?? null,
    evaluated_configuration: p.evaluatedConfiguration ?? null,
    recorded_mission_match: p.recordedMissionMatch ?? null,
    approximation: p.approximation ?? null,
  };
}

const TRAVEL_ONLY_NOTE = {
  ko: '비교용: 이동시간만 고려한 경로 (화재 위험 미반영) — 대피 경로 아님',
  en: 'Comparison only: travel-time-only route (fire hazard ignored) — not an evacuation route',
};

function routeProperties(input: ExportInput, route: ExportRoute, lang: Lang): Record<string, unknown> {
  const base = clockBase(input);
  const isComparison = route.role === 'travel_only_comparison';
  const props: Record<string, unknown> = {
    role: route.role,
    evacuation_route: !isComparison,
    verdict: route.verdict,
    verdict_label: pick(VERDICT_LABEL[route.verdict], lang),
    policy: route.policy,
    origin_id: route.origin.id,
    origin_name: route.origin.name,
    origin_source_tag: route.origin.sourceTag,
    shelter_id: route.shelter.id,
    shelter_name: route.shelter.name,
    shelter_source_tag: route.shelter.sourceTag,
    departure_s: route.departureS,
    departure_kst: kstDateClock(base, route.departureS) || null,
    arrival_s: route.arrivalS,
    arrival_kst: kstDateClock(base, route.arrivalS) || null,
    dwell_end_s: route.dwellEndS ?? null,
    times_s: route.timesS,
    length_m: route.lengthM ?? null,
    compute_s: route.computeS ?? null,
    job_id: route.jobId ?? null,
    exposure: (route.exposure ?? []).map((e) => ({
      scenario_id: e.scenarioId,
      peak_kw_m2: e.peakKwM2,
      dose_kj_m2: e.doseKjM2,
      contact: e.contact,
    })),
    fire_input_label: input.fireInputLabel,
    fire_input_type: input.fireInputType ?? 'recorded',
    scenario_set_id: input.scenario.scenarioSetId,
    input_time: input.scenario.inputTimeIso,
    issued_at: input.scenario.issuedAtIso ?? null,
    mock: input.mock,
    provenance: provenanceObject(route.provenance ?? input.provenance),
  };
  if (isComparison) {
    props.full_policy_pass = route.fullPolicyPass ?? null;
    props.full_policy_failures = route.fullPolicyFailures ?? null;
    props.note = pick(TRAVEL_ONLY_NOTE, lang);
  }
  return props;
}

/** Name, or "{category} · 이름 없음" — names are never invented. */
function placeLabel(p: { name: string | null; categoryLabel: string }, lang: Lang): string {
  return p.name || `${p.categoryLabel} · ${lang === 'en' ? 'unnamed' : '이름 없음'}`;
}

function docName(input: ExportInput, route: ExportRoute, lang: Lang): string {
  const region = lang === 'en' ? input.region.nameEn : input.region.nameKo;
  const head = lang === 'en' ? 'WildfireGuardian pre-season evacuation route' : 'WildfireGuardian 사전 대피 경로';
  return `${input.mock ? 'MOCK — ' : ''}${head} · ${region} · ${placeLabel(route.origin, lang)} → ${placeLabel(route.shelter, lang)}`;
}

/**
 * GeoJSON FeatureCollection (RFC 7946 with foreign members `name`, `wfg`, `provenance`) of a
 * checked route, plus optionally its travel-time-only comparison.
 */
export function routeToGeoJSON(
  input: ExportInput,
  route: ExportRoute | null = input.selectedRoute,
  opts: { comparison?: ExportRoute | null; lang?: Lang } = {},
): FeatureCollection & Record<string, unknown> {
  const lang = opts.lang ?? 'ko';
  assertExportable(route);
  const comparison = opts.comparison ?? null;
  if (comparison) {
    assertExportable(comparison);
    if (comparison.role !== 'travel_only_comparison') {
      throw new ExportRefusedError('ROLE_POLICY_MISMATCH', 'the comparison route must have role travel_only_comparison');
    }
  }
  const features: FeatureCollection['features'] = [];
  // drawn zones: the zones as an extra layer (polygons, properties.arrival_h_max), drawn first
  for (const z of zoneFeatures(input)) features.push(z);
  const line = (r: ExportRoute) => ({
    type: 'Feature' as const,
    id: `${r.role}:${r.origin.id}`,
    geometry: { type: 'LineString' as const, coordinates: r.coordinates.map((c) => [r7(c[0]), r7(c[1])]) },
    properties: routeProperties(input, r, lang),
  });
  features.push(line(route));
  if (comparison) features.push(line(comparison));
  const base = clockBase(input);
  features.push({
    type: 'Feature',
    id: `origin:${route.origin.id}`,
    geometry: { type: 'Point', coordinates: [r7(route.origin.lon), r7(route.origin.lat)] },
    properties: {
      role: 'origin',
      id: route.origin.id,
      name: route.origin.name,
      category: route.origin.categoryLabel,
      source_tag: route.origin.sourceTag,
      departure_s: route.departureS,
      departure_kst: kstDateClock(base, route.departureS) || null,
      mock: input.mock,
    },
  });
  features.push({
    type: 'Feature',
    id: `shelter:${route.shelter.id}`,
    geometry: { type: 'Point', coordinates: [r7(route.shelter.lon), r7(route.shelter.lat)] },
    properties: {
      role: 'shelter',
      id: route.shelter.id,
      name: route.shelter.name,
      category: route.shelter.categoryLabel,
      source_tag: route.shelter.sourceTag,
      verdict: route.verdict,
      arrival_s: route.arrivalS,
      arrival_kst: kstDateClock(base, route.arrivalS) || null,
      dwell_end_s: route.dwellEndS ?? null,
      mock: input.mock,
    },
  });
  return {
    type: 'FeatureCollection',
    name: docName(input, route, lang),
    wfg: {
      schema: EXPORT_SCHEMA,
      region_id: input.region.id,
      fire_input_label: input.fireInputLabel,
      fire_input_type: input.fireInputType ?? 'recorded',
      mock: input.mock,
      scenario_set_id: input.scenario.scenarioSetId,
      input_time: input.scenario.inputTimeIso,
      issued_at: input.scenario.issuedAtIso ?? null,
      generated_at: input.generatedAtIso,
      disclaimer: pick(FOOTER_APP, lang),
    },
    provenance: provenanceObject(input.provenance),
    features,
  };
}

/* ---------- drawn spread zones ---------- */

const ZONE_NOTE = {
  ko: '사용자 입력 확산 구역 (가정) — 근사, 전문가 검토 필요',
  en: 'User-drawn spread zone (assumption) — approximation, requires expert review',
};

function zoneFeatures(input: ExportInput): FeatureCollection['features'] {
  if (input.fireInputType !== 'spread_zones' || !input.zones) return [];
  return input.zones.features.map((f, i) => ({
    type: 'Feature' as const,
    id: `spread_zone:${(f.properties as Record<string, unknown> | null)?.arrival_h_max ?? i}`,
    geometry: f.geometry,
    properties: { role: 'spread_zone', ...(f.properties ?? {}), mock: input.mock },
  }));
}

/** The drawn zones alone (GeoJSON), with the fire-input label, issue time and provenance. */
export function zonesToGeoJSON(input: ExportInput, opts: { lang?: Lang } = {}): FeatureCollection & Record<string, unknown> {
  const lang = opts.lang ?? 'ko';
  const features = zoneFeatures(input);
  if (!features.length) throw new ExportRefusedError('NO_ROUTE_SELECTED', 'no drawn zones to export');
  const region = lang === 'en' ? input.region.nameEn : input.region.nameKo;
  return {
    type: 'FeatureCollection',
    name: `${input.mock ? 'MOCK — ' : ''}${lang === 'en' ? 'WildfireGuardian user-drawn spread zones' : 'WildfireGuardian 사용자 입력 확산 구역'} · ${region}`,
    wfg: {
      schema: EXPORT_SCHEMA,
      region_id: input.region.id,
      fire_input_label: input.fireInputLabel,
      fire_input_type: 'spread_zones',
      mock: input.mock,
      input_time: input.scenario.inputTimeIso,
      issued_at: input.scenario.issuedAtIso ?? null,
      burning_scenario_set_id: input.scenario.scenarioSetId,
      note: pick(ZONE_NOTE, lang),
      generated_at: input.generatedAtIso,
      disclaimer: pick(FOOTER_APP, lang),
    },
    provenance: provenanceObject(input.provenance),
    features,
  };
}

/* ---------- KML ---------- */

/** XML text/attribute escape; strips characters not allowed in XML 1.0. */
export function xmlEscape(v: unknown): string {
  const s = v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);
  return s
    .replace(/[^\u0009\u000A\u000D -퟿-�\u{10000}-\u{10FFFF}]/gu, '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function kmlData(pairs: [string, unknown][]): string {
  return `<ExtendedData>${pairs.map(([k, v]) => `<Data name="${xmlEscape(k)}"><value>${xmlEscape(v)}</value></Data>`).join('')}</ExtendedData>`;
}

/** KML colours are aabbggrr. */
const KML_GREEN = 'ff559e1a';
const KML_INK_60 = '990c0b0b';
const KML_INK = 'ff0c0b0b';

function routeKmlPairs(input: ExportInput, route: ExportRoute, lang: Lang): [string, unknown][] {
  const p = routeProperties(input, route, lang);
  const prov = p.provenance as Record<string, unknown>;
  const pairs: [string, unknown][] = Object.entries(p)
    .filter(([k]) => k !== 'provenance' && k !== 'times_s' && k !== 'exposure')
    .map(([k, v]) => [k, v]);
  pairs.push(['times_s', route.timesS.join(',')]);
  pairs.push(['exposure', p.exposure]);
  for (const [k, v] of Object.entries(prov)) pairs.push([`provenance_${k}`, v]);
  return pairs;
}

export function routeToKML(
  input: ExportInput,
  route: ExportRoute | null = input.selectedRoute,
  opts: { comparison?: ExportRoute | null; lang?: Lang } = {},
): string {
  const lang = opts.lang ?? 'ko';
  assertExportable(route);
  const comparison = opts.comparison ?? null;
  if (comparison) {
    assertExportable(comparison);
    if (comparison.role !== 'travel_only_comparison') {
      throw new ExportRefusedError('ROLE_POLICY_MISMATCH', 'the comparison route must have role travel_only_comparison');
    }
  }
  const base = clockBase(input);
  const coords = (r: ExportRoute) => r.coordinates.map((c) => `${r7(c[0])},${r7(c[1])},0`).join(' ');
  const mockTag = input.mock ? ' (MOCK)' : '';
  const description = [
    input.mock ? 'MOCK — ' + (lang === 'en' ? 'recorded results replayed by the mock server.' : '모의 서버가 기록 결과를 재생한 자료입니다.') : null,
    `${lang === 'en' ? 'Fire input' : '산불 입력'}: ${input.fireInputLabel}`,
    pick(FOOTER_APP, lang),
  ]
    .filter(Boolean)
    .join(' ');
  const routeName = (r: ExportRoute) =>
    r.role === 'travel_only_comparison'
      ? `${pick(TRAVEL_ONLY_NOTE, lang)}${mockTag}`
      : `${pick(VERDICT_LABEL.checked_route, lang)}: ${placeLabel(r.origin, lang)} → ${placeLabel(r.shelter, lang)}${mockTag}`;

  const out: string[] = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<kml xmlns="http://www.opengis.net/kml/2.2">',
    '<Document>',
    `<name>${xmlEscape(docName(input, route, lang))}</name>`,
    `<description>${xmlEscape(description)}</description>`,
    `<Style id="checked_route"><LineStyle><color>${KML_GREEN}</color><width>4</width></LineStyle></Style>`,
    `<Style id="travel_only_comparison"><LineStyle><color>${KML_INK_60}</color><width>2</width></LineStyle></Style>`,
    `<Style id="origin"><IconStyle><color>${KML_INK}</color><scale>1.0</scale></IconStyle><LabelStyle><scale>0.9</scale></LabelStyle></Style>`,
    `<Style id="shelter"><IconStyle><color>${KML_GREEN}</color><scale>1.1</scale></IconStyle><LabelStyle><scale>0.9</scale></LabelStyle></Style>`,
    kmlData([
      ['schema', EXPORT_SCHEMA],
      ['region_id', input.region.id],
      ['fire_input_label', input.fireInputLabel],
      ['fire_input_type', input.fireInputType ?? 'recorded'],
      ['mock', input.mock],
      ['scenario_set_id', input.scenario.scenarioSetId],
      ['input_time', input.scenario.inputTimeIso],
      ['generated_at', input.generatedAtIso],
      ...Object.entries(provenanceObject(input.provenance)).map(([k, v]) => [`provenance_${k}`, v] as [string, unknown]),
    ]),
  ];
  for (const r of comparison ? [route, comparison] : [route]) {
    out.push(
      `<Placemark id="${xmlEscape(`${r.role}-${slug(r.origin.id)}`)}"><name>${xmlEscape(routeName(r))}</name><styleUrl>#${r.role === 'travel_only_comparison' ? 'travel_only_comparison' : 'checked_route'}</styleUrl>${kmlData(
        routeKmlPairs(input, r, lang),
      )}<LineString><tessellate>1</tessellate><coordinates>${coords(r)}</coordinates></LineString></Placemark>`,
    );
  }
  out.push(
    `<Placemark id="origin"><name>${xmlEscape(`${lang === 'en' ? 'Origin' : '출발지'}: ${placeLabel(route.origin, lang)}${mockTag}`)}</name><styleUrl>#origin</styleUrl>${kmlData([
      ['role', 'origin'],
      ['id', route.origin.id],
      ['name', route.origin.name],
      ['source_tag', route.origin.sourceTag],
      ['departure_kst', kstDateClock(base, route.departureS)],
      ['mock', input.mock],
    ])}<Point><coordinates>${r7(route.origin.lon)},${r7(route.origin.lat)},0</coordinates></Point></Placemark>`,
  );
  out.push(
    `<Placemark id="shelter"><name>${xmlEscape(`${lang === 'en' ? 'Shelter' : '대피소'}: ${placeLabel(route.shelter, lang)}${mockTag}`)}</name><styleUrl>#shelter</styleUrl>${kmlData([
      ['role', 'shelter'],
      ['id', route.shelter.id],
      ['name', route.shelter.name],
      ['source_tag', route.shelter.sourceTag],
      ['verdict', route.verdict],
      ['arrival_kst', kstDateClock(base, route.arrivalS)],
      ['mock', input.mock],
    ])}<Point><coordinates>${r7(route.shelter.lon)},${r7(route.shelter.lat)},0</coordinates></Point></Placemark>`,
  );
  out.push('</Document>', '</kml>', '');
  return out.join('\n');
}

/* ---------- CSV ---------- */

export const CSV_BOM = '﻿';

export const CSV_COLUMNS: Record<Lang, string[]> = {
  ko: ['우선순위', '출발지', '구분', '출처 태그', '판정', '출발 마감 KST', '연속 확인 기준', '대피소', '도착 KST', '시나리오 입력 시각', 'API 모드', '비고'],
  en: [
    'Priority',
    'Origin',
    'Type',
    'Source tag',
    'Verdict',
    'Depart by (KST)',
    'Contiguous basis (KST)',
    'Shelter',
    'Arrival (KST)',
    'Scenario input time',
    'API mode',
    'Notes',
  ],
};

/** RFC 4180 field: quoted when it contains a comma, quote, CR or LF; quotes doubled. Spreadsheet
 *  formula prefixes (= + - @) are neutralised with a leading apostrophe. */
export function csvField(v: unknown): string {
  let s = v === null || v === undefined ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function csvRow(fields: unknown[]): string {
  return fields.map(csvField).join(',');
}

/** Planner urgency order (ARCHITECTURE.md §6) unless every origin carries an urgencyRank. */
export function orderOrigins(origins: ExportOrigin[]): ExportOrigin[] {
  if (origins.length > 0 && origins.every((o) => typeof o.urgencyRank === 'number')) {
    return [...origins].sort((a, b) => a.urgencyRank! - b.urgencyRank! || a.id.localeCompare(b.id));
  }
  const items = origins.map((o) => ({
    o,
    u: {
      id: o.id,
      name: o.name ?? '',
      vulnerable: o.vulnerable,
      plan: o.plan
        ? ({ bestVerdict: o.plan.bestVerdict, latestSafeDepartureS: o.plan.latestSafeDepartureS } as unknown as OriginPlan)
        : null,
    } satisfies UrgencyItem,
  }));
  items.sort((a, b) => compareUrgency(a.u, b.u));
  return items.map((x) => x.o);
}

function apiModeLabel(p: ExportProvenance, lang: Lang): string {
  if (p.apiMode === 'mock') return 'MOCK';
  if (p.apiMode === 'live') return lang === 'en' ? 'live API' : '실시간 API';
  const inner = p.cacheApiMode === 'mock' ? 'MOCK' : p.cacheApiMode === 'live' ? (lang === 'en' ? 'live API' : '실시간 API') : null;
  const head = lang === 'en' ? 'precomputed cache' : '사전 계산 캐시';
  return inner ? `${head} (${inner})` : head;
}

function originNotes(input: ExportInput, o: ExportOrigin, lang: Lang): string {
  const notes: string[] = [];
  const v: Verdict = o.plan?.bestVerdict ?? 'unresolved';
  if (v === 'model_no_route') notes.push(pick(ALT_PLAN_TEXT.model_no_route, lang));
  if (v === 'unresolved') {
    notes.push(pick(ALT_PLAN_TEXT.unresolved, lang));
    if (!o.plan) notes.push(pick(NOTE_LABEL.not_computed, lang));
    if (o.plan?.note) notes.push(pick(NOTE_LABEL[o.plan.note], lang));
    const r = reasonText(o.plan?.reasonCode ?? null, lang);
    if (r) notes.push(r);
  }
  if (v === 'checked_route' && o.plan) {
    const { latestSafeDepartureS: l, contiguousSafeDepartureS: c } = o.plan;
    if (c === null) notes.push(lang === 'en' ? 'first departure time not checked — no contiguous basis' : '첫 출발 시각부터 확인되지 않음 — 연속 확인 기준 없음');
    else if (l !== null && c < l) notes.push(lang === 'en' ? 'some departures before the deadline are not checked routes' : '마감 이전 일부 출발 시각은 확인된 경로 아님');
  }
  if (o.rsgLabel) notes.push(o.rsgLabel);
  if (o.vulnerable) notes.push(lang === 'en' ? 'vulnerable facility' : '취약시설');
  if (input.mock) notes.push(lang === 'en' ? 'MOCK data' : 'MOCK 자료');
  return notes.join(' · ');
}

/** Dispatch list CSV: UTF-8 with BOM, CRLF, one row per origin in urgency order. */
export function dispatchListCSV(input: ExportInput, opts: { lang?: Lang } = {}): string {
  const lang = opts.lang ?? 'ko';
  const base = clockBase(input);
  const scenarioTime = input.scenario.issuedAtIso
    ? `${kstStamp(input.scenario.issuedAtIso)}`
    : `${kstStamp(input.scenario.inputTimeIso)}`;
  const lines = [csvRow(CSV_COLUMNS[lang])];
  orderOrigins(input.origins).forEach((o, i) => {
    const plan = o.plan;
    const v: Verdict = plan?.bestVerdict ?? 'unresolved';
    const checked = v === 'checked_route' && plan !== null;
    const best = checked ? plan!.best : null;
    const unnamed = lang === 'en' ? 'Unnamed' : '이름 없음';
    const shelter = best ? `${best.shelter.name || unnamed} (${best.shelter.sourceTag})` : '';
    let contiguous = '';
    if (checked) contiguous = plan!.contiguousSafeDepartureS === null ? (lang === 'en' ? 'none' : '없음') : kstDateClock(base, plan!.contiguousSafeDepartureS);
    lines.push(
      csvRow([
        i + 1,
        o.name || unnamed,
        o.categoryLabel,
        `${o.sourceTag} · ${o.id}`,
        pick(VERDICT_LABEL[v], lang),
        checked ? kstDateClock(base, plan!.latestSafeDepartureS) : '',
        contiguous,
        shelter,
        best ? kstDateClock(base, best.arrivalS) : '',
        scenarioTime,
        apiModeLabel(input.provenance, lang),
        originNotes(input, o, lang),
      ]),
    );
  });
  return CSV_BOM + lines.join('\r\n') + '\r\n';
}

/* ---------- file names ---------- */

export function exportFileName(input: ExportInput, kind: 'route' | 'dispatch' | 'zones', ext: 'geojson' | 'kml' | 'csv', originId?: string): string {
  const t = Number.isFinite(parseUtc(input.scenario.inputTimeIso)) ? compactUtc(input.scenario.inputTimeIso) : 'scenario';
  const parts = ['wfg', input.region.id, t];
  if (input.fireInputType === 'spread_zones') parts.push('zones');
  if (kind === 'route' && originId) parts.push(slug(originId), 'route');
  else if (kind === 'zones') parts.push(input.scenario.issuedAtIso && Number.isFinite(parseUtc(input.scenario.issuedAtIso)) ? `issued${compactUtc(input.scenario.issuedAtIso)}` : 'drawn');
  else parts.push('dispatch');
  if (input.mock) parts.push('MOCK');
  return `${parts.join('_')}.${ext}`;
}

export const MIME = {
  geojson: 'application/geo+json',
  kml: 'application/vnd.google-earth.kml+xml',
  csv: 'text/csv;charset=utf-8',
} as const;
