/**
 * Plan sheet (planner/src/features/plansheet). All data here is SYNTHETIC test data
 * ("합성" names, round coordinates) — not villages, shelters or results of any region.
 *
 * The vitest config runs tests in the node environment, so the render tests install a local
 * jsdom window first and import React DOM and the dialog afterwards.
 */
import { createRequire } from 'node:module';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import { alternativePlanItems, deadlineCell, drawableRoute, exposureSummary, partialCheckedScenarios } from '../../planner/src/features/plansheet/sheetLogic';
import type { PlanSheetData, PlanSheetScenario } from '../../planner/src/features/plansheet/types';
import { ALT_PLAN_TEXT, LIMITATIONS, NOTE_LABEL } from '../../planner/src/features/shared/strings';
import { ENTRY_LIMIT_M, planFromAttempts } from '../../planner/src/domain/plan';
import type { Attempt, Place } from '../../planner/src/domain/types';
import { scenarioRow } from '../../planner/src/state/featureData';
import { translate } from '../../planner/src/i18n';

// jsdom is loaded with Node's resolver from planner/ (the tests live outside the Vite root).
const { JSDOM } = createRequire(new URL('../../planner/package.json', import.meta.url))('jsdom') as {
  JSDOM: new (html?: string, opts?: Record<string, unknown>) => { window: Window & typeof globalThis };
};

function installDom(): InstanceType<typeof JSDOM> {
  const dom = new JSDOM('<!doctype html><html lang="ko"><head></head><body></body></html>', {
    url: 'http://127.0.0.1/',
    pretendToBeVisual: true,
  });
  const w = dom.window as unknown as Record<string, unknown>;
  const g = globalThis as unknown as Record<string, unknown>;
  for (const k of [
    'window',
    'document',
    'navigator',
    'HTMLElement',
    'HTMLDivElement',
    'Element',
    'Node',
    'Text',
    'SVGElement',
    'Event',
    'KeyboardEvent',
    'MouseEvent',
    'getComputedStyle',
    'requestAnimationFrame',
    'cancelAnimationFrame',
    'DOMParser',
  ]) {
    Object.defineProperty(g, k, { value: k === 'window' ? dom.window : w[k], configurable: true, writable: true });
  }
  return dom;
}

const LINE = (coords: [number, number][]) => ({
  type: 'Feature' as const,
  properties: {},
  geometry: { type: 'LineString' as const, coordinates: coords },
});

function scenario(i: number, over: Partial<PlanSheetScenario>): PlanSheetScenario {
  return {
    scenarioSetId: `synthetic:set:${i}`,
    inputTimeIso: '2025-03-24T09:00:00Z',
    bestVerdict: 'checked_route',
    latestSafeDepartureS: 1800,
    contiguousSafeDepartureS: 1200,
    sweep: [
      { offsetS: 0, verdict: 'checked_route' },
      { offsetS: 600, verdict: 'checked_route' },
      { offsetS: 1200, verdict: 'checked_route' },
      { offsetS: 1800, verdict: 'checked_route' },
      { offsetS: 2400, verdict: 'unresolved' },
      { offsetS: 3000, verdict: 'window_closed' },
    ],
    shelter: { id: 'test:shelter:1', name: '합성 대피소 1', sourceTag: 'amenity=school', lon: 127.01, lat: 36.01, arrivalS: 2600 },
    route: LINE([
      [127.0, 36.0],
      [127.005, 36.006],
      [127.01, 36.01],
    ]),
    travelOnlyRoute: null,
    exposure: [
      { scenarioId: 'm0', peakKwM2: 0.2, doseKjM2: 1.5, contact: false },
      { scenarioId: 'm1', peakKwM2: 0.9, doseKjM2: 3.25, contact: false },
      { scenarioId: 'm2', peakKwM2: 0.0001, doseKjM2: 0.5, contact: false },
      { scenarioId: 'm3', peakKwM2: 0.4, doseKjM2: 2, contact: false },
    ],
    computeS: 1.2,
    host: 'synthetic host',
    reasonCode: null,
    ...over,
  };
}

function sheet(id: string, scenarios: PlanSheetScenario[], over: Partial<PlanSheetData> = {}): PlanSheetData {
  return {
    region: { id: 'test_region', nameKo: '합성 지역', nameEn: 'Synthetic region', fireYear: 2025 },
    fireInputLabel: '2025년 실제 산불 기록 기반 시나리오 재현',
    mock: true,
    origin: {
      id,
      name: `합성 마을 ${id}`,
      categoryLabel: '마을',
      sourceTag: 'place=village',
      lon: 127.0,
      lat: 36.0,
      snapDistanceM: 42,
      vulnerable: false,
    },
    facilities: [{ id: 'test:fac:1', name: null, categoryLabel: '요양시설', sourceTag: 'amenity=nursing_home', distanceM: 350 }],
    scenarios,
    generatedAtIso: '2026-10-17T09:00:00Z',
    provenance: {
      checkpoint: 'c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843',
      packageVersion: '1.0.0',
      kit: 'v3',
      apiMode: 'cache',
      apiVersion: '1.5.0',
      cacheCreatedAtIso: '2026-10-17T00:00:00Z',
      gitCommit: 'synthetic0000',
      cacheApiMode: 'mock',
    },
    ...over,
  };
}

const MIXED = sheet('A', [
  scenario(0, {}),
  scenario(1, {
    bestVerdict: 'model_no_route',
    latestSafeDepartureS: null,
    contiguousSafeDepartureS: null,
    shelter: null,
    // a geometry passed by mistake for a non-checked scenario must never be drawn
    route: LINE([
      [127.0, 36.0],
      [126.99, 35.99],
    ]),
    exposure: [],
    sweep: [
      { offsetS: 0, verdict: 'model_no_route' },
      { offsetS: 600, verdict: 'model_no_route' },
    ],
  }),
  scenario(2, {
    bestVerdict: 'unresolved',
    latestSafeDepartureS: null,
    contiguousSafeDepartureS: null,
    shelter: null,
    route: null,
    exposure: [],
    reasonCode: 'OTHER',
    sweep: [
      { offsetS: 0, verdict: 'unresolved' },
      { offsetS: 600, verdict: 'model_no_route' },
    ],
  }),
]);

describe('alternativePlanItems', () => {
  it('lists exactly the scenarios whose best verdict is not checked_route', () => {
    const items = alternativePlanItems(MIXED, 'ko');
    expect(items.map((x) => x.scenarioSetId)).toEqual(['synthetic:set:1', 'synthetic:set:2']);
    expect(items.map((x) => x.verdict)).toEqual(['model_no_route', 'unresolved']);
    expect(items[0]!.text).toBe('차량 대피 경로를 확인하지 못함: 조기 대피 또는 실내 대피(대피 장소 사전 지정) 등 대안 필요');
    expect(items[1]!.text).toBe('판단 불가 — 안전으로 간주하지 말 것');
    expect(items[1]!.reason).toContain('OTHER');
    expect(alternativePlanItems(sheet('B', [scenario(0, {})]), 'ko')).toEqual([]);
  });

  it('never words unresolved as safe (ko and en)', () => {
    for (const lang of ['ko', 'en'] as const) {
      const text = ALT_PLAN_TEXT.unresolved[lang];
      if (lang === 'ko') {
        expect(text).toContain('안전으로 간주하지 말 것');
        expect(/안전/.test(text.replace('안전으로 간주하지 말 것', ''))).toBe(false);
      } else {
        expect(text).toMatch(/do not treat as safe/i);
        expect(/safe/i.test(text.replace(/do not treat as safe/i, ''))).toBe(false);
      }
    }
  });
});

describe('partially checked scenarios', () => {
  it('a checked scenario whose earlier departures are unresolved is flagged, never "covered"', () => {
    const partial = sheet('P', [scenario(0, { latestSafeDepartureS: 600, contiguousSafeDepartureS: null })]);
    expect(alternativePlanItems(partial, 'ko')).toEqual([]);
    expect(partialCheckedScenarios(partial).map((x) => [x.tag, x.deadline, x.contiguous])).toEqual([['S1', '18:10', null]]);
    const full = sheet('F', [scenario(0, { latestSafeDepartureS: 1800, contiguousSafeDepartureS: 1800 })]);
    expect(partialCheckedScenarios(full)).toEqual([]);
  });
});

describe('limitations wording', () => {
  it('states the real entry-point rule (no "300 m") and the entry-point gap', () => {
    const km = String(ENTRY_LIMIT_M / 1000);
    for (const lang of ['ko', 'en'] as const) {
      expect(NOTE_LABEL.not_checkable[lang]).toContain(km);
      expect(NOTE_LABEL.not_checkable[lang]).not.toContain('300');
      const limit = LIMITATIONS.find((l) => l.id === 'entry_limit')!;
      expect(limit.text[lang]).toContain(km);
      expect(limit.short[lang]).toContain(km);
      expect(limit.text[lang]).not.toContain('300');
    }
    expect(LIMITATIONS.some((l) => l.id === 'snap_300')).toBe(false);
    const ids = LIMITATIONS.map((l) => l.id);
    expect(ids).toContain('entry_gap');
    expect(ids.indexOf('entry_gap')).toBe(ids.indexOf('traffic') + 1);
  });
});

describe('scenario rows without a checked route', () => {
  const t = (k: string, v?: Record<string, string | number>) => translate('ko', k, v);
  const origin: Place = {
    id: 'osm:node/1', role: 'origin', category: 'village', name: '합성 마을', nameEn: null, lon: 127, lat: 36, source: 'OpenStreetMap', sourceTag: 'place=village',
    osm: { type: 'node', id: 1 }, snapNode: 'osm:1', snapDistanceM: 10, entry: { node: 'osm:1', lon: 127, lat: 36, distanceM: 10, withinApiLonlatSnap: true },
    checkable: true, vulnerable: false, scenarioSetId: null, inputTime: null, caseId: null, recorded: null,
  };
  const a = (offsetS: number, verdict: Attempt['verdict'], computeS: number | null, rawStatus: string | null, reasonCode: string | null): Attempt => ({ offsetS, destinationId: 'd', verdict, arrivalS: null, computeS, jobId: `j${offsetS}`, reasonCode, rawStatus });
  const attempts = [
    a(0, 'model_no_route', 9.31, 'PROVEN_INFEASIBLE', null),
    a(600, 'unresolved', null, 'MOCK_NO_RECORDED_RESULT', 'OTHER'),
    a(1200, 'unresolved', null, 'MOCK_NO_RECORDED_RESULT', 'OTHER'),
  ];
  const plan = planFromAttempts({ originId: origin.id, offsetsS: [0, 600, 1200], attempts, source: 'live', mock: true });
  const row = scenarioRow(
    { scenarioSetId: 'synthetic:set', inputTimeIso: '2025-03-25T19:00:00Z', issuedAtIso: null, plans: { [origin.id]: plan }, route: () => null, travelOnly: () => null, hostFallback: null },
    origin,
    new Map([[origin.id, origin]]),
    t,
  );
  it('carries the compute time of the earliest check and its departure (no route needed)', () => {
    expect(row.bestVerdict).toBe('unresolved');
    expect(row.computeS).toBe(9.31);
    expect(row.computeOffsetS).toBe(0);
    expect(row.host).toBeNull(); // never invented
    expect(row.rawStatus).toBe('MOCK_NO_RECORDED_RESULT');
  });
  it('the alternative-plan reason lists the recorded no-route time and the MOCK status (not "기타 (OTHER)")', () => {
    const items = alternativePlanItems(sheet('R', [row]), 'ko');
    expect(items).toHaveLength(1);
    expect(items[0]!.reason).toContain('04:00 모델상 경로 없음');
    expect(items[0]!.reason).toContain('04:10–04:20 미확인');
    expect(items[0]!.reason).toContain('MOCK_NO_RECORDED_RESULT');
    expect(items[0]!.reason).not.toContain('기타');
  });
});

describe('sheet helpers', () => {
  it('formats the deadline with the contiguous basis', () => {
    const d = deadlineCell(scenario(0, {}), 'ko');
    expect(d.main).toBe('18:30');
    expect(d.sub).toBe('연속 확인 기준 18:20');
    expect(deadlineCell(scenario(0, { contiguousSafeDepartureS: 1800 }), 'ko').sub).toBe('연속 확인 기준 동일');
    expect(deadlineCell(scenario(0, { contiguousSafeDepartureS: null }), 'ko').sub).toBe('연속 확인 기준 없음');
    // unresolved never gets a deadline even if a number is passed by mistake
    expect(deadlineCell(scenario(0, { bestVerdict: 'unresolved', latestSafeDepartureS: 600 }), 'ko').main).toBe('—');
  });

  it('summarises exposure as the maximum over the four hazard scenarios', () => {
    const e = exposureSummary(scenario(0, {}))!;
    expect(e.members).toBe(4);
    expect(e.maxPeak).toBe(0.9);
    expect(e.maxDose).toBe(3.25);
    expect(e.anyContact).toBe(false);
    expect(exposureSummary(MIXED.scenarios[1]!)).toBeNull();
  });

  it('draws a route only for checked_route', () => {
    expect(drawableRoute(MIXED.scenarios[0]!) === null).toBe(false);
    expect(drawableRoute(MIXED.scenarios[1]!)).toBeNull();
    expect(drawableRoute(MIXED.scenarios[2]!)).toBeNull();
  });
});

describe('PlanSheetDialog (jsdom render)', () => {
  // Minimal local typings: the test tsconfig resolves neither React's types nor TSX, so React and
  // the dialog are loaded at runtime only (Node resolver for React, a runtime path for the dialog).
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
  let PlanSheetDialog: unknown;
  let host: HTMLDivElement | null = null;
  let root: RootLike | null = null;

  beforeAll(async () => {
    installDom();
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    const req = createRequire(new URL('../../planner/package.json', import.meta.url));
    React = req('react') as ReactLike;
    createRoot = (req('react-dom/client') as { createRoot: (el: Element) => RootLike }).createRoot;
    const dialogPath = '../../planner/src/features/plansheet/PlanSheetDialog';
    PlanSheetDialog = ((await import(/* @vite-ignore */ dialogPath)) as { PlanSheetDialog: unknown }).PlanSheetDialog;
  });

  afterEach(async () => {
    if (root) await React.act(() => root!.unmount());
    host?.remove();
    root = null;
    host = null;
  });

  async function render(sheets: PlanSheetData[], lang: 'ko' | 'en' = 'ko') {
    host = document.createElement('div');
    host.id = 'app-root';
    document.body.appendChild(host);
    root = createRoot(host);
    await React.act(async () => {
      root!.render(React.createElement(PlanSheetDialog, { open: true, onClose: () => {}, sheets, lang, forceSvgMaps: true, prepareAll: true }));
    });
    await React.act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });
    return document.querySelector<HTMLElement>('.wfgf-plansheet-root')!;
  }

  it('renders one A4 sheet per origin with the fire input, MOCK and footer', async () => {
    const dlg = await render([MIXED, sheet('B', [scenario(0, {})])]);
    expect(dlg).toBeTruthy();
    const pages = dlg.querySelectorAll('.wfgf-sheet');
    expect(pages.length).toBe(2);
    const first = pages[0] as HTMLElement;
    expect(first.textContent).toContain('기관용 사전 대피계획서');
    expect(first.textContent).toContain('2025년 실제 산불 기록 기반 시나리오 재현');
    expect(first.querySelector('[data-mock-badge]')?.textContent).toBe('MOCK');
    expect(first.textContent).toContain('사전 계획 보조 자료 · 실시간 대피 지휘용 아님 · 주민 검증 전');
    expect(first.textContent).toContain('1 / 2쪽');
    expect(first.textContent).toContain('amenity=nursing_home');
    // print scope + readiness hooks for the PDF script
    expect(dlg.getAttribute('data-print-scope')).toBe('all');
    expect(dlg.getAttribute('data-wfg-sheets-ready')).toBe('true');
    // app chrome is excluded from print by the html class
    expect(document.documentElement.classList.contains('wfgf-printing-sheets')).toBe(true);
  });

  it('lists exactly the non-checked scenarios under 대체 계획 필요 시나리오', async () => {
    const dlg = await render([MIXED]);
    const alt = Array.from(dlg.querySelectorAll<HTMLElement>('[data-alt-scenario]'));
    expect(alt.map((li) => li.dataset.altScenario)).toEqual(['synthetic:set:1', 'synthetic:set:2']);
    expect(alt[0]!.textContent).toContain('차량 대피 경로를 확인하지 못함: 조기 대피 또는 실내 대피(대피 장소 사전 지정) 등 대안 필요');
    expect(alt[1]!.textContent).toContain('판단 불가 — 안전으로 간주하지 말 것');
    expect(alt[1]!.querySelector('[data-verdict-icon]')!.getAttribute('data-verdict-icon')).toBe('unresolved');
    expect(dlg.querySelector('[data-alt-none]')).toBeNull();
  });

  it('never shows an unresolved row as safe or with a deadline', async () => {
    const dlg = await render([MIXED]);
    const row = dlg.querySelector<HTMLElement>('tr[data-verdict="unresolved"]')!;
    expect(row).toBeTruthy();
    expect(row.querySelector('[data-verdict-icon="checked_route"]')).toBeNull();
    expect(row.querySelector('[data-verdict-icon="unresolved"]') === null).toBe(false);
    expect(row.textContent).toContain('미확인');
    expect(/확인된 경로|안전합니다|\bsafe\b/.test(row.textContent ?? '')).toBe(false);
    const cells = row.querySelectorAll('td');
    expect(cells[2]!.textContent).toBe('—');
    expect(cells[4]!.textContent).toBe('—');
  });

  it('draws only checked routes on the (SVG fallback) map', async () => {
    const dlg = await render([MIXED]);
    const svg = dlg.querySelector('[data-map-fallback="svg"]')!;
    expect(svg).toBeTruthy();
    const green = Array.from(svg.querySelectorAll('path')).filter((p) => p.getAttribute('stroke') === '#1A9E55');
    expect(green.length).toBe(1);
  });

  it('says so when every scenario has a checked route', async () => {
    const dlg = await render([sheet('B', [scenario(0, {})])]);
    expect(dlg.querySelector('[data-alt-none]') === null).toBe(false);
    expect(dlg.querySelectorAll('[data-alt-scenario]').length).toBe(0);
  });

  it('a partially checked scenario gets a grey caveat instead of "출발 마감 전 출발 전제"', async () => {
    const dlg = await render([sheet('P', [scenario(0, { latestSafeDepartureS: 600, contiguousSafeDepartureS: null })])]);
    const caveat = dlg.querySelector<HTMLElement>('[data-alt-caveat]')!;
    expect(caveat).toBeTruthy();
    expect(caveat.textContent).toContain('S1');
    expect(caveat.textContent).toContain('미확인');
    expect(caveat.textContent).toContain('연속 확인 기준 없음');
    expect(caveat.querySelector('[data-verdict-icon]')!.getAttribute('data-verdict-icon')).toBe('unresolved');
    expect(dlg.textContent).not.toContain('출발 마감 전 출발 전제');
  });

  it('keeps "출발 마감 전 출발 전제" when every departure up to the deadline is checked', async () => {
    const dlg = await render([sheet('F', [scenario(0, { latestSafeDepartureS: 1800, contiguousSafeDepartureS: 1800 })])]);
    expect(dlg.querySelector('[data-alt-caveat]')).toBeNull();
    expect(dlg.querySelector('[data-alt-none]')!.textContent).toContain('출발 마감 전 출발 전제');
  });

  it('renders the entry-point limitation and labels the entry distance as not modelled', async () => {
    const dlg = await render([sheet('E', [scenario(0, {})], { origin: { ...MIXED.origin, id: 'E', snapDistanceM: 1191, entryKind: 'village' } })]);
    expect(dlg.querySelector('[data-limit="entry_gap"]')).toBeTruthy();
    expect(dlg.querySelector('[data-limit="entry_limit"]')!.textContent).toContain('2 km');
    const fact = dlg.querySelector<HTMLElement>('[data-entry-fact]')!;
    expect(fact.textContent).toContain('마을 진입 지점까지');
    expect(fact.textContent).toContain('1.2 km');
    expect(fact.textContent).toContain('이 구간 미반영');
    expect(fact.textContent).not.toContain('예상');
  });

  it('renders the English variant', async () => {
    const dlg = await render([MIXED], 'en');
    expect(dlg.textContent).toContain('Undetermined — do not treat as safe');
    expect(dlg.textContent).toContain('Pre-season evacuation plan');
  });
});

describe('AboutPanel (jsdom render)', () => {
  interface ReactLike {
    createElement: (type: unknown, props: Record<string, unknown>) => unknown;
    act: (fn: () => unknown) => Promise<void> | void;
  }
  it('lists the entry-point limitations', async () => {
    installDom();
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    const req = createRequire(new URL('../../planner/package.json', import.meta.url));
    const React = req('react') as ReactLike;
    const { createRoot } = req('react-dom/client') as { createRoot: (el: Element) => { render: (el: unknown) => void; unmount: () => void } };
    const aboutPath = '../../planner/src/features/about/AboutPanel';
    const { AboutPanel } = (await import(/* @vite-ignore */ aboutPath)) as { AboutPanel: unknown };
    const host = document.createElement('div');
    document.body.appendChild(host);
    const root = createRoot(host);
    await React.act(async () => {
      root.render(React.createElement(AboutPanel, { open: true, onClose: () => {}, lang: 'ko' }));
    });
    const panel = document.querySelector('[data-testid="about-panel"]')!;
    expect(panel.querySelector('[data-limit="entry_gap"]')).toBeTruthy();
    expect(panel.querySelector('[data-limit="entry_limit"]')!.textContent).toContain('2 km');
    expect(panel.textContent).not.toContain('300 m');
    await React.act(() => root.unmount());
    host.remove();
  });
});
