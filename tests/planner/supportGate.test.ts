/**
 * Fail-closed reader for results on support-masked packets (research/harness-2026-11/SUPPORT-OUTCOME/DESIGN.md,
 * orchestrator decision (c)): every masked result is unresolved (never a route, never "no route", never safe), the
 * packet writer's identity is shown with the reason, a missing identity or a failed support write has its own code, and
 * unmasked results are untouched.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { adaptAttempt, adaptDispatchJob, adaptRouteJob } from '../../planner/src/api/adapter';
import { cacheToModel, parseCacheIndex } from '../../planner/src/api/cache';
import { splitReasonCode, supportGate, SUPPORT_WRITE_FAILED, UNKNOWN_SUPPORT_NOT_EVALUATED, WRITER_IDENTITY_MISSING } from '../../planner/src/api/supportGate';
import { deadlineHeadline, headlineDepartureS } from '../../planner/src/domain/plan';
import { attemptReasonText, reasonText } from '../../planner/src/features/shared/strings';

const SHA = 'ab12cd34'.padEnd(64, '0');
const BASE = 'ff00ee11'.padEnd(64, '1');
const SUPPORT = { writer_version: 'wfg.f93.support-writer/1', rule: 'c651_unknown/1', mask_sha256: '9'.repeat(64), packet_writer_sha256: SHA, base_packet_writer_sha256: BASE };
const SUPPORT_WRITER = { version: 'wfg.f93.support-writer/1', rule: 'c651_unknown/1', packet_writer_sha256: SHA };

const attempt = (extra: Record<string, unknown> = {}) => ({
  depart_offset_s: 600, destination_id: 'osm:node/1', verdict: 'checked_route', arrival_s: 1500, compute_s: 3.2, route_check_job_id: 'rc_1', reason_code: null, raw_status: 'CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN', lower_bound_L_s: 1400, ...extra,
}) as unknown as Parameters<typeof adaptAttempt>[0];

describe('supportGate (unit)', () => {
  it('unmasked inputs pass through (null), including kit v2\'s unmasked form (support: null, unknown_support_involved: "none")', () => {
    expect(supportGate({})).toBeNull();
    expect(supportGate(null, undefined, { notes: ['x'] })).toBeNull();
    expect(supportGate({ support: null, unknown_support_involved: 'none' })).toBeNull();
    expect(supportGate({ support_writer: null })).toBeNull();
  });
  it('masked → UNKNOWN_SUPPORT_NOT_EVALUATED@sha8; no writer identity → WRITER_IDENTITY_MISSING; a failed support write → SUPPORT_WRITE_FAILED', () => {
    expect(supportGate({ support: SUPPORT })).toBe(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`);
    expect(supportGate({}, { support_writer: SUPPORT_WRITER })).toBe(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`);
    // kit v2 masked outcomes are not yet read: every value, including "none" on a masked packet, stays not evaluated
    for (const usi of ['route_crosses', 'refusal_depends', 'not_evaluated']) expect(supportGate({ unknown_support_involved: usi, support: SUPPORT })).toBe(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`);
    expect(supportGate({ unknown_support_involved: 'none', support: SUPPORT })).toBe(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`);
    expect(supportGate({ unknown_support_involved: 'route_crosses' })).toBe(WRITER_IDENTITY_MISSING);
    expect(supportGate({ support: { ...SUPPORT, packet_writer_sha256: undefined } })).toBe(WRITER_IDENTITY_MISSING);
    expect(supportGate({ support: { ...SUPPORT, packet_writer_sha256: 'short' } })).toBe(WRITER_IDENTITY_MISSING);
    expect(supportGate({ support: { ...SUPPORT, packet_writer_sha256: SHA.toUpperCase() } })).toBe(WRITER_IDENTITY_MISSING);
    for (const m of [{ notes: [SUPPORT_WRITE_FAILED] }, { markers: [SUPPORT_WRITE_FAILED] }, { raw_status: SUPPORT_WRITE_FAILED }, { support_write_failed: true }]) {
      expect(supportGate({ support: SUPPORT }, m)).toBe(SUPPORT_WRITE_FAILED);
      expect(supportGate(m)).toBe(SUPPORT_WRITE_FAILED); // even without the support block (a marker is never ignored)
    }
  });
  it('the writer identity travels with the code and is shown in every staff reason text (ko and en)', () => {
    expect(splitReasonCode(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`)).toEqual({ code: UNKNOWN_SUPPORT_NOT_EVALUATED, writer: 'ab12cd34' });
    expect(splitReasonCode('TIMEOUT')).toEqual({ code: 'TIMEOUT', writer: null });
    expect(reasonText(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`, 'en')).toBe('forecast with areas of unknown fire state — their effect was not evaluated (UNKNOWN_SUPPORT_NOT_EVALUATED; writer ab12cd34)');
    expect(reasonText(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`, 'ko')).toContain('작성기 ab12cd34');
    expect(attemptReasonText(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`, 'CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN', 'en')).toContain('writer ab12cd34');
    expect(reasonText(WRITER_IDENTITY_MISSING, 'en')).toBe('forecast packet writer identity missing (WRITER_IDENTITY_MISSING)');
    expect(reasonText('TIMEOUT', 'en')).toBe('30 s compute budget exceeded (TIMEOUT)'); // unchanged
    // staff wording only: never a safe word, never "no route"
    for (const c of [UNKNOWN_SUPPORT_NOT_EVALUATED, WRITER_IDENTITY_MISSING, SUPPORT_WRITE_FAILED]) for (const l of ['ko', 'en'] as const) expect(reasonText(c, l)).not.toMatch(/safe|안전|no route|경로 없음/i);
  });
});

describe('adapters: masked results are unresolved; unmasked results are untouched', () => {
  it('dispatch attempt: a masked checked_route becomes unresolved with no arrival or lower bound; unmasked is unchanged', () => {
    const plain = adaptAttempt(attempt());
    expect(plain).toEqual({ offsetS: 600, destinationId: 'osm:node/1', verdict: 'checked_route', arrivalS: 1500, computeS: 3.2, jobId: 'rc_1', reasonCode: null, rawStatus: 'CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN', lowerBoundS: 1400 });
    expect(adaptAttempt(attempt({ support: null, unknown_support_involved: 'none' }))).toEqual(plain);
    const m = adaptAttempt(attempt({ support: SUPPORT }));
    expect(m).toEqual({ ...plain, verdict: 'unresolved', arrivalS: null, lowerBoundS: null, reasonCode: `${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34` });
    // a refusal on a masked packet is never shown as "no route"
    const r = adaptAttempt(attempt({ verdict: 'model_no_route', raw_status: 'FULL_MODEL_REFUSAL_PROVEN', support: SUPPORT }));
    expect(r.verdict).toBe('unresolved');
  });

  it('dispatch job: a support_writer in the result provenance gates every attempt of every origin; the headline is unresolved, with no time', () => {
    const job = (prov: Record<string, unknown>) => ({
      job_id: 'dp_1', status: 'done', progress: { done: 1, total: 1 },
      request: { depart_offsets_s: [0, 600] },
      result: { provenance: prov, plans: [{ origin_id: 'o1', attempts: [attempt({ depart_offset_s: 0 }), attempt({ depart_offset_s: 600 })] }], rejected_origins: [], summary: {} },
    }) as unknown as Parameters<typeof adaptDispatchJob>[0];
    const plain = adaptDispatchJob(job({}), 'cache').plans[0]!;
    expect(plain.bestVerdict).toBe('checked_route');
    expect(headlineDepartureS(plain)).toBe(600);
    const m = adaptDispatchJob(job({ support_writer: SUPPORT_WRITER }), 'cache').plans[0]!;
    expect(m.bestVerdict).toBe('unresolved');
    expect(m.latestSafeDepartureS).toBeNull();
    expect(headlineDepartureS(m)).toBeNull();
    expect(deadlineHeadline(m).kind).toBe('unresolved');
    expect(m.sweep.flatMap((c) => c.attempts).every((a) => a.reasonCode === `${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`)).toBe(true);
    const missing = adaptDispatchJob(job({ support_writer: { version: 'x' } }), 'cache').plans[0]!;
    expect(missing.sweep.flatMap((c) => c.attempts).every((a) => a.reasonCode === WRITER_IDENTITY_MISSING && a.verdict === 'unresolved')).toBe(true);
  });

  it('route check: masked → unresolved, no route geometry, no arrival; unmasked → unchanged; a failed support write is refused', () => {
    const rc = (res: Record<string, unknown>) => ({
      job_id: 'rc_1', status: 'done',
      request: { start: { node_id: '1' }, destination: { node_id: '2' }, depart_offset_s: 0 },
      result: { verdict: 'checked_route', arrival_s: 900, departure_s: 0, route: { geometry: { coordinates: [[129, 36], [129.01, 36.01]] }, properties: { times_s: [0, 900], length_m: 1500 } }, ...res },
    }) as unknown as Parameters<typeof adaptRouteJob>[0];
    const plain = adaptRouteJob(rc({}));
    expect(plain.verdict).toBe('checked_route');
    expect(plain.coordinates).not.toBeNull();
    const m = adaptRouteJob(rc({ provenance: { support_writer: SUPPORT_WRITER } }));
    expect(m.verdict).toBe('unresolved');
    expect(m.coordinates).toBeNull();
    expect(m.arrivalS).toBeNull();
    expect(m.reasonCode).toBe(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`);
    const failed = adaptRouteJob(rc({ notes: [SUPPORT_WRITE_FAILED] }));
    expect(failed.verdict).toBe('unresolved');
    expect(failed.reasonCode).toBe(SUPPORT_WRITE_FAILED);
  });
});

describe('the six booth caches', () => {
  const PLANNER = new URL('../../planner/', import.meta.url);
  const index = parseCacheIndex(JSON.parse(readFileSync(new URL('cache/INDEX.json', PLANNER), 'utf8')));

  it('carry no support-masked result today (so this reader changes nothing visible now)', () => {
    let gated = 0;
    for (const e of index) {
      const model = cacheToModel(JSON.parse(readFileSync(new URL(`cache/${e.path}`, PLANNER), 'utf8')), e);
      for (const p of Object.values(model.plans)) for (const c of p.sweep) for (const a of c.attempts) if (a.reasonCode && splitReasonCode(a.reasonCode).code.match(/SUPPORT|WRITER_IDENTITY/)) gated += 1;
    }
    expect(gated).toBe(0);
  });

  it('with every result of a real cache marked as computed on a masked packet: 0 checked routes, 0 no-routes, 0 leave-by times; every reason names the writer', () => {
    for (const e of index.slice(0, 2)) {
      const doc = JSON.parse(readFileSync(new URL(`cache/${e.path}`, PLANNER), 'utf8')) as Record<string, any>;
      for (const j of Object.values(doc.route_checks ?? {}) as any[]) if (j?.result) j.result.provenance = { ...(j.result.provenance ?? {}), support_writer: SUPPORT_WRITER };
      for (const j of (doc.plans ?? []) as any[]) if (j?.result) j.result.provenance = { ...(j.result.provenance ?? {}), support_writer: SUPPORT_WRITER };
      const model = cacheToModel(doc as Parameters<typeof cacheToModel>[0], e);
      const plans = Object.values(model.plans);
      expect(plans.length).toBeGreaterThan(80);
      for (const p of plans) {
        expect(p.bestVerdict, p.originId).toBe('unresolved');
        expect(headlineDepartureS(p)).toBeNull();
        expect(deadlineHeadline(p).kind).toBe('unresolved');
        for (const c of p.sweep) for (const a of c.attempts) {
          expect(a.verdict).toBe('unresolved');
          expect(a.arrivalS).toBeNull();
          if (a.jobId) expect(a.reasonCode).toBe(`${UNKNOWN_SUPPORT_NOT_EVALUATED}@ab12cd34`);
        }
      }
    }
  }, 120_000);
});
