/**
 * "왜 이 시각인가요? / Why this time?" (planner/src/features/explain). The synthetic records here are invented test
 * data ("합성" places, round times) — not results of any region. The last block reads the committed explanation files
 * (planner/public/data/explanations) and renders every origin in both languages.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { computedOnText, explainView, hostText, matchesShown, onEvaluatedHost, sheetNoteText, slackText, whereText } from '../../planner/src/features/explain/text';
import { COMPUTED_MARK, EXPLAIN } from '../../planner/src/features/explain/strings';
import { kstClock } from '../../planner/src/domain/clock';
import { clearExplanationCache, explanationUrl, loadExplanationFile, parseExplanationFile } from '../../planner/src/features/explain/load';
import type { ExplFile, ExplItem, ExplOrigin, ExplShelter, ShownPlan } from '../../planner/src/features/explain/types';
import { cacheToModel, parseCacheIndex } from '../../planner/src/api/cache';
import type { WireCacheFile } from '../../planner/src/api/wire';

const INPUT = '2025-01-01T00:00:00Z'; // 09:00 KST

function item(over: Partial<ExplItem> = {}): ExplItem {
  return {
    edge_id: 'synthetic:e1',
    label_ko: '합성마을',
    label_en: 'Hapseong-ri',
    label_source: 'nearest_place',
    place_distance_m: 1200,
    near_node_id: 'synthetic:n1',
    flame_time_s: 2205.7,
    contact_time_s: 2516.7,
    members: [1],
    members_total: 4,
    pass_time_at_deadline_s: 1918,
    slack_s: 287.7,
    segment: 'edge',
    ...over,
  };
}

function origin(over: Partial<ExplOrigin> = {}): ExplOrigin {
  return {
    status: 'explained',
    verdict_summary: 'checked_route',
    deadline_offset_s: 1800,
    next_offset_s: 2400,
    next_verdict: 'model_no_route',
    reason_code: 'flame_on_route',
    binding: [item()],
    exits: [],
    notes: [],
    detail_code: 'route_meets_flame_when_shifted',
    window: { close_s: 3600, dwell_s: 120, fire_free: false, fastest_end_s: 3312, flame_avoiding_arrival_s: null, limit: 'scenario_window', horizon_s: 3600 },
    deadline_route: { route_check_job_id: 'rc_synthetic', destination_id: 'synthetic:shelter', dwell_s: 120 },
    checked_at_deadline: 1,
    proven_unreachable_next: 1,
    checks: { a: true, b: true, c: true },
    ...over,
  };
}

function file(origins: Record<string, ExplOrigin>): ExplFile {
  return {
    schema: 'wfg.explanation/1',
    region_id: 'synthetic_region',
    input_time: INPUT,
    scenario_set_id: 'synthetic:set',
    provenance: { cache_sha256: 'a'.repeat(64), packet_hashes: { 'HAZARD.json': 'b'.repeat(64) }, code_commit: 'c'.repeat(40), horizon_s: 3600, members: ['s:0', 's:1', 's:2', 's:3'] },
    summary: { origins: Object.keys(origins).length, explained: 0, explained_partial: 0, not_explainable: 0, by_reason: {} },
    origins,
  };
}

const SHOWN: ShownPlan = { bestVerdict: 'checked_route', deadlineS: 1800, bestDestinationId: 'synthetic:shelter', bestJobId: 'rc_synthetic' };

function view(rec: ExplOrigin, lang: 'ko' | 'en' = 'ko', shown: ShownPlan | null = SHOWN) {
  return explainView({ state: 'ready', file: file({ o: rec }), originId: 'o', inputTime: INPUT, lang, shown });
}

const FW = { close_s: 3600, dwell_s: 120, fire_free: true, fastest_end_s: 3895, flame_avoiding_arrival_s: null, limit: 'scenario_window' as const, horizon_s: 3600 };

function shelter(id: string, over: Partial<ExplShelter> = {}): ExplShelter {
  return { destination_id: id, checked_at_deadline: true, tried_next: true, class: 'window_fire_free', proven: true, close_s: 3600, dwell_s: 120,
    fire_free_fits: false, fire_free_end_s: 3895, flame_avoiding_arrival_s: null, ...over };
}

function noRouteOrigin(over: Partial<ExplOrigin> = {}): ExplOrigin {
  return origin({ verdict_summary: 'model_no_route', deadline_offset_s: null, next_offset_s: null, next_verdict: null, binding: [], deadline_route: null, ...over });
}
const NO_ROUTE: ShownPlan = { bestVerdict: 'model_no_route', deadlineS: null };

describe('explanation text (structured fields only)', () => {
  it('flame on the shown route: place, clock times, k of 4 and the margin as a lower bound', () => {
    const ko = view(origin());
    expect(ko.kind).toBe('explained');
    expect(ko.title).toBe('왜 이 시각인가요?');
    expect(ko.lines).toEqual([
      '09:40에 출발해 09:30에 확인된 같은 경로로 가면 합성마을에서 약 1.2 km 떨어진 도로에서 09:41에 시나리오상 화염과 만납니다(화재 시나리오 4개 중 1개).*',
      '출발 마감 09:30에 출발하면 차량은 09:31에 그 375 m 격자 칸을 벗어납니다.* 그 시나리오에서 이 칸이 타기 시작하는 09:36보다 4분 이상 이릅니다.*',
      '09:40에 출발하면 시나리오상 화염을 피하는 도로로는 그 대피소에 10:00까지 도착해 2분 체류를 마칠 수 없습니다.*',
    ]);
    expect(ko.dots).toEqual({ members: [1], total: 4, text: '화재 시나리오 4개 중 1개' });
    expect(ko.basis).toBe('예측에서 나온 화재 시나리오 4개를 기준으로 한 결과이며, 관측이 아닙니다.');
    expect(ko.statusLabel).toBe('설명됨(기록된 점검 재현)');
    expect(ko.computedNote).toBe('* 기록된 점검이 아니라 이 설명을 위해 도로망과 화재 시나리오로 계산한 값입니다.');
    const en = view(origin(), 'en');
    expect(en.title).toBe('Why this time?');
    expect(en.lines).toEqual([
      'Leaving at 09:40 on the same route that was checked for 09:30, the vehicle would meet flames on a road about 1.2 km from Hapseong-ri at 09:41 (1 of 4 fire scenarios).*',
      'Leaving at the leave-by time 09:30, the vehicle clears that 375 m grid cell at 09:31, at least 4 min before that cell starts burning in that scenario (09:36).*',
      'Leaving at 09:40, no road route that avoids the flames in the fire scenarios reaches that shelter by 10:00 (including the 2-minute stay).*',
    ]);
    expect(en.basis).toBe('Based on 4 fire scenarios from the forecast; not an observation.');
    expect(en.statusLabel).toBe('Explained (replay of recorded checks)');
    expect(en.computedNote).toBe('* Computed for this explanation from the road graph and the fire scenarios, not a recorded check.');
    // without a proof for every shelter checked at the deadline, no unreachability sentence
    expect(view(origin({ status: 'explained_partial', checked_at_deadline: 2, proven_unreachable_next: 1 })).lines.length).toBe(2);
  });

  it('several members, another cell, the same minute and several shelters', () => {
    const b = item({ members: [0, 2], contact_cell: 5, slack_cell: 6, pass_time_at_deadline_s: 1925, flame_time_s: 1950, slack_s: 25 });
    const en = view(origin({ binding: [b], checked_at_deadline: 3, proven_unreachable_next: 3,
      shelters_next: [shelter('synthetic:shelter', { class: 'flame_on_route', fire_free_fits: true, fire_free_end_s: 2600 }), shelter('b'), shelter('c')] }), 'en');
    expect(en.lines[1]).toBe('Leaving at the leave-by time 09:30, the vehicle clears a 375 m grid cell on that road at 09:32:05, under 1 min before that cell starts burning in one of those scenarios (09:32:30).*');
    expect(en.lines[2]).toBe('Leaving at 09:40, no road route that avoids the flames in the fire scenarios reaches any of the 3 shelters with a checked route at 09:30 by 10:00 (including the 2-minute stay).*');
    expect(en.dots?.text).toBe('2 of 4 fire scenarios');
  });

  it('slack is rounded down; places are named with a straight-line distance, the origin itself as this village', () => {
    expect(slackText(287.7, 'ko')).toBe('4분 이상');
    expect(slackText(60, 'en')).toBe('at least 1 min');
    expect(slackText(59.9, 'en')).toBe('under 1 min');
    expect(whereText(item({ label_source: 'unnamed', label_ko: null, label_en: null }), 'ko')).toBe('이름 없는 도로(도로 노드 synthetic:n1)');
    expect(whereText(item({ label_en: null }), 'en')).toBe('a road about 1.2 km from 합성마을'); // never transliterated
    expect(whereText(item({ place_is_origin: true, place_kind: 'village' }), 'en')).toBe('a road about 1.2 km from Hapseong-ri (this village)');
    expect(whereText(item({ place_is_origin: true, place_kind: 'village' }), 'ko')).toBe('이 마을(합성마을)에서 약 1.2 km 떨어진 도로');
    expect(whereText(item({ place_is_origin: true, place_kind: 'town' }), 'en')).toBe('a road about 1.2 km from Hapseong-ri (this place)');
  });

  it('time window: the range conclusion only when no shelter considered would be reached even without fire', () => {
    const one = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: FW, deadline_cause: 'time_window',
      shelters_next: [shelter('synthetic:shelter')] }));
    expect(one.lines).toEqual([
      '09:40에 출발하면 화재가 없더라도 가장 빠른 도로로 대피소에 도착해 2분 머무는 일이 10:04에야 끝나, 기록된 화재 시나리오가 끝나는 10:00를 넘습니다.*',
      '다음 점검 출발 시각인 09:40에 출발하면 이 대피소는 1시간 시나리오 범위를 벗어나므로, 이 출발 마감은 예측 화염이 아니라 시나리오 범위로 정해진 것입니다.*',
    ]);
    expect(one.dots).toBeNull();
    expect(view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: FW, deadline_cause: 'time_window',
      shelters_next: [shelter('synthetic:shelter')] }), 'en').lines[1]).toBe(
      'At the next checked departure, 09:40, the trip to this shelter falls outside the one-hour scenario range, so this leave-by time is set by that range, not by predicted flames.*',
    );
    const three = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: FW, deadline_cause: 'time_window',
      checked_at_deadline: 1, proven_unreachable_next: 1, shelters_next: [shelter('synthetic:shelter'), shelter('b', { checked_at_deadline: false }), shelter('c', { checked_at_deadline: false })] }), 'en');
    expect(three.lines.slice(1)).toEqual([
      'Even ignoring the fire, none of the other 2 candidate shelters can be reached by 10:00 (including the 2-minute stay) either.*',
      'At the next checked departure, 09:40, the trip to every one of these shelters falls outside the one-hour scenario range, so this leave-by time is set by that range, not by predicted flames.*',
    ]);
    expect(view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: FW, deadline_cause: 'time_window',
      checked_at_deadline: 1, proven_unreachable_next: 1, shelters_next: [shelter('synthetic:shelter'), shelter('b', { checked_at_deadline: false })] }), 'ko').lines.slice(1)).toEqual([
      '화재가 없더라도 나머지 후보 대피소 1곳에도 10:00까지 도착해 2분 체류를 마칠 수 없습니다.*',
      '다음 점검 출발 시각인 09:40에 출발하면 이 대피소들은 모두 1시간 시나리오 범위를 벗어나므로, 이 출발 마감은 예측 화염이 아니라 시나리오 범위로 정해진 것입니다.*',
    ]);
    // cause not established (a shelter would fit without fire, unproven): no conclusion, no claim about the others
    const open = view(origin({ status: 'explained_partial', reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: FW, deadline_cause: null,
      shelters_next: [shelter('synthetic:shelter'), shelter('b', { class: 'open', proven: false, fire_free_fits: true, fire_free_end_s: 3300 })] }), 'en');
    expect(open.lines.length).toBe(1);
  });

  it('B2: a fire-free end in the same minute as the scenario end is shown with seconds', () => {
    const v = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: { ...FW, fastest_end_s: 3616 }, deadline_cause: 'time_window',
      shelters_next: [shelter('synthetic:shelter', { fire_free_end_s: 3616 })] }), 'en');
    expect(v.lines[0]).toBe('Leaving at 09:40, even the fastest road route, ignoring the fire, would finish the 2-minute stay at the shelter only at 10:00:16, after the recorded fire scenarios end at 10:00:00.*');
    const arr = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', deadline_cause: 'time_window',
      window: { close_s: 3000, dwell_s: 120, fire_free: true, fastest_end_s: 3030, flame_avoiding_arrival_s: null, limit: 'arrival_window', horizon_s: 3600 },
      shelters_next: [shelter('synthetic:shelter', { close_s: 3000, fire_free_end_s: 3030 })] }), 'en');
    expect(arr.lines[0]).toContain("only at 09:50:30, after this recorded mission's arrival window closes at 09:50:00.*");
    expect(arr.lines[1]).toBe("At the next checked departure, 09:40, the trip to this shelter falls outside this recorded mission's arrival window, so this leave-by time is set by that window, not by predicted flames.*");
  });

  it('B1: shown shelter out of the range, the others only blocked by the flames', () => {
    const rec = origin({ reason_code: 'no_flame_avoiding_route', binding: [], detail_code: 'other_shelters_flame_blocked', window: { ...FW, fastest_end_s: 3851 },
      deadline_cause: 'flames', checked_at_deadline: 3, proven_unreachable_next: 3,
      shelters_next: [shelter('synthetic:shelter', { fire_free_end_s: 3851 }), shelter('b', { class: 'window_fire_detour', fire_free_fits: true, fire_free_end_s: 3563 }),
        shelter('c', { class: 'window_fire_detour', fire_free_fits: true, fire_free_end_s: 3552 })] });
    expect(view(rec, 'en').lines).toEqual([
      "Leaving at 09:40, the shown route's shelter is beyond the one-hour scenario range even without fire (the stay would end at 10:04); the other 2 shelters, which a fire-free road would still reach in time, cannot be reached on any road that avoids the flames in the fire scenarios.* So this leave-by time comes from the flames in the fire scenarios.*",
    ]);
    expect(view(rec, 'ko').lines).toEqual([
      '09:40에 출발하면 표시된 경로의 대피소는 화재가 없어도 1시간 시나리오 범위 안에 체류를 마칠 수 없고(10:04), 화재가 없다면 제때 갈 수 있는 나머지 대피소 2곳은 시나리오상 화염을 피하는 도로로 갈 수 없습니다.* 따라서 이 출발 마감은 시나리오상 화염 때문입니다.*',
    ]);
    // S1: one other shelter out of the range as well, one (refused at the deadline too) blocked by the flames
    const s1 = origin({ ...rec, shelters_next: [shelter('synthetic:shelter', { fire_free_end_s: 3851 }), shelter('b', { fire_free_end_s: 3760 }),
      shelter('c', { checked_at_deadline: false, class: 'flame_blocked', fire_free_fits: true, fire_free_end_s: 3490 })] });
    expect(view(s1, 'en').lines[0]).toContain('; another shelter, which a fire-free road would still reach in time, cannot be reached on any road that avoids the flames in the fire scenarios.* The remaining shelter cannot be reached in time even without fire.* So this leave-by time');
    expect(view(s1, 'ko').lines[0]).toBe('09:40에 출발하면 표시된 경로의 대피소는 화재가 없어도 1시간 시나리오 범위 안에 체류를 마칠 수 없고(10:04), 화재가 없다면 제때 갈 수 있는 다른 대피소 1곳은 시나리오상 화염을 피하는 도로로 갈 수 없습니다.* 나머지 대피소 1곳은 화재가 없어도 제때 갈 수 없습니다.* 따라서 이 출발 마감은 시나리오상 화염 때문입니다.*');
  });

  it('flame-forced detour and a no-route origin', () => {
    const detour = view(origin({ reason_code: 'no_flame_avoiding_route', binding: [], detail_code: 'window_fire_detour', deadline_cause: 'flames', checked_at_deadline: 3, proven_unreachable_next: 3,
      window: { close_s: 3600, dwell_s: 120, fire_free: false, fastest_end_s: 3312, flame_avoiding_arrival_s: null, limit: 'scenario_window', horizon_s: 3600 } }), 'en');
    expect(detour.lines[0]).toBe('Leaving at 09:40, no road route that avoids the flames in the fire scenarios reaches the shelter in time to finish the 2-minute stay by 10:00 (no flame-avoiding arrival at all by 10:00, when the scenarios end).* Without fire the fastest road would finish the stay at 09:55.* So this leave-by time comes from the flames in the fire scenarios.*');
    expect(detour.lines[1]).toBe('Leaving at 09:40, no road route that avoids the flames in the fire scenarios reaches any of the 3 shelters with a checked route at 09:30 by 10:00 (including the 2-minute stay).*');
    // N5: without an established cause the whole-origin conclusion is not stated
    expect(view(origin({ reason_code: 'no_flame_avoiding_route', binding: [], detail_code: 'window_fire_detour', deadline_cause: null,
      window: { close_s: 3600, dwell_s: 120, fire_free: false, fastest_end_s: 3312, flame_avoiding_arrival_s: 3579, limit: 'scenario_window', horizon_s: 3600 } }), 'ko').lines[0])
      .toBe('09:40에 출발하면 시나리오상 화염을 피하는 도로로는 10:00까지 대피소에 도착해 2분 체류를 마칠 수 없습니다(화염을 피하면 09:59 전에는 도착할 수 없음).* 화재가 없다면 가장 빠른 도로로 09:55에 체류를 마칠 수 있습니다.*');
    const nr = view(noRouteOrigin({ reason_code: 'no_flame_avoiding_route', detail_code: 'no_flame_avoiding_route_fits_window', deadline_cause: 'flames' }), 'en', NO_ROUTE);
    expect(nr.title).toBe('Why is there no checked route?');
    expect(nr.lines[0]).toContain('(including the 2-minute stay).* A fire-free road would reach at least one of them in time, so this comes from the flames in the fire scenarios.*');
    const ff = view(noRouteOrigin({ reason_code: 'window', detail_code: 'no_route_even_without_fire', deadline_cause: 'time_window' }), 'ko', NO_ROUTE);
    expect(ff.lines[0]).toBe('점검한 어느 출발 시각에도 화재가 없더라도 후보 대피소에 10:00까지 도착해 2분 체류를 마칠 수 있는 도로가 없으므로, 이는 예측 화염이 아니라 시간 범위 때문입니다.*');
  });

  it('last checked offset and unresolved next time are stated plainly', () => {
    const last = view(origin({ reason_code: 'no_later_offset', binding: [], next_offset_s: null, next_verdict: null, deadline_offset_s: 3000 }), 'ko', { ...SHOWN, deadlineS: 3000 });
    expect(last.lines[0]).toContain('점검한 마지막 출발 시각이 09:50입니다');
    expect(last.lines[0]).toContain('예측 화염으로 정해진 것이 아닙니다');
    const un = view(origin({ status: 'not_explainable', reason_code: 'unresolved_next', binding: [], next_verdict: 'unresolved' }));
    expect(un.kind).toBe('not_explainable');
    expect(un.lines[0]).toContain('다음 출발 시각(09:40)의 점검 결과는 미확인입니다');
    expect(un.dots).toBeNull();
    expect(un.basis).toBeNull();
  });

  it('cut-off origin: both road exits, the same road in both directions, k of 4', () => {
    const rec = noRouteOrigin({ reason_code: 'all_exits_blocked', detail_code: 'flame_free_area_closed',
      exits: [item({ edge_id: 'w123:s80:r', osm_way_id: 123, members: [0, 1, 2, 3], flame_time_s: 0, contact_time_s: 80, pass_time_at_deadline_s: null, slack_s: null }),
              item({ edge_id: 'w123:s87:f', osm_way_id: 123, members: [0, 1, 2, 3], flame_time_s: 0, contact_time_s: 140, pass_time_at_deadline_s: null, slack_s: null, label_ko: '합성리', label_en: null })] });
    const v = view(rec, 'ko', NO_ROUTE);
    expect(v.title).toBe('왜 확인된 경로가 없나요?');
    // every sentence about the computed exits carries the mark, and so does every item of the exit list
    expect(v.lines).toEqual([
      '진입 지점에서 화염과 만나지 않고 갈 수 있는 구역의 도로 출구 2곳이 모두 시나리오상 화염과 만납니다(화재 시나리오 4개 중 4개).*',
      '두 출구는 같은 도로(OSM way 123)의 양쪽 방향입니다.*',
      '이 도로들은 입력 시각(09:00)에 이미 타고 있는 것으로 표시된 칸을 지납니다.*',
    ]);
    expect(v.list).toEqual(['합성마을에서 약 1.2 km 떨어진 도로: 시나리오 4/4*', '합성리에서 약 1.2 km 떨어진 도로: 시나리오 4/4*']);
    expect(v.dots?.members).toEqual([0, 1, 2, 3]);
    expect([v.marked, v.computedNote]).toEqual([true, '* 기록된 점검이 아니라 이 설명을 위해 도로망과 화재 시나리오로 계산한 값입니다.']);
    const en = view(rec, 'en', NO_ROUTE);
    expect(en.lines[0]).toBe('Both road exits from the area that can be reached from the entry point without meeting flames run into flames in the fire scenarios (4 of 4 fire scenarios).*');
    expect(en.lines[1]).toBe('Both are on the same road (OSM way 123), one in each direction.*');
    expect(en.lines[2]).toBe('They cross cells already marked as burning at the input time (09:00).*');
    expect(en.list[0]).toBe('A road about 1.2 km from Hapseong-ri: 4/4 scenarios*');
    // the same road in one direction
    const oneWay = noRouteOrigin({ ...rec, exits: rec.exits.map((e) => ({ ...e, edge_id: e.edge_id!.replace(/:[fr]$/, ':f') })) });
    expect(view(oneWay, 'en', NO_ROUTE).lines[1]).toBe('Both are on the same road (OSM way 123).*');
    expect(view(oneWay, 'ko', NO_ROUTE).lines[1]).toBe('두 출구는 같은 도로(OSM way 123)에 있습니다.*');
  });

  it('a single exit is stated in the singular', () => {
    const rec = noRouteOrigin({ reason_code: 'all_exits_blocked', detail_code: 'flame_free_area_closed',
      exits: [item({ members: [0, 1, 2, 3], flame_time_s: 0, contact_time_s: 80, pass_time_at_deadline_s: null, slack_s: null })] });
    expect(view(rec, 'en', NO_ROUTE).lines).toEqual([
      'The only road leading out of the area that can be reached from the entry point without meeting flames runs into flames in the fire scenarios (4 of 4 fire scenarios).*',
      'It crosses cells already marked as burning at the input time (09:00).*',
    ]);
    expect(view(rec, 'ko', NO_ROUTE).lines).toEqual([
      '진입 지점에서 화염과 만나지 않고 갈 수 있는 구역을 벗어나는 도로는 1개뿐이며, 이 도로가 시나리오상 화염과 만납니다(화재 시나리오 4개 중 4개).*',
      '이 도로는 입력 시각(09:00)에 이미 타고 있는 것으로 표시된 칸을 지납니다.*',
    ]);
    expect(view(rec, 'en', NO_ROUTE).list).toEqual(['A road about 1.2 km from Hapseong-ri: 4/4 scenarios*']);
  });

  it('more than three exits: three listed and the rest counted, every item marked', () => {
    const exits = [0, 1, 2, 3, 4].map((i) => item({ edge_id: `w${100 + i}:s1:f`, osm_way_id: 100 + i, members: [0, 1, 2, 3], flame_time_s: 0, contact_time_s: 80, pass_time_at_deadline_s: null, slack_s: null }));
    const rec = noRouteOrigin({ reason_code: 'all_exits_blocked', detail_code: 'flame_free_area_closed', exits });
    const en = view(rec, 'en', NO_ROUTE);
    expect(en.lines).toEqual([
      'All 5 road exits from the area that can be reached from the entry point without meeting flames run into flames in the fire scenarios (4 of 4 fire scenarios).*',
      'They cross cells already marked as burning at the input time (09:00).*',
    ]);
    expect(en.list).toEqual([...Array(3).fill('A road about 1.2 km from Hapseong-ri: 4/4 scenarios*'), 'and 2 more*']);
    expect(view(rec, 'ko', NO_ROUTE).list[3]).toBe('외 2개*');
  });

  it('C4: an entry point in flames is stated for the first checked departure and at least one scenario only', () => {
    const rec = noRouteOrigin({ reason_code: 'all_exits_blocked', detail_code: 'entry_point_in_flame', first_offset_s: 0 });
    expect(view(rec, 'en', NO_ROUTE).lines).toEqual(['At the first checked departure, 09:00, the entry point itself is already in flames in at least one of the fire scenarios.*']);
    expect(view(rec, 'ko', NO_ROUTE).lines).toEqual(['점검한 첫 출발 시각인 09:00에 진입 지점이 이미 화재 시나리오 중 적어도 하나에서 화염 안에 있습니다.*']);
  });

  it('exits blocked in different members: "at least k", no single set of dots', () => {
    const rec = noRouteOrigin({ reason_code: 'all_exits_blocked', detail_code: 'flame_free_area_closed',
      exits: [item({ members: [0, 2], flame_time_s: 600, contact_time_s: 700, pass_time_at_deadline_s: null, slack_s: null }),
              item({ members: [1, 2, 3], flame_time_s: 900, contact_time_s: 950, pass_time_at_deadline_s: null, slack_s: null })] });
    const v = view(rec, 'en', NO_ROUTE);
    expect(v.lines[0]).toContain('(at least 2 of 4 fire scenarios)');
    expect(v.dots).toBeNull();
    expect(v.list).toEqual(['A road about 1.2 km from Hapseong-ri: 2/4 scenarios*', 'A road about 1.2 km from Hapseong-ri: 3/4 scenarios*']);
    expect(v.lines[1]).toBe('Each is already blocked when the vehicle could first reach it; the last one meets flames by 09:15.*');
  });

  it('refuses an explanation made for another route check; neutral fallbacks', () => {
    expect(matchesShown(origin(), SHOWN)).toBe(true);
    expect(view(origin(), 'ko', { ...SHOWN, deadlineS: 1200 }).kind).toBe('mismatch');
    expect(view(origin(), 'ko', { ...SHOWN, bestJobId: 'rc_live' }).kind).toBe('mismatch');
    expect(view(origin(), 'ko', { ...SHOWN, bestJobId: null }).kind).toBe('mismatch'); // S6: the printed route must be that check
    expect(view(origin(), 'ko', { ...SHOWN, bestVerdict: 'unresolved' }).kind).toBe('mismatch');
    const none = view(origin(), 'en', null); // N6: no result shown is not a difference
    expect([none.kind, none.lines[0]]).toEqual(['no_plan', 'There is no leave-by result for this origin to explain.']);
    expect(explainView({ state: 'absent', file: null, originId: 'o', inputTime: INPUT, lang: 'ko', shown: SHOWN }).lines).toEqual(['이 시나리오에 대한 설명 파일이 없습니다.']);
    expect(explainView({ state: 'ready', file: file({}), originId: 'o', inputTime: INPUT, lang: 'en', shown: SHOWN }).lines).toEqual(['No explanation for this origin.']);
  });
});

describe('recorded vs computed, and claims no wider than the replay', () => {
  /** templates stating a value computed for the explanation (road graph, flame-avoiding search, replay, exits) */
  const COMPUTED = ['windowFireFree', 'windowFireFreeUnreachable', 'windowArrivalFireFree', 'othersFireFreeOne', 'othersFireFree', 'rangeOne', 'rangeMany',
    'arrivalOne', 'limitsMany', 'noRouteFireFree', 'windowDetour', 'mixedFlameAllOne', 'mixedFlameAll', 'mixedFlameSomeOne', 'mixedFlameSome', 'mixedAlsoOutOne',
    'mixedAlsoOut', 'flamesConclusion', 'noRouteFlames', 'cdUnreachable', 'oneUnreachable', 'flame', 'flameSlackOne', 'flameSlackMany', 'dwell', 'exitsOne',
    'exitsTwo', 'exits', 'exitsSameWayBothDirections', 'exitsSameWay', 'exitsPresentOne', 'exitsPresent', 'exitsLatestOne', 'exitsLatest', 'entryInFlame'];
  /** exit-list items (not sentences, no full stop): a computed exit with its place distance and member count, the rest counted */
  const COMPUTED_ITEMS = ['exitItem', 'exitsMore'];
  /** the notes that explain the mark */
  const NOTES = ['computedNote', 'sheetNoteOff', 'sheetNoteOffUnknown', 'sheetNoteOn'];
  const LINUX = { platform: 'Linux-6.18.44-x86_64-with-glibc2.39', system: 'Linux', machine: 'x86_64', python: '3.12.3', numpy: '1.26.4', pyproj: '3.7.0' };

  function withProv(rec: ExplOrigin, prov: Partial<ExplFile['provenance']>): ExplFile {
    const f = file({ o: rec });
    return { ...f, provenance: { ...f.provenance, ...prov } };
  }

  it('exactly the templates resting on a computed value end their sentences with the mark', () => {
    expect(COMPUTED_MARK).toBe('*');
    for (const [key, s] of Object.entries(EXPLAIN)) {
      if (key === 'status') continue;
      for (const lang of ['ko', 'en'] as const) {
        const text = (s as Record<string, string>)[lang]!;
        if (NOTES.includes(key)) expect([key, lang, text.startsWith('* ')]).toEqual([key, lang, true]);
        else if (COMPUTED.includes(key)) {
          expect([key, lang, text.endsWith('.*')]).toEqual([key, lang, true]);
          // every mark follows a full stop: one per sentence, never inside a sentence
          expect([key, lang, [...text.matchAll(/\*/g)].every((m) => text[m.index! - 1] === '.')]).toEqual([key, lang, true]);
        } else if (COMPUTED_ITEMS.includes(key)) {
          // one mark, ending the item
          expect([key, lang, text.endsWith(COMPUTED_MARK), text.split(COMPUTED_MARK).length - 1, text.includes('.')]).toEqual([key, lang, true, 1, false]);
        } else expect([key, lang, text.includes('*')]).toEqual([key, lang, false]);
      }
    }
  });

  it('recorded-only explanations carry no mark; computed ones carry it with the note', () => {
    const last = view(origin({ reason_code: 'no_later_offset', binding: [], next_offset_s: null, next_verdict: null, deadline_offset_s: 3000 }), 'en', { ...SHOWN, deadlineS: 3000 });
    expect([last.marked, last.computedNote, last.sheetNote]).toEqual([false, null, null]);
    expect(last.lines.join(' ')).not.toContain('*');
    const win = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: FW, deadline_cause: 'time_window', shelters_next: [shelter('synthetic:shelter')] }), 'en');
    expect(win.marked).toBe(true);
    expect(win.computedNote).toBe('* Computed for this explanation from the road graph and the fire scenarios, not a recorded check.');
    const un = view(origin({ status: 'not_explainable', reason_code: 'unresolved_next', binding: [], next_verdict: 'unresolved' }), 'en');
    expect([un.marked, un.computedNote, un.host, un.sheetNote]).toEqual([false, null, null, null]);
  });

  it('says where the explanation was computed: never the evaluated host unless the file records it consistently', () => {
    const rec = origin();
    const linux = withProv(rec, { computed_on: LINUX, evaluated_host: false });
    const en = explainView({ state: 'ready', file: linux, originId: 'o', inputTime: INPUT, lang: 'en', shown: SHOWN });
    expect(en.host).toBe('Computed for this explanation on Linux x86_64, not on the evaluated host: the recorded route checks are replayed against the same hazard packet; no new route checks were run.');
    expect(en.sheetNote).toBe('* Computed on Linux x86_64 (not the evaluated host), not a recorded check.');
    const ko = explainView({ state: 'ready', file: linux, originId: 'o', inputTime: INPUT, lang: 'ko', shown: SHOWN });
    expect(ko.host).toBe('이 설명은 평가 호스트가 아닌 Linux x86_64에서 계산했습니다. 기록된 경로 점검을 같은 위험 패킷으로 재현했으며, 새 경로 점검은 하지 않았습니다.');
    expect(ko.sheetNote).toBe('* 평가 호스트가 아닌 Linux x86_64에서 계산한 값이며, 기록된 점검이 아닙니다.');
    // the evaluated host only for evaluated_host true on native macOS arm64
    const mac = { ...LINUX, platform: 'macOS-27.0.1-arm64-arm-64bit', system: 'Darwin', machine: 'arm64' };
    expect(onEvaluatedHost({ computed_on: mac, evaluated_host: true })).toBe(true);
    expect(hostText({ computed_on: mac, evaluated_host: true }, 'en')).toBe('Computed for this explanation on the evaluated host (macOS arm64): the recorded route checks are replayed against the same hazard packet; no new route checks were run.');
    expect(sheetNoteText({ computed_on: mac, evaluated_host: true }, 'ko')).toBe('* 평가 호스트(macOS arm64)에서 계산한 값이며, 기록된 점검이 아닙니다.');
    expect(onEvaluatedHost({ computed_on: mac, evaluated_host: false })).toBe(false);
    expect(onEvaluatedHost({ computed_on: LINUX, evaluated_host: true })).toBe(false); // inconsistent: not claimed
    expect(hostText({ computed_on: LINUX, evaluated_host: true }, 'en')).toContain('on Linux x86_64, not on the evaluated host');
    // no record of the computing host: still never the evaluated host
    expect(computedOnText({})).toBeNull();
    expect(hostText({}, 'en')).toBe('Not computed on the evaluated host: the recorded route checks are replayed against the same hazard packet; no new route checks were run.');
    expect(sheetNoteText({}, 'en')).toBe('* Computed off the evaluated host, not a recorded check.');
    expect(sheetNoteText({ evaluated_host: true }, 'ko')).toBe('* 평가 호스트가 아닌 곳에서 계산한 값이며, 기록된 점검이 아닙니다.');
  });

  it('status labels say replay, and conclusions name the next checked departure only', () => {
    expect(EXPLAIN.status.explained).toEqual({ ko: '설명됨(기록된 점검 재현)', en: 'Explained (replay of recorded checks)' });
    expect(EXPLAIN.status.explained_partial).toEqual({ ko: '부분 설명(기록된 점검 재현)', en: 'Partly explained (replay of recorded checks)' });
    expect(JSON.stringify(EXPLAIN)).not.toMatch(/[Vv]erified explanation|검증된 설명/);
    for (const key of ['rangeOne', 'rangeMany', 'arrivalOne', 'limitsMany'] as const) {
      for (const lang of ['ko', 'en'] as const) {
        const s = EXPLAIN[key][lang];
        expect([key, lang, s.includes('{next}'), /later departure|이보다 늦은 출발/.test(s)]).toEqual([key, lang, true, false]);
      }
    }
  });
});

describe('explanation file loader', () => {
  afterEach(() => {
    clearExplanationCache();
    vi.unstubAllGlobals();
  });

  it('builds a same-origin path under the base URL', () => {
    expect(explanationUrl('synthetic_region', '2025-03-24T09:00:00Z')).toBe('/data/explanations/synthetic_region__20250324T090000Z.json');
  });

  it('accepts only wfg.explanation/1 for this region and input time', () => {
    const f = file({});
    expect(parseExplanationFile(f, 'synthetic_region', INPUT)).not.toBeNull();
    expect(parseExplanationFile({ ...f, schema: 'other/1' }, 'synthetic_region', INPUT)).toBeNull();
    expect(parseExplanationFile(f, 'other_region', INPUT)).toBeNull();
    expect(parseExplanationFile(f, 'synthetic_region', '2025-01-01T01:00:00Z')).toBeNull();
    expect(parseExplanationFile(null, 'synthetic_region', INPUT)).toBeNull();
  });

  it('a missing file or an HTML fallback page resolves to null (fallback), a valid one to the document', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('not found', { status: 404 })));
    expect(await loadExplanationFile('synthetic_region', INPUT)).toBeNull();
    clearExplanationCache();
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<!doctype html>', { status: 200, headers: { 'content-type': 'text/html' } })));
    expect(await loadExplanationFile('synthetic_region', INPUT)).toBeNull();
    clearExplanationCache();
    const f = vi.fn(async () => new Response(JSON.stringify(file({ o: origin() })), { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', f);
    expect((await loadExplanationFile('synthetic_region', INPUT))?.origins.o?.reason_code).toBe('flame_on_route');
    await loadExplanationFile('synthetic_region', INPUT);
    expect(f).toHaveBeenCalledTimes(1); // cached per file
  });
});

// jsdom is loaded with Node's resolver from planner/ (the tests live outside the Vite root).
const { JSDOM } = createRequire(new URL('../../planner/package.json', import.meta.url))('jsdom') as {
  JSDOM: new (html?: string, opts?: Record<string, unknown>) => { window: Window & typeof globalThis };
};

describe('ExplainBlock (jsdom render)', () => {
  interface ReactLike {
    createElement: (type: unknown, props: Record<string, unknown>) => unknown;
    act: (fn: () => unknown) => Promise<void> | void;
  }
  interface RootLike {
    render: (el: unknown) => void;
    unmount: () => void;
  }
  let React: ReactLike;
  let createRoot: (el: Element) => RootLike;
  let mod: { ExplainBlock: unknown; ExplainSheetSection: unknown };
  let host: HTMLDivElement | null = null;
  let root: RootLike | null = null;

  beforeAll(async () => {
    const dom = new JSDOM('<!doctype html><html lang="ko"><head></head><body></body></html>', { url: 'http://127.0.0.1/', pretendToBeVisual: true });
    const g = globalThis as unknown as Record<string, unknown>;
    const w = dom.window as unknown as Record<string, unknown>;
    for (const k of ['window', 'document', 'navigator', 'HTMLElement', 'HTMLDivElement', 'Element', 'Node', 'Text', 'SVGElement', 'Event', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame']) {
      Object.defineProperty(g, k, { value: k === 'window' ? dom.window : w[k], configurable: true, writable: true });
    }
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    const req = createRequire(new URL('../../planner/package.json', import.meta.url));
    React = req('react') as ReactLike;
    createRoot = (req('react-dom/client') as { createRoot: (el: Element) => RootLike }).createRoot;
    const p = '../../planner/src/features/explain/ExplainBlock';
    mod = (await import(/* @vite-ignore */ p)) as typeof mod;
  });

  afterEach(async () => {
    if (root) await React.act(() => root!.unmount());
    host?.remove();
    root = null;
    host = null;
    clearExplanationCache();
    vi.unstubAllGlobals();
  });

  async function render(el: unknown) {
    host = document.createElement('div');
    document.body.appendChild(host);
    root = createRoot(host);
    await React.act(async () => root!.render(el));
    await React.act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    return host;
  }

  it('falls back to a plain line when the explanation file does not exist', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('nope', { status: 404 })));
    const h = await render(React.createElement(mod.ExplainBlock, { regionId: 'synthetic_region', inputTime: INPUT, originId: 'o', lang: 'ko', shown: SHOWN }));
    const sec = h.querySelector('[data-testid="explain"]') as HTMLElement;
    expect(sec.dataset.explainState).toBe('absent');
    expect(sec.textContent).toContain('왜 이 시각인가요?');
    expect(sec.textContent).toContain('이 시나리오에 대한 설명 파일이 없습니다.');
    expect(sec.querySelector('.wfgx-dots')).toBeNull();
  });

  it('renders the sentence, k-of-4 dots and the forecast note from the structured fields', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(file({ o: origin() })), { status: 200, headers: { 'content-type': 'application/json' } })));
    const h = await render(React.createElement(mod.ExplainBlock, { regionId: 'synthetic_region', inputTime: INPUT, originId: 'o', lang: 'en', shown: SHOWN }));
    const sec = h.querySelector('[data-testid="explain"]') as HTMLElement;
    expect(sec.dataset.explainState).toBe('explained');
    expect(sec.dataset.explainReason).toBe('flame_on_route');
    expect(sec.textContent).toContain('Why this time?');
    expect(sec.textContent).toContain('Leaving at 09:40 on the same route that was checked for 09:30, the vehicle would meet flames');
    expect(sec.textContent).toContain('Based on 4 fire scenarios from the forecast; not an observation.');
    const dots = sec.querySelector('.wfgx-dots') as HTMLElement;
    expect(dots.getAttribute('aria-label')).toBe('1 of 4 fire scenarios');
    expect(dots.querySelectorAll('.wfgx-dot').length).toBe(4);
    expect(dots.querySelectorAll('.wfgx-dot--on').length).toBe(1);
    expect(sec.textContent).toContain('Explained (replay of recorded checks)');
    // what the mark means and where the explanation was computed (this synthetic file records no host)
    expect(sec.querySelector('[data-explain-note="computed"]')?.textContent).toBe('* Computed for this explanation from the road graph and the fire scenarios, not a recorded check.');
    expect(sec.querySelector('[data-explain-note="host"]')?.textContent).toBe('Not computed on the evaluated host: the recorded route checks are replayed against the same hazard packet; no new route checks were run.');
  });

  it('the panel names the computing host recorded in the file', async () => {
    const f = file({ o: origin() });
    f.provenance = { ...f.provenance, computed_on: { platform: 'Linux-6.18.44-x86_64-with-glibc2.39', system: 'Linux', machine: 'x86_64' }, evaluated_host: false };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(f), { status: 200, headers: { 'content-type': 'application/json' } })));
    const h = await render(React.createElement(mod.ExplainBlock, { regionId: 'synthetic_region', inputTime: INPUT, originId: 'o', lang: 'ko', shown: SHOWN }));
    expect(h.querySelector('[data-explain-note="host"]')?.textContent).toBe('이 설명은 평가 호스트가 아닌 Linux x86_64에서 계산했습니다. 기록된 경로 점검을 같은 위험 패킷으로 재현했으며, 새 경로 점검은 하지 않았습니다.');
    expect(h.querySelector('.wfgx-status')?.textContent).toBe('설명됨(기록된 점검 재현)');
  });

  it('a not_explainable origin shows the plain statement without dots or basis', async () => {
    const rec = origin({ status: 'not_explainable', reason_code: 'unresolved_next', binding: [], next_verdict: 'unresolved' });
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(file({ o: rec })), { status: 200, headers: { 'content-type': 'application/json' } })));
    const h = await render(React.createElement(mod.ExplainBlock, { regionId: 'synthetic_region', inputTime: INPUT, originId: 'o', lang: 'ko', shown: SHOWN }));
    const sec = h.querySelector('[data-testid="explain"]') as HTMLElement;
    expect(sec.dataset.explainState).toBe('not_explainable');
    expect(sec.textContent).toContain('미확인을 안전으로 해석하지 마십시오.');
    expect(sec.querySelector('.wfgx-dots')).toBeNull();
    expect(sec.textContent).not.toContain('관측이 아닙니다');
  });

  it('plan sheet: one row per recorded scenario, fallback rows when absent', async () => {
    vi.stubGlobal('fetch', vi.fn(async (u: string) => (String(u).includes('20250101T000000Z')
      ? new Response(JSON.stringify(file({ o: origin() })), { status: 200, headers: { 'content-type': 'application/json' } })
      : new Response('nope', { status: 404 }))));
    const route = (job: string) => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: [[127, 36], [127.01, 36.01]] }, properties: { times_s: [], job_id: job, policy: 'full' } });
    const scen = (input: string, job = 'rc_synthetic') => ({ scenarioSetId: `synthetic:${input}`, inputTimeIso: input, bestVerdict: 'checked_route', latestSafeDepartureS: 1800, contiguousSafeDepartureS: 1800, sweep: [], shelter: { id: 'synthetic:shelter', name: '합성 대피소', sourceTag: 'amenity=school', lon: 127, lat: 36, arrivalS: 2000 }, route: route(job), travelOnlyRoute: null, exposure: [], computeS: null, host: null, reasonCode: null });
    const sheet = { region: { id: 'synthetic_region', nameKo: '합성', nameEn: 'Synthetic', fireYear: 2025 }, fireInputLabel: '합성', mock: false, origin: { id: 'o', name: '합성마을', categoryLabel: '마을', sourceTag: 'place=village', lon: 127, lat: 36, snapDistanceM: 10, vulnerable: false }, facilities: [], scenarios: [scen(INPUT), scen('2025-01-02T00:00:00Z'), scen(INPUT, 'rc_other')], generatedAtIso: INPUT, provenance: { checkpoint: 'x', packageVersion: '1', kit: 'v3', apiMode: 'cache', apiVersion: null, cacheCreatedAtIso: null, gitCommit: null } };
    const h = await render(React.createElement(mod.ExplainSheetSection, { sheet, lang: 'ko' }));
    const rows = h.querySelectorAll<HTMLElement>('.wfgx-sheet__row');
    expect(rows.length).toBe(3);
    expect(rows[0]!.dataset.explainState).toBe('explained');
    expect(rows[0]!.textContent).toContain('화재 시나리오 4개 중 1개');
    expect(rows[1]!.dataset.explainState).toBe('absent');
    // S6: a printed route from another route check never gets this explanation (no road it does not use is named)
    expect(rows[2]!.dataset.explainState).toBe('mismatch');
    expect(rows[2]!.textContent).not.toContain('합성마을에서');
    expect(h.textContent).toContain('예측에서 나온 화재 시나리오 4개를 기준으로 한 결과이며, 관측이 아닙니다.');
    // the marked row's note, once per sheet, in the section footer
    const notes = h.querySelectorAll('[data-explain-note="computed"]');
    expect(notes.length).toBe(1);
    expect(notes[0]!.closest('.wfgx-sheet__basis')).not.toBeNull();
    expect(notes[0]!.textContent).toBe(' * 평가 호스트가 아닌 곳에서 계산한 값이며, 기록된 점검이 아닙니다.');
  });

  function sheetOf(scenarios: unknown[]) {
    return { region: { id: 'synthetic_region', nameKo: '합성', nameEn: 'Synthetic', fireYear: 2025 }, fireInputLabel: '합성', mock: false, origin: { id: 'o', name: '합성마을', categoryLabel: '마을', sourceTag: 'place=village', lon: 127, lat: 36, snapDistanceM: 10, vulnerable: false }, facilities: [], scenarios, generatedAtIso: INPUT, provenance: { checkpoint: 'x', packageVersion: '1', kit: 'v3', apiMode: 'cache', apiVersion: null, cacheCreatedAtIso: null, gitCommit: null } };
  }
  const scenRow = (input: string, deadline: number) => ({ scenarioSetId: `synthetic:${input}`, inputTimeIso: input, bestVerdict: 'checked_route', latestSafeDepartureS: deadline, contiguousSafeDepartureS: deadline, sweep: [], shelter: { id: 'synthetic:shelter', name: '합성 대피소', sourceTag: 'amenity=school', lon: 127, lat: 36, arrivalS: 2000 }, route: { type: 'Feature', geometry: { type: 'LineString', coordinates: [[127, 36], [127.01, 36.01]] }, properties: { times_s: [], job_id: 'rc_synthetic', policy: 'full' } }, travelOnlyRoute: null, exposure: [], computeS: null, host: null, reasonCode: null });

  it('plan sheet footer: the computing host once when a printed sentence is marked, nothing for recorded-only rows', async () => {
    const f = file({
      o: origin(),
      last: origin({ reason_code: 'no_later_offset', binding: [], next_offset_s: null, next_verdict: null, deadline_offset_s: 3000, detail_code: 'last_checked_offset' }),
    });
    f.provenance = { ...f.provenance, computed_on: { system: 'Linux', machine: 'x86_64' }, evaluated_host: false };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(f), { status: 200, headers: { 'content-type': 'application/json' } })));
    const marked = await render(React.createElement(mod.ExplainSheetSection, { sheet: sheetOf([scenRow(INPUT, 1800)]), lang: 'en' }));
    expect(marked.querySelector('.wfgx-sheet__basis')?.textContent).toBe(
      'Based on 4 fire scenarios from the forecast; not an observation. * Computed on Linux x86_64 (not the evaluated host), not a recorded check.',
    );
    await React.act(() => root!.unmount());
    host?.remove();
    root = null;
    const lastSheet = sheetOf([scenRow(INPUT, 3000)]);
    lastSheet.origin.id = 'last';
    const plain = await render(React.createElement(mod.ExplainSheetSection, { sheet: lastSheet, lang: 'en' }));
    expect(plain.querySelector('.wfgx-sheet__row')?.getAttribute('data-explain-state')).toBe('explained');
    expect(plain.querySelector('.wfgx-sheet__row')?.textContent).not.toContain('*');
    expect(plain.querySelector('[data-explain-note]')).toBeNull();
    expect(plain.querySelector('.wfgx-sheet__basis')?.textContent).toBe('Based on 4 fire scenarios from the forecast; not an observation.');
  });
});

describe('committed explanation files render in both languages', () => {
  const dir = new URL('../../planner/public/data/explanations/', import.meta.url);
  const names = readdirSync(dir).filter((n) => n.endsWith('.json'));

  it('there is one file per recorded cache file', () => {
    expect(names.length).toBe(6);
  });

  it.each(names)('%s', (name) => {
    const f = JSON.parse(readFileSync(new URL(name, dir), 'utf8')) as ExplFile;
    // computed by tools/explain_deadlines off the evaluated host: the file says so, and so does every explanation shown
    const platform = computedOnText(f.provenance);
    expect([platform, f.provenance.evaluated_host, onEvaluatedHost(f.provenance)]).toEqual(['Linux x86_64', false, false]);
    for (const [oid, rec] of Object.entries(f.origins)) {
      const shown: ShownPlan = { bestVerdict: rec.verdict_summary, deadlineS: rec.deadline_offset_s, bestDestinationId: rec.deadline_route?.destination_id ?? null, bestJobId: rec.deadline_route?.route_check_job_id ?? null };
      for (const lang of ['ko', 'en'] as const) {
        const v = explainView({ state: 'ready', file: f, originId: oid, inputTime: f.input_time, lang, shown });
        expect(v.kind).toBe(rec.status);
        expect(v.lines.length).toBeGreaterThan(0);
        const text = [...v.lines, ...v.list, v.basis ?? '', v.dots?.text ?? '', v.computedNote ?? '', v.host ?? '', v.sheetNote ?? ''].join(' ');
        expect(text).not.toMatch(/\{\w+\}|undefined|NaN|null|—/); // every template field filled from data
        expect(text).not.toMatch(/안전한|safe route|simulation|시뮬레이션/i);
        if (rec.status !== 'not_explainable') {
          expect(v.basis).toBeTruthy();
          expect(v.host).toContain('Linux x86_64');
          expect(v.host).toMatch(lang === 'en' ? /not on the evaluated host.*no new route checks/ : /평가 호스트가 아닌.*새 경로 점검은 하지 않았습니다/);
        }
        // a sentence resting on a computed value carries the mark, and the notes explain it
        const marked = [...v.lines, ...v.list].some((l) => l.includes(COMPUTED_MARK));
        expect([oid, lang, v.marked, Boolean(v.computedNote), Boolean(v.sheetNote)]).toEqual([oid, lang, marked, marked, marked]);
        if (['flame_on_route', 'no_flame_avoiding_route', 'all_exits_blocked'].includes(rec.reason_code) || rec.detail_code === 'window_fire_free') expect([oid, marked]).toEqual([oid, true]);
        if (rec.reason_code === 'no_later_offset' || rec.reason_code === 'unresolved_next' || rec.reason_code === 'other') expect([oid, marked]).toEqual([oid, false]);
        // sentence by sentence: in a computed explanation every sentence ends with the mark and so does every exit-list
        // item; a recorded-only explanation (last checked time, 시간창 밖 skip, unresolved, withdrawn) carries none
        if (rec.status !== 'not_explainable') {
          const recordedOnly = ['no_later_offset', 'unresolved_next', 'other'].includes(rec.reason_code) || rec.detail_code === 'outside_recorded_arrival_window';
          const sentences = v.lines.flatMap((l) => l.split(/(?<=\.\*?) (?=\S)/));
          const unmarked = [...sentences.filter((s) => !s.endsWith(`.${COMPUTED_MARK}`)), ...v.list.filter((x) => !x.endsWith(COMPUTED_MARK))];
          expect([oid, lang, recordedOnly ? marked : unmarked]).toEqual([oid, lang, recordedOnly ? false : []]);
        }
        // a time-window conclusion names the next checked departure, the only later time evaluated
        if (rec.detail_code === 'window_fire_free' && rec.deadline_cause === 'time_window') {
          const last = v.lines[v.lines.length - 1]!;
          expect([oid, last.startsWith(lang === 'en' ? 'At the next checked departure, ' : '다음 점검 출발 시각인 '), last.includes(kstClock(f.input_time, rec.next_offset_s!))]).toEqual([oid, true, true]);
        }
        if (rec.reason_code === 'flame_on_route') expect(v.dots?.members).toEqual(rec.binding[0]!.members);
      }
    }
  });
});

describe('committed explanation files agree with the planner (TypeScript cacheToModel)', () => {
  // N2: the deadline, next time and shown route each file explains are the planner's own, computed here by the
  // planner code from the recorded cache files (planner/cache), not by the Python mirror in tools/explain_deadlines.
  const cacheDir = new URL('../../planner/cache/', import.meta.url);
  const explDir = new URL('../../planner/public/data/explanations/', import.meta.url);
  const index = parseCacheIndex(JSON.parse(readFileSync(new URL('INDEX.json', cacheDir), 'utf8')));

  it('covers the six recorded caches', () => {
    expect(index.length).toBe(6);
  });

  it.each(index.map((e) => [e.path, e] as const))('%s', (_path, entry) => {
    const model = cacheToModel(JSON.parse(readFileSync(new URL(entry.path, cacheDir), 'utf8')) as WireCacheFile, entry);
    const compact = entry.inputTime.replace(/[-:]/g, '').replace(/\.\d+/, '');
    const f = JSON.parse(readFileSync(new URL(`${entry.regionId}__${compact}.json`, explDir), 'utf8')) as ExplFile;
    expect(f.input_time).toBe(entry.inputTime);
    expect(Object.keys(f.origins).sort()).toEqual(Object.keys(model.plans).sort());
    for (const [oid, rec] of Object.entries(f.origins)) {
      const plan = model.plans[oid]!;
      expect([oid, rec.verdict_summary, rec.deadline_offset_s]).toEqual([oid, plan.bestVerdict, plan.latestSafeDepartureS]);
      const later = plan.latestSafeDepartureS === null ? [] : plan.sweep.filter((c) => c.offsetS > plan.latestSafeDepartureS!);
      if (plan.latestSafeDepartureS !== null) expect([oid, rec.next_offset_s]).toEqual([oid, later[0]?.offsetS ?? null]);
      if (rec.deadline_route) {
        expect([oid, rec.deadline_route.route_check_job_id, rec.deadline_route.destination_id]).toEqual([oid, plan.best?.jobId ?? null, plan.best?.destinationId ?? null]);
      }
      const shown: ShownPlan = { bestVerdict: plan.bestVerdict, deadlineS: plan.latestSafeDepartureS, bestDestinationId: plan.best?.destinationId ?? null, bestJobId: plan.best?.jobId ?? null };
      expect([oid, matchesShown(rec, shown)]).toEqual([oid, true]); // what the panel passes shows every explanation
    }
  });
});
