/**
 * 25 March 2025 replay in the planner (research/kcf-replay → planner/src/data/replayPacks.ts,
 * planner/src/features/replay): pack index loading, the witness route on every place-hour that has
 * one, the six-place file against the committed CSV and RESULTS.md §4, the reported times kept apart
 * from outcomes, and the MEASURED hook.
 */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { cacheToModel, isTestDataHost, parseCacheIndex } from '../../planner/src/api/cache';
import type { WireCacheFile } from '../../planner/src/api/wire';
import { REPLAY_PACKS, availablePacks, packCacheDir, packOfScenario } from '../../planner/src/data/replayPacks';
import { bestCheckedAttempt, deadlineHeadline } from '../../planner/src/domain/plan';
import type { Attempt } from '../../planner/src/domain/types';
import { packSets, parseNamedPlaces, type NamedPlacesDoc } from '../../planner/src/features/replay/data';
// @ts-expect-error plain ES module script without types
import { buildNamedPlaces, kstToUtc, parseCsv } from '../../planner/scripts/build_replay_named_places.mjs';

const PLANNER = fileURLToPath(new URL('../../planner/', import.meta.url));
const REPO = fileURLToPath(new URL('../../', import.meta.url));
const RUNNING = REPLAY_PACKS.find((p) => p.id === 'kcf-replay-RUNNING_8h')!;
const PACK_DIR = join(PLANNER, String(RUNNING.source));
const RAW_INDEX = JSON.parse(readFileSync(join(PACK_DIR, 'INDEX.json'), 'utf8')) as { region_id: string; scenario_set_id: string; path: string; input_time: string }[];
const NAMED_FILE = join(PLANNER, 'public', String(RUNNING.namedPlaces));
const NAMED = JSON.parse(readFileSync(NAMED_FILE, 'utf8')) as NamedPlacesDoc;

describe('replay pack registry', () => {
  it('RUNNING, MEASURED and MEASURED+GUST (provisional) are available; nothing is pending', () => {
    expect(availablePacks().map((p) => p.id)).toEqual(['kcf-replay-RUNNING_8h', 'kcf-replay-MEASURED_8h', 'kcf-replay-MEASURED_GUST_8h']);
    expect(REPLAY_PACKS.filter((p) => p.status === 'pending')).toEqual([]);
    expect(REPLAY_PACKS.filter((p) => p.provisional).map((p) => p.standin)).toEqual(['MEASURED_GUST']);
    for (const p of availablePacks()) {
      expect(p.namedPlaces, p.id).not.toBeNull();
      expect(p.source, p.id).not.toBeNull();
    }
  });

  it('scenario ids map to their pack by prefix; booth ids map to none', () => {
    expect(packOfScenario('kcf-replay:RUNNING:8h:20250325T030000Z')?.id).toBe('kcf-replay-RUNNING_8h');
    // MEASURED's prefix must not swallow MEASURED_GUST
    expect(packOfScenario('kcf-replay:MEASURED:8h:20250325T030000Z')?.id).toBe('kcf-replay-MEASURED_8h');
    expect(packOfScenario('kcf-replay:MEASURED_GUST:8h:20250325T030000Z')?.id).toBe('kcf-replay-MEASURED_GUST_8h');
    expect(packOfScenario('ffb1:20250325T190000Z:abc')).toBeNull();
    expect(packOfScenario(null)).toBeNull();
  });
});

describe('pack index', () => {
  const entries = parseCacheIndex(RAW_INDEX, RUNNING);

  it('13 issue hours (12:00–24:00 KST) per region, paths under cache/packs/<id>/, tagged with the pack', () => {
    expect(entries).toHaveLength(26);
    for (const region of ['uiseong_andong_2025', 'yeongdeok_2025']) {
      const mine = entries.filter((e) => e.regionId === region).map((e) => e.inputTime).sort();
      expect(mine).toHaveLength(13);
      expect(mine[0]).toBe('2025-03-25T03:00:00Z');
      expect(mine[12]).toBe('2025-03-25T15:00:00Z');
    }
    for (const e of entries) {
      expect(e.pack).toBe(RUNNING.id);
      expect(e.path.startsWith(`${packCacheDir(RUNNING.id)}/`)).toBe(true);
    }
  });

  it('drops an entry that is not a replay scenario (a pack never adds booth scenarios)', () => {
    const extra = [...RAW_INDEX, { region_id: 'yeongdeok_2025', scenario_set_id: 'ffb1:20250325T190000Z:x', path: 'x.json', input_time: '2025-03-25T19:00:00Z' }];
    expect(parseCacheIndex(extra, RUNNING)).toHaveLength(26);
  });

  it('booth entries stay untagged; pack sets are listed by issue time, booth sets left out', () => {
    expect(parseCacheIndex(RAW_INDEX).every((e) => e.pack === undefined)).toBe(true);
    const sets = entries
      .filter((e) => e.regionId === 'yeongdeok_2025')
      .reverse()
      .map((e) => ({ id: e.scenarioSetId, inputTime: e.inputTime, scenarioIds: [], horizonS: null, hazardSha256: null, source: 'cache' as const, pack: e.pack }));
    sets.push({ id: 'ffb1:20250325T190000Z:x', inputTime: '2025-03-25T19:00:00Z', scenarioIds: [], horizonS: null, hazardSha256: null, source: 'cache', pack: undefined });
    const mine = packSets(sets, RUNNING.id);
    expect(mine).toHaveLength(13);
    expect(mine.map((s) => s.inputTime)).toEqual([...mine.map((s) => s.inputTime)].sort());
  });
});

describe('evidence tie-break (route line)', () => {
  const a = (dest: string, jobId: string | null, arrivalS: number | null = null): Attempt => ({ offsetS: 0, destinationId: dest, verdict: 'checked_route', arrivalS, computeS: null, jobId, reasonCode: null });

  it('with unknown arrivals, the checked attempt whose route is stored wins over an earlier destination id', () => {
    expect(bestCheckedAttempt([a('A', null), a('B', 'job-b')])?.destinationId).toBe('B');
  });

  it('a known earlier arrival still wins (booth results are unchanged)', () => {
    expect(bestCheckedAttempt([a('A', 'job-a', 100), a('B', 'job-b', 50)])?.destinationId).toBe('B');
    expect(bestCheckedAttempt([a('A', 'job-a', 50), a('B', 'job-b', 50)])?.destinationId).toBe('A');
  });
});

interface CsvRow { region: string; place_id: string; issue_kst: string; standin: string; horizon: string; departure_state: string; latest_safe_departure_kst: string; last_departure_in_horizon_kst: string }
const CSV: CsvRow[] = (() => {
  const text = readFileSync(join(REPO, 'research/kcf-replay/per_place.csv'), 'utf8');
  return parseCsv(text) as CsvRow[];
})();

describe.each(availablePacks().map((p) => [p.id, p] as const))('replay cache %s in the planner model', (_id, pack) => {
  const dir = join(PLANNER, String(pack.source));
  const entries = parseCacheIndex(JSON.parse(readFileSync(join(dir, 'INDEX.json'), 'utf8')), pack);

  it('13 issue hours in both regions; every place-hour matches per_place.csv on the 30-minute grid and draws its witness route', () => {
    expect(entries).toHaveLength(26);
    const rows = new Map(CSV.filter((r) => r.standin === pack.standin && r.horizon === pack.horizon).map((r) => [`${r.region}|${r.place_id}|${kstToUtc(r.issue_kst)}`, r]));
    let cut = 0;
    let compared = 0;
    for (const e of entries) {
      const doc = JSON.parse(readFileSync(join(dir, ...e.path.slice(packCacheDir(pack.id).length + 1).split('/')), 'utf8')) as WireCacheFile;
      const model = cacheToModel(doc, e);
      expect(model.meta.testData).toBe(true);
      expect(isTestDataHost(model.meta.computeHost, false)).toBe(true);
      const T = Date.parse(e.inputTime);
      const last = Math.max(...model.offsetsS);
      for (const plan of Object.values(model.plans)) {
        const row = rows.get(`${e.regionId}|${plan.originId}|${e.inputTime.replace(/\.\d+Z$/, 'Z')}`);
        expect(row, `${e.scenarioSetId} ${plan.originId}`).toBeDefined();
        compared += 1;
        // the latest checked grid departure is the field's latest safe departure rounded down to the grid
        if (row!.departure_state === 'LATEST_SAFE_DEPARTURE') {
          cut += 1;
          const ldS = (Date.parse(kstToUtc(row!.latest_safe_departure_kst)!) - T) / 1000;
          const want = Math.min(last, Math.floor(ldS / 1800) * 1800);
          if (ldS >= 0) expect(plan.latestSafeDepartureS, `${e.scenarioSetId} ${plan.originId}`).toBe(want);
        } else if (row!.departure_state === 'NOT_CUT_WITHIN_H') {
          // no road cut inside the horizon: the last departure that still arrives (plus the dwell) within it
          const lastS = (Date.parse(kstToUtc(row!.last_departure_in_horizon_kst)!) - T) / 1000;
          expect(plan.latestSafeDepartureS, `${e.scenarioSetId} ${plan.originId}`).toBe(Math.min(last, Math.floor(lastS / 1800) * 1800));
        } else {
          expect(plan.bestVerdict, `${e.scenarioSetId} ${plan.originId} ${row!.departure_state}`).not.toBe('checked_route');
        }
        // wherever a leave-by time is shown, its witness route is drawable
        const h = deadlineHeadline(plan);
        if (h.kind !== 'deadline' || h.deadlineS === null) continue;
        const cell = plan.sweep.find((c) => c.offsetS === h.deadlineS)!;
        const route = cell.best?.jobId ? model.route(cell.best.jobId) : null;
        expect(route?.verdict, `${e.scenarioSetId} ${plan.originId}`).toBe('checked_route');
        expect(route?.coordinates?.length ?? 0).toBeGreaterThan(1);
      }
    }
    // 174 places × 13 hours; RESULTS.md §5 place-hours with a latest safe departure, 8 h: RUNNING 1,093, MEASURED 349, MEASURED+GUST 492
    expect(compared).toBe(2262);
    expect(cut).toBe({ RUNNING: 1093, MEASURED: 349, MEASURED_GUST: 492 }[pack.standin]);
  }, 120_000);
});

describe('six named places (RESULTS.md §4)', () => {
  it.each(availablePacks().map((p) => [p.id, p] as const))('%s: the committed file is exactly what the generator writes from per_place.csv', (_id, pack) => {
    const buf = readFileSync(join(REPO, 'research/kcf-replay/per_place.csv'));
    const doc = buildNamedPlaces({
      csvText: buf.toString('utf8'),
      csvSha256: createHash('sha256').update(buf).digest('hex'),
      reported: JSON.parse(readFileSync(join(PLANNER, 'scripts/kcf_reported_times.json'), 'utf8')),
      standin: pack.standin,
      horizon: pack.horizon,
      pack: pack.id,
    });
    const file = join(PLANNER, 'public', String(pack.namedPlaces));
    expect(`${JSON.stringify(doc, null, 1)}\n`).toBe(readFileSync(file, 'utf8'));
    const named = JSON.parse(readFileSync(file, 'utf8'));
    expect(parseNamedPlaces(named, pack.id)).not.toBeNull();
    expect(parseNamedPlaces(named, 'other-pack')).toBeNull();
  });

  it('MEASURED and MEASURED+GUST match their RESULTS.md §4 tables (8 h, 16:00–21:00 KST; "+1" = 26 March)', () => {
    const tables: Record<string, Record<string, (string | null)[]>> = {
      MEASURED: {
        화매리: ['not cut', 'not cut', '20:27', null, null, null],
        지품리: ['not cut', 'not cut', '18:19', null, null, null],
        옥류리: ['not cut', 'not cut', 'not cut', '20:54', '20:51', null],
        매정리: ['not cut', 'not cut', 'not cut', 'not cut', 'not cut', '22:50'],
        노물리: ['not cut', 'not cut', 'not cut', 'not cut', 'not cut', '23:36'],
        강구리: ['not cut', 'not cut', 'not cut', 'not cut', 'not cut', '+1 00:26'],
      },
      MEASURED_GUST: {
        화매리: ['not cut', 'not cut', '20:10', null, null, null],
        지품리: ['not cut', '23:51', '18:16', null, null, null],
        옥류리: ['not cut', 'not cut', '+1 01:46', '20:41', '20:45', null],
        매정리: ['not cut', 'not cut', 'not cut', 'not cut', '+1 03:27', '22:37'],
        노물리: ['not cut', 'not cut', 'not cut', 'not cut', 'not cut', '23:17'],
        강구리: ['not cut', 'not cut', 'not cut', 'not cut', 'not cut', '+1 00:02'],
      },
    };
    const hours = ['16:00', '17:00', '18:00', '19:00', '20:00', '21:00'].map((h) => kstToUtc(`03-25 ${h}`));
    for (const [standin, table] of Object.entries(tables)) {
      const pack = availablePacks().find((p) => p.standin === standin)!;
      const named = JSON.parse(readFileSync(join(PLANNER, 'public', String(pack.namedPlaces)), 'utf8')) as NamedPlacesDoc;
      for (const p of named.places) {
        hours.forEach((iu, i) => {
          const h = p.hours.find((x) => x.issue_utc === iu)!;
          const want = table[p.name]![i]!;
          const where = `${standin} ${p.name} ${iu}`;
          if (want === null) expect(h.state, where).toBe('INSIDE_KNOWN_FIRE_AREA');
          else if (want === 'not cut') expect(h.state, where).toBe('NOT_CUT_WITHIN_H');
          else expect(h.latest_safe_departure_utc, where).toBe(kstToUtc(want.startsWith('+1 ') ? `03-26 ${want.slice(3)}` : `03-25 ${want}`));
        });
      }
    }
  });

  it('matches the RESULTS.md §4 table (RUNNING, 8 h, 16:00–21:00 KST)', () => {
    const table: Record<string, (string | null)[]> = {
      화매리: ['18:47', '18:38', '18:25', null, null, null],
      지품리: ['18:33', '18:18', '18:03', null, null, null],
      옥류리: ['19:58', '19:41', '19:24', '19:19', '20:07', null],
      매정리: ['21:10', '20:53', '20:36', '20:37', '21:21', '21:17'],
      노물리: ['21:19', '21:02', '20:46', '20:46', '21:30', '21:26'],
      강구리: ['20:44', '20:32', '20:25', '20:42', '21:29', '21:37'],
    };
    const hours = ['16:00', '17:00', '18:00', '19:00', '20:00', '21:00'].map((h) => kstToUtc(`03-25 ${h}`));
    expect(NAMED.places.map((p) => p.name)).toEqual(Object.keys(table));
    for (const p of NAMED.places) {
      hours.forEach((iu, i) => {
        const h = p.hours.find((x) => x.issue_utc === iu)!;
        const want = table[p.name]![i];
        if (want === null) expect(h.state, `${p.name} ${iu}`).toBe('INSIDE_KNOWN_FIRE_AREA');
        else expect(h.latest_safe_departure_utc, `${p.name} ${iu}`).toBe(kstToUtc(`03-25 ${want}`));
      });
    }
    expect(NAMED.issue_hours_utc).toHaveLength(13);
  });

  it('places are the planner origins of the same region (selectable on the map)', () => {
    const places = JSON.parse(readFileSync(join(PLANNER, 'public/data/regions', NAMED.region_id, 'places.geojson'), 'utf8')) as { features: { properties: { id: string; name: string; role: string } }[] };
    for (const p of NAMED.places) {
      const f = places.features.find((x) => x.properties.id === p.place_id);
      expect(f?.properties.name).toBe(p.name);
      expect(f?.properties.role).toBe('origin');
    }
  });

  it('reported times carry a source (outlet, date, https link) and the single-source flag; none is stored as a replay result', () => {
    for (const p of NAMED.places) {
      expect(p.reported.length, p.name).toBeGreaterThan(0);
      for (const r of p.reported) {
        expect(r.source.url).toMatch(/^https:\/\//);
        expect(r.source.outlet.length).toBeGreaterThan(0);
        expect(r.source.date).toMatch(/^2025-03-\d\d$/);
        expect(r.flags).toContain('SINGLE');
        expect(r.utc).not.toBeNull();
      }
      // replay results live in hours[], reported times only in reported[]
      for (const h of p.hours) expect(Object.keys(h).sort()).toEqual(['issue_utc', 'latest_safe_departure_utc', 'route_cut_before_departure', 'shelter_name', 'state', 'step']);
    }
    // every source URL is one SOURCES.md lists
    const sources = readFileSync(join(REPO, 'research/kcf-replay/SOURCES.md'), 'utf8');
    for (const p of NAMED.places) for (const r of p.reported) expect(sources.includes(r.source.url), r.source.url).toBe(true);
  });
});
