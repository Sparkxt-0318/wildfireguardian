/**
 * SYNTHETIC test data for the last-mile kit (planner/src/features/lastmile). Every name here is
 * "합성 …" / "Synthetic …", the region is not a real region and every number is made up for the
 * tests — none of it is a village, shelter, road, fire or result of any recorded scenario.
 *
 * synExplanation() follows the deadline-explanation contract `wfg.explanation/1`
 * (planner/public/data/explanations/<region_id>__<input>.json, written by tools/explain_deadlines)
 * field by field, including the fields of the real files (detail_code, deadline_cause,
 * shelters_next, window, destination_classes, destination_ids, place_is_origin, …) and one origin for
 * each final reason code: flame_on_route, dwell_at_destination, no_flame_avoiding_route
 * (window_fire_detour, other_shelters_flame_blocked; no_flame_avoiding_route_fits_window for
 * model_no_route), window (window_fire_free; no_route_even_without_fire for model_no_route),
 * no_later_offset, all_exits_blocked (several exits, one exit, a shared label, entry_point_in_flame),
 * unresolved_next, other, and an unknown code. The real files are not part of this branch.
 */
import type { ExplanationFile, LastMileInput, LmCell } from '../../planner/src/features/lastmile/types';

export const SYN_INPUT_TIME = '2025-03-24T09:00:00Z'; // 18:00 KST
export const SYN_SET = 'ffb1:20250324T090000Z:synthetic0000';
export const SYN_REGION = 'synthetic_region';

const OFFSETS = [0, 600, 1200, 1800, 2400, 3000];

export function cells(verdicts: (LmCell['verdict'] | { v: LmCell['verdict']; attempts: LmCell['attempts'] })[]): LmCell[] {
  return verdicts.map((x, i) => {
    const offsetS = OFFSETS[i]!;
    if (typeof x === 'object') return { offsetS, verdict: x.v, attempts: x.attempts };
    const v = x;
    const attempts =
      v === 'window_closed'
        ? []
        : v === 'checked_route'
          ? [
              { destinationId: 'syn:dest:a', verdict: 'checked_route' as const, arrivalS: offsetS + 1500 },
              { destinationId: 'syn:dest:b', verdict: 'model_no_route' as const, arrivalS: null },
            ]
          : [
              { destinationId: 'syn:dest:a', verdict: v, arrivalS: null },
              { destinationId: 'syn:dest:b', verdict: v, arrivalS: null },
            ];
    return { offsetS, verdict: v, attempts };
  });
}

export function synInput(over: Partial<LastMileInput> & { originId?: string } = {}): LastMileInput {
  const { originId, ...rest } = over;
  const id = originId ?? 'syn:origin:checked';
  const base: LastMileInput = {
    region: { id: SYN_REGION, name: { ko: '합성 지역', en: 'Synthetic region' }, fireYear: 2025 },
    fireInputLabel: { ko: '2025년 실제 산불 기록 기반 시나리오 재현', en: 'Recorded 2025 wildfire · scenario replay' },
    replay: true,
    mock: false,
    testData: false,
    scenario: { scenarioSetId: SYN_SET, inputTimeIso: SYN_INPUT_TIME, horizonS: 3600 },
    origin: {
      id,
      name: { ko: '합성마을', en: 'Hapseong-ri' },
      display: { ko: '합성마을', en: 'Hapseong-ri' },
      category: { ko: '마을', en: 'Village' },
      kind: 'village',
      vulnerable: false,
      entryDistanceM: 120,
      sourceTag: 'place=village',
    },
    plan: {
      bestVerdict: 'checked_route',
      latestSafeDepartureS: 1800,
      contiguousSafeDepartureS: 1800,
      sweep: cells(['checked_route', 'checked_route', 'checked_route', 'checked_route', 'model_no_route', 'model_no_route']),
      note: null,
    },
    destinations: {
      'syn:dest:a': { id: 'syn:dest:a', name: { ko: '합성초등학교', en: 'Hapseong Elementary School' }, display: { ko: '합성초등학교', en: 'Hapseong Elementary School' }, category: { ko: '학교', en: 'School' } },
      'syn:dest:b': { id: 'syn:dest:b', name: null, display: { ko: '이름 없는 마을회관 · node 9', en: 'Unnamed community hall · node 9' }, category: { ko: '마을회관', en: 'Community hall' } },
    },
    urgencyRank: 1,
    provenance: { source: 'cache', cachePath: 'synthetic_region/20250324T090000Z.json', cacheCreatedAtIso: '2026-10-17T22:54:05Z', host: null },
    generatedAtIso: '2026-11-02T05:00:00Z',
  };
  return { ...base, ...rest };
}

export const SYN_NO_ROUTE_ID = 'syn:origin:noroute';
export const SYN_UNRESOLVED_ID = 'syn:origin:unresolved';

/** The same input under another origin id (one id per reason code of the synthetic file). */
export function withId(input: LastMileInput, id: string): LastMileInput {
  return { ...input, origin: { ...input.origin, id } };
}

export function synNoRoute(id = SYN_NO_ROUTE_ID): LastMileInput {
  return synInput({
    originId: id,
    plan: {
      bestVerdict: 'model_no_route',
      latestSafeDepartureS: null,
      contiguousSafeDepartureS: null,
      sweep: cells(['model_no_route', 'model_no_route', 'model_no_route', 'model_no_route', 'model_no_route', 'model_no_route']),
      note: null,
    },
  });
}

export function synUnresolved(): LastMileInput {
  return synInput({
    originId: SYN_UNRESOLVED_ID,
    plan: {
      bestVerdict: 'unresolved',
      latestSafeDepartureS: null,
      contiguousSafeDepartureS: null,
      sweep: cells(['unresolved', 'unresolved', 'model_no_route', 'unresolved', 'unresolved', 'unresolved']),
      note: null,
    },
  });
}

/** Checked at every departure time: T is the last departure time requested (no later offset). */
export function synNoLater(id = 'syn:origin:nolater'): LastMileInput {
  return synInput({
    originId: id,
    plan: {
      bestVerdict: 'checked_route',
      latestSafeDepartureS: 3000,
      contiguousSafeDepartureS: 3000,
      sweep: cells(['checked_route', 'checked_route', 'checked_route', 'checked_route', 'checked_route', 'checked_route']),
      note: null,
    },
  });
}

/** Origin ids of the synthetic file, one per reason code of the real files. */
export const SYN_IDS = {
  flame: 'syn:origin:checked',
  windowFree: 'syn:origin:window',
  windowMixed: 'syn:origin:window-mixed',
  detour: 'syn:origin:detour',
  otherShelters: 'syn:origin:other-shelters',
  dwell: 'syn:origin:dwell',
  unknown: 'syn:origin:unknown-code',
  noLater: 'syn:origin:nolater',
  unresolvedNext: 'syn:origin:unresolved-next',
  exits: SYN_NO_ROUTE_ID,
  exitOne: 'syn:origin:exit-one',
  exitDup: 'syn:origin:exit-dup',
  exitPlace: 'syn:origin:exit-place',
  noRouteWindow: 'syn:origin:noroute-window',
  noRouteTime: 'syn:origin:noroute-time',
  entryInFlame: 'syn:origin:entry-in-flame',
  unresolved: SYN_UNRESOLVED_ID,
} as const;

const item = (over: Record<string, unknown> = {}) => ({
  edge_id: 'w100:s1:f',
  osm_way_id: 100,
  label_ko: '합성로',
  label_en: 'Hapseong-ro',
  label_source: 'osm_name',
  place_osm_id: null,
  place_kind: null,
  place_distance_m: null,
  place_is_origin: false,
  near_node_id: 'osm:1',
  point: [128.5, 36.4],
  flame_time_s: 2700, // 18:45 KST
  contact_time_s: 2950,
  members: [0, 2],
  members_total: 4,
  pass_time_at_deadline_s: 2100,
  slack_s: 600,
  segment: 'edge',
  leg_index: 3,
  destination_ids: ['syn:dest:a'],
  rules: { closed_footprint: true, router_cells: true },
  ...over,
});

/** An exit item (no deadline fields, `reached_at_s`, no binding-only fields). */
const exit = (over: Record<string, unknown> = {}) => {
  const it: Record<string, unknown> = item({ pass_time_at_deadline_s: null, slack_s: null, reached_at_s: 60, ...over });
  delete it.destination_ids;
  delete it.leg_index;
  delete it.rules;
  return it;
};

const deadlineRoute = { route_check_job_id: 'rc_synthetic', destination_id: 'syn:dest:a', departure_s: 1800, arrival_s: 3300, dwell_s: 120, route_sha256: 'synthetic', raw_status: 'CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN' };
const windowFacts = (over: Record<string, unknown> = {}) => ({ close_s: 3600, dwell_s: 120, fire_free: true, fastest_end_s: 4020, flame_avoiding_arrival_s: null, limit: 'scenario_window', horizon_s: 3600, ...over });

const leaveByEntry = (over: Record<string, unknown>) => ({
  status: 'explained',
  verdict_summary: 'checked_route',
  deadline_offset_s: 1800,
  next_offset_s: 2400,
  next_verdict: 'model_no_route',
  binding: [],
  exits: [],
  notes: [],
  origin_kind: 'dispatch',
  deadline_route: deadlineRoute,
  checked_at_deadline: 1,
  proven_unreachable_next: 1,
  next_attempts: { model_no_route: 2 },
  checks: { a_route: true, c: true, kit_a_route: true },
  ...over,
});

const noRouteEntry = (over: Record<string, unknown>) => ({
  status: 'explained',
  verdict_summary: 'model_no_route',
  deadline_offset_s: null,
  next_offset_s: null,
  next_verdict: null,
  binding: [],
  exits: [],
  notes: [],
  origin_kind: 'dispatch',
  first_offset_s: 0,
  reachable_nodes: 38,
  checks: { c: true, e: true },
  ...over,
});

/** A `wfg.explanation/1` file for the synthetic region (contract field by field). */
export function synExplanation(): ExplanationFile {
  return {
    schema: 'wfg.explanation/1',
    region_id: SYN_REGION,
    input_time: SYN_INPUT_TIME,
    scenario_set_id: SYN_SET,
    provenance: { cache_sha256: 'synthetic', packet_hashes: { 'HAZARD.json': 'synthetic' }, code_commit: 'synthetic', horizon_s: 3600 },
    summary: { origins: 18, explained: 13, explained_partial: 2, not_explainable: 2 },
    origins: {
      [SYN_IDS.flame]: leaveByEntry({
        reason_code: 'flame_on_route',
        detail_code: 'route_meets_flame_when_shifted',
        deadline_cause: 'flames',
        binding: [item()],
        destination_classes: { 'syn:dest:a': 'flame_on_route' },
        window: windowFacts({ fire_free: false, fastest_end_s: 3500 }),
      }),
      [SYN_IDS.windowFree]: leaveByEntry({
        reason_code: 'window',
        detail_code: 'window_fire_free',
        deadline_cause: 'time_window',
        destination_classes: { 'syn:dest:a': 'window_fire_free' },
        shelters_next: [{ destination_id: 'syn:dest:a', checked_at_deadline: true, tried_next: true, class: 'window_fire_free', proven: true, close_s: 3600, dwell_s: 120, fire_free_fits: false, fire_free_end_s: 4020, flame_avoiding_arrival_s: null }],
        window: windowFacts(),
        checks: { a_route: true, c: true, w: true, kit_a_route: true },
      }),
      // window with the cause not established (explained_partial): no "not a fire" claim
      [SYN_IDS.windowMixed]: leaveByEntry({
        status: 'explained_partial',
        reason_code: 'window',
        detail_code: 'window_fire_free',
        deadline_cause: null,
        destination_classes: { 'syn:dest:a': 'window_fire_free', 'syn:dest:c': 'flame_on_route' },
        checked_at_deadline: 2,
        proven_unreachable_next: 2,
        window: windowFacts(),
      }),
      [SYN_IDS.detour]: leaveByEntry({
        reason_code: 'no_flame_avoiding_route',
        detail_code: 'window_fire_detour',
        deadline_cause: 'flames',
        destination_classes: { 'syn:dest:a': 'window_fire_detour' },
        window: windowFacts({ fire_free: false, fastest_end_s: 3450 }),
      }),
      // the shown shelter is out of reach even without fire, the others are blocked by the flames
      [SYN_IDS.otherShelters]: leaveByEntry({
        reason_code: 'no_flame_avoiding_route',
        detail_code: 'other_shelters_flame_blocked',
        deadline_cause: 'flames',
        destination_classes: { 'syn:dest:a': 'window_fire_free', 'syn:dest:c': 'window_fire_detour' },
        checked_at_deadline: 2,
        proven_unreachable_next: 2,
        window: windowFacts(),
      }),
      [SYN_IDS.dwell]: leaveByEntry({
        status: 'explained_partial',
        reason_code: 'dwell_at_destination',
        detail_code: 'stay_meets_flame',
        deadline_cause: 'flames',
        binding: [item({ edge_id: 'dwell:syn:dest:a', segment: 'dwell', label_ko: '합성리', label_en: 'Hapseong-ri', label_source: 'nearest_place', place_kind: 'village', place_distance_m: 1240, flame_time_s: 3400, pass_time_at_deadline_s: 3300, slack_s: 100 })],
        window: windowFacts({ fire_free: false }),
      }),
      [SYN_IDS.unknown]: leaveByEntry({ reason_code: 'brand_new_reason', detail_code: 'brand_new_detail', deadline_cause: 'flames' }),
      [SYN_IDS.noLater]: leaveByEntry({
        deadline_offset_s: 3000,
        next_offset_s: null,
        next_verdict: null,
        reason_code: 'no_later_offset',
        detail_code: 'last_checked_offset',
        deadline_route: { ...deadlineRoute, departure_s: 3000, arrival_s: 3300 },
        window: windowFacts({ fire_free: null, fastest_end_s: null }),
        checked_at_deadline: undefined,
        proven_unreachable_next: undefined,
        next_attempts: undefined,
      }),
      [SYN_IDS.unresolvedNext]: leaveByEntry({
        status: 'not_explainable',
        next_verdict: 'unresolved',
        reason_code: 'unresolved_next',
        detail_code: 'next_offset_unresolved',
        next_attempt_verdicts: { 'unresolved/AT_ISSUE_FAILURE': 2 },
      }),
      [SYN_IDS.exits]: noRouteEntry({
        reason_code: 'all_exits_blocked',
        detail_code: 'flame_free_area_closed',
        exits: [
          exit({ edge_id: 'w200:s1:f', label_ko: '합성로', label_en: 'Hapseong-ro', flame_time_s: 900, members: [0, 1, 2] }),
          exit({ edge_id: 'w201:s1:f', label_ko: '7', label_en: '7', label_source: 'osm_ref', flame_time_s: 1500, members: [3] }),
          exit({ edge_id: 'w202:s1:r', label_ko: null, label_en: null, label_source: 'unnamed', flame_time_s: 2400, members: [0, 1] }),
        ],
      }),
      [SYN_IDS.exitOne]: noRouteEntry({
        reason_code: 'all_exits_blocked',
        detail_code: 'flame_free_area_closed',
        deadline_cause: 'flames',
        // the place is the origin itself: "a road about 800 m from this village"
        exits: [exit({ edge_id: 'w300:s2:f', label_ko: '합성리', label_en: 'Hapseong-ri', label_source: 'nearest_place', place_osm_id: 'node/1', place_kind: 'village', place_is_origin: true, place_distance_m: 797, flame_time_s: 0, members: [0, 1, 2, 3] })],
      }),
      [SYN_IDS.exitDup]: noRouteEntry({
        reason_code: 'all_exits_blocked',
        detail_code: 'flame_free_area_closed',
        deadline_cause: 'flames',
        exits: [
          exit({ edge_id: 'w400:s1:f', label_ko: '옆마을', label_en: 'Yeop-ri', label_source: 'nearest_place', place_kind: 'hamlet', place_distance_m: 780, flame_time_s: 0, members: [0, 1, 2, 3] }),
          exit({ edge_id: 'w401:s5:r', label_ko: '옆마을', label_en: 'Yeop-ri', label_source: 'nearest_place', place_kind: 'hamlet', place_distance_m: 820, flame_time_s: 0, members: [0, 1, 2, 3] }),
        ],
      }),
      // two exits near the same place at different distances: one merged label
      [SYN_IDS.exitPlace]: noRouteEntry({
        reason_code: 'all_exits_blocked',
        detail_code: 'flame_free_area_closed',
        deadline_cause: 'flames',
        exits: [
          exit({ edge_id: 'w500:s1:f', label_ko: '합성리', label_en: 'Hapseong-ri', label_source: 'nearest_place', place_kind: 'village', place_is_origin: true, place_distance_m: 702, flame_time_s: 0, members: [0, 1, 2, 3] }),
          exit({ edge_id: 'w501:s2:r', label_ko: '합성리', label_en: 'Hapseong-ri', label_source: 'nearest_place', place_kind: 'village', place_is_origin: true, place_distance_m: 1488, flame_time_s: 0, members: [0, 1, 2, 3] }),
        ],
      }),
      [SYN_IDS.entryInFlame]: noRouteEntry({ reason_code: 'all_exits_blocked', detail_code: 'entry_point_in_flame', deadline_cause: 'flames', exits: [] }),
      [SYN_IDS.noRouteTime]: noRouteEntry({ reason_code: 'window', detail_code: 'no_route_even_without_fire', deadline_cause: 'time_window', window: windowFacts({ fastest_end_s: null }) }),
      [SYN_IDS.noRouteWindow]: noRouteEntry({
        reason_code: 'no_flame_avoiding_route',
        detail_code: 'no_flame_avoiding_route_fits_window',
        deadline_cause: 'flames',
        notes: ['recheck_replaced_attempts'],
        window: windowFacts({ fire_free: false, fastest_end_s: null }),
        checks: { e: true },
      }),
      [SYN_IDS.unresolved]: {
        status: 'not_explainable',
        verdict_summary: 'unresolved',
        deadline_offset_s: null,
        next_offset_s: null,
        next_verdict: null,
        reason_code: 'other',
        detail_code: 'origin_unresolved',
        binding: [],
        exits: [],
        notes: [],
        origin_kind: 'dispatch',
        attempt_verdicts: { 'unresolved/AT_ISSUE_FAILURE': 12 },
        checks: {},
      },
    } as unknown as ExplanationFile['origins'],
  };
}

/** Same file with one origin entry replaced (contract-shaped object, possibly invalid on purpose). */
export function withEntry(id: string, entry: Record<string, unknown>): ExplanationFile {
  const f = synExplanation();
  return { ...f, origins: { ...f.origins, [id]: entry as never } };
}

export const ITEM = item;
export const EXIT = exit;
