/**
 * "왜 이 시각인가요? / Why this time?" (planner/src/features/explain). The synthetic records here are invented test
 * data ("합성" places, round times) — not results of any region. The last block reads the committed explanation files
 * (planner/public/data/explanations) and renders every origin in both languages.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { explainView, matchesShown, slackText, whereText } from '../../planner/src/features/explain/text';
import { clearExplanationCache, explanationUrl, loadExplanationFile, parseExplanationFile } from '../../planner/src/features/explain/load';
import type { ExplFile, ExplItem, ExplOrigin, ShownPlan } from '../../planner/src/features/explain/types';

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

describe('explanation text (structured fields only)', () => {
  it('flame on the shown route: places, clock times, k of 4 and the slack', () => {
    const ko = view(origin());
    expect(ko.kind).toBe('explained');
    expect(ko.title).toBe('왜 이 시각인가요?');
    expect(ko.lines[0]).toBe('09:40에 출발하면 출발 마감 경로는 합성마을 부근 도로(1.2 km 거리)에서 09:41에 시나리오상 화염과 만납니다(화재 시나리오 4개 중 1개).');
    expect(ko.lines[1]).toBe('출발 마감 09:30에 출발하면 차량은 09:31에 그 도로의 해당 375 m 격자 칸을 벗어나며, 시나리오상 화염이 그 칸에 닿는 시각(09:36)보다 4분 이상 앞섭니다.');
    expect(ko.lines[2]).toBe('09:40에 출발하면 시나리오상 화염을 피하는 도로로는 그 대피소에 제때(체류 포함) 도착할 수 없습니다.');
    expect(ko.lines.length).toBe(3);
    expect(ko.dots).toEqual({ members: [1], total: 4, text: '화재 시나리오 4개 중 1개' });
    expect(ko.basis).toBe('예측에서 나온 화재 시나리오 4개를 기준으로 한 결과이며, 관측이 아닙니다.');
    const en = view(origin(), 'en');
    expect(en.title).toBe('Why this time?');
    expect(en.lines[0]).toContain('the road near Hapseong-ri (1.2 km away) at 09:41 (1 of 4 fire scenarios)');
    expect(en.lines[1]).toBe('Leaving at the leave-by time 09:30, the vehicle leaves the 375 m grid cell in question on that road at 09:31, at least 4 min before the flame reaches that cell in the fire scenarios (09:36).');
    // without a proof for every shelter checked at the deadline, no unreachability sentence
    expect(view(origin({ status: 'explained_partial', checked_at_deadline: 2, proven_unreachable_next: 1 })).lines.length).toBe(2);
    expect(en.basis).toBe('Based on 4 fire scenarios from the forecast; not an observation.');
  });

  it('slack is rounded down and unnamed roads name their node', () => {
    expect(slackText(287.7, 'ko')).toBe('4분 이상');
    expect(slackText(60, 'en')).toBe('at least 1 min');
    expect(slackText(59.9, 'en')).toBe('under 1 min');
    expect(whereText(item({ label_source: 'unnamed', label_ko: null, label_en: null }), 'ko')).toBe('이름 없는 도로(도로 노드 synthetic:n1)');
    expect(whereText(item({ label_en: null }), 'en')).toBe('the road near 합성마을 (1.2 km away)'); // never transliterated
  });

  it('window: fire-free and detour wording, never a fire claim for the fire-free case', () => {
    const free = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_free', window: { close_s: 3600, dwell_s: 120, fire_free: true, fastest_end_s: 3895, flame_avoiding_arrival_s: null, limit: 'scenario_window', horizon_s: 3600 } }));
    expect(free.lines[0]).toBe('09:40에 출발하면 화재가 없더라도 가장 빠른 도로로 대피소에 도착해 2분 머무는 일이 10:04에야 끝나, 기록된 화재 시나리오가 끝나는 10:00를 넘습니다. 이 마감은 예측 화염이 아니라 1시간 시나리오 범위에서 정해졌습니다.');
    expect(free.dots).toBeNull();
    const detour = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_detour', checked_at_deadline: 3, proven_unreachable_next: 3 }), 'en');
    expect(detour.lines[0]).toContain('no road route that avoids the flames in the fire scenarios reaches the shelter');
    expect(detour.lines[0]).toContain('(no flame-avoiding arrival at all by 10:00, when the scenarios end)');
    expect(detour.lines[0]).toContain('so this leave-by time comes from the flames in the fire scenarios');
    expect(detour.lines[1]).toBe('Leaving at 09:40, no road route that avoids the flames in the fire scenarios reaches any of the 3 shelters checked at 09:30 in time (stay included).');
    const late = view(origin({ reason_code: 'window', binding: [], detail_code: 'window_fire_detour', window: { close_s: 3600, dwell_s: 120, fire_free: false, fastest_end_s: 3371, flame_avoiding_arrival_s: 3579, limit: 'scenario_window', horizon_s: 3600 } }), 'ko');
    expect(late.lines[0]).toContain('(화염을 피하면 09:59 전에는 도착할 수 없음)');
    expect(late.lines.length).toBe(1);
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

  it('cut-off origin lists the blocked exits with k of 4', () => {
    const rec = origin({
      verdict_summary: 'model_no_route', deadline_offset_s: null, next_offset_s: null, next_verdict: null, reason_code: 'all_exits_blocked',
      binding: [], deadline_route: null, detail_code: 'flame_free_area_closed',
      exits: [item({ members: [0, 1, 2, 3], flame_time_s: 0, contact_time_s: 80, pass_time_at_deadline_s: null, slack_s: null }),
              item({ members: [0, 1, 2, 3], flame_time_s: 0, contact_time_s: 140, pass_time_at_deadline_s: null, slack_s: null, label_ko: '합성리', label_en: null })],
    });
    const v = view(rec, 'ko', { bestVerdict: 'model_no_route', deadlineS: null });
    expect(v.title).toBe('왜 확인된 경로가 없나요?');
    expect(v.lines[0]).toBe('진입 지점에서 화염과 만나지 않고 갈 수 있는 구역을 벗어나는 도로 2개가 모두 시나리오상 화염과 만납니다(화재 시나리오 4개 중 4개).');
    expect(v.lines[1]).toBe('이 도로들은 입력 시각(09:00)에 이미 타고 있는 것으로 표시된 칸을 지납니다.');
    expect(v.list).toEqual(['합성마을 부근 도로(1.2 km 거리): 시나리오 4/4', '합성리 부근 도로(1.2 km 거리): 시나리오 4/4']);
    expect(v.dots?.members).toEqual([0, 1, 2, 3]);
  });

  it('exits blocked in different members: "at least k", no single set of dots', () => {
    const rec = origin({
      verdict_summary: 'model_no_route', deadline_offset_s: null, next_offset_s: null, next_verdict: null, reason_code: 'all_exits_blocked',
      binding: [], deadline_route: null, detail_code: 'flame_free_area_closed',
      exits: [item({ members: [0, 2], flame_time_s: 600, contact_time_s: 700, pass_time_at_deadline_s: null, slack_s: null }),
              item({ members: [1, 2, 3], flame_time_s: 900, contact_time_s: 950, pass_time_at_deadline_s: null, slack_s: null })],
    });
    const v = view(rec, 'en', { bestVerdict: 'model_no_route', deadlineS: null });
    expect(v.lines[0]).toContain('(at least 2 of 4 fire scenarios)');
    expect(v.dots).toBeNull();
    expect(v.list).toEqual(['the road near Hapseong-ri (1.2 km away): 2/4 scenarios', 'the road near Hapseong-ri (1.2 km away): 3/4 scenarios']);
  });

  it('refuses an explanation made from other results, and falls back when absent or missing', () => {
    expect(matchesShown(origin(), SHOWN)).toBe(true);
    expect(view(origin(), 'ko', { ...SHOWN, deadlineS: 1200 }).kind).toBe('mismatch');
    expect(view(origin(), 'ko', { ...SHOWN, bestJobId: 'rc_live' }).kind).toBe('mismatch');
    expect(view(origin(), 'ko', { ...SHOWN, bestVerdict: 'unresolved' }).kind).toBe('mismatch');
    expect(view(origin(), 'ko', null).kind).toBe('mismatch');
    expect(explainView({ state: 'absent', file: null, originId: 'o', inputTime: INPUT, lang: 'ko', shown: SHOWN }).lines).toEqual(['이 시나리오에 대한 설명 파일이 없습니다.']);
    expect(explainView({ state: 'ready', file: file({}), originId: 'o', inputTime: INPUT, lang: 'en', shown: SHOWN }).lines).toEqual(['No explanation for this origin.']);
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
    expect(sec.textContent).toContain('Leaving at 09:40, the route shown for the leave-by time meets flames');
    expect(sec.textContent).toContain('Based on 4 fire scenarios from the forecast; not an observation.');
    const dots = sec.querySelector('.wfgx-dots') as HTMLElement;
    expect(dots.getAttribute('aria-label')).toBe('1 of 4 fire scenarios');
    expect(dots.querySelectorAll('.wfgx-dot').length).toBe(4);
    expect(dots.querySelectorAll('.wfgx-dot--on').length).toBe(1);
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
    const scen = (input: string) => ({ scenarioSetId: `synthetic:${input}`, inputTimeIso: input, bestVerdict: 'checked_route', latestSafeDepartureS: 1800, contiguousSafeDepartureS: 1800, sweep: [], shelter: { id: 'synthetic:shelter', name: '합성 대피소', sourceTag: 'amenity=school', lon: 127, lat: 36, arrivalS: 2000 }, route: null, travelOnlyRoute: null, exposure: [], computeS: null, host: null, reasonCode: null });
    const sheet = { region: { id: 'synthetic_region', nameKo: '합성', nameEn: 'Synthetic', fireYear: 2025 }, fireInputLabel: '합성', mock: false, origin: { id: 'o', name: '합성마을', categoryLabel: '마을', sourceTag: 'place=village', lon: 127, lat: 36, snapDistanceM: 10, vulnerable: false }, facilities: [], scenarios: [scen(INPUT), scen('2025-01-02T00:00:00Z')], generatedAtIso: INPUT, provenance: { checkpoint: 'x', packageVersion: '1', kit: 'v3', apiMode: 'cache', apiVersion: null, cacheCreatedAtIso: null, gitCommit: null } };
    const h = await render(React.createElement(mod.ExplainSheetSection, { sheet, lang: 'ko' }));
    const rows = h.querySelectorAll<HTMLElement>('.wfgx-sheet__row');
    expect(rows.length).toBe(2);
    expect(rows[0]!.dataset.explainState).toBe('explained');
    expect(rows[0]!.textContent).toContain('화재 시나리오 4개 중 1개');
    expect(rows[1]!.dataset.explainState).toBe('absent');
    expect(h.textContent).toContain('예측에서 나온 화재 시나리오 4개를 기준으로 한 결과이며, 관측이 아닙니다.');
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
    for (const [oid, rec] of Object.entries(f.origins)) {
      const shown: ShownPlan = { bestVerdict: rec.verdict_summary, deadlineS: rec.deadline_offset_s, bestDestinationId: rec.deadline_route?.destination_id ?? null, bestJobId: rec.deadline_route?.route_check_job_id ?? null };
      for (const lang of ['ko', 'en'] as const) {
        const v = explainView({ state: 'ready', file: f, originId: oid, inputTime: f.input_time, lang, shown });
        expect(v.kind).toBe(rec.status);
        expect(v.lines.length).toBeGreaterThan(0);
        const text = [...v.lines, ...v.list, v.basis ?? '', v.dots?.text ?? ''].join(' ');
        expect(text).not.toMatch(/\{\w+\}|undefined|NaN|null|—/); // every template field filled from data
        expect(text).not.toMatch(/안전한|safe route|simulation|시뮬레이션/i);
        if (rec.status !== 'not_explainable') expect(v.basis).toBeTruthy();
        if (rec.reason_code === 'flame_on_route') expect(v.dots?.members).toEqual(rec.binding[0]!.members);
      }
    }
  });
});
