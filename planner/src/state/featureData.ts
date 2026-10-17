/**
 * Builds the inputs of the feature modules (plan sheet, exports) from the store. The feature
 * modules never see wire formats; everything here comes from the internal model.
 */
import type { Feature, FeatureCollection, LineString, MultiPolygon, Polygon } from 'geojson';
import { compactUtc, kstDateTime } from '../domain/clock';
import { fireInputBanner } from '../domain/labels';
import { haversineM, sortByUrgency } from '../domain/plan';
import type { CacheData, OriginPlan, Place, ProvenanceInfo, RouteDetail } from '../domain/types';
import { rsgTags, sortDrawn, zonesFeatureCollection, zoneSummary, ZONE_KEYS, type RsgTag } from '../domain/zones';
import type { Lang, TFunction } from '../i18n';
import type { ExportInput, ExportOrigin, ExportPlace, ExportProvenance, ExportRoute } from '../features/exports/types';
import type { PlanSheetData, PlanSheetScenario, PlanSheetSweepCell } from '../features/plansheet/types';
import { categoryLabel, hostLabel, placeName, sourceTag } from '../components/format';
import { recordedComparison } from './controller';
import { currentScenarioSet, drawnFireInput, drawnIssuedAt, isMockActive, regionEntry, routeById, scenarioSetsOf } from './selectors';
import { DRAWN_SCENARIO, type PlannerState } from './store';
import { scenarioOrigins } from '../data/staticData';

/** Fixed identities of the evaluated configuration (ARCHITECTURE.md §1), used only when no API or cache provenance is loaded. */
const FIXED = { checkpoint: 'c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843', packageVersion: '1.0.0', kit: 'v3' };

function routeFeature(r: RouteDetail | null): Feature<LineString> | null {
  if (!r || r.verdict !== 'checked_route' || !r.coordinates || r.coordinates.length < 2) return null;
  return { type: 'Feature', geometry: { type: 'LineString', coordinates: r.coordinates }, properties: { times_s: r.timesS ?? [], job_id: r.jobId, policy: r.policy } };
}

function anyProvenance(s: PlannerState): ProvenanceInfo | null {
  const sel = s.selectedOriginId ? s.plans[s.selectedOriginId] : null;
  const r = routeById(s, sel?.best?.jobId);
  if (r?.provenance) return r.provenance;
  for (const p of Object.values(s.plans)) {
    const d = routeById(s, p.best?.jobId);
    if (d?.provenance) return d.provenance;
  }
  return null;
}

function provenanceOf(s: PlannerState, t: TFunction, route: RouteDetail | null): ExportProvenance {
  const p = route?.provenance ?? anyProvenance(s);
  const health = s.health ?? s.cache?.meta.health ?? null;
  const set = currentScenarioSet(s);
  const apiMode: ExportProvenance['apiMode'] = s.dataSource === 'cache' ? 'cache' : isMockActive(s) ? 'mock' : 'live';
  return {
    checkpoint: p?.checkpoint ?? health?.checkpoint ?? FIXED.checkpoint,
    packageName: p?.packageName ?? 'wfg_latest',
    packageVersion: p?.packageVersion ?? health?.packageVersion ?? FIXED.packageVersion,
    kit: p?.kit ?? health?.kit ?? FIXED.kit,
    apiMode,
    cacheApiMode: s.cache ? (s.cache.meta.apiMode === 'mock' ? 'mock' : 'live') : null,
    apiVersion: p?.apiVersion ?? health?.apiVersion ?? null,
    gitCommit: p?.gitCommit ?? health?.gitCommit ?? null,
    cacheCreatedAtIso: s.cache?.meta.createdAt ?? null,
    scenarioSetId: p?.scenarioSetId ?? set?.id ?? null,
    scenarioIds: p?.scenarioIds?.length ? p.scenarioIds : set?.scenarioIds ?? [],
    inputHashes: p?.inputHashes ?? {},
    graphId: p?.graphId ?? null,
    hostLabel: hostLabel(p?.host ?? s.cache?.meta.computeHost ?? null, t),
    evaluatedConfiguration: p?.evaluatedConfiguration ?? null,
    recordedMissionMatch: p?.recordedMissionMatch ?? null,
    approximation: p?.approximation ?? drawnApproximation(s),
  };
}

/** provenance.approximation of any drawn-zone check on screen (spread_zones results carry it). */
function drawnApproximation(s: PlannerState): string | null {
  if (s.scenarioId !== DRAWN_SCENARIO) return null;
  for (const d of s.drawn.dispatch) if (d.provenance?.approximation) return d.provenance.approximation;
  for (const p of Object.values(s.plans)) {
    for (const c of p.sweep) {
      for (const a of c.attempts) {
        const r = routeById(s, a.jobId);
        if (r?.provenance?.approximation) return r.provenance.approximation;
      }
    }
  }
  return null;
}

/** Ready-Set-Go tag text (planner-side point-in-polygon), e.g. "실행(Go) — 전원 대피". */
function rsgText(tag: RsgTag | null | undefined, t: TFunction): string | null {
  return tag ? t(`rsg.${tag}`) : null;
}

/**
 * The drawn zones as an extra GeoJSON layer: one polygon feature per zone with arrival_h_max, the
 * assumption label and the zone summary (exports in drawn-zone mode).
 */
export function drawnZonesLayer(s: PlannerState, t: TFunction): FeatureCollection<Polygon | MultiPolygon> | null {
  if (s.scenarioId !== DRAWN_SCENARIO) return null;
  const fc = zonesFeatureCollection(s.drawn.zones);
  if (!fc.features.length) return null;
  const issuedAt = drawnIssuedAt(s);
  const features = fc.features.map((f) => {
    const key = ZONE_KEYS.find((k) => s.drawn.zones[k].arrivalHMax === f.properties.arrival_h_max) ?? 'h8';
    const zone = s.drawn.zones[key];
    const sum = zoneSummary(zone);
    return {
      type: 'Feature' as const,
      geometry: f.geometry,
      properties: {
        layer: 'spread_zone',
        arrival_h_max: f.properties.arrival_h_max,
        zone: key === 'h5' ? '5h' : '8h',
        assumption: true,
        label: zone.preset ? t('drawn.zone.source.preset', { time: kstDateTime(zone.preset.inputTime) }) + (zone.edited ? ` ${t('drawn.zone.edited')}` : '') : t('drawn.zone.source.drawn'),
        preset_input_time: zone.preset?.inputTime ?? null,
        edited: zone.edited,
        polygons: sum.polygons,
        vertex_count: sum.vertices,
        area_km2: Math.round(sum.areaKm2 * 1000) / 1000,
        input_time: s.drawn.settings.inputTime,
        issued_at: issuedAt,
        margin_min: s.drawn.settings.marginMin,
      },
    };
  });
  return { type: 'FeatureCollection', features };
}

function exportPlace(p: Place, t: TFunction): ExportPlace {
  return { id: p.id, name: p.name, nameEn: p.nameEn, categoryLabel: categoryLabel(p, t), sourceTag: sourceTag(p), lon: p.lon, lat: p.lat };
}

function sweepCells(plan: OriginPlan): PlanSheetSweepCell[] {
  return plan.sweep.map((c) => ({ offsetS: c.offsetS, verdict: c.skipped === 'window_unsatisfiable' ? 'window_closed' : c.verdict }));
}

function bestReason(plan: OriginPlan): string | null {
  for (const c of plan.sweep) for (const a of c.attempts) if (a.reasonCode) return a.reasonCode;
  return plan.rejectReason?.code ?? null;
}

interface RowSource {
  scenarioSetId: string;
  inputTimeIso: string;
  issuedAtIso: string | null;
  plans: Record<string, OriginPlan>;
  route: (jobId: string | null | undefined) => RouteDetail | null;
  travelOnly: (originId: string) => RouteDetail | null;
  hostFallback: string | null;
}

function scenarioRow(src: RowSource, o: Place, byId: Map<string, Place>, t: TFunction): PlanSheetScenario {
  const plan = src.plans[o.id];
  const route = src.route(plan?.best?.jobId);
  const travel = src.travelOnly(o.id);
  const dest = plan?.best ? byId.get(plan.best.destinationId) : null;
  return {
    scenarioSetId: src.scenarioSetId,
    inputTimeIso: src.inputTimeIso,
    issuedAtIso: src.issuedAtIso,
    bestVerdict: plan?.bestVerdict ?? 'unresolved',
    latestSafeDepartureS: plan?.latestSafeDepartureS ?? null,
    contiguousSafeDepartureS: plan?.contiguousSafeDepartureS ?? null,
    sweep: plan ? sweepCells(plan) : [],
    shelter: dest
      ? { id: dest.id, name: dest.name, sourceTag: sourceTag(dest), lon: dest.lon, lat: dest.lat, arrivalS: plan?.best?.arrivalS ?? null, categoryLabel: categoryLabel(dest, t) }
      : null,
    departureS: plan?.latestSafeDepartureS ?? null,
    route: routeFeature(route),
    travelOnlyRoute: travel?.coordinates && travel.coordinates.length > 1 ? { type: 'Feature', geometry: { type: 'LineString', coordinates: travel.coordinates }, properties: { policy: 'travel_only' } } : null,
    travelOnlyFullPolicyPass: travel?.fullPolicy?.pass ?? null,
    exposure: (route?.exposure ?? []).map((e) => ({ scenarioId: e.scenarioId, peakKwM2: e.peakKwM2, doseKjM2: e.doseKjM2, contact: e.contact })),
    limits: route?.limits ? { peakKwM2: route.limits.peakKwM2, doseKjM2: route.limits.doseKjM2 } : null,
    computeS: route?.computeS ?? plan?.best?.computeS ?? null,
    host: hostLabel(route?.provenance?.host, t) ?? src.hostFallback,
    reasonCode: plan && plan.bestVerdict === 'unresolved' ? bestReason(plan) : null,
    note: plan?.note ?? null,
  };
}

function cacheRoute(routes: Record<string, RouteDetail>, cache: CacheData | null) {
  return (jobId: string | null | undefined) => (jobId ? routes[jobId] ?? cache?.route(jobId) ?? null : null);
}

/**
 * One plan sheet per origin. Recorded: one row for the scenario on screen. Drawn zones: the
 * drawn-zone result as its own row labelled with the issue time, plus — when the recorded results
 * of the same base input time were loaded before switching — that recorded row for comparison.
 */
export function buildPlanSheets(s: PlannerState, t: TFunction, lang: Lang): PlanSheetData[] {
  const region = regionEntry(s);
  if (!region) return [];
  const drawn = s.scenarioId === DRAWN_SCENARIO;
  const set = currentScenarioSet(s);
  const baseInput = drawn ? s.drawn.settings.inputTime : set?.inputTime ?? null;
  if (!baseInput || (!drawn && !set)) return [];
  const origins = scenarioOrigins(s.places, drawn ? null : set!.id);
  const byId = new Map(s.places.map((p) => [p.id, p]));
  const prov = provenanceOf(s, t, null);
  const mock = isMockActive(s);
  const label = fireInputBanner({ type: drawn ? 'spread_zones' : 'recorded' }, region.fireYear, lang);
  const vulnerable = origins.filter((o) => o.vulnerable);
  const routeOf = (jobId: string | null | undefined) => routeById(s, jobId);
  const sources: RowSource[] = [];
  if (drawn) {
    const issuedAt = drawnIssuedAt(s) ?? baseInput;
    sources.push({
      scenarioSetId: `spread_zones:${compactUtc(issuedAt)}`,
      inputTimeIso: baseInput,
      issuedAtIso: issuedAt,
      plans: s.plans,
      route: routeOf,
      travelOnly: (id) => s.travelOnly[id]?.detail ?? null,
      hostFallback: null,
    });
    const cmp = recordedComparison();
    const cmpSet = cmp ? scenarioSetsOf(s).find((x) => x.id === cmp.scenarioId) : null;
    if (cmp && cmpSet && cmpSet.inputTime === baseInput) {
      sources.push({
        scenarioSetId: cmpSet.id,
        inputTimeIso: cmpSet.inputTime,
        issuedAtIso: null,
        plans: cmp.plans,
        route: cacheRoute(s.routes, cmp.cache),
        travelOnly: (id) => cmp.travelOnly[id]?.detail ?? (cmp.plans[id]?.source === 'cache' ? cmp.cache?.travelOnly[id] ?? null : null),
        hostFallback: hostLabel(cmp.cache?.meta.computeHost ?? null, t),
      });
    }
  } else {
    sources.push({
      scenarioSetId: set!.id,
      inputTimeIso: set!.inputTime,
      issuedAtIso: null,
      plans: s.plans,
      route: routeOf,
      travelOnly: (id) => s.travelOnly[id]?.detail ?? null,
      hostFallback: hostLabel(s.cache?.meta.computeHost ?? null, t),
    });
  }
  // same order as the origin list (drawn: inside zones first, then urgency)
  const rsg = drawn ? rsgTags(origins, s.drawn.zones) : new Map<string, RsgTag>();
  const items = origins.map((o) => ({ id: o.id, name: placeName(o, t, lang), vulnerable: o.vulnerable, plan: s.plans[o.id] ?? null, rsg: rsg.get(o.id) ?? null, o }));
  const ordered = (drawn ? sortDrawn(items) : sortByUrgency(items)).map((x) => x.o);
  return ordered.map((o) => {
    const scenarios = sources.map((src) => scenarioRow(src, o, byId, t));
    const facilities = vulnerable
      .filter((v) => v.id !== o.id)
      .map((v) => ({ v, d: haversineM([o.lon, o.lat], [v.lon, v.lat]) }))
      .filter((x) => x.d <= 5000)
      .sort((a, b) => a.d - b.d)
      .slice(0, 5)
      .map(({ v, d }) => ({ id: v.id, name: v.name, categoryLabel: categoryLabel(v, t), sourceTag: sourceTag(v), distanceM: Math.round(d) }));
    const tag = rsg.get(o.id) ?? null;
    return {
      region: { id: region.id, nameKo: region.nameKo, nameEn: region.nameEn, fireYear: region.fireYear },
      fireInputLabel: label,
      fireInputType: drawn ? 'spread_zones' : 'recorded',
      mock,
      origin: {
        id: o.id,
        name: o.name,
        nameEn: o.nameEn,
        categoryLabel: categoryLabel(o, t),
        sourceTag: sourceTag(o),
        lon: o.lon,
        lat: o.lat,
        snapDistanceM: o.entry?.distanceM ?? o.snapDistanceM,
        vulnerable: o.vulnerable,
      },
      rsgLabel: rsgText(tag, t),
      facilities,
      scenarios,
      generatedAtIso: new Date().toISOString(),
      provenance: {
        checkpoint: prov.checkpoint,
        packageVersion: prov.packageVersion,
        kit: prov.kit,
        apiMode: prov.apiMode,
        apiVersion: prov.apiVersion,
        cacheCreatedAtIso: prov.cacheCreatedAtIso,
        gitCommit: prov.gitCommit,
        cacheApiMode: prov.cacheApiMode ?? null,
        approximation: prov.approximation ?? null,
      },
    } satisfies PlanSheetData;
  });
}

function exportRoute(s: PlannerState, t: TFunction, d: RouteDetail, origin: Place, shelter: Place, role: ExportRoute['role']): ExportRoute | null {
  if (!d.coordinates || !d.timesS) return null;
  return {
    role,
    origin: exportPlace(origin, t),
    shelter: exportPlace(shelter, t),
    verdict: d.verdict,
    policy: d.policy,
    fullPolicyPass: d.fullPolicy?.pass ?? null,
    fullPolicyFailures: d.fullPolicy?.components ?? null,
    departureS: d.departOffsetS,
    arrivalS: d.arrivalS,
    dwellEndS: d.dwellEndS,
    coordinates: d.coordinates,
    timesS: d.timesS,
    lengthM: d.lengthM,
    exposure: d.exposure.map((e) => ({ scenarioId: e.scenarioId, peakKwM2: e.peakKwM2, doseKjM2: e.doseKjM2, contact: e.contact })),
    computeS: d.computeS,
    jobId: d.jobId,
    provenance: provenanceOf(s, t, d),
  };
}

export function buildExportInput(s: PlannerState, t: TFunction, lang: Lang): ExportInput | null {
  const region = regionEntry(s);
  const drawn = s.scenarioId === DRAWN_SCENARIO;
  const set = currentScenarioSet(s);
  const baseInput = drawn ? s.drawn.settings.inputTime : set?.inputTime ?? null;
  if (!region || !baseInput || (!drawn && !set)) return null;
  const origins = scenarioOrigins(s.places, drawn ? null : set!.id);
  const byId = new Map(s.places.map((p) => [p.id, p]));
  const rsg = drawn ? rsgTags(origins, s.drawn.zones) : new Map<string, RsgTag>();
  const exportOrigins: ExportOrigin[] = origins.map((o) => {
    const plan = s.plans[o.id];
    const dest = plan?.best ? byId.get(plan.best.destinationId) : null;
    return {
      ...exportPlace(o, t),
      vulnerable: o.vulnerable,
      rsgLabel: rsgText(rsg.get(o.id), t),
      urgencyRank: null,
      plan: plan
        ? {
            bestVerdict: plan.bestVerdict,
            latestSafeDepartureS: plan.latestSafeDepartureS,
            contiguousSafeDepartureS: plan.contiguousSafeDepartureS,
            sweep: sweepCells(plan),
            best: plan.best && dest ? { shelter: exportPlace(dest, t), departureS: plan.best.offsetS, arrivalS: plan.best.arrivalS } : null,
            reasonCode: plan.bestVerdict === 'unresolved' ? bestReason(plan) : null,
            note: plan.note ?? null,
          }
        : null,
    };
  });
  let selectedRoute: ExportRoute | null = null;
  let comparisonRoute: ExportRoute | null = null;
  const sel = s.selectedOriginId ? byId.get(s.selectedOriginId) : null;
  const plan = sel ? s.plans[sel.id] : null;
  if (sel && plan) {
    const cell = plan.sweep.find((c) => c.offsetS === s.selectedOffsetS);
    const attempt = cell?.best ?? plan.best;
    const d = routeById(s, attempt?.jobId);
    const shelter = attempt ? byId.get(attempt.destinationId) : null;
    if (d && shelter && d.verdict === 'checked_route') selectedRoute = exportRoute(s, t, d, sel, shelter, 'evacuation_route');
    const tr = s.travelOnly[sel.id]?.detail;
    const trShelter = plan.best ? byId.get(plan.best.destinationId) : null;
    if (tr && trShelter && tr.coordinates) comparisonRoute = exportRoute(s, t, tr, sel, trShelter, 'travel_only_comparison');
  }
  const fi = drawn ? drawnFireInput(s) : null;
  return {
    region: { id: region.id, nameKo: region.nameKo, nameEn: region.nameEn, fireYear: region.fireYear },
    fireInputLabel: fireInputBanner({ type: drawn ? 'spread_zones' : 'recorded' }, region.fireYear, lang),
    fireInputType: drawn ? 'spread_zones' : 'recorded',
    mock: isMockActive(s),
    scenario: drawn
      ? { scenarioSetId: fi?.burningScenarioSetId ?? null, inputTimeIso: baseInput, issuedAtIso: drawnIssuedAt(s) }
      : { scenarioSetId: set!.id, inputTimeIso: set!.inputTime, issuedAtIso: null },
    zones: drawnZonesLayer(s, t),
    origins: exportOrigins,
    selectedRoute,
    comparisonRoute,
    provenance: provenanceOf(s, t, selectedRoute ? routeById(s, selectedRoute.jobId) : null),
    generatedAtIso: new Date().toISOString(),
  };
}
