/**
 * Deadline provenance flags (stream 3): the per-cache files split from Richard's verified F-3.1 field (Owen PASS WITH
 * NOTES), joined to the planner's own staff headline over the six booth caches. Staff outputs only.
 */
import { readFileSync } from 'node:fs';
import { beforeAll, describe, expect, it } from 'vitest';
import { deadlineHeadline } from '../../planner/src/domain/plan';
import { parseProvenanceFile, provenanceText, staffProvenance, PROVENANCE_HELP, PROVENANCE_TAG, type ProvenanceFile } from '../../planner/src/features/provenance/model';
import { FORBIDDEN } from '../../planner/src/features/lastmile/strings';
import { clockTimes } from '../../planner/src/features/lastmile/checks';
import { loadBoothCaches, type BoothCache } from './lastmile.cachedata';
import { scenarioRow } from '../../planner/src/state/featureData';
import { dispatchListCSV } from '../../planner/src/features/exports/exports';
import { cardFor } from '../../planner/src/features/publicview/model';
import { buildChannels } from '../../planner/src/features/lastmile/channels/build';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import { translate } from '../../planner/src/i18n';

const PLANNER = new URL('../../planner/', import.meta.url);
let booth: BoothCache[] = [];
const files = new Map<string, ProvenanceFile>();
const raw = new Map<string, unknown>();

beforeAll(() => {
  booth = loadBoothCaches();
  for (const b of booth) {
    const name = `${b.entry.regionId}__${b.entry.inputTime.replace(/[-:]/g, '')}.json`;
    const r = JSON.parse(readFileSync(new URL(`public/data/provenance/${name}`, PLANNER), 'utf8'));
    raw.set(b.entry.path, r);
    const f = parseProvenanceFile(r, { path: b.entry.path, sha256: b.entry.sha256 });
    if (f) files.set(b.entry.path, f);
  }
}, 300_000);

describe('provenance files', () => {
  it('one file per booth cache, accepted only for exactly that cache (path and sha256); the verified source is recorded', () => {
    expect(files.size).toBe(6);
    for (const b of booth) {
      const f = files.get(b.entry.path)!;
      expect(f.source.sha256).toBe('3f558d92c36417f39d26043d8682485f3b3d24f7bd74032c78b5a1eb9414f558');
      expect(f.source.commit.startsWith('f0577de')).toBe(true);
      expect(parseProvenanceFile(raw.get(b.entry.path), { path: b.entry.path, sha256: 'f'.repeat(64) })).toBeNull();
      const other = booth.find((x) => x.entry.path !== b.entry.path)!;
      // a record from a different input time gets no label: the file is refused for another cache
      expect(parseProvenanceFile(raw.get(other.entry.path), { path: b.entry.path, sha256: b.entry.sha256 })).toBeNull();
    }
  });
});

describe('labels joined to the staff headline (531 real places)', () => {
  it('counts; every labelled deadline satisfies T ≤ exact leave_by_s; unresolved never gets a time; forecast gap in whole minutes', () => {
    const c: Record<string, number> = {};
    const gaps: number[] = [];
    for (const b of booth) {
      const f = files.get(b.entry.path)!;
      for (const i of b.inputs) {
        const plan = b.plans[i.origin.id];
        const h = deadlineHeadline(plan);
        const p = staffProvenance(h, i.origin.id, f);
        c[`${h.kind}:${p.kind}`] = (c[`${h.kind}:${p.kind}`] ?? 0) + 1;
        if (p.kind === 'window' || p.kind === 'present_fire' || p.kind === 'forecast_dependent') expect(h.deadlineS!).toBeLessThanOrEqual(f.records[i.origin.id]!.leave_by_s!);
        if (p.kind === 'forecast_dependent') gaps.push(p.laterMin);
        if (h.kind !== 'deadline') expect(['none', 'unresolved_proven_no_route']).toContain(p.kind);
        // the staff text never carries a clock time or a kit-forbidden word
        for (const l of ['ko', 'en'] as const) {
          const t = provenanceText(p, l) ?? '';
          expect(clockTimes(t)).toEqual([]);
          expect(FORBIDDEN[l].some((w) => t.toLowerCase().includes(w.toLowerCase())), t).toBe(false);
        }
      }
    }
    console.log('[provenance] headline kind : label over 531 real places', JSON.stringify(c), 'forecast gaps (min):', JSON.stringify(gaps.sort((a, b) => a - b)));
    expect(c).toEqual({
      'deadline:window': 473,
      'deadline:present_fire': 7,
      'deadline:forecast_dependent': 21,
      'no_route:none': 11,
      'unresolved:unresolved_proven_no_route': 10,
      'unresolved:none': 9,
    });
    expect(Math.max(...gaps)).toBeLessThanOrEqual(25);
  });

  it('fail closed: no file → not established; a deadline after the exact one → not established; no record → not computed', () => {
    const b = booth[0]!;
    const f = files.get(b.entry.path)!;
    const id = Object.keys(f.records).find((k) => f.records[k]!.provenance === 'window')!;
    const T = f.records[id]!.leave_by_s!;
    expect(staffProvenance({ kind: 'deadline', deadlineS: T }, id, null)).toEqual({ kind: 'not_established', why: 'file' });
    expect(staffProvenance({ kind: 'deadline', deadlineS: T + 1 }, id, f)).toEqual({ kind: 'not_established', why: 'after_exact' });
    expect(staffProvenance({ kind: 'deadline', deadlineS: T }, 'osm:node/does-not-exist', f)).toEqual({ kind: 'not_computed' });
    expect(staffProvenance({ kind: 'partial', deadlineS: null }, id, f)).toEqual({ kind: 'none' });
    expect(Object.keys(PROVENANCE_TAG).length).toBe(6);
  });
});

describe('surfaces', () => {
  const t = (k: string, v?: Record<string, string | number>) => translate('ko', k, v);
  it('A4 sheet row carries the kind only (never a later value); CSV carries the kind only (no later value, raw seconds included)', () => {
    const sheetKinds: Record<string, number> = {};
    let csvForecast = 0;
    for (const b of booth) {
      const f = files.get(b.entry.path)!;
      const byId = new Map(b.places.map((p) => [p.id, p]));
      for (const i of b.inputs) {
        const row = scenarioRow({ scenarioSetId: b.entry.scenarioSetId, inputTimeIso: b.entry.inputTime, issuedAtIso: null, plans: b.plans, route: () => null, travelOnly: () => null, hostFallback: null, provenance: f }, byId.get(i.origin.id)!, byId, t);
        sheetKinds[String(row.deadlineProvenance)] = (sheetKinds[String(row.deadlineProvenance)] ?? 0) + 1;
      }
    }
    expect(sheetKinds).toEqual({ window: 473, present_fire: 7, forecast_dependent: 21, unresolved_proven_no_route: 10, null: 20 });
    // CSV: the kind only — no later value in any form (orchestrator): neither raw value appears anywhere in the file
    const b = booth.find((x) => Object.values(files.get(x.entry.path)!.records).some((r) => r.provenance === 'forecast_dependent'))!;
    const f = files.get(b.entry.path)!;
    const origins = b.inputs.map((i) => {
      const plan = b.plans[i.origin.id]!;
      const p = staffProvenance(deadlineHeadline(plan), i.origin.id, f, plan);
      return {
        id: i.origin.id, name: 'x', categoryLabel: '마을', sourceTag: 'place=village', lon: 127, lat: 36, vulnerable: false,
        deadlineProvenance: p.kind === 'none' ? null : { kind: p.kind },
        plan: { bestVerdict: plan.bestVerdict, latestSafeDepartureS: plan.latestSafeDepartureS, contiguousSafeDepartureS: plan.contiguousSafeDepartureS, best: null },
      };
    });
    const csv = dispatchListCSV({ region: { id: 'r', nameKo: 'r', nameEn: 'r', fireYear: 2025 }, fireInputLabel: 'x', fireInputType: 'recorded', mock: false, scenario: { scenarioSetId: 's', inputTimeIso: b.entry.inputTime }, origins, selectedRoute: null, provenance: { checkpoint: 'x', packageVersion: '1', kit: 'v3', apiMode: 'cache', cacheApiMode: null, apiVersion: null, gitCommit: null, cacheCreatedAtIso: null, scenarioSetId: 's', scenarioIds: [] }, generatedAtIso: '2026-11-12T00:00:00Z' } as never);
    const lines = csv.slice(1).split('\r\n').filter(Boolean);
    expect(lines[0]!.split(',').length).toBe(13);
    for (const line of lines.slice(1)) if (line.endsWith(',예측 의존')) csvForecast += 1;
    for (const r of Object.values(f.records)) if (r.provenance === 'forecast_dependent') expect(csv.includes(String(r.leave_by_present_fire_only_s))).toBe(false);
    expect(csvForecast).toBeGreaterThan(0);
  });

  it('no provenance text or tag reaches any resident output (public card, kit messages) — every real and every synthetic place', () => {
    const strings = [
      ...Object.values(PROVENANCE_TAG).flatMap((x) => [x.ko, x.en]),
      ...(['window', 'present_fire', 'forecast_dependent', 'not_computed'] as const).flatMap((k) => ['ko', 'en'].map((l) => provenanceText(k === 'forecast_dependent' ? { kind: k, laterMin: 7, horizonS: 3600 } : k === 'not_computed' ? { kind: k } : { kind: k, horizonS: 3600 }, l as 'ko' | 'en')!)),
    ].filter((x) => x.length > 3);
    for (const b of booth) for (const i of b.inputs) {
      const c = cardFor(i);
      const card = [c.words, c.time, c.guidance, c.dataAge, c.handoff?.text].flatMap((x) => (x ? [x.ko, x.en] : [])).join('\n');
      const k = buildChannels(messagePlan(i, null), { nowIso: '2026-11-12T10:00:00Z' });
      const kit = (['ko', 'en'] as const).flatMap((l) => [k.text[l].head.script, k.text[l].voice, k.text[l].familyText, ...k.text[l].familyScript]).join('\n');
      for (const s of strings) {
        expect(card.includes(s), s).toBe(false);
        expect(kit.includes(s), s).toBe(false);
      }
    }
  });

  it('a live or MOCK plan on screen gets no label from the cache field (not established)', () => {
    const b = booth[0]!;
    const f = files.get(b.entry.path)!;
    const i = b.inputs.find((x) => b.plans[x.origin.id]!.bestVerdict === 'checked_route')!;
    const plan = b.plans[i.origin.id]!;
    expect(staffProvenance(deadlineHeadline(plan), i.origin.id, f, { ...plan, source: 'live' })).toEqual({ kind: 'not_established', why: 'file' });
    expect(staffProvenance(deadlineHeadline(plan), i.origin.id, f, { ...plan, mock: true })).toEqual({ kind: 'not_established', why: 'file' });
  });
});

describe('fail closed on malformed records (Mira N1)', () => {
  it('an unknown or malformed record is kept apart at parse time: that place is "not established", never a crash', () => {
    const b = booth[0]!;
    const r = JSON.parse(JSON.stringify(raw.get(b.entry.path))) as { records: Record<string, Record<string, unknown>> };
    const ids = Object.keys(r.records);
    r.records[ids[0]!]!.provenance = 'research_only';
    r.records[ids[1]!]!.leave_by_s = '18:30';
    r.records[ids[2]!] = { provenance: 'forecast_dependent', leave_by_s: 100, fire_free_leave_by_s: 200 } as never;
    const f = parseProvenanceFile(r, { path: b.entry.path, sha256: b.entry.sha256 })!;
    expect(f).not.toBeNull();
    expect(f.invalid).toEqual(ids.slice(0, 3));
    for (const id of ids.slice(0, 3)) {
      expect(f.records[id]).toBeUndefined();
      const p = staffProvenance({ kind: 'deadline', deadlineS: 0 }, id, f);
      expect(p).toEqual({ kind: 'not_established', why: 'invalid_record' });
      expect(provenanceText(p, 'ko')).toMatch(/근거 확인 안 됨/);
      expect(staffProvenance({ kind: 'unresolved', deadlineS: null }, id, f)).toEqual({ kind: 'none' });
    }
    // an unknown kind can never reach the text table as itself
    expect(provenanceText({ kind: 'research_only' } as never, 'en')).toBeNull();
  });

  it('the help sentence matches the data: the shown time is at or below the exact bound in every labelled real case', () => {
    expect(PROVENANCE_HELP.en).toMatch(/at or before it/);
    expect(PROVENANCE_HELP.ko).toMatch(/그 시각이거나 그보다 앞선/);
  });
});

describe('message-kit staff block (W-KIT): the provenance line goes to staff only', () => {
  it('over the 531 real places: staff.provenance present exactly when there is a label; resident outputs and violations unchanged; no clock time', () => {
    const counts: Record<string, number> = {};
    for (const b of booth) {
      const f = files.get(b.entry.path)!;
      for (const i of b.inputs) {
        const plan = b.plans[i.origin.id]!;
        const prov = staffProvenance(deadlineHeadline(plan), i.origin.id, f, plan);
        const mp = messagePlan(i, null);
        const a = buildChannels(mp, { nowIso: '2026-11-12T10:00:00Z' });
        const s = buildChannels(mp, { nowIso: '2026-11-12T10:00:00Z', deadlineProvenance: prov });
        expect(s.violations).toEqual(a.violations);
        for (const l of ['ko', 'en'] as const) {
          const { staff: sa, ...ra } = a.text[l];
          const { staff: sb, ...rb } = s.text[l];
          expect(rb).toEqual(ra); // every resident output identical
          expect({ ...sb, provenance: undefined }).toEqual({ ...sa, provenance: undefined });
          if (prov.kind === 'none') expect(sb.provenance ?? null).toBeNull();
          else {
            expect(sb.provenance).toContain(PROVENANCE_TAG[prov.kind][l]);
            expect(clockTimes(sb.provenance!)).toEqual([]);
          }
        }
        counts[prov.kind] = (counts[prov.kind] ?? 0) + 1;
      }
    }
    expect(counts).toEqual({ window: 473, present_fire: 7, forecast_dependent: 21, unresolved_proven_no_route: 10, none: 20 });
  });
});

describe('kit staff line fails closed on a mismatched label (Mira N1)', () => {
  it('a deadline label (window / present_fire / forecast_dependent) on a place without a checked time is refused and reported as not established, with no new violation, in ko and en', () => {
    let n = 0;
    for (const b of booth) for (const i of b.inputs) {
      const mp = messagePlan(i, null);
      if (mp.kind === 'leave_by') continue;
      for (const prov of [{ kind: 'window', horizonS: 3600 }, { kind: 'present_fire', horizonS: 3600 }, { kind: 'forecast_dependent', laterMin: 7, horizonS: 3600 }] as const) {
        const a = buildChannels(mp, { nowIso: '2026-11-12T10:00:00Z' });
        const s = buildChannels(mp, { nowIso: '2026-11-12T10:00:00Z', deadlineProvenance: prov });
        // refused and reported as "not established", the same in both languages; never the deadline wording
        expect(s.text.ko.staff.provenance).toMatch(/근거 확인 안 됨/);
        expect(s.text.en.staff.provenance).toMatch(/Provenance not established/);
        expect(s.text.ko.staff.provenance).not.toMatch(/출발 마감|시간창|예측에 따라/);
        expect(s.text.en.staff.provenance).not.toMatch(/window|burning|forecast/i);
        expect(s.violations).toEqual(a.violations);
        n += 1;
      }
    }
    expect(n).toBe(30 * 3);
  });

  it('the symmetric case: a "proven no route" label on a place that is not unresolved (leave-by, partial, no route) is refused and reported as not established; on an unresolved place it is kept, in ko and en', () => {
    const byKind: Record<string, number> = {};
    for (const b of booth) for (const i of b.inputs) {
      const mp = messagePlan(i, null);
      const a = buildChannels(mp, { nowIso: '2026-11-12T10:00:00Z' });
      const s = buildChannels(mp, { nowIso: '2026-11-12T10:00:00Z', deadlineProvenance: { kind: 'unresolved_proven_no_route' } });
      if (mp.kind === 'unresolved') {
        expect(s.text.ko.staff.provenance).toMatch(/정밀 분석상 경로 없음/);
        expect(s.text.en.staff.provenance).toMatch(/exact analysis: no route/);
      } else {
        expect(s.text.ko.staff.provenance).toMatch(/근거 확인 안 됨/);
        expect(s.text.en.staff.provenance).toMatch(/Provenance not established/);
        expect(s.text.ko.staff.provenance).not.toMatch(/경로 없음|시간 초과/);
        expect(s.text.en.staff.provenance).not.toMatch(/no route|timed out/i);
      }
      expect(s.violations).toEqual(a.violations);
      byKind[mp.kind] = (byKind[mp.kind] ?? 0) + 1;
    }
    console.log('[provenance] symmetric guard cases by kit kind:', JSON.stringify(byKind));
    expect(byKind.leave_by ?? 0).toBeGreaterThan(0);
    expect(byKind.unresolved ?? 0).toBeGreaterThan(0);
  });
});
