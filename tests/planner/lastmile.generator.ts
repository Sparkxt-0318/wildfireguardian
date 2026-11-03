/**
 * SEEDED SYNTHETIC case generator for the last-mile property tests (lastmile.property.test.ts) — no
 * new dependency: a mulberry32 PRNG drives random but contract-shaped inputs that go through the
 * app's own code (domain/plan.ts planFromAttempts, features/lastmile/input.ts buildLastMileInputs):
 * any 2025 date and hour (minutes too), horizons of 30–120 min, every departure step the planner
 * allows, sweeps of every shape (a checked run then no route, gaps, a late first check, all no route,
 * all unresolved, window-closed tails), 1–3 destinations, names that are missing, Hangul-only,
 * Latin or very long, road entry points 0–1,999 m away, cache or live results (Linux, macOS or
 * unknown hosts), MOCK and test-data flags, and — for most cases — a `wfg.explanation/1` entry of
 * every reason code, some deliberately inconsistent with the planner (shifted deadline, wrong
 * destination, unknown codes, partial status). Every name is "합성 …" / "Hapseong …": nothing here
 * is a real place, road, fire or result.
 */
import { ALLOWED_STEPS_MIN, gridOffsets, planFromAttempts, unresolvedPlan } from '../../planner/src/domain/plan';
import type { Attempt, HostInfo, OriginPlan, Place, PlaceCategory, Verdict } from '../../planner/src/domain/types';
import { buildLastMileInputs } from '../../planner/src/features/lastmile/input';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import type { ExplanationFile, LastMileInput } from '../../planner/src/features/lastmile/types';

/** mulberry32: a small, well-known 32-bit PRNG (deterministic for a seed). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface GenCase {
  n: number;
  input: LastMileInput;
  /** the scenario's explanation file (one entry for this origin), or null */
  file: ExplanationFile | null;
  /** what the case was built to exercise (for failure messages and coverage counts) */
  tags: string[];
}

const REGION = { id: 'synthetic_region', nameKo: '합성 지역', nameEn: 'Synthetic region', fireYear: 2025 };
const SET = 'ffb1:synthetic:generated';
const LINUX: HostInfo = { recorded: false, machine: 'x86_64', os: 'Linux', platform: 'Linux-6.18-x86_64-with-glibc2.39', cpuCount: 4 };
const MAC: HostInfo = { recorded: false, machine: 'arm64', os: 'Darwin', platform: 'macOS-26.0-arm64-arm-64bit', cpuCount: 12 };

/** [Korean name, English name] — null: unnamed; a Hangul English name: OSM has no Latin-script name. */
const ORIGIN_NAMES: ([string, string] | null)[] = [
  null,
  ['합성리', 'Hapseong-ri'],
  ['합성마을', '합성마을'],
  ['합성 1리', 'Hapseong 1-ri'],
  ['가나다라마바사아자차카타파하합성리', '가나다라마바사아자차카타파하합성리'],
  ['합성군노인복지관부설재가노인복지센터', 'Hapseong County Senior Welfare Center Home Care Annex'],
  ['안전마을', 'Anjeon-maeul'],
];
const DEST_NAMES: ([string, string] | null)[] = [
  null,
  ['합성초등학교', 'Hapseong Elementary School'],
  ['합성중학교', '합성중학교'],
  ['구 합성초등학교 합성분교 터', '구 합성초등학교 합성분교 터'],
  ['합성 마을회관', 'Hapseong Community Hall'],
];
const ORIGIN_CATS: PlaceCategory[] = ['village', 'hamlet', 'nursing_home', 'social_facility'];
const DEST_CATS: PlaceCategory[] = ['shelter', 'school', 'community_hall', 'assembly_point', 'temporary_housing'];

function place(id: string, role: 'origin' | 'destination', category: PlaceCategory, name: [string, string] | null, entryM: number | null, checkable: boolean, vulnerable: boolean): Place {
  return {
    id,
    role,
    category,
    name: name ? name[0] : null,
    nameEn: name ? name[1] : null,
    lon: 128.5,
    lat: 36.4,
    source: 'SYNTHETIC',
    sourceTag: 'synthetic',
    osm: null,
    snapNode: `syn:node:${id}`,
    snapDistanceM: entryM,
    entry: entryM === null ? null : { node: `syn:node:${id}`, lon: 128.5, lat: 36.4, distanceM: entryM, withinApiLonlatSnap: true },
    checkable,
    vulnerable,
    scenarioSetId: null,
    inputTime: null,
    caseId: null,
    recorded: null,
  };
}

/** Generates `count` cases from `seed` (the same seed always gives the same cases). */
export function generateCases(seed: number, count: number): GenCase[] {
  const r = mulberry32(seed);
  const int = (lo: number, hi: number) => lo + Math.floor(r() * (hi - lo + 1));
  const pick = <T>(xs: readonly T[]): T => xs[Math.floor(r() * xs.length)]!;
  const chance = (p: number) => r() < p;
  const out: GenCase[] = [];

  for (let n = 0; n < count; n += 1) {
    const tags: string[] = [];
    // ---------------------------------------------------------------- scenario
    const month = int(1, 12);
    const day = int(1, 28);
    const hour = int(0, 23);
    const minute = chance(0.7) ? 0 : pick([5, 30, 59, int(0, 59)]);
    const inputTimeIso = new Date(Date.UTC(2025, month - 1, day, hour, minute) - 9 * 3600 * 1000).toISOString().replace('.000Z', 'Z');
    const horizonS = chance(0.8) ? 3600 : pick([1800, 5400, 7200]);
    const offsets = gridOffsets(horizonS, pick(ALLOWED_STEPS_MIN));

    // ---------------------------------------------------------------- places
    const originId = `syn:gen:${n}:origin`;
    const category = pick(ORIGIN_CATS);
    const checkable = !chance(0.04);
    const origin = place(originId, 'origin', category, pick(ORIGIN_NAMES), chance(0.1) ? null : int(0, 1999), checkable, chance(0.3));
    const dests = Array.from({ length: int(1, 3) }, (_, k) => place(`syn:gen:${n}:dest:${k}`, 'destination', pick(DEST_CATS), pick(DEST_NAMES), int(0, 900), true, false));

    // ---------------------------------------------------------------- the planner's result
    const wcFrom = chance(0.2) ? int(1, offsets.length - 1) : offsets.length;
    const skipped: Record<number, 'window_unsatisfiable'> = {};
    offsets.forEach((o, i) => {
      if (i >= wcFrom) skipped[o] = 'window_unsatisfiable';
    });
    const shape = pick(['deadline', 'deadline', 'deadline', 'gap', 'late_start', 'all_no_route', 'all_unresolved', 'random'] as const);
    const cut = int(0, Math.max(0, wcFrom - 1));
    const verdictAt = (i: number): Verdict => {
      switch (shape) {
        case 'deadline':
          return i <= cut ? 'checked_route' : chance(0.85) ? 'model_no_route' : 'unresolved';
        case 'gap':
          return i === Math.max(1, cut - 1) ? 'unresolved' : i <= cut + 1 ? 'checked_route' : 'model_no_route';
        case 'late_start':
          return i === 0 ? pick(['unresolved', 'model_no_route'] as const) : i <= cut + 1 ? 'checked_route' : 'model_no_route';
        case 'all_no_route':
          return 'model_no_route';
        case 'all_unresolved':
          return 'unresolved';
        default:
          return pick(['checked_route', 'model_no_route', 'unresolved'] as const);
      }
    };
    tags.push(`shape:${shape}`);
    const attempts: Attempt[] = [];
    offsets.forEach((offsetS, i) => {
      if (i >= wcFrom) return;
      const v = verdictAt(i);
      // a checked cell has at least one checked destination (any of them); others may have no route there
      const sure = int(0, dests.length - 1);
      dests.forEach((d, k) => {
        const dv: Verdict = v === 'checked_route' ? (k === sure || chance(0.5) ? 'checked_route' : 'model_no_route') : v;
        const room = horizonS - offsetS - 60;
        attempts.push({
          offsetS,
          destinationId: d.id,
          verdict: dv,
          arrivalS: dv === 'checked_route' ? offsetS + Math.max(1, int(30, Math.max(31, room))) : null,
          computeS: null,
          jobId: `syn:gen:${n}:job:${attempts.length}`,
          reasonCode: null,
        });
      });
    });
    const live = chance(0.2);
    const mock = chance(0.15);
    const cacheTestData = chance(0.15);
    let plan: OriginPlan | null;
    if (!checkable) plan = null; // the input builder makes it "not checkable"
    else if (chance(0.04)) plan = unresolvedPlan(originId, offsets, pick(['not_computed', 'rejected'] as const), live ? 'live' : 'cache', mock);
    else if (chance(0.03)) plan = null; // not computed at all
    else plan = planFromAttempts({ originId, offsetsS: offsets, attempts, source: live ? 'live' : 'cache', mock, skipped });
    if (live) tags.push('live');
    if (mock) tags.push('mock');
    if (cacheTestData && !live) tags.push('cache_test_data');

    const hosts = live ? pick([[LINUX], [MAC], [], [MAC, LINUX]]) : [];
    const [input] = buildLastMileInputs({
      region: REGION,
      scenario: { scenarioSetId: SET, inputTimeIso, horizonS },
      places: [origin, ...dests],
      plans: plan ? { [originId]: plan } : {},
      mock,
      cache: { path: 'synthetic_region/generated.json', createdAtIso: '2026-10-17T22:54:05Z', testData: cacheTestData },
      liveHosts: live ? { [originId]: hosts } : {},
      source: live ? 'live' : 'cache',
      generatedAtIso: '2026-11-02T05:00:00Z',
    });
    if (!input) throw new Error(`case ${n}: no input built`);

    // ---------------------------------------------------------------- explanation entry
    let file: ExplanationFile | null = null;
    if (chance(0.7)) {
      const entry = explanationEntry(input, { int, pick, chance }, tags);
      file = {
        schema: 'wfg.explanation/1',
        region_id: REGION.id,
        input_time: inputTimeIso,
        scenario_set_id: SET,
        provenance: { synthetic: true, code_commit: 'synthetic', generated_at: '2026-11-02T18:14:36+00:00' },
        summary: {},
        origins: { [originId]: entry } as unknown as ExplanationFile['origins'],
      };
    }
    out.push({ n, input, file, tags });
  }
  return out;
}

type Rand = { int: (lo: number, hi: number) => number; pick: <T>(xs: readonly T[]) => T; chance: (p: number) => boolean };

/** A road label of every source the contract allows (composed labels stay within 40 characters). */
function label(g: Rand): Record<string, unknown> {
  const src = g.pick(['osm_name', 'osm_ref', 'nearest_place', 'unnamed'] as const);
  if (src === 'osm_name') return g.chance(0.5) ? { label_ko: '합성로', label_en: 'Hapseong-ro', label_source: src } : { label_ko: '합성 시험용 아주 긴 이름의 지방도로 (마흔 글자 이내)', label_en: 'Synthetic test road, a long 40-char name', label_source: src };
  if (src === 'osm_ref') return { label_ko: String(g.int(1, 999)), label_en: null, label_source: src };
  if (src === 'unnamed') return { label_ko: null, label_en: null, label_source: src };
  return { label_ko: '합성리', label_en: 'Hapseong-ri', label_source: src, place_distance_m: g.int(0, 3000), place_is_origin: g.chance(0.4), place_kind: 'village' };
}

function members(g: Rand): number[] {
  const all = [0, 1, 2, 3].filter(() => g.chance(0.6));
  return all.length ? all : [g.int(0, 3)];
}

/**
 * One origin entry built from the planner's own result (messagePlan without a file) and a reason
 * code picked at random; some are deliberately inconsistent (the reader must then give no reason).
 */
function explanationEntry(input: LastMileInput, g: Rand, tags: string[]): Record<string, unknown> {
  const p = messagePlan(input, null);
  const horizon = input.scenario.horizonS;
  const D = input.plan?.latestSafeDepartureS ?? null;
  const sweep = [...(input.plan?.sweep ?? [])].sort((a, b) => a.offsetS - b.offsetS);
  const next = D === null ? null : sweep.find((c) => c.offsetS > D) ?? null;
  const nextVerdict = !next ? null : next.verdict === 'window_closed' ? 'window' : next.verdict === 'checked_route' ? null : next.verdict;
  const base = { binding: [], exits: [], notes: [] };
  if (p.kind === 'leave_by' && D !== null) {
    const kind = g.pick(['flame_on_route', 'dwell_at_destination', 'window', 'no_flame_avoiding_route', 'window_partial', 'unknown', 'shifted', 'other_destination'] as const);
    tags.push(`entry:leave_by:${kind}`);
    const deadline = kind === 'shifted' ? D + (next ? next.offsetS - D : 600) : D;
    const common = { ...base, status: 'explained', verdict_summary: 'checked_route', deadline_offset_s: deadline, next_offset_s: next?.offsetS ?? null, next_verdict: nextVerdict };
    if (kind === 'flame_on_route' || kind === 'dwell_at_destination' || kind === 'shifted' || kind === 'other_destination') {
      const pass = Math.min(horizon - 2, D + g.int(1, 900));
      const flame = Math.min(horizon, pass + g.int(1, 900));
      const ids = kind === 'other_destination' ? ['syn:not:the:destination'] : [p.destination?.id ?? 'syn:none'];
      const item = { edge_id: 'syn:edge', ...label(g), flame_time_s: flame, members: members(g), members_total: 4, pass_time_at_deadline_s: pass, slack_s: flame - pass, destination_ids: ids };
      const reason = kind === 'dwell_at_destination' ? 'dwell_at_destination' : 'flame_on_route';
      return { ...common, status: kind === 'dwell_at_destination' ? 'explained_partial' : 'explained', reason_code: reason, detail_code: reason === 'dwell_at_destination' ? 'stay_meets_flame' : 'route_meets_flame_when_shifted', deadline_cause: 'flames', binding: [item] };
    }
    if (kind === 'window') return { ...common, reason_code: 'window', detail_code: 'window_fire_free', deadline_cause: 'time_window' };
    if (kind === 'window_partial') return { ...common, status: 'explained_partial', reason_code: 'window', detail_code: 'window_fire_free', deadline_cause: null };
    if (kind === 'no_flame_avoiding_route') return { ...common, reason_code: 'no_flame_avoiding_route', detail_code: g.pick(['window_fire_detour', 'other_shelters_flame_blocked']), deadline_cause: 'flames' };
    return { ...common, reason_code: 'brand_new_reason', detail_code: 'brand_new_detail', deadline_cause: 'flames' };
  }
  if (p.kind === 'no_route') {
    const kind = g.pick(['all_exits_blocked', 'entry_point_in_flame', 'no_flame_avoiding_route', 'window', 'partial'] as const);
    tags.push(`entry:no_route:${kind}`);
    const common = { ...base, status: kind === 'partial' ? 'explained_partial' : 'explained', verdict_summary: 'model_no_route', deadline_offset_s: null, next_offset_s: null, next_verdict: null };
    if (kind === 'all_exits_blocked' || kind === 'partial') {
      const exits = Array.from({ length: g.int(1, 4) }, (_, k) => ({ edge_id: `syn:exit:${k}`, ...label(g), flame_time_s: g.chance(0.3) ? 0 : g.int(0, horizon), members: members(g), members_total: 4, pass_time_at_deadline_s: null, slack_s: null, reached_at_s: 60 }));
      return { ...common, reason_code: 'all_exits_blocked', detail_code: 'flame_free_area_closed', deadline_cause: 'flames', exits };
    }
    if (kind === 'entry_point_in_flame') return { ...common, reason_code: 'all_exits_blocked', detail_code: 'entry_point_in_flame', deadline_cause: 'flames' };
    if (kind === 'no_flame_avoiding_route') return { ...common, reason_code: 'no_flame_avoiding_route', detail_code: 'no_flame_avoiding_route_fits_window', deadline_cause: 'flames' };
    return { ...common, reason_code: 'window', detail_code: 'no_route_even_without_fire', deadline_cause: 'time_window' };
  }
  // unresolved and partial messages: whatever the file says, no reason
  tags.push(`entry:${p.kind}:claimed`);
  return { ...base, status: 'explained', verdict_summary: input.plan?.bestVerdict ?? 'unresolved', deadline_offset_s: D, next_offset_s: next?.offsetS ?? null, next_verdict: nextVerdict, reason_code: 'window', detail_code: 'window_fire_free', deadline_cause: 'time_window' };
}
