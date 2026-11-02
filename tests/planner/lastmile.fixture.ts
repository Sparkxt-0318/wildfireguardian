/**
 * SYNTHETIC test data for the last-mile kit (planner/src/features/lastmile). Every name here is
 * "합성 …" / "Synthetic …", the region is not a real region and every number is made up for the
 * tests — none of it is a village, shelter, road, fire or result of any recorded scenario.
 *
 * SYNTHETIC_EXPLANATION follows the deadline-explanation contract `wfg.explanation/1`
 * (planner/public/data/explanations/<region_id>__<input>.json, written by tools/explain_deadlines)
 * field by field, so the reader is tested against the contract before the real files exist.
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
    provenance: { cacheCreatedAtIso: '2026-10-17T22:54:05Z', source: 'cache' },
    generatedAtIso: '2026-11-02T05:00:00Z',
  };
  return { ...base, ...rest };
}

export const SYN_NO_ROUTE_ID = 'syn:origin:noroute';
export const SYN_UNRESOLVED_ID = 'syn:origin:unresolved';

export function synNoRoute(): LastMileInput {
  return synInput({
    originId: SYN_NO_ROUTE_ID,
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

const item = (over: Record<string, unknown> = {}) => ({
  edge_id: 'w100:s1:f',
  label_ko: '합성로',
  label_en: 'Hapseong-ro',
  label_source: 'osm_name',
  flame_time_s: 2700, // 18:45 KST
  members: [0, 2],
  members_total: 4,
  pass_time_at_deadline_s: 2100,
  slack_s: 600,
  ...over,
});

/** A `wfg.explanation/1` file for the synthetic region (contract field by field). */
export function synExplanation(): ExplanationFile {
  return {
    schema: 'wfg.explanation/1',
    region_id: SYN_REGION,
    input_time: SYN_INPUT_TIME,
    scenario_set_id: SYN_SET,
    provenance: { cache_sha256: 'synthetic', packet_hashes: { hazard: 'synthetic' }, code_commit: 'synthetic' },
    summary: { explained: 2, explained_partial: 0, not_explainable: 1 },
    origins: {
      'syn:origin:checked': {
        status: 'explained',
        verdict_summary: 'checked_route',
        deadline_offset_s: 1800,
        next_offset_s: 2400,
        next_verdict: 'model_no_route',
        reason_code: 'flame_on_route',
        binding: [item() as never],
        exits: [],
        notes: [],
      },
      [SYN_NO_ROUTE_ID]: {
        status: 'explained',
        verdict_summary: 'model_no_route',
        deadline_offset_s: null,
        next_offset_s: null,
        next_verdict: null,
        reason_code: 'all_exits_blocked',
        binding: [],
        exits: [
          item({ edge_id: 'w200:s1:f', label_ko: '합성로', label_en: 'Hapseong-ro', flame_time_s: 900, members: [0, 1, 2], pass_time_at_deadline_s: null, slack_s: null }) as never,
          item({ edge_id: 'w201:s1:f', label_ko: '7', label_en: '7', label_source: 'osm_ref', flame_time_s: 1500, members: [3], pass_time_at_deadline_s: null, slack_s: null }) as never,
          item({ edge_id: 'w202:s1:r', label_ko: null, label_en: null, label_source: 'unnamed', flame_time_s: 2400, members: [0, 1], pass_time_at_deadline_s: null, slack_s: null }) as never,
        ],
        notes: [],
      },
      [SYN_UNRESOLVED_ID]: {
        status: 'not_explainable',
        verdict_summary: 'unresolved',
        deadline_offset_s: null,
        next_offset_s: null,
        next_verdict: null,
        reason_code: 'other',
        binding: [],
        exits: [],
        notes: ['synthetic: unresolved origins are never explained'],
      },
    },
  };
}

/** Same file with one origin entry replaced (contract-shaped object, possibly invalid on purpose). */
export function withEntry(id: string, entry: Record<string, unknown>): ExplanationFile {
  const f = synExplanation();
  return { ...f, origins: { ...f.origins, [id]: entry as never } };
}

export const ITEM = item;
