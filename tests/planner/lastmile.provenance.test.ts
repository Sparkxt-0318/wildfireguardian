/**
 * Result provenance per ORIGIN (planner/src/features/lastmile/connect.ts + input.ts): a result
 * computed through the API — recomputed in a cached scenario, or in a live API session such as the
 * Docker front door's Linux API — never carries the precomputed cache's "사전 계산 <time>" stamp, and
 * it is marked "시험 데이터 · 평가 호스트 아님" with its compute host unless every host its results
 * report is the evaluated native macOS arm64 host (src/api/cache.ts isTestDataHost; an unknown host
 * counts as not evaluated) — in every output and in the CSV. Cached results keep the cache's
 * provenance. Drives the store-aware lastMileArgs with the real booth cache uiseong_andong_2025
 * 2025-03-26 02:00 KST (read only); the live results' route provenance (hosts) is SYNTHETIC.
 */
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { planFromAttempts } from '../../planner/src/domain/plan';
import type { HostInfo, OriginPlan, RouteDetail } from '../../planner/src/domain/types';
import { lastMileArgs } from '../../planner/src/features/lastmile/connect';
import { fieldMessagesCSV } from '../../planner/src/features/lastmile/csv';
import { buildLastMileInputs, liveHostsOf } from '../../planner/src/features/lastmile/input';
import { allTexts, buildFieldMessages, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import { getState, type PlannerState } from '../../planner/src/state/store';
import { loadBoothCacheModel } from './lastmile.cachedata';

const PATH = 'uiseong_andong_2025/20250325T170000Z.json';
/** 삼춘리 (leave_by in the cache): the origin the reviewers recomputed */
const SAMCHUN = 'osm:node/415160437';
const LINUX: HostInfo = { recorded: false, machine: 'x86_64', os: 'Linux', platform: 'Linux-6.18-x86_64-with-glibc2.39', cpuCount: 4 };
const MAC: HostInfo = { recorded: false, machine: 'arm64', os: 'Darwin', platform: 'macOS-26.0-arm64-arm-64bit', cpuCount: 12 };
const NOW = new Date('2026-11-02T05:00:00Z');

let data: ReturnType<typeof loadBoothCacheModel>;

beforeAll(() => {
  data = loadBoothCacheModel(PATH);
}, 120_000);

/** The cached plan recomputed "live": the same attempts under new job ids whose routes report `host` (null: no host). */
function relive(plan: OriginPlan, host: HostInfo | null, tag: string): { plan: OriginPlan; routes: Record<string, RouteDetail> } {
  const routes: Record<string, RouteDetail> = {};
  const skipped = Object.fromEntries(plan.sweep.filter((c) => c.skipped).map((c) => [c.offsetS, c.skipped!]));
  const attempts = plan.sweep
    .flatMap((c) => c.attempts)
    .map((a, i) => {
      const jobId = `${tag}:${plan.originId}:${i}`;
      routes[jobId] = { jobId, mock: false, provenance: host ? { host } : null } as unknown as RouteDetail;
      return { ...a, jobId };
    });
  return { plan: planFromAttempts({ originId: plan.originId, offsetsS: data.model.offsetsS, attempts, source: 'live', mock: false, skipped }), routes };
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

describe('a result recomputed through the API inside a cached scenario', () => {
  it('Linux API: never the cache\'s "사전 계산" stamp; marked as not computed on the evaluated host, with its compute host, in every output and the CSV', () => {
    const live = relive(data.plans[SAMCHUN]!, LINUX, 'linux');
    const items = messagesOf(lastMileArgs(cachedState({ plans: { ...data.plans, [SAMCHUN]: live.plan }, routes: live.routes }), NOW));
    const fm = items.find((x) => x.originId === SAMCHUN)!;
    // the recomputed result has the cache's verdicts; only its provenance differs
    expect(fm.kind).toBe('leave_by');
    expect(fm.violations).toEqual([]);
    expect(fm.plan.input.provenance).toEqual({ source: 'live', cachePath: null, cacheCreatedAtIso: null, host: { ko: 'Linux x86_64 · 4 vCPU', en: 'Linux x86_64 · 4 vCPU' } });
    expect(fm.plan.input.testData).toBe(true);
    for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed/);
    expect(fm.text.ko.lms.split('\n')[0]).toBe('[시험 데이터 · 2025년 기록 재현 · 실제 상황 아님]');
    expect(fm.text.ko.lms).toContain('자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 실시간 API 계산 · 계산 호스트 Linux x86_64 · 4 vCPU');
    expect(fm.text.ko.lms).toContain('시험 데이터: 평가 호스트가 아닌 장비(Linux x86_64 · 4 vCPU)에서 실시간 API로 계산한 결과입니다.');
    expect(fm.text.en.lms).toContain('Data time: 2025-03-26 02:00 KST · Live API · host Linux x86_64 · 4 vCPU');
    expect(fm.text.en.lms).toContain('Test data: computed through the live API on a host other than the evaluation host (Linux x86_64 · 4 vCPU).');
    expect(fm.text.ko.sms.split('\n')[0]).toBe('[25.3.26 02:00 시험자료]');
    expect(fm.text.en.sms.split('\n')[0]).toBe('TEST REPLAY of 2025-03-26 02:00 KST data, not live');
    expect(fm.text.ko.broadcast).toContain('시험용');
    expect(fm.text.ko.call).toContain('시험용 계산 자료입니다.');
    expect(fm.text.en.broadcast + fm.text.en.call).toContain('test results');
    expect(fm.text.ko.card.badges).toContain('시험 데이터 · 평가 호스트 아님');
    expect(fm.text.en.card.badges).toContain('Test data · not the evaluation host');
    expect(fm.text.ko.card.meta).toContain('실시간 API 계산 · 계산 호스트 Linux x86_64 · 4 vCPU');
    expect(fm.text.en.card.meta).toContain('Live API · host Linux x86_64 · 4 vCPU');
    // every other origin is still the precomputed cache, with the cache's stamp and no test-data marking
    const others = items.filter((x) => x.originId !== SAMCHUN);
    expect(others.length).toBeGreaterThan(50);
    for (const x of others) {
      expect(x.plan.input.provenance.source).toBe('cache');
      expect(x.plan.input.testData).toBe(false);
      expect(x.text.ko.lms).toContain(' · 사전 계산 2026-10-18 08:10 KST');
      expect(x.text.ko.card.meta).toContain('사전 계산 2026-10-18 08:10 KST');
      for (const t of everyText(x)) expect(t).not.toMatch(/실시간 API|Live API|시험 데이터|Test data|TEST/);
    }
    // the CSV: every row its own result source
    const rows = fieldMessagesCSV(items, { lang: 'ko' }).split('\r\n');
    expect(rows.find((r) => r.includes(`,${SAMCHUN},`))).toContain(',시험 데이터,실시간 API 계산 · 계산 호스트 Linux x86_64 · 4 vCPU · 평가 호스트 아님,');
    expect(rows.find((r) => r.includes(',osm:node/415160471,'))).toContain(`,,,사전 계산 캐시 · ${PATH} · 2026-10-18 08:10 KST,`);
    const en = fieldMessagesCSV(items, { lang: 'en' }).split('\r\n');
    expect(en.find((r) => r.includes(`,${SAMCHUN},`))).toContain(',test data,Live API · host Linux x86_64 · 4 vCPU · not the evaluation host,');
  }, 60_000);

  it('macOS arm64 API (the evaluated host type): not test data, and still never the cache\'s stamp', () => {
    const live = relive(data.plans[SAMCHUN]!, MAC, 'mac');
    const fm = messagesOf(lastMileArgs(cachedState({ plans: { ...data.plans, [SAMCHUN]: live.plan }, routes: live.routes }), NOW)).find((x) => x.originId === SAMCHUN)!;
    expect(fm.violations).toEqual([]);
    expect(fm.plan.input.testData).toBe(false);
    expect(fm.plan.input.provenance.host).toEqual({ ko: 'macOS arm64 · 12 vCPU', en: 'macOS arm64 · 12 vCPU' });
    for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed|시험 데이터|시험자료|Test data|TEST/);
    expect(fm.text.ko.lms).toContain('· 실시간 API 계산 · 계산 호스트 macOS arm64 · 12 vCPU');
    expect(fm.text.ko.card.meta).toContain('실시간 API 계산 · 계산 호스트 macOS arm64 · 12 vCPU');
  });

  it('a live result whose compute host is unknown is marked (fail closed)', () => {
    const live = relive(data.plans[SAMCHUN]!, null, 'nohost');
    const fm = messagesOf(lastMileArgs(cachedState({ plans: { ...data.plans, [SAMCHUN]: live.plan }, routes: live.routes }), NOW)).find((x) => x.originId === SAMCHUN)!;
    expect(fm.violations).toEqual([]);
    expect(fm.plan.input.testData).toBe(true);
    expect(fm.plan.input.provenance.host).toBeNull();
    for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed/);
    expect(fm.text.ko.lms).toContain('· 실시간 API 계산 · 계산 호스트 미상');
    expect(fm.text.ko.lms).toContain('시험 데이터: 계산 호스트를 알 수 없어 평가 호스트의 결과로 보지 않습니다.');
    expect(fm.text.en.lms).toContain('Test data: the compute host is unknown, so this is not treated as evaluation-host output.');
    expect(fm.text.ko.card.badges).toContain('시험 데이터 · 평가 호스트 아님');
  });

  it('liveHostsOf: the distinct hosts the results report, in sweep order; none without route provenance', () => {
    const plan = relive(data.plans[SAMCHUN]!, LINUX, 'h').plan;
    const routes: Record<string, RouteDetail> = {};
    plan.sweep.forEach((c, i) => c.attempts.forEach((a) => (routes[a.jobId!] = { provenance: { host: i === 0 ? MAC : LINUX } } as unknown as RouteDetail)));
    expect(liveHostsOf(plan, (j) => routes[j] ?? null)).toEqual([MAC, LINUX]);
    expect(liveHostsOf(plan, () => null)).toEqual([]);
  });
});

describe('a live API session without a precomputed cache (the Docker front door: VITE_WFG_API_MODE=real, Linux API)', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  /** Every scenario origin computed live on `host` (origins the cache never computed stay without a result). */
  function liveSession(host: HostInfo, tag: string) {
    const plans: Record<string, OriginPlan> = {};
    let routes: Record<string, RouteDetail> = {};
    for (const [id, p] of Object.entries(data.plans)) {
      if (p.sweep.some((c) => c.attempts.length)) {
        const live = relive(p, host, tag);
        plans[id] = live.plan;
        routes = { ...routes, ...live.routes };
      } else plans[id] = { ...p, source: 'live' };
    }
    return { plans, routes };
  }

  it('every computed origin is marked as not computed on the evaluated host; nothing says "사전 계산"', async () => {
    vi.stubEnv('VITE_WFG_API_MODE', 'real');
    vi.resetModules();
    const connect = (await import('../../planner/src/features/lastmile/connect')) as typeof import('../../planner/src/features/lastmile/connect');
    const { plans, routes } = liveSession(LINUX, 'docker');
    const args = connect.lastMileArgs(cachedState({ plans, routes, cache: null, dataSource: 'live' }), NOW);
    expect(args.ok && args.args.mock).toBe(false);
    const items = messagesOf(args);
    let computed = 0;
    for (const fm of items) {
      expect(fm.violations, fm.originId).toEqual([]);
      expect(fm.plan.input.provenance.source).toBe('live');
      for (const t of everyText(fm)) expect(t, fm.originId).not.toMatch(/사전 계산|Precomputed/);
      if (fm.plan.input.plan?.sweep.some((c) => c.attempts.length)) {
        computed += 1;
        expect(fm.plan.input.testData, fm.originId).toBe(true);
        expect(fm.text.ko.lms).toContain('· 실시간 API 계산 · 계산 호스트 Linux x86_64 · 4 vCPU');
        expect(fm.text.ko.sms.split('\n')[0]).toContain('시험자료');
        expect(fm.text.ko.card.badges).toContain('시험 데이터 · 평가 호스트 아님');
      } else {
        // nothing was computed for it: no "computed on another host" claim
        expect(fm.plan.input.testData, fm.originId).toBe(false);
      }
    }
    expect(computed).toBeGreaterThan(50);
  }, 60_000);

  it('with the default MOCK build setting the same session is marked MOCK (the planner\'s session-wide rule), still never "사전 계산"', () => {
    const { plans, routes } = liveSession(LINUX, 'mockenv');
    const items = messagesOf(lastMileArgs(cachedState({ plans, routes, cache: null, dataSource: 'live' }), NOW));
    for (const fm of items) {
      expect(fm.plan.input.mock).toBe(true);
      expect(fm.violations, fm.originId).toEqual([]);
      for (const t of everyText(fm)) expect(t).not.toMatch(/사전 계산|Precomputed/);
      expect(fm.text.ko.sms.split('\n')[0]).toContain('MOCK');
    }
  }, 60_000);
});
