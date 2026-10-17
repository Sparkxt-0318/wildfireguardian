/**
 * Client-side exports (planner/src/features/exports). All data here is SYNTHETIC test data
 * ("합성" names, round coordinates) — not villages, shelters or results of any region.
 */
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';
import {
  assertExportable,
  CSV_BOM,
  CSV_COLUMNS,
  csvField,
  dispatchListCSV,
  exportFileName,
  ExportRefusedError,
  isExportable,
  orderOrigins,
  routeToGeoJSON,
  routeToKML,
} from '../../planner/src/features/exports/exports';
import type { ExportInput, ExportOrigin, ExportRoute } from '../../planner/src/features/exports/types';

// jsdom is loaded with Node's resolver from planner/ (the tests live outside the Vite root).
const { JSDOM } = createRequire(new URL('../../planner/package.json', import.meta.url))('jsdom') as {
  JSDOM: new (html?: string, opts?: Record<string, unknown>) => { window: Window & typeof globalThis };
};

const PROV = {
  checkpoint: 'c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843',
  packageVersion: '1.0.0',
  kit: 'v3',
  apiMode: 'cache' as const,
  cacheApiMode: 'mock' as const,
  apiVersion: '1.5.0',
  gitCommit: 'synthetic0000',
  cacheCreatedAtIso: '2026-10-17T00:00:00Z',
  scenarioSetId: 'synthetic:set:0',
  scenarioIds: ['synthetic:set:0:0', 'synthetic:set:0:1', 'synthetic:set:0:2', 'synthetic:set:0:3'],
};

const ORIGIN = { id: 'test:origin:a', name: '합성 마을 A', categoryLabel: '마을', sourceTag: 'place=village', lon: 127.0, lat: 36.0 };
const SHELTER = { id: 'test:shelter:1', name: '합성 대피소 & "1" <학교>', categoryLabel: '학교', sourceTag: 'amenity=school', lon: 127.01, lat: 36.01 };

function route(over: Partial<ExportRoute> = {}): ExportRoute {
  return {
    role: 'evacuation_route',
    origin: ORIGIN,
    shelter: SHELTER,
    verdict: 'checked_route',
    policy: 'full',
    departureS: 600,
    arrivalS: 1500,
    dwellEndS: 1620,
    coordinates: [
      [127.0, 36.0],
      [127.005, 36.004],
      [127.01, 36.01],
    ],
    timesS: [600, 1000, 1500],
    lengthM: 1500,
    exposure: [{ scenarioId: 'synthetic:set:0:0', peakKwM2: 0.5, doseKjM2: 2, contact: false }],
    computeS: 1.0,
    jobId: 'rc_synthetic',
    ...over,
  };
}

function origin(id: string, name: string | null, plan: ExportOrigin['plan'], extra: Partial<ExportOrigin> = {}): ExportOrigin {
  return { id, name, categoryLabel: '마을', sourceTag: 'place=village', lon: 127, lat: 36, vulnerable: false, plan, ...extra };
}

function input(over: Partial<ExportInput> = {}): ExportInput {
  return {
    region: { id: 'test_region', nameKo: '합성 지역', nameEn: 'Synthetic region', fireYear: 2025 },
    fireInputLabel: '2025년 실제 산불 기록 기반 시나리오 재현',
    fireInputType: 'recorded',
    mock: true,
    scenario: { scenarioSetId: 'synthetic:set:0', inputTimeIso: '2025-03-24T09:00:00Z' },
    origins: [
      origin('o:checked-late', '합성 마을 늦음', {
        bestVerdict: 'checked_route',
        latestSafeDepartureS: 3000,
        contiguousSafeDepartureS: 1800,
        best: { shelter: SHELTER, departureS: 3000, arrivalS: 3500 },
      }),
      origin('o:noroute', '합성, 마을 "경로없음"', { bestVerdict: 'model_no_route', latestSafeDepartureS: null, contiguousSafeDepartureS: null, best: null }),
      origin('o:unresolved', '합성 마을\n미확인', {
        bestVerdict: 'unresolved',
        latestSafeDepartureS: null,
        contiguousSafeDepartureS: null,
        best: null,
        reasonCode: 'TIMEOUT',
      }),
      origin('o:checked-early', '=합성 마을 이름', {
        bestVerdict: 'checked_route',
        latestSafeDepartureS: 600,
        contiguousSafeDepartureS: 600,
        best: { shelter: SHELTER, departureS: 600, arrivalS: 1500 },
      }),
      origin('o:none', null, null, { vulnerable: true, categoryLabel: '요양시설', sourceTag: 'amenity=nursing_home' }),
    ],
    selectedRoute: route(),
    comparisonRoute: route({ role: 'travel_only_comparison', policy: 'travel_only', fullPolicyPass: false, fullPolicyFailures: ['FLAME'], arrivalS: 1300 }),
    provenance: PROV,
    generatedAtIso: '2026-10-17T09:00:00Z',
    ...over,
  };
}

// The vitest config runs tests in the node environment; a local jsdom gives us a standards DOMParser.
const DOMParser = new JSDOM('').window.DOMParser;

/** Minimal RFC 4180 parser for the round-trip check. */
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let i = 0;
  let quoted = false;
  while (i < text.length) {
    const c = text[i]!;
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i += 2;
        continue;
      }
      if (c === '"') {
        quoted = false;
        i += 1;
        continue;
      }
      field += c;
      i += 1;
      continue;
    }
    if (c === '"') {
      quoted = true;
      i += 1;
    } else if (c === ',') {
      row.push(field);
      field = '';
      i += 1;
    } else if (c === '\r' && text[i + 1] === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
      i += 2;
    } else {
      field += c;
      i += 1;
    }
  }
  if (field !== '' || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

describe('routeToGeoJSON', () => {
  it('emits a valid FeatureCollection with the route, origin and shelter', () => {
    const fc = routeToGeoJSON(input(), undefined, { comparison: null });
    expect(fc.type).toBe('FeatureCollection');
    expect(fc.features.map((f) => f.geometry.type)).toEqual(['LineString', 'Point', 'Point']);
    const line = fc.features[0]!;
    expect(line.geometry.type).toBe('LineString');
    const coords = (line.geometry as GeoJSON.LineString).coordinates;
    const p = line.properties as Record<string, unknown>;
    expect(coords.length).toBe((p.times_s as number[]).length);
    for (const c of coords) {
      expect(c.length).toBe(2);
      expect(c[0]).toBeGreaterThanOrEqual(-180);
      expect(c[0]).toBeLessThanOrEqual(180);
      expect(c[1]).toBeGreaterThanOrEqual(-90);
      expect(c[1]).toBeLessThanOrEqual(90);
    }
    expect(p.verdict).toBe('checked_route');
    expect(p.role).toBe('evacuation_route');
    expect(p.evacuation_route).toBe(true);
    expect(p.arrival_s).toBe(1500);
    expect(p.arrival_kst).toBe('2025-03-24 18:25');
    expect(p.departure_kst).toBe('2025-03-24 18:10');
    expect(p.fire_input_label).toBe('2025년 실제 산불 기록 기반 시나리오 재현');
    expect((p.provenance as Record<string, unknown>).checkpoint).toBe(PROV.checkpoint);
    expect(fc.provenance).toBeTruthy();
    expect((fc.wfg as Record<string, unknown>).mock).toBe(true);
    expect(String(fc.name)).toContain('MOCK');
    // JSON round trip keeps it identical (no undefined / NaN)
    expect(JSON.parse(JSON.stringify(fc))).toEqual(fc);
    const roles = fc.features.map((f) => (f.properties as Record<string, unknown>).role);
    expect(roles).toEqual(['evacuation_route', 'origin', 'shelter']);
  });

  it('omits MOCK from the name when the data is not mock', () => {
    const fc = routeToGeoJSON(input({ mock: false }));
    expect(String(fc.name).includes('MOCK')).toBe(false);
  });

  it('labels a travel-only comparison as a comparison with its verdict fields', () => {
    const inp = input();
    const fc = routeToGeoJSON(inp, inp.selectedRoute, { comparison: inp.comparisonRoute });
    const cmp = fc.features.find((f) => (f.properties as Record<string, unknown>).role === 'travel_only_comparison');
    expect(cmp).toBeTruthy();
    const p = cmp!.properties as Record<string, unknown>;
    expect(p.evacuation_route).toBe(false);
    expect(p.policy).toBe('travel_only');
    expect(p.verdict).toBe('checked_route');
    expect(p.full_policy_pass).toBe(false);
    expect(String(p.note)).toContain('대피 경로 아님');
  });

  it('refuses anything but a checked route', () => {
    for (const verdict of ['model_no_route', 'unresolved'] as const) {
      const r = route({ verdict });
      expect(isExportable(r)).toBe(false);
      try {
        routeToGeoJSON(input({ selectedRoute: r }));
        expect.unreachable('should refuse');
      } catch (e) {
        expect(e).toBeInstanceOf(ExportRefusedError);
        expect((e as ExportRefusedError).code).toBe('NO_CHECKED_ROUTE');
      }
      expect(() => routeToKML(input({ selectedRoute: r }))).toThrow(ExportRefusedError);
    }
    expect(() => routeToGeoJSON(input({ selectedRoute: null }))).toThrow(/no route selected/);
  });

  it('refuses a travel-only route presented as an evacuation route, and bad geometry', () => {
    expect(() => assertExportable(route({ policy: 'travel_only' }))).toThrow(/full policy/);
    expect(() => assertExportable(route({ role: 'travel_only_comparison', policy: 'full' }))).toThrow(ExportRefusedError);
    expect(() => assertExportable(route({ coordinates: [[127, 36]], timesS: [0] }))).toThrow(/two finite/);
    expect(() => assertExportable(route({ timesS: [0, 1] }))).toThrow(/times_s/);
    const inp = input();
    // a comparison must be passed as role travel_only_comparison
    expect(() => routeToGeoJSON(inp, inp.selectedRoute, { comparison: route() })).toThrow(ExportRefusedError);
  });
});

describe('routeToKML', () => {
  it('is well-formed KML 2.2 with styles, placemarks and extended data', () => {
    const inp = input();
    const kml = routeToKML(inp, inp.selectedRoute, { comparison: inp.comparisonRoute });
    const doc = new DOMParser().parseFromString(kml, 'application/xml');
    expect(doc.getElementsByTagName('parsererror').length).toBe(0);
    const root = doc.documentElement;
    expect(root.localName).toBe('kml');
    expect(root.namespaceURI).toBe('http://www.opengis.net/kml/2.2');
    const name = doc.querySelector('Document > name')!.textContent!;
    expect(name).toContain('MOCK');
    expect(name).toContain('합성 대피소 & "1" <학교>');
    expect(doc.getElementsByTagName('Style').length).toBeGreaterThanOrEqual(4);
    const placemarks = Array.from(doc.getElementsByTagName('Placemark'));
    expect(placemarks.length).toBe(4);
    const lines = doc.getElementsByTagName('LineString');
    expect(lines.length).toBe(2);
    const coords = lines[0]!.getElementsByTagName('coordinates')[0]!.textContent!.trim().split(/\s+/);
    expect(coords.length).toBe(3);
    expect(coords[0]).toBe('127,36,0');
    const data = Array.from(doc.getElementsByTagName('Data')).map((d) => [d.getAttribute('name'), d.textContent]);
    expect(data).toContainEqual(['fire_input_label', '2025년 실제 산불 기록 기반 시나리오 재현']);
    expect(data).toContainEqual(['verdict', 'checked_route']);
    expect(data.some(([k, v]) => k === 'provenance_checkpoint' && v === PROV.checkpoint)).toBe(true);
    const roles = Array.from(doc.getElementsByTagName('Data'))
      .filter((d) => d.getAttribute('name') === 'role')
      .map((d) => d.textContent);
    expect(roles).toContain('travel_only_comparison');
    expect(roles).toContain('evacuation_route');
  });

  it('has no MOCK marker when not mock', () => {
    const kml = routeToKML(input({ mock: false }));
    const doc = new DOMParser().parseFromString(kml, 'application/xml');
    expect(doc.getElementsByTagName('parsererror').length).toBe(0);
    expect(doc.querySelector('Document > name')!.textContent!.includes('MOCK')).toBe(false);
  });
});

describe('dispatchListCSV', () => {
  it('has a UTF-8 BOM, the documented columns and CRLF rows', () => {
    const csv = dispatchListCSV(input());
    expect(csv.startsWith(CSV_BOM)).toBe(true);
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    const body = csv.slice(1);
    expect(body.endsWith('\r\n')).toBe(true);
    const rows = parseCsv(body);
    expect(rows[0]).toEqual(CSV_COLUMNS.ko);
    expect(rows[0]).toEqual([
      '우선순위',
      '출발지',
      '구분',
      '출처 태그',
      '판정',
      '출발 마감 KST',
      '연속 확인 기준',
      '대피소',
      '도착 KST',
      '시나리오 입력 시각',
      'API 모드',
      '비고',
    ]);
    expect(rows.length).toBe(1 + 5);
    for (const r of rows) expect(r.length).toBe(12);
  });

  it('quotes per RFC 4180 and round-trips names with commas, quotes and newlines', () => {
    expect(csvField('a,b')).toBe('"a,b"');
    expect(csvField('say "hi"')).toBe('"say ""hi"""');
    expect(csvField('line1\nline2')).toBe('"line1\nline2"');
    expect(csvField('plain')).toBe('plain');
    expect(csvField('=SUM(A1)')).toBe("'=SUM(A1)");
    const rows = parseCsv(dispatchListCSV(input()).slice(1));
    const names = rows.slice(1).map((r) => r[1]);
    expect(names).toContain('합성, 마을 "경로없음"');
    expect(names).toContain('합성 마을\n미확인');
    expect(names).toContain("'=합성 마을 이름");
  });

  it('orders by urgency and never gives an unresolved origin a deadline', () => {
    const rows = parseCsv(dispatchListCSV(input()).slice(1)).slice(1);
    const ids = rows.map((r) => r[3]!.split(' · ')[1]);
    // model_no_route → unresolved (vulnerable first, then name) → checked by deadline ascending
    expect(ids).toEqual(['o:noroute', 'o:none', 'o:unresolved', 'o:checked-early', 'o:checked-late']);
    expect(rows.map((r) => r[0])).toEqual(['1', '2', '3', '4', '5']);
    const byId = Object.fromEntries(rows.map((r) => [r[3]!.split(' · ')[1], r]));
    const unresolved = byId['o:unresolved']!;
    expect(unresolved[4]).toBe('미확인');
    expect(unresolved[5]).toBe('');
    expect(unresolved[11]).toContain('판단 불가 — 안전으로 간주하지 말 것');
    expect(unresolved[11]).toContain('TIMEOUT');
    expect(byId['o:none']![4]).toBe('미확인');
    expect(byId['o:none']![5]).toBe('');
    const noroute = byId['o:noroute']!;
    expect(noroute[4]).toBe('모델상 경로 없음');
    expect(noroute[11]).toContain('차량 대피 경로를 확인하지 못함');
    const late = byId['o:checked-late']!;
    expect(late[4]).toBe('확인된 경로');
    expect(late[5]).toBe('2025-03-24 18:50');
    expect(late[6]).toBe('2025-03-24 18:30');
    expect(late[8]).toBe('2025-03-24 18:58');
    expect(late[9]).toBe('2025-03-24 18:00 KST');
    expect(late[10]).toBe('사전 계산 캐시 (MOCK)');
    expect(late[11]).toContain('MOCK');
  });

  it('uses the API urgency rank when every origin has one', () => {
    const inp = input();
    const ranked = inp.origins.map((o, i) => ({ ...o, urgencyRank: inp.origins.length - i }));
    expect(orderOrigins(ranked).map((o) => o.id)).toEqual(ranked.map((o) => o.id).reverse());
  });

  it('has an English header variant', () => {
    const rows = parseCsv(dispatchListCSV(input(), { lang: 'en' }).slice(1));
    expect(rows[0]).toEqual(CSV_COLUMNS.en);
    expect(rows.slice(1).some((r) => r[4] === 'Unresolved')).toBe(true);
  });
});

describe('exportFileName', () => {
  it('marks MOCK files and names the scenario', () => {
    const inp = input();
    expect(exportFileName(inp, 'dispatch', 'csv')).toBe('wfg_test_region_20250324T090000Z_dispatch_MOCK.csv');
    expect(exportFileName(inp, 'route', 'geojson', 'osm:node/1')).toBe('wfg_test_region_20250324T090000Z_osm-node-1_route_MOCK.geojson');
    expect(exportFileName(input({ mock: false }), 'route', 'kml', 'x').includes('MOCK')).toBe(false);
  });
});
