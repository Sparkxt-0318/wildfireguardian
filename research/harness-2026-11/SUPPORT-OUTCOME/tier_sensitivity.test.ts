/**
 * MEASUREMENT (not product code): the planner's displayed staff headline per origin, recomputed with the job verdicts
 * of each of Richard's unknown-support tiers (F-3.1, commit b927c21c, threeway_jobs/), using the planner's own
 * planFromAttempts + deadlineHeadline. Answers Iris: at how many places does the leave-by time shown to staff differ
 * between the rate-assumed 8.2 km/h tier (R8.2) and Tier A, and between each tier and the recorded result.
 *
 * Tier label -> planner verdict: checked(contact) -> checked_route (contact-only; never "certified"),
 * no_route -> model_no_route, unresolved -> unresolved. A job missing from Richard's file stays as recorded and is
 * counted. Run: cd planner && npx vitest run --dir ../research/harness-2026-11/SUPPORT-OUTCOME
 * (needs the six threeway_jobs files; THREEWAY_DIR or `git show b927c21c:…` into a folder).
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { it } from 'vitest';
import { deadlineHeadline, planFromAttempts } from '../../../planner/src/domain/plan';
import type { OriginPlan, Verdict } from '../../../planner/src/domain/types';
import { loadBoothCaches } from '../../../tests/planner/lastmile.cachedata';

const COMMIT = 'b927c21c0f3226584f4c03e5c66753e2e4eece17';
const TIERS = ['A', 'B1.5', 'B8.2', 'R1.5', 'R8.2'] as const;
const MAP: Record<string, Verdict> = { 'checked(contact)': 'checked_route', no_route: 'model_no_route', unresolved: 'unresolved' };

function jobsFor(region: string, input: string): Map<string, Record<string, string>> {
  const name = `research/harness-2026-11/F-3.1/results/threeway_jobs/${region}__${input}.json`;
  const doc = JSON.parse(execFileSync('git', ['show', `${COMMIT}:${name}`], { encoding: 'utf8', maxBuffer: 1 << 26 }));
  return new Map(doc.jobs.map((j: Record<string, string>) => [j.job, j]));
}

/**
 * Downgrade-only (the presentation rule): a tier can only make a recorded result MORE cautious. A recorded
 * checked_route whose tier label is not checked(contact) becomes unresolved (a tier "no_route" is contact-field
 * infeasibility, not a whole-road refusal certificate, so it is never model_no_route). A recorded model_no_route or
 * unresolved never changes. `direct` maps the tier label straight through (for comparison only).
 */
function tierVerdict(recorded: Verdict, label: string, direct: boolean): Verdict {
  if (direct) return MAP[label] ?? 'unresolved';
  return recorded === 'checked_route' && label !== 'checked(contact)' ? 'unresolved' : recorded;
}
const up = { n: 0 };
/** would-be upgrades by tier, recorded verdict -> tier label, and by the recorded raw status (Iris) */
const upTypes: Record<string, number> = {};
const upRaw: Record<string, number> = {};
/** Iris: denominators, and why the kit left the would-be upgrades unresolved (recorded reason code / raw status) */
const denom: Record<string, number> = {};
const why: Record<string, Record<string, number>> = {};
const seen = new Set<string>();
/** reconciliation with Richard (Iris): his `recorded` per job vs the planner's verdict for the same attempt */
const recon: Record<string, number> = {};
const richardUnresolvedInfeasible = new Set<string>();
const mineUnresolvedNoRoute = new Set<string>();
const recheckOutcome: Record<string, number> = {};

function rebuild(p: OriginPlan, tier: string | null, jobs: Map<string, Record<string, string>>, miss: { n: number }, direct = false): OriginPlan {
  if (!p.sweep?.length) return p;
  const attempts = p.sweep.flatMap((c) => c.attempts).map((a) => {
    if (!tier) return a;
    const j = a.jobId ? jobs.get(a.jobId) : undefined;
    if (!j) { if (a.jobId) miss.n += 1; return a; }
    const v = tierVerdict(a.verdict, j[tier]!, direct);
    if (direct && tier === 'A' && a.jobId && !seen.has(`recon|${a.jobId}`)) {
      seen.add(`recon|${a.jobId}`);
      const k = `richard:${j.recorded}|planner:${a.verdict}${a.recheckOf ? '|recheck' : ''}`;
      recon[k] = (recon[k] ?? 0) + 1;
      if (j.recorded === 'unresolved' && String(j.optimistic) === 'false') richardUnresolvedInfeasible.add(a.jobId);
      if (a.verdict === 'unresolved' && j.A === 'no_route') mineUnresolvedNoRoute.add(a.jobId);
    }
    // a re-check that replaced an original: what the original looked like in Richard's rows, and what the re-check gave
    if (direct && tier === 'A' && a.recheckOf && !seen.has(`orig|${a.recheckOf}`)) {
      seen.add(`orig|${a.recheckOf}`);
      const o = jobs.get(a.recheckOf);
      const k = o ? `original:${o.recorded}/${o.raw}/optimistic=${o.optimistic}|recheck:${a.verdict}` : 'original:not_in_rows';
      recheckOutcome[k] = (recheckOutcome[k] ?? 0) + 1;
    }
    if (direct && a.jobId && !seen.has(`${tier}|${a.jobId}`)) {
      seen.add(`${tier}|${a.jobId}`);
      denom[`${tier}|recorded:${a.verdict}`] = (denom[`${tier}|recorded:${a.verdict}`] ?? 0) + 1;
      if (a.verdict === 'unresolved' && j[tier] !== 'unresolved') {
        const w = `${tier}|unresolved->${j[tier]}`;
        const r = `${a.reasonCode ?? '-'} / ${a.rawStatus ?? '-'}`;
        (why[w] ??= {})[r] = (why[w]![r] ?? 0) + 1;
      }
    }
    if (direct && a.verdict !== 'checked_route' && v !== a.verdict) {
      up.n += 1;
      const k = `${tier}|${a.verdict}->${j[tier]}`;
      upTypes[k] = (upTypes[k] ?? 0) + 1;
      if (a.verdict === 'model_no_route' && v === 'checked_route') {
        const r = `${tier}|${a.rawStatus ?? '-'}|optimistic=${j.optimistic}`;
        upRaw[r] = (upRaw[r] ?? 0) + 1;
      }
    }
    return { ...a, verdict: v };
  });
  const skipped = Object.fromEntries(p.sweep.filter((c) => c.skipped).map((c) => [c.offsetS, c.skipped!]));
  return planFromAttempts({ originId: p.originId, offsetsS: p.sweep.map((c) => c.offsetS), attempts, source: p.source, mock: p.mock, skipped });
}

const key = (p: OriginPlan) => { const h = deadlineHeadline(p); return `${h.kind}:${h.deadlineS ?? '-'}`; };
/**
 * How much a headline claims: unresolved (nothing) < no_route (a refusal) and partial < deadline, and a later deadline
 * claims more than an earlier one. An "upgrade move" is a headline that claims more than the recorded one.
 */
function rank(k: string): number {
  const [kind, t] = k.split(':');
  if (kind === 'unresolved') return 0;
  if (kind === 'no_route') return 1;
  return 2 + (t && t !== '-' ? Number(t) / 1e6 : 0) + (kind === 'deadline' ? 0.5 : 0);
}

it('tier sensitivity of the staff headline', () => {
  const out: Record<string, unknown> = {};
  const tot: Record<string, number> = {};
  for (const c of loadBoothCaches()) {
    const input = c.entry.inputTime.replace(/[-:]/g, '').replace(/\.\d+/, '');
    const jobs = jobsFor(c.entry.regionId, input);
    const miss = { n: 0 };
    const recorded: Record<string, string> = {};
    const byTier: Record<string, Record<string, string>> = {};
    for (const [id, p] of Object.entries(c.plans)) {
      recorded[id] = key(rebuild(p, null, jobs, miss));
      if (recorded[id] !== key(p)) throw new Error(`rebuild does not reproduce the recorded headline for ${id}`);
      for (const t of TIERS) (byTier[t] ??= {})[id] = key(rebuild(p, t, jobs, miss));
      for (const t of TIERS) (byTier[`${t}_direct`] ??= {})[id] = key(rebuild(p, t, jobs, { n: 0 }, true));
    }
    const ids = Object.keys(recorded);
    const cnt = (a: Record<string, string>, b: Record<string, string>) => ids.filter((i) => a[i] !== b[i]).length;
    const kinds = (m: Record<string, string>) => ids.reduce((acc, i) => { const k = m[i]!.split(':')[0]!; acc[k] = (acc[k] ?? 0) + 1; return acc; }, {} as Record<string, number>);
    const row = {
      origins: ids.length,
      jobs_missing_in_tier_file: miss.n / (TIERS.length + 0),
      'R8.2_vs_A': cnt(byTier['R8.2']!, byTier.A!),
      'R8.2_vs_recorded': cnt(byTier['R8.2']!, recorded),
      'R1.5_vs_recorded': cnt(byTier['R1.5']!, recorded),
      'A_vs_recorded': cnt(byTier.A!, recorded),
      'R8.2_direct_vs_downgrade_only': cnt(byTier['R8.2_direct']!, byTier['R8.2']!),
      // the headlines the downgrade-only rule keeps from moving (Iris: list them by place), and a check that with the
      // rule on no headline moves in the upgrade direction in any tier
      excluded_R82: ids.filter((i) => byTier['R8.2_direct']![i] !== byTier['R8.2']![i]).map((i) => ({ origin: i, recorded: recorded[i], direct: byTier['R8.2_direct']![i], downgrade_only: byTier['R8.2']![i] })),
      upgrade_moves_with_rule: TIERS.reduce((n, t) => n + ids.filter((i) => rank(byTier[t]![i]!) > rank(recorded[i]!)).length, 0),
      kinds: { recorded: kinds(recorded), 'R1.5': kinds(byTier['R1.5']!), 'R8.2': kinds(byTier['R8.2']!), A: kinds(byTier.A!) },
    };
    out[c.entry.path] = row;
    for (const k of ['origins', 'R8.2_vs_A', 'R8.2_vs_recorded', 'R1.5_vs_recorded', 'A_vs_recorded', 'R8.2_direct_vs_downgrade_only', 'upgrade_moves_with_rule'] as const) tot[k] = (tot[k] ?? 0) + (row[k] as number);
  }
  out.total = tot;
  out.upgrade_attempts_direct_all_tiers = up.n;
  out.upgrade_types_direct = Object.fromEntries(Object.entries(upTypes).sort());
  out.no_route_to_checked_by_raw_status = Object.fromEntries(Object.entries(upRaw).sort());
  out.denominators_distinct_jobs = Object.fromEntries(Object.entries(denom).sort());
  out.why_unresolved_distinct_jobs = Object.fromEntries(Object.entries(why).sort());
  out.reconciliation_richard_vs_planner = Object.fromEntries(Object.entries(recon).sort());
  out.richard_unresolved_infeasible_jobs_seen_by_planner = richardUnresolvedInfeasible.size;
  out.mine_unresolved_to_no_route = mineUnresolvedNoRoute.size;
  out.mine_subset_of_richard = [...mineUnresolvedNoRoute].every((x) => richardUnresolvedInfeasible.has(x));
  out.recheck_outcomes_of_replaced_originals = Object.fromEntries(Object.entries(recheckOutcome).sort());
  writeFileSync(process.env.TIER_OUT ?? '/dev/stdout', JSON.stringify(out, null, 1) + '\n');
  console.log('[tier sensitivity] total', JSON.stringify(tot), 'upgrade attempts (direct, all tiers):', up.n);
}, 600_000);
