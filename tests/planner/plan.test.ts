/**
 * Domain rules of the planner (planner/src/domain/plan.ts). All places, ids and numbers below are
 * SYNTHETIC test data ("합성" names, round coordinates) — not real villages, shelters or results.
 */
import { describe, expect, it } from 'vitest';
import {
  CONTRACT_LIMITS,
  buildSweep,
  coarseToFine,
  combineVerdicts,
  contiguousSafeDeparture,
  countAttempts,
  deadlineHeadline,
  departureOffsets,
  gridOffsets,
  groupDispatch,
  kNearestDestinations,
  latestSafeDeparture,
  normalizeShelterCount,
  normalizeStepMin,
  osmCheckSpecs,
  originOffsets,
  placeLocation,
  planFromAttempts,
  positionAt,
  researchCheckSpecs,
  sortByUrgency,
  summarize,
  unresolvedPlan,
  verdictWindows,
  windowUnsatisfiable,
  sameNodeDestinations,
} from '../../planner/src/domain/plan';
import type { Attempt, Place, Verdict } from '../../planner/src/domain/types';

function att(offsetS: number, destinationId: string, verdict: Verdict, arrivalS: number | null = null): Attempt {
  return { offsetS, destinationId, verdict, arrivalS, computeS: verdict === 'unresolved' ? null : 5, jobId: `job-${offsetS}-${destinationId}`, reasonCode: verdict === 'unresolved' ? 'TIMEOUT' : null };
}

function place(id: string, lon: number, lat: number, extra: Partial<Place> = {}): Place {
  return {
    id,
    role: 'origin',
    category: 'village',
    name: `합성마을 ${id}`,
    nameEn: null,
    lon,
    lat,
    source: 'OpenStreetMap',
    sourceTag: 'place=village',
    osm: null,
    snapNode: `osm:${id}`,
    snapDistanceM: 10,
    entry: { node: `osm:${id}`, lon, lat, distanceM: 10, withinApiLonlatSnap: true },
    checkable: true,
    vulnerable: false,
    scenarioSetId: null,
    inputTime: null,
    caseId: null,
    recorded: null,
    ...extra,
  };
}

describe('per-offset verdict rule', () => {
  it('is checked if any destination is checked', () => {
    expect(combineVerdicts(['unresolved', 'model_no_route', 'checked_route'])).toBe('checked_route');
  });
  it('is model_no_route only if every attempted destination is model_no_route', () => {
    expect(combineVerdicts(['model_no_route', 'model_no_route'])).toBe('model_no_route');
    expect(combineVerdicts(['model_no_route', 'unresolved'])).toBe('unresolved');
  });
  it('is unresolved with no attempts (never safe)', () => {
    expect(combineVerdicts([])).toBe('unresolved');
  });
  it('picks the earliest-arrival checked attempt as the cell best', () => {
    const sweep = buildSweep([0], [att(0, 'b', 'checked_route', 900), att(0, 'a', 'checked_route', 600), att(0, 'c', 'unresolved')]);
    expect(sweep[0]!.verdict).toBe('checked_route');
    expect(sweep[0]!.best?.destinationId).toBe('a');
  });
});

describe('departure deadlines', () => {
  // 0 checked, 600 unresolved, 1200 checked, 1800 model_no_route
  const attempts = [att(0, 'a', 'checked_route', 500), att(600, 'a', 'unresolved'), att(1200, 'a', 'checked_route', 1900), att(1800, 'a', 'model_no_route')];
  const plan = planFromAttempts({ originId: 'o', offsetsS: [0, 600, 1200, 1800], attempts, source: 'live', mock: false });

  it('latestSafeDepartureS is the latest checked offset', () => {
    expect(plan.latestSafeDepartureS).toBe(1200);
    expect(plan.best?.offsetS).toBe(1200);
  });
  it('contiguousSafeDepartureS follows the contract v1.4 rule (stops at the first unchecked offset)', () => {
    expect(plan.contiguousSafeDepartureS).toBe(0);
  });
  it('contiguous is null when the earliest offset is not checked', () => {
    const p = planFromAttempts({ originId: 'o', offsetsS: [0, 600], attempts: [att(0, 'a', 'unresolved'), att(600, 'a', 'checked_route', 900)], source: 'live', mock: false });
    expect(p.latestSafeDepartureS).toBe(600);
    expect(p.contiguousSafeDepartureS).toBeNull();
  });
  it('headline shows the deadline with a caveat when contiguous differs or is null', () => {
    expect(deadlineHeadline(plan)).toEqual({ kind: 'deadline', deadlineS: 1200, caveat: { contiguousS: 0 } });
    const all = planFromAttempts({ originId: 'o', offsetsS: [0, 600], attempts: [att(0, 'a', 'checked_route', 1), att(600, 'a', 'checked_route', 2)], source: 'live', mock: false });
    expect(deadlineHeadline(all)).toEqual({ kind: 'deadline', deadlineS: 600, caveat: null });
  });
  it('unresolved cells never count as safe', () => {
    const p = planFromAttempts({ originId: 'o', offsetsS: [0, 600], attempts: [att(0, 'a', 'unresolved'), att(600, 'a', 'unresolved')], source: 'live', mock: false });
    expect(p.bestVerdict).toBe('unresolved');
    expect(p.latestSafeDepartureS).toBeNull();
    expect(p.contiguousSafeDepartureS).toBeNull();
    expect(deadlineHeadline(p).kind).toBe('unresolved');
    expect(latestSafeDeparture(p.sweep)).toBeNull();
  });
  it('model_no_route everywhere gives the no-route headline', () => {
    const p = planFromAttempts({ originId: 'o', offsetsS: [0, 600], attempts: [att(0, 'a', 'model_no_route'), att(600, 'a', 'model_no_route')], source: 'live', mock: false });
    expect(p.bestVerdict).toBe('model_no_route');
    expect(deadlineHeadline(p).kind).toBe('no_route');
  });
  it('a plan without results is unresolved', () => {
    const p = unresolvedPlan('o', [0, 600], 'not_checkable', 'live', false);
    expect(p.bestVerdict).toBe('unresolved');
    expect(p.sweep.every((c) => c.verdict === 'unresolved')).toBe(true);
    expect(summarize([p, undefined]).unresolved).toBe(2);
  });
  it('verdict windows merge consecutive cells', () => {
    expect(verdictWindows(plan.sweep).map((w) => [w.verdict, w.fromS, w.toS])).toEqual([
      ['checked_route', 0, 0],
      ['unresolved', 600, 600],
      ['checked_route', 1200, 1200],
      ['model_no_route', 1800, 1800],
    ]);
  });
});

describe('window-unsatisfiable offsets', () => {
  it('applies max(off, open) + dwell > min(close, horizon)', () => {
    expect(windowUnsatisfiable(2400, [0, 2619], 120, 3600)).toBe(false); // 2520 ≤ 2619
    expect(windowUnsatisfiable(3000, [0, 2619], 120, 3600)).toBe(true); // 3120 > 2619
    expect(windowUnsatisfiable(0, [1064, 3600], 120, 3600)).toBe(false); // waits for the window to open
    expect(windowUnsatisfiable(3500, [0, 3600], 120, 3600)).toBe(true);
    expect(windowUnsatisfiable(0, [0, 3600], 120, 1000)).toBe(false);
    expect(windowUnsatisfiable(900, [0, 3600], 120, 1000)).toBe(true); // horizon closes first
  });
  it('research specs skip unsatisfiable offsets and keep them as "시간창 밖" cells', () => {
    const r = place('r1', 128.5, 36.5, {
      role: 'research_origin',
      category: 'research',
      name: null,
      scenarioSetId: 'set-synthetic',
      recorded: { destinationId: 'rd1', destinationNode: 'osm:999', departOffsetS: 300, dwellS: 120, destinationWindow: [0, 2619], incurredDoseKjM2: 12.5, limits: { peakKwM2: 10, doseKjM2: 50 }, horizonS: 3600 },
    });
    const offs = originOffsets(r, 3600, 10);
    expect(offs).toEqual([0, 300, 600, 1200, 1800, 2400, 3000]);
    const { specs, skipped } = researchCheckSpecs(r, offs, 3600);
    expect(Object.keys(skipped).map(Number)).toEqual([3000]);
    expect(specs.map((s) => s.offsetS)).toEqual([0, 300, 600, 1200, 1800, 2400]);
    expect(specs[0]).toMatchObject({ start: { kind: 'node', nodeId: 'osm:r1' }, destination: { kind: 'node', nodeId: 'osm:999' }, dwellS: 120, window: [0, 2619], incurredDoseKjM2: 12.5, limits: { peakKwM2: 10, doseKjM2: 50 }, policy: 'full' });
    // skipped cells are not counted in verdicts or deadlines
    const plan = planFromAttempts({ originId: r.id, offsetsS: offs, attempts: specs.map((s) => att(s.offsetS, 'rd1', 'checked_route', s.offsetS + 900)), source: 'live', mock: false, skipped });
    const cell = plan.sweep.find((c) => c.offsetS === 3000)!;
    expect(cell.skipped).toBe('window_unsatisfiable');
    expect(cell.verdict).toBe('unresolved');
    expect(plan.latestSafeDepartureS).toBe(2400);
    expect(plan.contiguousSafeDepartureS).toBe(2400);
    expect(plan.bestVerdict).toBe('checked_route');
    expect(contiguousSafeDeparture(plan.sweep)).toBe(2400);
  });
});

describe('skips other than window_unsatisfiable', () => {
  it('a refused request is an unresolved cell, not "시간창 밖", and breaks the contiguous run', () => {
    const sweep = buildSweep([0, 600, 1200], [att(1200, 'a', 'checked_route', 2000)], { 0: 'window_unsatisfiable', 600: 'NODE_NOT_ALLOWED' });
    const c0 = sweep.find((c) => c.offsetS === 0)!;
    const c600 = sweep.find((c) => c.offsetS === 600)!;
    expect(c0.skipped).toBe('window_unsatisfiable');
    expect(c600.verdict).toBe('unresolved');
    expect(c600.skipped).not.toBe('window_unsatisfiable');
    // windows: the "시간창 밖" run covers 0 only; the refused offset is a plain unresolved run
    const w = verdictWindows(sweep);
    expect(w.map((x) => [x.verdict, x.fromS, x.toS, Boolean(x.skipped)])).toEqual([
      ['unresolved', 0, 0, true],
      ['unresolved', 600, 600, false],
      ['checked_route', 1200, 1200, false],
    ]);
    // 0 is not a requested offset (left out); 600 was requested and has no checked route → no contiguous basis
    expect(contiguousSafeDeparture(sweep)).toBeNull();
    const plan = planFromAttempts({ originId: 'o', offsetsS: [0, 600, 1200], attempts: [att(1200, 'a', 'checked_route', 2000)], source: 'cache', mock: false, skipped: { 0: 'window_unsatisfiable', 600: 'NODE_NOT_ALLOWED' } });
    expect(plan.windows.filter((x) => x.skipped).map((x) => [x.fromS, x.toS])).toEqual([[0, 0]]);
    expect(deadlineHeadline(plan).caveat).toEqual({ contiguousS: null });
  });
});

describe('offsets', () => {
  it('grid every step over [0, horizon) plus recorded offsets', () => {
    expect(gridOffsets(3600, 10)).toEqual([0, 600, 1200, 1800, 2400, 3000]);
    expect(departureOffsets(3600, 10, [300, 600, 3600, -1])).toEqual([0, 300, 600, 1200, 1800, 2400, 3000]);
    expect(normalizeStepMin('15')).toBe(15);
    expect(normalizeStepMin('7')).toBe(10);
    expect(normalizeShelterCount('9')).toBe(3);
    expect(normalizeShelterCount(5)).toBe(5);
  });
  it('coarse-to-fine visits every offset once, ends first', () => {
    const xs = gridOffsets(3600, 5);
    const order = coarseToFine(xs);
    expect(order.slice(0, 2)).toEqual([0, 3300]);
    expect([...order].sort((a, b) => a - b)).toEqual(xs);
  });
});

describe('K-nearest shelters and dispatch grouping', () => {
  const shelters = [place('s1', 128.0, 36.0, { role: 'destination', category: 'school' }), place('s2', 128.1, 36.0, { role: 'destination', category: 'school' }), place('s3', 128.5, 36.0, { role: 'destination', category: 'shelter' }), place('s4', 129.0, 36.0, { role: 'destination', category: 'shelter', checkable: false })];
  it('nearest checkable destinations, never the same road node', () => {
    const o = place('o1', 128.01, 36.0);
    expect(kNearestDestinations(o, shelters, 2).map((d) => d.id)).toEqual(['s1', 's2']);
    const sameNode = place('o2', 128.0, 36.0, { entry: { node: 'osm:s1', lon: 128, lat: 36, distanceM: 1, withinApiLonlatSnap: true } });
    expect(kNearestDestinations(sameNode, shelters, 2).map((d) => d.id)).toEqual(['s2', 's3']);
    expect(kNearestDestinations(o, shelters, 9).map((d) => d.id)).not.toContain('s4');
  });
  it('K nearest have K distinct entry nodes (shelters sharing a node are one alternative)', () => {
    const o = place('o1', 128.0, 36.0);
    const sharedA = place('sa', 128.01, 36.0, { role: 'destination', category: 'school', entry: { node: 'osm:shared', lon: 128.01, lat: 36.0, distanceM: 5, withinApiLonlatSnap: true } });
    const sharedB = place('sb', 128.011, 36.0, { role: 'destination', category: 'school', entry: { node: 'osm:shared', lon: 128.01, lat: 36.0, distanceM: 8, withinApiLonlatSnap: true } });
    const other = place('so', 128.05, 36.0, { role: 'destination', category: 'shelter' });
    const far = place('sf', 128.2, 36.0, { role: 'destination', category: 'shelter' });
    const near = kNearestDestinations(o, [sharedB, far, other, sharedA], 3);
    expect(near.map((d) => d.id)).toEqual(['sa', 'so', 'sf']);
    expect(new Set(near.map((d) => d.entry!.node)).size).toBe(3);
    expect(sameNodeDestinations(sharedA, [sharedA, sharedB, other]).map((d) => d.id)).toEqual(['sb']);
  });
  it('OSM places are sent by their entry node', () => {
    expect(placeLocation(place('o1', 128.01, 36.0))).toEqual({ kind: 'node', nodeId: 'osm:o1' });
    expect(placeLocation(place('o9', 128.01, 36.0, { entry: null, snapNode: null }))).toEqual({ kind: 'lonlat', lon: 128.01, lat: 36.0 });
  });
  it('groups by identical shelter sets and never sends non-checkable origins', () => {
    const origins = [place('a', 128.01, 36.0), place('b', 128.02, 36.0), place('c', 128.49, 36.0), place('x', 128.0, 36.0, { checkable: false })];
    const groups = groupDispatch(origins, shelters, 2, [0, 600]);
    const all = groups.flatMap((g) => g.originIds);
    expect(all.sort()).toEqual(['a', 'b', 'c']);
    expect(groups.find((g) => g.originIds.includes('a'))!.originIds).toContain('b');
    expect(countAttempts(groups)).toBe(3 * 2 * 2);
  });
  it('splits plans within the contract limits (≤200 origins, ≤20 destinations, ≤24 offsets, ≤4800 attempts)', () => {
    const many = Array.from({ length: 450 }, (_, i) => place(`m${i}`, 128.0 + i * 1e-6, 36.0));
    const dests = Array.from({ length: 25 }, (_, i) => place(`d${i}`, 128.0 + i * 1e-3, 36.001, { role: 'destination', category: 'school' }));
    const offsets = gridOffsets(3600 * 5, 10); // 30 offsets
    const groups = groupDispatch(many, dests, 25, offsets);
    for (const g of groups) {
      expect(g.originIds.length).toBeLessThanOrEqual(CONTRACT_LIMITS.origins);
      expect(g.destinationIds.length).toBeLessThanOrEqual(CONTRACT_LIMITS.destinations);
      expect(g.offsetsS.length).toBeLessThanOrEqual(CONTRACT_LIMITS.offsets);
      expect(g.originIds.length * g.destinationIds.length * g.offsetsS.length).toBeLessThanOrEqual(CONTRACT_LIMITS.attempts);
    }
    // every origin × destination × offset is covered exactly once
    expect(countAttempts(groups)).toBe(450 * 25 * 30);
  });
  it('OSM specs use window [0, horizon] and dwell 120 for every shelter and offset', () => {
    const specs = osmCheckSpecs(place('a', 128.01, 36.0), shelters.slice(0, 2), [0, 600], 3600);
    expect(specs).toHaveLength(4);
    expect(specs[0]).toMatchObject({ window: [0, 3600], dwellS: 120, policy: 'full', limits: null, incurredDoseKjM2: null, start: { kind: 'node', nodeId: 'osm:a' } });
    expect(osmCheckSpecs(place('x', 1, 1, { checkable: false }), shelters, [0], 3600)).toEqual([]);
  });
});

describe('urgency order', () => {
  const mk = (id: string, verdict: Verdict, latest: number | null, contiguous: number | null, vulnerable = false) => ({
    id,
    name: `합성 ${id}`,
    vulnerable,
    plan: { originId: id, bestVerdict: verdict, latestSafeDepartureS: latest, contiguousSafeDepartureS: contiguous, sweep: [], windows: [], source: 'live' as const, mock: false },
  });
  it('model_no_route, then unresolved, then checked by contiguous (null first, as the API); ties vulnerable first, then name', () => {
    const items = [
      mk('c-late', 'checked_route', 3000, 3000),
      mk('c-gap', 'checked_route', 3000, 600), // contiguous 600
      mk('c-null', 'checked_route', 1200, null), // no checked route at the earliest departure: most urgent checked
      mk('u', 'unresolved', null, null),
      mk('n', 'model_no_route', null, null),
      mk('c-tie-b', 'checked_route', 1800, 1800),
      mk('c-tie-a', 'checked_route', 1800, 1800, true),
    ];
    expect(sortByUrgency(items).map((i) => i.id)).toEqual(['n', 'u', 'c-null', 'c-gap', 'c-tie-a', 'c-tie-b', 'c-late']);
  });
  it('matches the contract order: an origin whose earliest departure is unresolved ranks first among checked', () => {
    // A: 0 TIMEOUT then 600–3000 checked; B checked 0–1200; C checked 0–600; D checked only at 0
    const items = [mk('B', 'checked_route', 1200, 1200), mk('A', 'checked_route', 3000, null), mk('C', 'checked_route', 600, 600), mk('D', 'checked_route', 0, 0)];
    expect(sortByUrgency(items).map((i) => i.id)).toEqual(['A', 'D', 'C', 'B']);
    // two null contiguous: by latest checked offset, never NaN
    const two = [mk('late', 'checked_route', 3000, null), mk('early', 'checked_route', 600, null), mk('z', 'checked_route', 0, 0)];
    expect(sortByUrgency(two).map((i) => i.id)).toEqual(['early', 'late', 'z']);
  });
});

describe('vehicle position', () => {
  it('interpolates along per-vertex times', () => {
    const coords: [number, number][] = [[0, 0], [10, 0], [10, 10]];
    expect(positionAt(coords, [100, 200, 300], 50)).toEqual([0, 0]);
    expect(positionAt(coords, [100, 200, 300], 150)).toEqual([5, 0]);
    expect(positionAt(coords, [100, 200, 300], 250)).toEqual([10, 5]);
    expect(positionAt(coords, [100, 200, 300], 999)).toEqual([10, 10]);
    expect(positionAt([], [], 1)).toBeNull();
  });
});
