/**
 * Result provenance per ORIGIN (planner/src/features/lastmile/connect.ts + input.ts): a result
 * computed through the API — recomputed in a cached scenario, or in a live API session such as the
 * Docker front door's Linux API — never carries the precomputed cache's "사전 계산 <time>" stamp, and
 * it is marked "시험 데이터 · 평가 호스트 아님" with its compute host unless every host its results
 * report is the evaluated native macOS arm64 host (src/api/cache.ts isTestDataHost; an unknown host
 * counts as not evaluated) — in every output and in the CSV. Cached results keep the cache's
 * provenance. An origin its source holds NO result for (not computed yet, not checkable, refused,
 * or every check failed before a job existed) is never called computed: "API 점검 · 이 출발지 결과
 * 없음" / "사전 계산 캐시 <time> · 이 출발지 결과 없음" on the long text's data line, the card's staff
 * line and the CSV ("결과 출처"); the dialog is checked in lastmile.render.test.ts. Drives the
 * store-aware lastMileArgs with the real booth cache uiseong_andong_2025 2025-03-26 02:00 KST (read
 * only); the live results' route provenance (hosts) and the no-result states are SYNTHETIC.
 */
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import type { HostInfo, OriginPlan, RouteDetail } from '../../planner/src/domain/types';
import { lastMileArgs } from '../../planner/src/features/lastmile/connect';
import { fieldMessagesCSV } from '../../planner/src/features/lastmile/csv';
import { buildLastMileInputs, liveHostsOf } from '../../planner/src/features/lastmile/input';
import { allTexts, buildFieldMessages, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import { getState, type PlannerState } from '../../planner/src/state/store';
import { liveOnlySession, loadBoothCacheModel, reliveOnHost, type NoResultOrigins } from './lastmile.cachedata';

const PATH = 'uiseong_andong_2025/20250325T170000Z.json';
/** 삼춘리 (leave_by in the cache): the origin the reviewers recomputed */
const SAMCHUN = 'osm:node/415160437';
/** origins the cache computed, given no API result in the live-only sessions below */
const YONGBONG = 'osm:node/415160449';
const GUGYE = 'osm:node/415160471';
const GWANGYEON = 'osm:node/415160467';
/** the not-checkable villages of this scenario (no road point within 2 km: no result anywhere) */
const NOT_CHECKABLE = ['osm:node/415160364', 'osm:node/415160399'];
const LINUX: HostInfo = { recorded: false, machine: 'x86_64', os: 'Linux', platform: 'Linux-6.18-x86_64-with-glibc2.39', cpuCount: 4 };
const MAC: HostInfo = { recorded: false, machine: 'arm64', os: 'Darwin', platform: 'macOS-26.0-arm64-arm-64bit', cpuCount: 12 };
const NOW = new Date('2026-11-02T05:00:00Z');

/** What a no-result origin's result source says, written out here (not taken from the module). */
const NO_RESULT_LIVE = { ko: 'API 점검 · 이 출발지 결과 없음', en: 'API checks · no result for this origin' };
const NO_RESULT_CACHE = { ko: '사전 계산 캐시 2026-10-18 08:10 KST · 이 출발지 결과 없음', en: 'Precomputed cache 2026-10-18 08:10 KST · no result for this origin' };
/** Anything that claims a computation for an origin. */
const CLAIMS_COMPUTED = /API 점검 결과|API results|계산 호스트|host unknown|\bhost [A-Za-z]|실시간 API|Live API|사전 계산 2|Precomputed 2|시험 데이터|시험자료|시험용|Test data|test results|TEST/;

let data: ReturnType<typeof loadBoothCacheModel>;

beforeAll(() => {
  data = loadBoothCacheModel(PATH);
}, 120_000);

/** The cached plan recomputed "live": the same attempts under new job ids whose routes report `host` (null: no host). */
function relive(plan: OriginPlan, host: HostInfo | null | ((cell: number) => HostInfo), tag: string) {
  return reliveOnHost(data, plan, host, tag);
}

function cachedState(over: Partial<PlannerState>): PlannerState {
  return {
    ...getState(),
    regionIndex: [data.region],
    regionId: data.region.id,
    cacheIndex: [data.entry],
    scenarioId: data.entry.scenarioSetId,
    places: data.places,
    plans: data.plans,
    cache: data.model,
    dataSource: 'cache',
    routes: {},
    ...over,
  };
}

function messagesOf(args: ReturnType<typeof lastMileArgs>): FieldMessages[] {
  if (!args.ok) throw new Error(args.reason);
  return buildLastMileInputs(args.args).map((i) => buildFieldMessages(i, null));
}

const everyText = (fm: FieldMessages) => [...Object.values(allTexts(fm, 'ko')), ...Object.values(allTexts(fm, 'en'))];

/** RFC 4180 rows of the CSV (quoted cells may hold commas, quotes and line breaks). */
function parseCsv(text: string): string[][] {
  const s = text.replace(/^\uFEFF/, '');
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < s.length; i += 1) {
    const ch = s[i]!;
    if (quoted) {
      if (ch === '"' && s[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') {
      row.push(cell);
      cell = '';
    } else if (ch === '\r' && s[i + 1] === '\n') {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
      i += 1;
    } else cell += ch;
  }
  if (cell || row.length) rows.push([...row, cell]);
  return rows;
}

/** The CSV's "결과 출처" / "Result source" cell of every origin. */
function csvSources(items: FieldMessages[], lang: 'ko' | 'en'): Map<string, string> {
  const [head, ...rows] = parseCsv(fieldMessagesCSV(items, { lang }));
  const id = head!.indexOf(lang === 'ko' ? '출발지 ID' : 'Origin ID');
  const src = head!.indexOf(lang === 'ko' ? '결과 출처' : 'Result source');
  expect(id).toBeGreaterThanOrEqual(0);
  expect(src).toBeGreaterThanOrEqual(0);
  for (const r of rows) expect(r.length).toBe(head!.length);
  return new Map(rows.map((r) => [r[id]!, r[src]!]));
}

/** Data line of the long text, the card's staff line and the CSV cell of one live origin say `want` and claim nothing more. */
function expectNoResult(fm: FieldMessages, want: { ko: string; en: string }, csv: Record<'ko' | 'en', Map<string, string>>) {
  const at = fm.originId;
  expect(fm.plan.input.provenance.computed, at).toBe(false);
  expect(fm.plan.input.testData, at).toBe(false);
  expect(fm.violations, at).toEqual([]);
  expect(fm.kind, at).toBe('unresolved');
  expect(fm.text.ko.lms.split('\n')[2], at).toBe(`자료 기준: 2025년 3월 26일 02:00 (한국 시각) · ${want.ko}`);
  expect(fm.text.en.lms.split('\n')[2], at).toBe(`Data time: 2025-03-26 02:00 KST · ${want.en}`);
  expect(fm.text.ko.card.meta.endsWith(` · ${want.ko}`), `${at} ${fm.text.ko.card.meta}`).toBe(true);
  expect(fm.text.en.card.meta.endsWith(` · ${want.en}`), `${at} ${fm.text.en.card.meta}`).toBe(true);
  for (const t of everyText(fm)) expect(t, at).not.toMatch(CLAIMS_COMPUTED);
  for (const l of ['ko', 'en'] as const) expect(csv[l].get(at), `${at} ${l} CSV`).toBe(want[l]);
}

describe('a result recomputed through the API inside a cached scenario', () => {
  it('Linux API: never the cache\'s "사전 계산" stamp; marked as not computed on the evaluated host, with its compute host, in every output and the CSV', () => {
    const live = relive(data.plans[SAMCHUN]!, LINUX, 'linux');
    const items = messagesOf(lastMileArgs(cachedState({ plans: { ...data.plans, [SAMCHUN]: live.plan }, routes: live.routes }), NOW));
    const fm = items.find((x) => x.originId === SAMCHUN)!;
    // the recomputed result has the cache's verdicts; only its provenance differs
    expect(fm.kind).toBe('leave_by');
    expect(fm.violations).toEqual([]);
    const linux = { ko: 'Linux x86_64 · 4 vCPU', en: 'Linux x86_64 · 4 vCPU' };
    expect(fm.plan.input.provenance).toEqual({ source: 'live', computed: true, cachePath: null, cacheCreatedAtIso: null, host: linux, testHost: linux });
    expect(fm.plan.input.testData).toBe(true);
    for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed|실시간 API|Live API|live API/);
    expect(fm.text.ko.lms.split('\n')[0]).toBe('[시험 데이터 · 2025년 기록 재현 · 실제 상황 아님]');
    expect(fm.text.ko.lms).toContain('자료 기준: 2025년 3월 26일 02:00 (한국 시각) · API 점검 결과 · 계산 호스트 Linux x86_64 · 4 vCPU');
    expect(fm.text.ko.lms).toContain('시험 데이터: 평가 호스트가 아닌 장비(Linux x86_64 · 4 vCPU)에서 API로 계산한 결과입니다.');
    expect(fm.text.en.lms).toContain('Data time: 2025-03-26 02:00 KST · API results · host Linux x86_64 · 4 vCPU');
    expect(fm.text.en.lms).toContain('Test data: computed through the API on a host other than the evaluation host (Linux x86_64 · 4 vCPU).');
    expect(fm.text.ko.sms.split('\n')[0]).toBe('[25.3.26 02:00 시험자료]');
    expect(fm.text.en.sms.split('\n')[0]).toBe('TEST REPLAY of 2025-03-26 02:00 KST data, not live');
    expect(fm.text.ko.broadcast).toContain('시험용');
    expect(fm.text.ko.call).toContain('시험용 계산 자료입니다.');
    expect(fm.text.en.broadcast + fm.text.en.call).toContain('test results');
    expect(fm.text.ko.card.badges).toContain('시험 데이터 · 평가 호스트 아님');
    expect(fm.text.en.card.badges).toContain('Test data · not the evaluation host');
    expect(fm.text.ko.card.meta).toContain('API 점검 결과 · 계산 호스트 Linux x86_64 · 4 vCPU');
    expect(fm.text.en.card.meta).toContain('API results · host Linux x86_64 · 4 vCPU');
    // every other origin is still the precomputed cache, with the cache's stamp and no test-data marking;
    // the not-checkable ones, which the cache holds no result for, are never called precomputed
    const others = items.filter((x) => x.originId !== SAMCHUN);
    expect(others.length).toBeGreaterThan(50);
    for (const x of others) {
      expect(x.plan.input.provenance.source).toBe('cache');
      expect(x.plan.input.testData).toBe(false);
      expect(x.plan.input.provenance.computed, x.originId).toBe(!NOT_CHECKABLE.includes(x.originId));
      const stamp = NOT_CHECKABLE.includes(x.originId) ? NO_RESULT_CACHE.ko : '사전 계산 2026-10-18 08:10 KST';
      expect(x.text.ko.lms.split('\n')[2]).toBe(`자료 기준: 2025년 3월 26일 02:00 (한국 시각) · ${stamp}`);
      // (a leave-by card with an unnamed destination adds its id after the source)
      expect(x.text.ko.card.meta).toContain(` · ${stamp}`);
      for (const t of everyText(x)) expect(t).not.toMatch(/API 점검|API results|API checks|실시간 API|Live API|시험 데이터|Test data|TEST/);
    }
    // the CSV: every row its own result source
    const ko = csvSources(items, 'ko');
    expect(ko.get(SAMCHUN)).toBe('API 점검 결과 · 계산 호스트 Linux x86_64 · 4 vCPU · 평가 호스트 아님');
    expect(ko.get(GUGYE)).toBe(`사전 계산 캐시 · ${PATH} · 2026-10-18 08:10 KST`);
    expect(csvSources(items, 'en').get(SAMCHUN)).toBe('API results · host Linux x86_64 · 4 vCPU · not the evaluation host');
  }, 60_000);

  it('macOS arm64 API (the evaluated host type): not test data, and still never the cache\'s stamp', () => {
    const live = relive(data.plans[SAMCHUN]!, MAC, 'mac');
    const fm = messagesOf(lastMileArgs(cachedState({ plans: { ...data.plans, [SAMCHUN]: live.plan }, routes: live.routes }), NOW)).find((x) => x.originId === SAMCHUN)!;
    expect(fm.violations).toEqual([]);
    expect(fm.plan.input.testData).toBe(false);
    expect(fm.plan.input.provenance.host).toEqual({ ko: 'macOS arm64 · 12 vCPU', en: 'macOS arm64 · 12 vCPU' });
    expect(fm.plan.input.provenance.testHost).toBeNull();
    for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed|시험 데이터|시험자료|Test data|TEST/);
    expect(fm.text.ko.lms).toContain('· API 점검 결과 · 계산 호스트 macOS arm64 · 12 vCPU');
    expect(fm.text.ko.card.meta).toContain('API 점검 결과 · 계산 호스트 macOS arm64 · 12 vCPU');
  });

  it('a live result whose compute host is unknown is marked (fail closed)', () => {
    const live = relive(data.plans[SAMCHUN]!, null, 'nohost');
    const fm = messagesOf(lastMileArgs(cachedState({ plans: { ...data.plans, [SAMCHUN]: live.plan }, routes: live.routes }), NOW)).find((x) => x.originId === SAMCHUN)!;
    expect(fm.violations).toEqual([]);
    expect(fm.plan.input.testData).toBe(true);
    expect(fm.plan.input.provenance.computed).toBe(true);
    expect(fm.plan.input.provenance.host).toBeNull();
    for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed/);
    expect(fm.text.ko.lms).toContain('· API 점검 결과 · 계산 호스트 미상');
    expect(fm.text.en.lms).toContain('· API results · host unknown');
    expect(fm.text.ko.lms).toContain('시험 데이터: 계산 호스트를 알 수 없어 평가 호스트의 결과로 보지 않습니다.');
    expect(fm.text.en.lms).toContain('Test data: the compute host is unknown, so this is not treated as evaluation-host output.');
    expect(fm.text.ko.card.badges).toContain('시험 데이터 · 평가 호스트 아님');
  });

  it('results from the evaluated host and another one: marked, and the note names only the other host', () => {
    const live = relive(data.plans[SAMCHUN]!, (cell) => (cell === 0 ? MAC : LINUX), 'mixed');
    const fm = messagesOf(lastMileArgs(cachedState({ plans: { ...data.plans, [SAMCHUN]: live.plan }, routes: live.routes }), NOW)).find((x) => x.originId === SAMCHUN)!;
    expect(fm.violations).toEqual([]);
    expect(fm.plan.input.testData).toBe(true);
    // the data line names every host the results report; the test-data note only the non-evaluated one
    expect(fm.text.ko.lms).toContain('· API 점검 결과 · 계산 호스트 macOS arm64 · 12 vCPU, Linux x86_64 · 4 vCPU');
    expect(fm.text.ko.lms).toContain('시험 데이터: 평가 호스트가 아닌 장비(Linux x86_64 · 4 vCPU)에서 API로 계산한 결과가 섞여 있습니다.');
    expect(fm.text.en.lms).toContain('Test data: includes results computed through the API on a host other than the evaluation host (Linux x86_64 · 4 vCPU).');
    for (const l of ['ko', 'en'] as const) expect(fm.text[l].lms).not.toMatch(/\(macOS arm64[^)]*\)/);
  });

  it('liveHostsOf: the distinct hosts the results report, in sweep order; none without route provenance', () => {
    const plan = relive(data.plans[SAMCHUN]!, LINUX, 'h').plan;
    const routes: Record<string, RouteDetail> = {};
    plan.sweep.forEach((c, i) => c.attempts.forEach((a) => (routes[a.jobId!] = { provenance: { host: i === 0 ? MAC : LINUX } } as unknown as RouteDetail)));
    expect(liveHostsOf(plan, (j) => routes[j] ?? null)).toEqual([MAC, LINUX]);
    expect(liveHostsOf(plan, () => null)).toEqual([]);
  });
});

describe('an origin the precomputed cache holds no result for (not checkable)', () => {
  it('is never called precomputed: "사전 계산 캐시 <time> · 이 출발지 결과 없음" on the data line, the staff line and in the CSV', () => {
    const items = messagesOf(lastMileArgs(cachedState({}), NOW));
    const none = items.filter((x) => !x.plan.input.provenance.computed);
    expect(none.map((x) => x.originId).sort()).toEqual([...NOT_CHECKABLE].sort());
    const csv = { ko: csvSources(items, 'ko'), en: csvSources(items, 'en') };
    for (const fm of none) {
      expect(fm.plan.input.plan?.note).toBe('not_checkable');
      expect(fm.text.ko.lms.split('\n')[2]).toBe(`자료 기준: 2025년 3월 26일 02:00 (한국 시각) · ${NO_RESULT_CACHE.ko}`);
      expect(fm.text.en.lms.split('\n')[2]).toBe(`Data time: 2025-03-26 02:00 KST · ${NO_RESULT_CACHE.en}`);
      expect(fm.text.ko.card.meta.endsWith(` · ${NO_RESULT_CACHE.ko}`)).toBe(true);
      expect(fm.text.en.card.meta.endsWith(` · ${NO_RESULT_CACHE.en}`)).toBe(true);
      expect(csv.ko.get(fm.originId)).toBe(`사전 계산 캐시 · ${PATH} · 2026-10-18 08:10 KST · 이 출발지 결과 없음`);
      expect(csv.en.get(fm.originId)).toBe(`Precomputed cache · ${PATH} · 2026-10-18 08:10 KST · no result for this origin`);
      for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산 2|Precomputed 2|API/);
    }
  }, 60_000);
});

describe('a live API session without a precomputed cache (the Docker front door: VITE_WFG_API_MODE=real, Linux API)', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  /** connect.ts as the Docker front door builds it (VITE_WFG_API_MODE=real: no MOCK marking). */
  async function realConnect() {
    vi.stubEnv('VITE_WFG_API_MODE', 'real');
    vi.resetModules();
    return (await import('../../planner/src/features/lastmile/connect')) as typeof import('../../planner/src/features/lastmile/connect');
  }

  function liveState(session: { plans: Record<string, OriginPlan>; routes: Record<string, RouteDetail> }): PlannerState {
    return cachedState({ plans: session.plans, routes: session.routes, cache: null, dataSource: 'live' });
  }

  it('every computed origin is marked as not computed on the evaluated host; nothing says "사전 계산"', async () => {
    const connect = await realConnect();
    const args = connect.lastMileArgs(liveState(liveOnlySession(data, LINUX, 'docker')), NOW);
    expect(args.ok && args.args.mock).toBe(false);
    const items = messagesOf(args);
    let computed = 0;
    for (const fm of items) {
      expect(fm.violations, fm.originId).toEqual([]);
      expect(fm.plan.input.provenance.source).toBe('live');
      for (const t of everyText(fm)) expect(t, fm.originId).not.toMatch(/사전 계산|Precomputed|실시간 API|Live API/);
      if (fm.plan.input.plan?.sweep.some((c) => c.attempts.length)) {
        computed += 1;
        expect(fm.plan.input.provenance.computed, fm.originId).toBe(true);
        expect(fm.plan.input.testData, fm.originId).toBe(true);
        expect(fm.text.ko.lms).toContain('· API 점검 결과 · 계산 호스트 Linux x86_64 · 4 vCPU');
        expect(fm.text.ko.sms.split('\n')[0]).toContain('시험자료');
        expect(fm.text.ko.card.badges).toContain('시험 데이터 · 평가 호스트 아님');
      } else {
        // nothing was computed for it: no "computed" and no "computed on another host" claim
        expect(NOT_CHECKABLE).toContain(fm.originId);
        expect(fm.plan.input.provenance.computed, fm.originId).toBe(false);
        expect(fm.plan.input.testData, fm.originId).toBe(false);
      }
    }
    expect(computed).toBe(items.length - NOT_CHECKABLE.length);
    expect(computed).toBeGreaterThan(50);
  }, 60_000);

  it('an origin without an API result — not computed yet, not checkable, refused, or failed before any job — is never called computed: data line, staff line, CSV', async () => {
    const connect = await realConnect();
    const none: NoResultOrigins = { notComputed: [YONGBONG], rejected: [GUGYE], failed: [GWANGYEON] };
    const session = liveOnlySession(data, LINUX, 'docker', none);
    // the states the controller stores (domain/plan.ts unresolvedPlan, planFromAttempts with refused attempts)
    expect(session.plans[YONGBONG]!.note).toBe('not_computed');
    expect(session.plans[GUGYE]!.note).toBe('rejected');
    expect(session.plans[GWANGYEON]!.sweep.flatMap((c) => c.attempts).every((a) => a.jobId === null && a.verdict === 'unresolved')).toBe(true);
    for (const id of NOT_CHECKABLE) expect(session.plans[id]).toMatchObject({ source: 'live', note: 'not_checkable' });
    const items = messagesOf(connect.lastMileArgs(liveState(session), NOW));
    const csv = { ko: csvSources(items, 'ko'), en: csvSources(items, 'en') };
    const targets = [YONGBONG, GUGYE, GWANGYEON, ...NOT_CHECKABLE];
    for (const id of targets) expectNoResult(items.find((x) => x.originId === id)!, NO_RESULT_LIVE, csv);
    // the body says why, in the same text
    const lms = (id: string) => items.find((x) => x.originId === id)!.text.ko.lms;
    expect(lms(YONGBONG)).toContain('■ 이 출발지는 아직 계산하지 않았습니다.');
    expect(lms(GUGYE)).toContain('■ 계산 요청이 거부되어 점검하지 못했습니다.');
    for (const id of NOT_CHECKABLE) expect(lms(id)).toContain('2 km 안에 점검할 수 있는 도로 지점이 없어 점검하지 않았습니다.');
    // every other origin has results and says so
    for (const fm of items.filter((x) => !targets.includes(x.originId))) {
      expect(fm.plan.input.provenance.computed, fm.originId).toBe(true);
      expect(csv.ko.get(fm.originId)).toBe('API 점검 결과 · 계산 호스트 Linux x86_64 · 4 vCPU · 평가 호스트 아님');
    }
  }, 60_000);

  it('before any result (every origin not computed yet): no text claims a computation', async () => {
    const connect = await realConnect();
    const ids = Object.keys(data.plans).filter((id) => !NOT_CHECKABLE.includes(id));
    const items = messagesOf(connect.lastMileArgs(liveState(liveOnlySession(data, LINUX, 'none', { notComputed: ids })), NOW));
    const csv = { ko: csvSources(items, 'ko'), en: csvSources(items, 'en') };
    expect(items.length).toBeGreaterThan(80);
    for (const fm of items) expectNoResult(fm, NO_RESULT_LIVE, csv);
  }, 60_000);

  it('with the default MOCK build setting the same session is marked MOCK (the planner\'s session-wide rule), still never "사전 계산", and a no-result origin is still not called computed', () => {
    const items = messagesOf(lastMileArgs(liveState(liveOnlySession(data, LINUX, 'mockenv', { notComputed: [YONGBONG] })), NOW));
    for (const fm of items) {
      expect(fm.plan.input.mock).toBe(true);
      expect(fm.violations, fm.originId).toEqual([]);
      for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed/);
      expect(fm.text.ko.sms.split('\n')[0]).toContain('MOCK');
    }
    for (const id of [YONGBONG, ...NOT_CHECKABLE]) {
      const fm = items.find((x) => x.originId === id)!;
      expect(fm.text.ko.lms.split('\n')[2]).toBe(`자료 기준: 2025년 3월 26일 02:00 (한국 시각) · ${NO_RESULT_LIVE.ko}`);
      expect(fm.text.en.card.meta.endsWith(` · ${NO_RESULT_LIVE.en}`)).toBe(true);
    }
  }, 60_000);
});
