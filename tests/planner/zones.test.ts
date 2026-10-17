/**
 * User-drawn spread zones (planner/src/domain/zones.ts, domain/assumptions.ts, the spread_zones
 * request builders in api/adapter.ts and the deep-link helpers of state/controller.ts).
 * All coordinates, ids and numbers below are SYNTHETIC test data (round numbers around a made-up
 * point) — not real villages, shelters, fires or API results.
 */
import { describe, expect, it } from 'vitest';
import {
  addPolygon,
  clearZone,
  closeRing,
  compareDrawn,
  defaultPresetTimes,
  deleteVertex,
  distanceToZoneM,
  douglasPeucker,
  emptyZones,
  fingerprint,
  geometryToPolygons,
  insertVertex,
  isNested,
  issuedAtFor,
  localProjection,
  moveVertex,
  originsNearZones,
  parseStoredZones,
  pointInPolygon,
  pointInZone,
  presetZone,
  ringIsCcw,
  ringSelfIntersections,
  rsgTag,
  segmentRelation,
  rsgTags,
  secondsSinceIssue,
  segmentsIntersect,
  simplifyRing,
  sortDrawn,
  validateZone,
  zoneAreaKm2,
  zonesFeatureCollection,
  type DrawnUrgencyItem,
  type DrawnZone,
  type DrawnZones,
  type LonLat,
  type Ring,
} from '../../planner/src/domain/zones';
import { arrayText, flattenAssumptions, mockAssumptionText, primitiveText } from '../../planner/src/domain/assumptions';
import { adaptRouteJob, attemptFromRoute, toWireDispatch, toWireFireInput, toWireRouteCheck } from '../../planner/src/api/adapter';
import { deadlineHeadline, planFromAttempts, summarize } from '../../planner/src/domain/plan';
import type { FireInput, OriginPlan, Place } from '../../planner/src/domain/types';
import type { WireRouteCheckJob } from '../../planner/src/api/wire';
import { readQuery, resolveScenarioParam } from '../../planner/src/state/controller';
import { clockAt } from '../../planner/src/features/shared/format';
import { dispatchListCSV, routeToGeoJSON, zonesToGeoJSON } from '../../planner/src/features/exports/exports';
import type { ExportInput, ExportRoute } from '../../planner/src/features/exports/types';
import { DRAWN_SCENARIO } from '../../planner/src/state/store';

// ---------------------------------------------------------------- synthetic geometry helpers

const C: LonLat = [128.7, 36.4];
const proj = localProjection(C[0], C[1]);
/** synthetic point `dx`, `dy` metres east/north of C */
const m = (dx: number, dy: number): LonLat => proj.toLonLat([dx, dy]);
/** axis-aligned square ring (open), side `s` metres, centred at (cx, cy) metres */
const square = (s: number, cx = 0, cy = 0): Ring => [m(cx - s / 2, cy - s / 2), m(cx + s / 2, cy - s / 2), m(cx + s / 2, cy + s / 2), m(cx - s / 2, cy + s / 2)];

function zone(key: 'h5' | 'h8', polys: Ring[][]): DrawnZone {
  return { key, arrivalHMax: key === 'h5' ? 5 : 8, polygons: polys, preset: null, edited: false };
}

function zonesOf(h5: Ring[][], h8: Ring[][]): DrawnZones {
  return { h5: zone('h5', h5), h8: zone('h8', h8) };
}

/** distance (m) from point p to polyline `line` (open) in the local projection */
function distToPolyline(p: LonLat, line: LonLat[], closed = false): number {
  const P = proj.toXY(p);
  let best = Infinity;
  const n = closed ? line.length : line.length - 1;
  for (let i = 0; i < n; i += 1) {
    const a = proj.toXY(line[i]!);
    const b = proj.toXY(line[(i + 1) % line.length]!);
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const l2 = dx * dx + dy * dy;
    const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((P[0] - a[0]) * dx + (P[1] - a[1]) * dy) / l2));
    best = Math.min(best, Math.hypot(a[0] + t * dx - P[0], a[1] + t * dy - P[1]));
  }
  return best;
}

const REGION_BBOX: [number, number, number, number] = [C[0] - 0.2, C[1] - 0.2, C[0] + 0.2, C[1] + 0.2];

// ---------------------------------------------------------------- validity

describe('polygon validity', () => {
  it('segment intersection: crossing, touching, collinear overlap, disjoint', () => {
    expect(segmentsIntersect([0, 0], [2, 2], [0, 2], [2, 0])).toBe(true);
    expect(segmentsIntersect([0, 0], [1, 0], [1, 0], [2, 1])).toBe(true); // shared endpoint
    expect(segmentsIntersect([0, 0], [2, 0], [1, 0], [3, 0])).toBe(true); // collinear overlap
    expect(segmentsIntersect([0, 0], [1, 0], [0, 1], [1, 1])).toBe(false); // parallel
    expect(segmentsIntersect([0, 0], [1, 1], [2, 2], [3, 0])).toBe(false);
  });

  it('classifies crossing, overlap and single-point touching', () => {
    expect(segmentRelation([0, 0], [2, 2], [0, 2], [2, 0])).toBe('cross');
    expect(segmentRelation([0, 0], [2, 0], [1, 0], [3, 0])).toBe('overlap');
    expect(segmentRelation([0, 0], [1, 0], [2, 0], [3, 0])).toBe('none'); // collinear but apart
    expect(segmentRelation([0, 0], [2, 0], [1, 0], [1, 1])).toBe('touch'); // T-junction
    expect(segmentRelation([0, 0], [1, 0], [1, 0], [2, 1])).toBe('touch');
  });

  it('a hole touching its shell at one point is valid (as in dissolved cell footprints); a crossing hole is not', () => {
    const shell: Ring = [m(0, 0), m(3000, 0), m(3000, 3000), m(0, 3000)];
    const touching: Ring = [m(0, 1000), m(1000, 1500), m(1000, 500)]; // shares the point on the west edge
    expect(validateZone(zone('h8', [[shell, touching]]), REGION_BBOX)).toEqual([]);
    const crossing: Ring = [m(-500, 1000), m(1000, 1500), m(1000, 500)];
    expect(validateZone(zone('h8', [[shell, crossing]]), REGION_BBOX).map((i) => i.code)).toContain('rings_cross');
  });

  it('a simple ring has no self-intersection; a bow-tie has one at its centre', () => {
    expect(ringSelfIntersections(square(1000))).toEqual([]);
    const bowtie: Ring = [m(-500, -500), m(500, 500), m(500, -500), m(-500, 500)];
    const x = ringSelfIntersections(bowtie);
    expect(x.length).toBe(1);
    expect(Math.hypot(...proj.toXY(x[0]!))).toBeLessThan(1);
    const issues = validateZone(zone('h5', [[bowtie]]), REGION_BBOX);
    expect(issues.map((i) => i.code)).toContain('self_intersection');
    expect(issues.find((i) => i.code === 'self_intersection')!.severity).toBe('error');
  });

  it('needs at least 3 vertices per ring and a non-zero area', () => {
    expect(validateZone(zone('h8', [[[m(0, 0), m(100, 0)]]]), REGION_BBOX).map((i) => i.code)).toContain('too_few_vertices');
    expect(validateZone(zone('h8', [[[m(0, 0), m(100, 0), m(200, 0)]]]), REGION_BBOX).map((i) => i.code)).toContain('zero_area');
    expect(validateZone(zone('h8', [[square(1000)]]), REGION_BBOX)).toEqual([]);
  });

  it('flags a hole that crosses or lies outside its outer ring', () => {
    const crossing = validateZone(zone('h8', [[square(1000), square(400, 500, 0)]]), REGION_BBOX);
    expect(crossing.map((i) => i.code)).toContain('rings_cross');
    const outside = validateZone(zone('h8', [[square(1000), square(100, 3000, 0)]]), REGION_BBOX);
    expect(outside.map((i) => i.code)).toContain('hole_outside');
    expect(validateZone(zone('h8', [[square(1000), square(200)]]), REGION_BBOX)).toEqual([]);
  });

  it('warns when partly outside the region and errors when entirely outside (ZONES_OUTSIDE_REGION)', () => {
    const partly = validateZone(zone('h5', [[square(1000, 0, 0)]]), [C[0], C[1] - 0.2, C[0] + 0.2, C[1] + 0.2]);
    expect(partly).toEqual([expect.objectContaining({ code: 'partly_outside_region', severity: 'warning' })]);
    const far = validateZone(zone('h5', [[square(1000, 100000, 0)]]), REGION_BBOX);
    expect(far).toEqual([expect.objectContaining({ code: 'outside_region', severity: 'error' })]);
  });
});

// ---------------------------------------------------------------- Douglas–Peucker

describe('Douglas–Peucker vertex reduction', () => {
  // synthetic edge: a vertex every 100 m with ≤ 16 m jitter and one real 400 m bump in the middle
  const stairs: LonLat[] = [];
  for (let i = 0; i <= 40; i += 1) {
    stairs.push(m(i * 100, (i % 3) * 8 + (i === 20 ? 400 : 0)));
  }

  it('keeps both endpoints and every removed vertex within the tolerance', () => {
    const tol = 50;
    const out = douglasPeucker(stairs, tol);
    expect(out[0]).toEqual(stairs[0]);
    expect(out[out.length - 1]).toEqual(stairs[stairs.length - 1]);
    expect(out.length).toBeLessThan(stairs.length / 4);
    expect(out).toContainEqual(stairs[20]); // the real feature survives
    for (const p of stairs) expect(distToPolyline(p, out)).toBeLessThanOrEqual(tol + 1e-6);
    // kept points are original points, in order
    let j = 0;
    for (const p of out) {
      while (j < stairs.length && stairs[j] !== p) j += 1;
      expect(j).toBeLessThan(stairs.length);
    }
  });

  it('returns the input for two points or a non-positive tolerance', () => {
    expect(douglasPeucker(stairs.slice(0, 2), 50)).toEqual(stairs.slice(0, 2));
    expect(douglasPeucker(stairs, 0)).toEqual(stairs);
  });

  it('simplifies a closed ring, stays simple, keeps ≥ 3 vertices and every vertex within tolerance', () => {
    // synthetic ring: square with 40 extra nearly-collinear vertices along each side (≤ 20 m bumps)
    const ring: Ring = [];
    const side = 3000;
    const corners = [m(0, 0), m(side, 0), m(side, side), m(0, side)];
    for (let k = 0; k < 4; k += 1) {
      const a = proj.toXY(corners[k]!);
      const b = proj.toXY(corners[(k + 1) % 4]!);
      for (let i = 0; i < 40; i += 1) {
        const t = i / 40;
        const bump = i % 2 ? 20 : 0;
        const nx = -(b[1] - a[1]) / side;
        const ny = (b[0] - a[0]) / side;
        ring.push(proj.toLonLat([a[0] + (b[0] - a[0]) * t + nx * bump, a[1] + (b[1] - a[1]) * t + ny * bump]));
      }
    }
    const out = simplifyRing(ring, 50);
    expect(out.length).toBeGreaterThanOrEqual(3);
    expect(out.length).toBeLessThanOrEqual(8);
    expect(ringSelfIntersections(out)).toEqual([]);
    for (const p of ring) expect(distToPolyline(p, out, true)).toBeLessThanOrEqual(50 + 1e-6);
    expect(out[0]).toEqual(ring[0]); // the split vertex is kept
  });

  it('presetZone copies a footprint geometry, reduces vertices and reports both counts', () => {
    const coords = closeRing([...stairs, m(4000, -2000), m(0, -2000)]);
    const z = presetZone('h5', { inputTime: '2099-01-01T00:00:00Z', geometry: { type: 'Polygon', coordinates: [coords] } });
    expect(z.arrivalHMax).toBe(5);
    expect(z.preset).toMatchObject({ kind: 'footprint', inputTime: '2099-01-01T00:00:00Z', toleranceM: 50, verticesBefore: stairs.length + 2 });
    expect(z.preset!.verticesAfter).toBeLessThan(z.preset!.verticesBefore);
    expect(z.preset!.verticesAfter).toBe(z.polygons[0]![0]!.length);
    // never buffered or scaled: area changes only by the vertex reduction (< 5 % here)
    const before = zoneAreaKm2(zone('h5', geometryToPolygons({ type: 'Polygon', coordinates: [coords] })));
    expect(Math.abs(zoneAreaKm2(z) - before) / before).toBeLessThan(0.05);
  });
});

// ---------------------------------------------------------------- point in polygon / Ready-Set-Go

describe('point-in-polygon Ready-Set-Go tagging', () => {
  const donut: Ring[] = [square(4000), square(1000)];

  it('respects holes and multipolygon parts', () => {
    expect(pointInPolygon(m(1500, 0), donut)).toBe(true);
    expect(pointInPolygon(m(0, 0), donut)).toBe(false); // in the hole
    expect(pointInPolygon(m(3000, 0), donut)).toBe(false);
    const multi = zone('h8', [donut, [square(1000, 10000, 0)]]);
    expect(pointInZone(m(10000, 0), multi)).toBe(true);
    expect(pointInZone(m(6000, 0), multi)).toBe(false);
    expect(pointInZone(m(0, 0), multi)).toBe(false);
  });

  it('Go inside the 5 h zone, Set inside the 8 h zone only, nothing outside', () => {
    const zs = zonesOf([[square(2000)]], [[square(8000)]]);
    expect(rsgTag(m(0, 0), zs)).toBe('go');
    expect(rsgTag(m(3000, 0), zs)).toBe('set');
    expect(rsgTag(m(9000, 0), zs)).toBeNull();
    // a hole in the 8 h zone is not part of it
    const holed = zonesOf([], [donut]);
    expect(rsgTag(m(0, 0), holed)).toBeNull();
    expect(rsgTag(m(1500, 0), holed)).toBe('set');
    // non-nested zones: inside the 5 h zone is Go even outside the 8 h zone
    const apart = zonesOf([[square(1000, 20000, 0)]], [[square(1000)]]);
    expect(rsgTag(m(20000, 0), apart)).toBe('go');
    expect(isNested(apart.h5, apart.h8)).toBe(false);
    expect(isNested(zs.h5, zs.h8)).toBe(true);
    const tags = rsgTags(
      [
        { id: 'a', lon: m(0, 0)[0], lat: m(0, 0)[1] },
        { id: 'b', lon: m(3000, 0)[0], lat: m(3000, 0)[1] },
        { id: 'c', lon: m(9000, 0)[0], lat: m(9000, 0)[1] },
      ],
      zs,
    );
    expect([...tags.entries()]).toEqual([
      ['a', 'go'],
      ['b', 'set'],
    ]);
  });

  it('origins inside or within 2 km of the zones ("구역 안·주변 마을")', () => {
    const zs = zonesOf([], [[square(2000)]]);
    const pts = [
      { id: 'in', lon: m(0, 0)[0], lat: m(0, 0)[1] },
      { id: 'near', lon: m(2500, 0)[0], lat: m(2500, 0)[1] },
      { id: 'far', lon: m(4000, 0)[0], lat: m(4000, 0)[1] },
    ];
    const r = originsNearZones(pts, zs);
    expect(r.inside.map((p) => p.id)).toEqual(['in']);
    expect(r.near.map((p) => p.id)).toEqual(['near']);
    expect(distanceToZoneM(m(2500, 0), zs.h8)).toBeCloseTo(1500, -1);
    expect(originsNearZones(pts, emptyZones())).toEqual({ inside: [], near: [] });
  });
});

// ---------------------------------------------------------------- request building

const SET = 'synthetic:set:0001';
const INPUT = '2099-01-01T09:00:00Z';

function drawnFire(zs: DrawnZones, opts: Partial<Extract<FireInput, { type: 'spread_zones' }>> = {}): Extract<FireInput, { type: 'spread_zones' }> {
  return {
    type: 'spread_zones',
    issuedAt: issuedAtFor(INPUT, 0),
    inputTime: INPUT,
    zones: zonesFeatureCollection(zs),
    marginMin: 60,
    burningScenarioSetId: SET,
    ...opts,
  };
}

describe('spread_zones request building (contract v1.5 SpreadZonesFireInput)', () => {
  const zs = zonesOf([[square(2000)]], [[square(8000), square(500, 3000, 3000)], [square(1000, 20000, 0)]]);

  it('ZoneCollection: one feature per zone, Polygon / MultiPolygon, closed rings, CCW outer / CW holes, properties exactly {arrival_h_max}', () => {
    const fc = zonesFeatureCollection(zs);
    expect(fc.type).toBe('FeatureCollection');
    expect(fc.features.map((f) => f.properties)).toEqual([{ arrival_h_max: 5 }, { arrival_h_max: 8 }]);
    expect(fc.features.map((f) => f.geometry.type)).toEqual(['Polygon', 'MultiPolygon']);
    const p5 = fc.features[0]!.geometry as GeoJSON.Polygon;
    const ring = p5.coordinates[0]!;
    expect(ring[0]).toEqual(ring[ring.length - 1]);
    expect(ringIsCcw(ring.slice(0, -1) as LonLat[])).toBe(true);
    const mp = fc.features[1]!.geometry as GeoJSON.MultiPolygon;
    expect(mp.coordinates.length).toBe(2);
    expect(ringIsCcw(mp.coordinates[0]![1]!.slice(0, -1) as LonLat[])).toBe(false); // hole clockwise
    // coordinates rounded to 1e-6°
    for (const c of ring) for (const v of c) expect(Math.abs(v * 1e6 - Math.round(v * 1e6))).toBeLessThan(1e-6);
    // an empty zone is left out
    expect(zonesFeatureCollection(zonesOf([[square(1000)]], [])).features.map((f) => f.properties.arrival_h_max)).toEqual([5]);
  });

  it('issued_at is ISO UTC (input_time − offset); the relative clock counts from it', () => {
    expect(issuedAtFor(INPUT, 0)).toBe('2099-01-01T09:00:00Z');
    expect(issuedAtFor(INPUT, 2)).toBe('2099-01-01T07:00:00Z');
    expect(issuedAtFor(INPUT, 8)).toBe('2099-01-01T01:00:00Z');
    expect(secondsSinceIssue(INPUT, issuedAtFor(INPUT, 2), 600)).toBe(2 * 3600 + 600);
  });

  it('POST /route-checks body: recorded input_time + fire_input {type, zones, issued_at, margin_min, burning_scenario_set_id}', () => {
    const fire = drawnFire(zs, { issuedAt: issuedAtFor(INPUT, 1), marginMin: 30 });
    const body = toWireRouteCheck(
      { offsetS: 600, start: { kind: 'node', nodeId: 'osm:1' }, destination: { kind: 'node', nodeId: 'osm:2' }, dwellS: 120, window: [0, 3600], policy: 'full', limits: null, incurredDoseKjM2: null },
      { region: 'synthetic_region', inputTime: INPUT, scenarioSetId: SET, fireInput: fire },
      'test',
    );
    expect(body.input_time).toBe(INPUT);
    expect(body.start).toEqual({ node_id: 'osm:1' });
    expect(body.depart_offset_s).toBe(600);
    const fi = body.fire_input;
    expect(Object.keys(fi).sort()).toEqual(['burning_scenario_set_id', 'issued_at', 'margin_min', 'type', 'zones']);
    expect(fi).toMatchObject({ type: 'spread_zones', issued_at: '2099-01-01T08:00:00Z', margin_min: 30, burning_scenario_set_id: SET });
    if (fi.type !== 'spread_zones') throw new Error('unreachable');
    expect(fi.zones.type).toBe('FeatureCollection');
    for (const f of fi.zones.features) {
      expect(Object.keys(f).sort()).toEqual(['geometry', 'properties', 'type']);
      expect(Object.keys(f.properties)).toEqual(['arrival_h_max']);
      expect(['Polygon', 'MultiPolygon']).toContain(f.geometry.type);
    }
    expect(fi.zones.features.map((f) => f.properties.arrival_h_max)).toEqual([5, 8]);
    // a recorded context still sends the recorded fire input
    const rec = toWireRouteCheck(
      { offsetS: 0, start: { kind: 'node', nodeId: 'osm:1' }, destination: { kind: 'node', nodeId: 'osm:2' }, dwellS: 120, window: [0, 3600], policy: 'full', limits: null, incurredDoseKjM2: null },
      { region: 'synthetic_region', inputTime: INPUT, scenarioSetId: SET },
    );
    expect(rec.fire_input).toEqual({ type: 'recorded', scenario_set_id: SET });
  });

  it('burning_scenario_set_id is optional (omitted when unknown); margin_min defaults are sent explicitly', () => {
    const fi = toWireFireInput(drawnFire(zs, { burningScenarioSetId: null }));
    expect('burning_scenario_set_id' in fi).toBe(false);
    expect(fi).toMatchObject({ type: 'spread_zones', margin_min: 60 });
  });

  it('POST /dispatch-plans carries the same fire input, policy full', () => {
    const place = (id: string, node: string): Place =>
      ({ id, role: 'origin', category: 'village', name: null, nameEn: null, lon: 0, lat: 0, source: 'OpenStreetMap', sourceTag: 'place=village', osm: null, snapNode: node, snapDistanceM: 0, entry: { node, lon: 0, lat: 0, distanceM: 0, withinApiLonlatSnap: true }, checkable: true, vulnerable: false, scenarioSetId: null, inputTime: null, caseId: null, recorded: null }) as Place;
    const byId = new Map([
      ['o1', place('o1', 'osm:1')],
      ['d1', { ...place('d1', 'osm:9'), role: 'destination' as const }],
    ]);
    const fire = drawnFire(zs);
    const body = toWireDispatch({ originIds: ['o1'], destinationIds: ['d1'], offsetsS: [0, 600, 1200, 1800, 2400, 3000] }, byId, { region: 'r', inputTime: INPUT, scenarioSetId: SET, fireInput: fire, horizonS: 3600 });
    expect(body.policy).toBe('full');
    expect(body.depart_offsets_s).toEqual([0, 600, 1200, 1800, 2400, 3000]);
    expect(body.fire_input).toEqual(toWireFireInput(fire));
  });

  it('fingerprints change with the zones and settings (stale results are dropped)', () => {
    const a = fingerprint({ region: 'r', ...drawnFire(zs) });
    expect(fingerprint({ region: 'r', ...drawnFire(zs) })).toBe(a);
    expect(fingerprint({ region: 'r', ...drawnFire(zs, { marginMin: 50 }) })).not.toBe(a);
    const moved = moveVertex(zs, { zone: 'h5', poly: 0, ring: 0, index: 0 }, m(-1100, -1000));
    expect(fingerprint({ region: 'r', ...drawnFire(moved) })).not.toBe(a);
  });
});

// ---------------------------------------------------------------- editing / persistence

describe('zone editing and persistence', () => {
  it('delete keeps ≥ 3 vertices: a triangle loses its polygon; insert and move mark presets as edited', () => {
    const tri: Ring = [m(0, 0), m(1000, 0), m(0, 1000)];
    const zs = addPolygon(emptyZones(), 'h8', tri);
    expect(zs.h8.polygons.length).toBe(1);
    const del = deleteVertex(zs, { zone: 'h8', poly: 0, ring: 0, index: 1 });
    expect(del.removed).toBe('polygon');
    expect(del.zones.h8.polygons).toEqual([]);
    const ins = insertVertex(zs, { zone: 'h8', poly: 0, ring: 0, index: 0 }, m(500, -10));
    expect(ins.zones.h8.polygons[0]![0]!.length).toBe(4);
    expect(ins.ref.index).toBe(1);
    expect(deleteVertex(ins.zones, ins.ref)).toMatchObject({ removed: 'vertex' });
    const preset: DrawnZones = { ...zs, h5: { ...zone('h5', [[square(500)]]), preset: { kind: 'footprint', inputTime: INPUT, verticesBefore: 4, verticesAfter: 4, toleranceM: 50 } } };
    expect(moveVertex(preset, { zone: 'h5', poly: 0, ring: 0, index: 0 }, m(1, 1)).h5.edited).toBe(true);
    expect(clearZone(preset, 'h5').h5).toEqual(zone('h5', []));
  });

  it('stored zones round-trip; malformed storage starts empty', () => {
    const zs = zonesOf([[square(1000)]], []);
    const stored = { version: 1, zones: zs, settings: { inputTime: INPUT, issueOffsetH: 3, marginMin: 45 }, savedAt: 'x' };
    const back = parseStoredZones(JSON.parse(JSON.stringify(stored)));
    expect(back?.zones.h5.polygons).toEqual(zs.h5.polygons);
    expect(back?.settings).toEqual({ inputTime: INPUT, issueOffsetH: 3, marginMin: 45 });
    expect(parseStoredZones({ version: 2 })).toBeNull();
    expect(parseStoredZones('nope')).toBeNull();
    expect(parseStoredZones({ version: 1, zones: { h5: { polygons: [[[['a', 'b']]]] } } })?.zones.h5.polygons).toEqual([]);
    expect(parseStoredZones({ version: 1, zones: {}, settings: { issueOffsetH: 99, marginMin: -5 } })?.settings).toMatchObject({ issueOffsetH: 8, marginMin: 0 });
  });

  it('default presets: 5 h ← footprint at the base time, 8 h ← the next later recorded footprint (never invented)', () => {
    const times = ['2099-01-02T00:00:00Z', '2099-01-01T09:00:00Z', '2099-01-01T17:00:00Z'];
    expect(defaultPresetTimes(times, '2099-01-01T09:00:00Z')).toEqual({ h5: '2099-01-01T09:00:00Z', h8: '2099-01-01T17:00:00Z' });
    expect(defaultPresetTimes(times, '2099-01-02T00:00:00Z')).toEqual({ h5: '2099-01-02T00:00:00Z', h8: null });
    expect(defaultPresetTimes(times, '2099-01-01T12:00:00Z')).toEqual({ h5: null, h8: '2099-01-01T17:00:00Z' });
    expect(defaultPresetTimes([], INPUT)).toEqual({ h5: null, h8: null });
  });
});

// ---------------------------------------------------------------- drawn-mode sort order

function plan(id: string, verdict: OriginPlan['bestVerdict'], latest: number | null = null): OriginPlan {
  return { originId: id, latestSafeDepartureS: latest, contiguousSafeDepartureS: latest, bestVerdict: verdict, sweep: [], windows: [], source: 'live', mock: false };
}

describe('drawn-mode list order', () => {
  it('inside zones first (Go before Set), then the urgency order', () => {
    const items: DrawnUrgencyItem[] = [
      { id: 'out-norte', name: '합성 바깥', vulnerable: false, plan: plan('out-norte', 'model_no_route'), rsg: null },
      { id: 'set-checked', name: '합성 준비2', vulnerable: false, plan: plan('set-checked', 'checked_route', 1200), rsg: 'set' },
      { id: 'go-checked', name: '합성 실행1', vulnerable: false, plan: plan('go-checked', 'checked_route', 600), rsg: 'go' },
      { id: 'set-unres', name: '합성 준비1', vulnerable: false, plan: plan('set-unres', 'unresolved'), rsg: 'set' },
      { id: 'go-noroute', name: '합성 실행2', vulnerable: false, plan: plan('go-noroute', 'model_no_route'), rsg: 'go' },
      { id: 'set-vuln', name: '합성 준비3', vulnerable: true, plan: plan('set-vuln', 'unresolved'), rsg: 'set' },
    ];
    expect(sortDrawn(items).map((i) => i.id)).toEqual(['go-noroute', 'go-checked', 'set-vuln', 'set-unres', 'set-checked', 'out-norte']);
    expect(compareDrawn(items[2]!, items[0]!)).toBeLessThan(0);
  });
});

// ---------------------------------------------------------------- assumptions (verbatim)

describe('assumptions rendering never alters numbers', () => {
  const synthetic = {
    adapter: 'synthetic-adapter/1',
    margin_min: 60.0,
    active_duration_s: 3970.4642815249267,
    tiny: 1e-7,
    sum: 0.1 + 0.2,
    big: 12345678901234,
    neg: -3600.0,
    flag: false,
    nothing: null,
    clock: { issued_minus_input_s: 0.0, rule: 'synthetic rule text' },
    bands_detail: [{ arrival_h_max: 5.0, ignition_times_s_from_input_time: [-3600.0, 5999.999999999999, 11999.999999999998, 18000.0], effective_packet_times_s: [0.0, null, null, null] }],
    limitations: ['a', 'b'],
  };

  it('prints every number with String(n) and parses back to the identical value', () => {
    const rows = flattenAssumptions(synthetic);
    const byPath = new Map(rows.map((r) => [r.path, r]));
    for (const [path, v] of [
      ['margin_min', 60],
      ['active_duration_s', 3970.4642815249267],
      ['tiny', 1e-7],
      ['sum', 0.30000000000000004],
      ['big', 12345678901234],
      ['neg', -3600],
      ['clock.issued_minus_input_s', 0],
    ] as const) {
      const r = byPath.get(path)!;
      expect(r.kind).toBe('number');
      expect(r.value).toBe(String(v));
      expect(Number(r.value)).toBe(v);
    }
    const arr = byPath.get('bands_detail[0].ignition_times_s_from_input_time')!;
    expect(arr.value).toBe('[-3600, 5999.999999999999, 11999.999999999998, 18000]');
    expect(JSON.parse(arr.value!)).toEqual(synthetic.bands_detail[0]!.ignition_times_s_from_input_time);
    expect(byPath.get('bands_detail[0].effective_packet_times_s')!.value).toBe('[0, null, null, null]');
    expect(byPath.get('flag')!.value).toBe('false');
    expect(byPath.get('nothing')!.value).toBe('null');
    expect(byPath.get('clock.rule')!.value).toBe('synthetic rule text');
    expect(byPath.get('limitations')!.value).toBe('["a", "b"]');
  });

  it('keeps the key order and nesting of the object as sent', () => {
    const rows = flattenAssumptions(synthetic);
    expect(rows.filter((r) => r.depth === 0).map((r) => r.key)).toEqual(Object.keys(synthetic));
    expect(rows.find((r) => r.path === 'clock')).toMatchObject({ kind: 'group', value: null });
    expect(rows.find((r) => r.path === 'bands_detail[0].arrival_h_max')).toMatchObject({ depth: 2, value: '5' });
    expect(primitiveText(5999.999999999999)).toBe('5999.999999999999');
    expect(arrayText([1.5, 'x', null])).toBe('[1.5, "x", null]');
    expect(flattenAssumptions(null)).toEqual([{ path: 'value', key: 'value', depth: 0, value: 'null', kind: 'null' }]);
  });

  it('shows the MOCK text of an unevaluated spread_zones answer', () => {
    const a = { mock: true, evaluated: false, text: { ko: '합성 안내문', en: 'synthetic notice' }, zones_received: 2 };
    expect(mockAssumptionText(a, 'ko')).toBe('합성 안내문');
    expect(mockAssumptionText(a, 'en')).toBe('synthetic notice');
    expect(mockAssumptionText({ mock: false, text: 'x' }, 'ko')).toBeNull();
    expect(flattenAssumptions(a).map((r) => [r.path, r.value])).toEqual([
      ['mock', 'true'],
      ['evaluated', 'false'],
      ['text', null],
      ['text.ko', '합성 안내문'],
      ['text.en', 'synthetic notice'],
      ['zones_received', '2'],
    ]);
  });
});

// ---------------------------------------------------------------- MOCK unresolved is never safe

describe('MOCK spread_zones results are unresolved and never counted as safe', () => {
  const mockJob = (offset: number): WireRouteCheckJob =>
    ({
      job_id: `mock-${offset}`,
      kind: 'route_check',
      status: 'done',
      created_at: '2099-01-01T00:00:00Z',
      request: { depart_offset_s: offset, start: { node_id: 'osm:1' }, destination: { node_id: 'osm:2' }, dwell_s: 120, destination_window: [0, 3600], policy: 'full' },
      snap: null,
      mock: true,
      error: null,
      result: {
        verdict: 'unresolved',
        reason_code: 'OTHER',
        raw_status: 'MOCK_SPREAD_ZONES_NOT_EVALUATED',
        raw_reason: null,
        arrival_s: null,
        lower_bound_L_s: null,
        dwell_end_s: null,
        route: null,
        exposure: [],
        compute_s: null,
        within_budget: true,
        assumptions: { mock: true, evaluated: false, text: { ko: '합성', en: 'synthetic' } },
        notes: [],
        provenance: { api_version: 'x', package: 'wfg_latest', package_version: 'x', kit: 'x', checkpoint: 'x', git_commit: 'x', input_hashes: {}, scenario_ids: [], fire_input_type: 'spread_zones', approximation: 'approximation, requires expert review', mock: true },
      },
    }) as unknown as WireRouteCheckJob;

  it('adapts as unresolved, keeps the assumptions verbatim and the approximation', () => {
    const d = adaptRouteJob(mockJob(0));
    expect(d.verdict).toBe('unresolved');
    expect(d.mock).toBe(true);
    expect(d.coordinates).toBeNull();
    expect(d.rawStatus).toBe('MOCK_SPREAD_ZONES_NOT_EVALUATED');
    expect(d.assumptions).toEqual({ mock: true, evaluated: false, text: { ko: '합성', en: 'synthetic' } });
    expect(d.provenance?.approximation).toBe('approximation, requires expert review');
  });

  it('gives no deadline, no checked count and an unresolved headline', () => {
    const offsets = [0, 600, 1200, 1800, 2400, 3000];
    const attempts = offsets.map((o) => attemptFromRoute(adaptRouteJob(mockJob(o)), 'd1', o));
    const p = planFromAttempts({ originId: 'o1', offsetsS: offsets, attempts, source: 'live', mock: true });
    expect(p.bestVerdict).toBe('unresolved');
    expect(p.latestSafeDepartureS).toBeNull();
    expect(p.contiguousSafeDepartureS).toBeNull();
    expect(p.best).toBeUndefined();
    expect(p.sweep.every((c) => c.verdict === 'unresolved')).toBe(true);
    expect(summarize([p])).toEqual({ checked_route: 0, model_no_route: 0, unresolved: 1 });
    expect(deadlineHeadline(p).kind).toBe('unresolved');
  });
});

// ---------------------------------------------------------------- deep links

describe('deep-link query', () => {
  it('reads ?region&scenario&origin&lang (+ input, preset); ignores unknown languages', () => {
    expect(readQuery('?region=r1&scenario=20990101T090000Z&origin=osm%3Anode%2F1&lang=en&print=all')).toEqual({ region: 'r1', scenario: '20990101T090000Z', origin: 'osm:node/1', lang: 'en' });
    expect(readQuery('?scenario=zones&preset=footprints&input=20990101T090000Z&lang=fr')).toEqual({ scenario: 'zones', preset: 'footprints', input: '20990101T090000Z' });
  });

  it('resolves input_compact, ISO, set ids and "zones" to scenarios', () => {
    const sets = [
      { id: 'ffb1:20990101T090000Z:aaaa', inputTime: '2099-01-01T09:00:00Z' },
      { id: 'ffb1:20990102T090000Z:bbbb', inputTime: '2099-01-02T09:00:00Z' },
    ];
    expect(resolveScenarioParam('20990102T090000Z', sets)).toBe('ffb1:20990102T090000Z:bbbb');
    expect(resolveScenarioParam('2099-01-01T09:00:00Z', sets)).toBe('ffb1:20990101T090000Z:aaaa');
    expect(resolveScenarioParam('ffb1:20990101T090000Z:aaaa', sets)).toBe('ffb1:20990101T090000Z:aaaa');
    expect(resolveScenarioParam('zones', sets)).toBe(DRAWN_SCENARIO);
    expect(resolveScenarioParam('drawn', sets)).toBe(DRAWN_SCENARIO);
    expect(resolveScenarioParam('20990103T090000Z', sets)).toBeNull();
    expect(resolveScenarioParam(undefined, sets)).toBeNull();
  });
});

// ---------------------------------------------------------------- plan sheet clock / exports in drawn mode

describe('drawn-zone clock and exports', () => {
  it('wall clock = input time + offset; T+ counts from the issue time', () => {
    const base = { inputTimeIso: '2099-01-01T09:00:00Z', issuedAtIso: '2099-01-01T07:00:00Z' };
    expect(clockAt(base, 600)).toBe('18:10 (T+2:10)');
    expect(clockAt({ inputTimeIso: '2099-01-01T09:00:00Z', issuedAtIso: '2099-01-01T09:00:00Z' }, 600)).toBe('18:10 (T+0:10)');
    expect(clockAt({ inputTimeIso: '2099-01-01T09:00:00Z' }, 600)).toBe('18:10');
  });

  const zs = zonesOf([[square(2000)]], [[square(8000)]]);
  const prov = { checkpoint: 'c', packageVersion: '1', kit: 'v3', apiMode: 'live' as const, apiVersion: '1.5.0', gitCommit: null, cacheCreatedAtIso: null, scenarioSetId: SET, approximation: 'approximation, requires expert review' };
  const place = (id: string, p: LonLat) => ({ id, name: `합성 ${id}`, categoryLabel: '마을', sourceTag: 'synthetic', lon: p[0], lat: p[1] });
  const fc = zonesFeatureCollection(zs);
  const input: ExportInput = {
    region: { id: 'synthetic_region', nameKo: '합성', nameEn: 'Synthetic', fireYear: 2099 },
    fireInputLabel: '사용자 입력 확산 구역 (가정)',
    fireInputType: 'spread_zones',
    mock: false,
    scenario: { scenarioSetId: SET, inputTimeIso: INPUT, issuedAtIso: issuedAtFor(INPUT, 2) },
    zones: { type: 'FeatureCollection', features: fc.features.map((f) => ({ ...f, properties: { ...f.properties, layer: 'spread_zone', assumption: true } })) },
    origins: [{ ...place('o1', m(0, 0)), vulnerable: false, rsgLabel: '실행(Go) — 전원 대피', plan: null }],
    selectedRoute: null,
    provenance: prov,
    generatedAtIso: '2099-01-01T00:00:00Z',
  };

  it('zones GeoJSON carries every zone polygon with arrival_h_max, the label and the issue time', () => {
    const g = zonesToGeoJSON(input);
    expect(g.features.map((f) => (f.properties as Record<string, unknown>).arrival_h_max)).toEqual([5, 8]);
    expect(g.features.every((f) => (f.properties as Record<string, unknown>).role === 'spread_zone')).toBe(true);
    expect((g.wfg as Record<string, unknown>).issued_at).toBe('2099-01-01T07:00:00Z');
    expect((g.wfg as Record<string, unknown>).fire_input_label).toBe('사용자 입력 확산 구역 (가정)');
  });

  it('a checked route GeoJSON includes the zones as an extra polygon layer; the CSV notes carry the Ready-Set-Go tag', () => {
    const route: ExportRoute = {
      role: 'evacuation_route',
      origin: place('o1', m(0, 0)),
      shelter: place('d1', m(500, 0)),
      verdict: 'checked_route',
      policy: 'full',
      departureS: 600,
      arrivalS: 700,
      coordinates: [m(0, 0), m(500, 0)],
      timesS: [600, 700],
    };
    const g = routeToGeoJSON(input, route);
    const roles = g.features.map((f) => (f.properties as Record<string, unknown>).role);
    expect(roles).toEqual(['spread_zone', 'spread_zone', 'evacuation_route', 'origin', 'shelter']);
    const line = g.features.find((f) => (f.properties as Record<string, unknown>).role === 'evacuation_route')!;
    expect((line.properties as Record<string, unknown>).departure_kst).toBe('2099-01-01 18:10'); // input time + offset, not issue time
    expect(dispatchListCSV(input)).toContain('실행(Go) — 전원 대피');
  });
});
