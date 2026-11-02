/**
 * Public static demo (VITE_WFG_API_MODE=static) under the GitHub Pages base path "/wildfireguardian/",
 * run against the COMMITTED data: a stubbed fetch serves planner/public/** and planner/cache/** from
 * disk (what `npm run build:static` copies into dist/) and records every URL the app asks for.
 * No network.
 *
 * - no request ever goes to the Route-Check API, 127.0.0.1, localhost or another origin, and every
 *   request the UI makes is answered by a committed file (the only 404 allowed is the optional
 *   temporary_housing.geojson);
 * - every scenario of the cache loads; the verdicts on screen are exactly the recorded verdicts of
 *   planner/cache/INDEX.json; every route detail and travel-time-only comparison is served from the
 *   cache; live computation (recompute, batches, drawn-zone checks, forecast cells) sends nothing;
 * - the same-origin guard, base-path helpers and demo texts (intro ≤ 80 words, no e-mail address).
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

const PLANNER = fileURLToPath(new URL('../../planner/', import.meta.url));
const REPO = fileURLToPath(new URL('../../', import.meta.url));
const BASE = '/wildfireguardian/';
const PAGE = 'https://sparkxt-0318.github.io/wildfireguardian/';

interface Seen {
  url: string;
  status: number;
}
const seen: Seen[] = [];

const MIME: Record<string, string> = { json: 'application/json', geojson: 'application/geo+json', pmtiles: 'application/octet-stream', pbf: 'application/x-protobuf', png: 'image/png' };

/** Serves <BASE>cache/** from planner/cache and every other <BASE>** from planner/public. */
function serveCommittedFile(input: RequestInfo | URL): Promise<Response> {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  let status = 404;
  let body: ArrayBuffer | null = null;
  let type = 'text/plain';
  if (url.startsWith(BASE)) {
    const rel = decodeURIComponent(url.slice(BASE.length).split(/[?#]/)[0]!);
    const parts = rel.split('/');
    const file = parts[0] === 'cache' ? join(PLANNER, 'cache', ...parts.slice(1)) : join(PLANNER, 'public', ...parts);
    if (!parts.some((p) => p === '..' || p.startsWith('.')) && existsSync(file) && statSync(file).isFile()) {
      status = 200;
      body = new Uint8Array(readFileSync(file)).buffer;
      type = MIME[rel.split('.').pop() ?? ''] ?? 'application/octet-stream';
    }
  }
  seen.push({ url, status });
  return Promise.resolve(new Response(status === 200 ? body : 'not found', { status, headers: { 'Content-Type': type } }));
}

type Mods = {
  env: typeof import('../../planner/src/config/env');
  paths: typeof import('../../planner/src/config/paths');
  client: typeof import('../../planner/src/api/client');
  controller: typeof import('../../planner/src/state/controller');
  store: typeof import('../../planner/src/state/store');
  selectors: typeof import('../../planner/src/state/selectors');
  labels: typeof import('../../planner/src/domain/labels');
};
let m: Mods;
const fetchStub = vi.fn(serveCommittedFile);

beforeAll(async () => {
  vi.stubEnv('VITE_WFG_API_MODE', 'static');
  vi.stubEnv('BASE_URL', BASE);
  vi.stubGlobal('fetch', fetchStub);
  vi.resetModules();
  m = {
    env: await import('../../planner/src/config/env'),
    paths: await import('../../planner/src/config/paths'),
    client: await import('../../planner/src/api/client'),
    controller: await import('../../planner/src/state/controller'),
    store: await import('../../planner/src/state/store'),
    selectors: await import('../../planner/src/state/selectors'),
    labels: await import('../../planner/src/domain/labels'),
  };
});

afterAll(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

interface IndexEntry {
  region_id: string;
  scenario_set_id: string;
  input_time: string;
  path: string;
  checks: number;
  verdicts: Record<string, number>;
}
const INDEX: IndexEntry[] = JSON.parse(readFileSync(join(PLANNER, 'cache', 'INDEX.json'), 'utf8'));

function forbidden(url: string): boolean {
  return /127\.0\.0\.1|localhost|\/api\/|^[a-z]+:\/\/|^\/\//i.test(url);
}

describe('static mode configuration', () => {
  it('builds in static mode under the Pages base path', () => {
    expect(m.env.CONFIG.apiMode).toBe('static');
    expect(m.env.STATIC_DEMO).toBe(true);
    expect(m.paths.BASE_URL).toBe(BASE);
    expect(m.paths.appPath('data/regions/index.json')).toBe('/wildfireguardian/data/regions/index.json');
    // the static bundle never offers the VWorld internet raster and has no API target
    expect(m.env.CONFIG.vworldKey).toBeNull();
    expect(m.env.CONFIG.apiTarget).toBe('');
  });
  it('`vite build --mode static` and VITE_WFG_API_MODE=static both select the static mode', () => {
    expect(m.env.resolveApiMode({ MODE: 'static' })).toBe('static');
    expect(m.env.resolveApiMode({ MODE: 'production', VITE_WFG_API_MODE: 'static' })).toBe('static');
    expect(m.env.resolveApiMode({ MODE: 'production', VITE_WFG_API_MODE: 'real' })).toBe('real');
    expect(m.env.resolveApiMode({ MODE: 'development' })).toBe('mock');
    expect(m.labels.parseApiMode('STATIC')).toBe('static');
  });
  it('the static mode alone never shows the MOCK badge; mock results still do', () => {
    expect(m.labels.mockActive({ envMode: 'static', healthMock: false, resultsMock: false })).toBe(false);
    expect(m.labels.mockActive({ envMode: 'static', healthMock: false, resultsMock: true })).toBe(true);
  });
  it('feedback goes to the bilingual issue template of the repository (no e-mail address)', () => {
    expect(m.env.CONFIG.feedbackUrl).toBe('https://github.com/Sparkxt-0318/wildfireguardian/issues/new?template=planner-feedback.md');
    const tpl = readFileSync(join(REPO, '.github', 'ISSUE_TEMPLATE', 'planner-feedback.md'), 'utf8');
    expect(tpl).toMatch(/^---\nname: /);
    for (const q of ['역할', 'Role', '지역', 'Region', '이해하기 어려웠던', 'unclear', '쓸 수 있으려면', 'usable']) expect(tpl).toContain(q);
  });
});

describe('static API client: nothing is ever sent', () => {
  it('every endpoint rejects with STATIC_DEMO without calling fetch', async () => {
    const before = fetchStub.mock.calls.length;
    const { api, STATIC_DEMO_CODE } = m.client;
    const calls: Promise<unknown>[] = [
      api.health(),
      api.regions(),
      api.forecast('uiseong_andong_2025', '2025-03-24T09:00:00Z'),
      api.submitRouteCheck({} as never),
      api.routeCheck('rc_1'),
      api.submitDispatch({} as never),
      api.dispatch('dp_1'),
    ];
    for (const c of calls) await expect(c).rejects.toMatchObject({ code: STATIC_DEMO_CODE, status: 0 });
    expect(fetchStub.mock.calls.length).toBe(before);
  });
});

describe('static data flow against the committed cache', () => {
  it('serves every scenario, route and comparison from committed files only', async () => {
    const { controller, store, selectors } = m;
    seen.length = 0;
    // the controller must never even try the API client in static mode (not only be refused by it)
    const apiSpies = (Object.keys(m.client.api) as (keyof typeof m.client.api)[]).map((k) => vi.spyOn(m.client.api, k));
    await controller.initApp();
    let s = store.getState();
    expect(s.apiStatus).toBe('offline');
    expect(s.apiError?.code).toBe('STATIC_DEMO');
    expect(s.health).toBeNull();
    // only regions with recorded results are offered
    const cachedRegions = [...new Set(INDEX.map((e) => e.region_id))].sort();
    expect(s.regionIndex.map((r) => r.id).sort()).toEqual(cachedRegions);

    let routeChecks = 0;
    for (const region of cachedRegions) {
      await controller.selectRegion(region);
      for (const e of INDEX.filter((x) => x.region_id === region)) {
        await controller.selectScenario(e.scenario_set_id);
        s = store.getState();
        expect(s.dataSource, e.path).toBe('cache');
        expect(s.cache?.meta.entry.path).toBe(e.path);
        // the evaluated-host booth cache: neither MOCK nor test data
        expect(s.cache?.meta.mock).toBe(false);
        expect(s.cache?.meta.testData).toBe(false);
        expect(selectors.isMockActive(s)).toBe(false);
        // the forecast layer needs the API: unavailable, nothing requested
        expect(s.forecast.state).toBe('unavailable');

        // every recorded route check is served from the cache
        const doc = JSON.parse(readFileSync(join(PLANNER, 'cache', ...e.path.split('/')), 'utf8')) as { route_checks: Record<string, unknown> };
        const ids = Object.keys(doc.route_checks);
        expect(ids.length).toBe(e.checks);
        routeChecks += ids.length;
        for (const id of ids) expect(selectors.routeById(s, id), `${e.path} ${id}`).not.toBeNull();

        // the verdicts on screen are exactly the recorded ones (INDEX.json totals)
        const counts: Record<string, number> = {};
        for (const p of Object.values(s.plans)) {
          for (const c of p.sweep) {
            for (const a of c.attempts) {
              const k = a.verdict === 'unresolved' ? `unresolved/${a.reasonCode}` : a.verdict;
              counts[k] = (counts[k] ?? 0) + 1;
            }
          }
        }
        expect(counts, e.path).toEqual(e.verdicts);

        // every origin of the scenario has a plan; selecting it needs no request
        const origins = s.places.filter((p) => p.role === 'origin' || (p.role === 'research_origin' && p.scenarioSetId === e.scenario_set_id));
        const requestsBefore = seen.length;
        for (const o of origins) {
          const plan = store.getState().plans[o.id];
          expect(plan, o.id).toBeDefined();
          controller.selectOrigin(o.id);
          await Promise.resolve();
          const st = store.getState();
          if (plan!.bestVerdict === 'checked_route') {
            expect(plan!.latestSafeDepartureS).not.toBeNull();
            expect(selectors.routeById(st, plan!.best!.jobId)?.verdict).toBe('checked_route');
            // the travel-time-only comparison comes from the cache, never from a request
            expect(st.travelOnly[o.id]?.state, o.id).toBe('ready');
            expect(st.travelOnly[o.id]?.source).toBe('cache');
          } else {
            expect(plan!.latestSafeDepartureS).toBeNull();
          }
        }
        expect(seen.length).toBe(requestsBefore);
      }
    }
    expect(routeChecks).toBe(INDEX.reduce((n, e) => n + e.checks, 0));

    // live computation is not offered and sends nothing
    const before = seen.length;
    const calls = fetchStub.mock.calls.length;
    const anyOrigin = store.getState().places.find((p) => p.role === 'origin' && p.checkable)!;
    await controller.recomputeOrigin(anyOrigin.id);
    controller.prepareBatch();
    await controller.startBatch();
    await controller.ensureTravelOnly(anyOrigin.id, true);
    await controller.loadForecast();
    expect(store.getState().recompute).toBeNull();
    expect(store.getState().batch.state).toBe('idle');
    expect(fetchStub.mock.calls.length).toBe(calls);
    expect(seen.length).toBe(before);

    // drawn spread zones: editing works (recorded footprints are static files), checking does not
    await controller.selectScenario(store.DRAWN_SCENARIO, { preset: true });
    await vi.waitFor(() => expect(store.getState().drawn.footprints.state).toBe('ready'));
    controller.applyDefaultPreset();
    s = store.getState();
    expect(selectors.drawnReadiness(s).problems).toEqual(['api_offline']);
    const drawnFetches = fetchStub.mock.calls.length;
    await controller.recomputeOrigin(anyOrigin.id);
    controller.prepareDrawnBatch();
    await controller.startDrawnBatch();
    expect(fetchStub.mock.calls.length).toBe(drawnFetches);
    expect(store.getState().batch.state).toBe('idle');
    expect(Object.values(store.getState().plans).every((p) => p.bestVerdict !== 'checked_route')).toBe(true);
    expect(apiSpies.map((s) => s.mock.calls.length)).toEqual(apiSpies.map(() => 0));
    for (const s of apiSpies) s.mockRestore();

    // every request: same-origin, under the base, never the API; answered by a committed file
    expect(seen.length).toBeGreaterThan(0);
    for (const r of seen) {
      expect(forbidden(r.url), r.url).toBe(false);
      expect(r.url.startsWith(BASE), r.url).toBe(true);
      if (r.status !== 200) expect(r.url, 'only the optional temporary housing file may be missing').toMatch(/\/temporary_housing\.geojson$/);
    }
    const paths = new Set(seen.map((r) => r.url.slice(BASE.length)));
    const expected = new Set([
      'data/regions/index.json',
      'cache/INDEX.json',
      ...INDEX.map((e) => `cache/${e.path}`),
      ...cachedRegions.flatMap((r) => [`data/regions/${r}/places.geojson`, `data/regions/${r}/temporary_housing.geojson`]),
    ]);
    const drawnRegion = store.getState().regionId!;
    expected.add(`data/regions/${drawnRegion}/footprints.geojson`);
    expect([...paths].sort()).toEqual([...expected].sort());
  }, 120_000);
});

describe('same-origin guard', async () => {
  const { guardUrl, installFetchGuard } = await import('../../planner/src/config/sameOrigin');
  const ctx = { pageHref: `${PAGE}?region=x#scenario=y`, appDir: BASE, block: true };

  it('blocks every request that would leave the origin or reach an API', () => {
    for (const url of [
      'http://127.0.0.1:8765/v1/health',
      'http://localhost:5173/api/v1/regions',
      'http://localhost/x.json',
      'https://api.vworld.kr/req/wmts/1.0.0/KEY/gray/1/1/1.png',
      '//cdn.example.com/x.js',
      'https://sparkxt-0318.github.io.evil.example/wildfireguardian/data/x.json',
      'http://sparkxt-0318.github.io/wildfireguardian/data/regions/index.json',
      'ws://sparkxt-0318.github.io/wildfireguardian/socket',
      '/api/v1/health',
      '/wildfireguardian/api/v1/route-checks',
      'api/v1/dispatch-plans',
    ]) {
      expect(guardUrl(url, ctx).action, url).toBe('block');
    }
  });
  it('moves root-absolute app paths under the base (a generated public/data file needs no code change)', () => {
    expect(guardUrl('/data/explanations/uiseong_andong_2025__20250324T090000Z.json', ctx)).toEqual({
      action: 'rewrite',
      url: '/wildfireguardian/data/explanations/uiseong_andong_2025__20250324T090000Z.json',
    });
    expect(guardUrl('/cache/INDEX.json?x=1', ctx)).toEqual({ action: 'rewrite', url: '/wildfireguardian/cache/INDEX.json?x=1' });
    expect(guardUrl('/basemap/fonts/Noto%20Sans%20Regular/0-255.pbf', ctx).action).toBe('rewrite');
  });
  it('passes same-origin files under the base and local data:/blob: URLs', () => {
    for (const url of [
      '/wildfireguardian/cache/INDEX.json',
      'https://sparkxt-0318.github.io/wildfireguardian/data/regions/index.json',
      'data/regions/yeongdeok_2025/places.geojson',
      'data:application/json,{}',
      'blob:https://sparkxt-0318.github.io/0b5f5c0e-0000-4000-8000-000000000000',
    ]) {
      expect(guardUrl(url, ctx).action, url).toBe('pass');
    }
  });
  it('outside the static demo nothing is blocked (booth modes talk to their API)', () => {
    expect(guardUrl('http://127.0.0.1:8765/v1/health', { ...ctx, block: false }).action).toBe('pass');
    expect(guardUrl('/api/v1/health', { ...ctx, block: false }).action).toBe('pass');
    expect(guardUrl('/data/x.json', { ...ctx, appDir: '/', block: false }).action).toBe('pass');
  });
  it('the installed guard rewrites, blocks before sending, and uninstalls', async () => {
    const underlying = vi.fn((input: RequestInfo | URL) => Promise.resolve(new Response(String(input))));
    const target = { fetch: underlying as unknown as typeof fetch, location: { href: PAGE } };
    const uninstall = installFetchGuard({ block: true, appDir: BASE, target });
    await expect(target.fetch('http://127.0.0.1:8765/v1/health')).rejects.toBeInstanceOf(TypeError);
    await expect(target.fetch('/api/v1/regions')).rejects.toThrow(/static demo/);
    expect(underlying).not.toHaveBeenCalled();
    await target.fetch('/data/explanations/a__b.json');
    expect(underlying).toHaveBeenLastCalledWith('/wildfireguardian/data/explanations/a__b.json', undefined);
    uninstall();
    expect(target.fetch).toBe(underlying);
  });
  it('is not installed when there is nothing to guard (booth mode at "/")', () => {
    const underlying = vi.fn() as unknown as typeof fetch;
    const target = { fetch: underlying, location: { href: 'http://127.0.0.1:5173/' } };
    installFetchGuard({ block: false, appDir: '/', target });
    expect(target.fetch).toBe(underlying);
  });
});

describe('base-path helpers', async () => {
  const { normalizeBase, appPath, appUrl, appDirPath } = await import('../../planner/src/config/paths');
  it('normalises the base setting', () => {
    expect(normalizeBase(undefined)).toBe('/');
    expect(normalizeBase('/')).toBe('/');
    expect(normalizeBase('wildfireguardian')).toBe('/wildfireguardian/');
    expect(normalizeBase('/wildfireguardian')).toBe('/wildfireguardian/');
    expect(normalizeBase('./')).toBe('./');
    expect(normalizeBase('.')).toBe('./');
  });
  it('builds fetch paths and absolute MapLibre URLs (template tokens unescaped)', () => {
    expect(appPath('/cache/INDEX.json', '/wildfireguardian/')).toBe('/wildfireguardian/cache/INDEX.json');
    expect(appPath('data/x.json', './')).toBe('./data/x.json');
    expect(appUrl('basemap/fonts/{fontstack}/{range}.pbf', '/wildfireguardian/', `${PAGE}?a=1#b`)).toBe(
      'https://sparkxt-0318.github.io/wildfireguardian/basemap/fonts/{fontstack}/{range}.pbf',
    );
    // a relative base resolves against the page: the same build works under any path
    expect(appUrl('basemap/uiseong_andong_2025.pmtiles', './', 'https://example.org/demo/planner/index.html')).toBe('https://example.org/demo/planner/basemap/uiseong_andong_2025.pmtiles');
    expect(appDirPath('./', 'https://example.org/demo/planner/index.html')).toBe('/demo/planner/');
    expect(appDirPath('/wildfireguardian/', PAGE)).toBe('/wildfireguardian/');
  });
  it('fetchAppJson reads any committed public/data file under the base, null when it does not exist', async () => {
    const regions = await m.paths.fetchAppJson<{ region_id: string }[]>('data/regions/index.json');
    expect(Array.isArray(regions) && regions.some((r) => r.region_id === 'yeongdeok_2025')).toBe(true);
    expect(await m.paths.fetchAppJson('data/explanations/not_generated__20250324T090000Z.json')).toBeNull();
    expect(seen.at(-1)?.url).toBe('/wildfireguardian/data/explanations/not_generated__20250324T090000Z.json');
  });
  it('the static demo lists only regions with recorded results (all when the cache is empty)', () => {
    const regions = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
    expect(m.controller.regionsWithResults(regions, [{ regionId: 'b' }, { regionId: 'b' }])).toEqual([{ id: 'b' }]);
    expect(m.controller.regionsWithResults(regions, [])).toEqual(regions);
  });
});

describe('demo texts', async () => {
  const { translate } = await import('../../planner/src/i18n');
  const { periodLabel, joinNames, localRunUrl } = await import('../../planner/src/components/demo/StaticDemo');
  const { preferredLanguage } = await import('../../planner/src/components/demo/language');
  const { introDismissed, rememberIntroDismissed } = await import('../../planner/src/components/demo/DemoIntro');
  const { DEMO_STRINGS } = await import('../../planner/src/components/demo/strings');
  const words = (s: string) => s.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;

  it('the DEMO chip names the recorded period from the cache index (March 2025)', () => {
    const times = INDEX.map((e) => e.input_time);
    expect(periodLabel(times, (k, v) => translate('en', k, v))).toBe('March 2025');
    expect(periodLabel(times, (k, v) => translate('ko', k, v))).toBe('2025년 3월');
    expect(translate('en', 'demo.chipText', { period: 'March 2025' })).toBe('recorded March 2025 scenarios · research prototype');
    expect(periodLabel([], (k, v) => translate('en', k, v))).toBeNull();
  });
  it('the introduction stays within 80 words in both languages (title + text + the three verdicts)', () => {
    for (const lang of ['ko', 'en'] as const) {
      const t = (k: string, v?: Record<string, string | number>) => translate(lang, k, v);
      const period = periodLabel(INDEX.map((e) => e.input_time), t)!;
      const regions = joinNames(lang === 'en' ? ['Uiseong–Andong', 'Yeongdeok'] : ['의성·안동', '영덕'], lang);
      const text = [t('demo.intro.title'), t('demo.intro.body', { period, regions }), t('verdict.checked_route'), t('verdict.model_no_route'), t('verdict.unresolved')].join(' ');
      expect(words(text), `${lang}: ${text}`).toBeLessThanOrEqual(80);
      expect(text).not.toMatch(/\{\w+\}/);
    }
  });
  it('never calls a route safe and never calls scenarios simulations of the actual fire', () => {
    for (const lang of ['ko', 'en'] as const) {
      for (const [k, v] of Object.entries(DEMO_STRINGS[lang])) {
        expect(v, k).not.toMatch(/\bsafe\b|안전한|안전 경로|simulation|시뮬레이션/i);
        expect(v, k).not.toMatch(/[\w.+-]+@[\w-]+\.[\w.]+/); // no e-mail address
      }
    }
    expect(Object.keys(DEMO_STRINGS.ko).sort()).toEqual(Object.keys(DEMO_STRINGS.en).sort());
  });
  it('links the local-run instructions of the README', () => {
    expect(localRunUrl('https://github.com/Sparkxt-0318/wildfireguardian')).toBe('https://github.com/Sparkxt-0318/wildfireguardian/blob/HEAD/planner/README.md#real-route-check-api');
    const readme = readFileSync(join(PLANNER, 'README.md'), 'utf8');
    expect(readme).toMatch(/^### Real Route-Check API$/m);
  });
  it('first visit: Korean browsers get Korean, everyone else English', () => {
    expect(preferredLanguage(['ko-KR', 'en-US'])).toBe('ko');
    expect(preferredLanguage(['en-US', 'ko'])).toBe('ko');
    expect(preferredLanguage(['en-GB'])).toBe('en');
    expect(preferredLanguage(['kok-IN'])).toBe('en');
    expect(preferredLanguage(undefined)).toBe('en');
  });
  it('remembers the dismissed introduction, and survives blocked storage', () => {
    const mem = new Map<string, string>();
    const storage = { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v) };
    expect(introDismissed(storage)).toBe(false);
    rememberIntroDismissed(storage);
    expect(introDismissed(storage)).toBe(true);
    const blocked = {
      getItem: () => {
        throw new Error('SecurityError');
      },
      setItem: () => {
        throw new Error('QuotaExceededError');
      },
    };
    expect(introDismissed(blocked)).toBe(false);
    expect(() => rememberIntroDismissed(blocked)).not.toThrow();
  });
});

describe('demo assets in the repository', () => {
  it('every file the static build ships from planner/public and planner/cache is < 50 MB', () => {
    const big: string[] = [];
    const walk = (dir: string) => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const p = join(dir, e.name);
        if (e.isDirectory()) walk(p);
        else if (statSync(p).size >= 50 * 1024 * 1024) big.push(p);
      }
    };
    walk(join(PLANNER, 'public'));
    walk(join(PLANNER, 'cache'));
    expect(big).toEqual([]);
  });
});
