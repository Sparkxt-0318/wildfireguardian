/**
 * Planner internal model → last-mile inputs (pure; no store, no I/O). The app calls it through
 * ./connect.ts with the store's contents; the tests call it with planner/cache/** loaded by the
 * app's own cache reader (src/api/cache.ts) and places parser (src/data/staticData.ts).
 *
 * Names come only from the places file (OSM) or the planner's descriptors; an origin without a
 * result is unresolved (never safe), with the planner's note (not checkable / not computed).
 */
import { isTestDataHost } from '../../api/cache';
import { scenarioOrigins } from '../../data/staticData';
import { fireInputBanner } from '../../domain/labels';
import { sortByUrgency } from '../../domain/plan';
import type { HostInfo, OriginPlan, Place, RouteDetail } from '../../domain/types';
import { categoryLabel, hostLabel, placeName } from '../../components/format';
import { translate } from '../../i18n';
import type { LastMileInput, LmCell, LmDestination, LmOriginKind, LmText } from './types';

export interface LastMileBuildArgs {
  region: { id: string; nameKo: string; nameEn: string; fireYear: number | null };
  scenario: { scenarioSetId: string; inputTimeIso: string; horizonS: number };
  places: Place[];
  plans: Record<string, OriginPlan>;
  /** MOCK data (session-wide, the planner's MOCK rule) */
  mock: boolean;
  /** the precomputed cache on screen, if any: the provenance of every plan whose source is 'cache' */
  cache: { path: string; createdAtIso: string | null; testData: boolean } | null;
  /** the compute hosts of each live plan's results (liveHostsOf), by origin id */
  liveHosts: Record<string, HostInfo[]>;
  /** the session's data source — used only for an origin that has no plan at all */
  source: 'cache' | 'live';
  generatedAtIso: string;
}

const tKo = (k: string, v?: Record<string, string | number>) => translate('ko', k, v);
const tEn = (k: string, v?: Record<string, string | number>) => translate('en', k, v);

function both(f: (lang: 'ko' | 'en') => string): LmText {
  return { ko: f('ko'), en: f('en') };
}

function realName(p: Place): LmText | null {
  if (!p.name && !p.nameEn) return null;
  return { ko: (p.name ?? p.nameEn)!, en: (p.nameEn ?? p.name)! };
}

function category(p: Place): LmText {
  return { ko: categoryLabel(p, tKo), en: categoryLabel(p, tEn) };
}

function display(p: Place): LmText {
  return both((lang) => placeName(p, lang === 'ko' ? tKo : tEn, lang));
}

function kindOf(p: Place): LmOriginKind {
  if (p.role === 'research_origin') return 'research';
  return p.category === 'village' || p.category === 'hamlet' ? 'village' : 'facility';
}

/**
 * The compute hosts a live plan's results report (each route's provenance `host`), distinct, in
 * sweep order. `routeOf` looks a job up (the store's routes); a result without provenance adds
 * nothing, so a plan whose results carry no host gives [] (an unknown host).
 */
export function liveHostsOf(plan: OriginPlan, routeOf: (jobId: string) => RouteDetail | null): HostInfo[] {
  const out: HostInfo[] = [];
  const seen = new Set<string>();
  for (const c of plan.sweep) {
    for (const a of c.attempts) {
      const h = a.jobId ? routeOf(a.jobId)?.provenance?.host ?? null : null;
      if (!h) continue;
      const key = JSON.stringify([h.recorded, h.platform, h.os, h.machine, h.cpuCount]);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(h);
    }
  }
  return out;
}

/**
 * Provenance of ONE origin's result, from its own plan (never the session): a cache result keeps
 * the cache's provenance (created time, evaluated host or test data); a live result never carries
 * the cache's stamp and is test data unless every host its results report is the evaluated host
 * (isTestDataHost — an unknown host counts as not evaluated). A live plan with no API result at all
 * (nothing was computed for it) is not marked as computed anywhere.
 */
export function originProvenance(plan: OriginPlan | undefined, originId: string, a: LastMileBuildArgs): { testData: boolean; provenance: LastMileInput['provenance'] } {
  const source = plan ? plan.source : a.source;
  if (source === 'cache') {
    return {
      // a cache result without the cache's metadata has no established provenance: marked
      testData: a.cache ? a.cache.testData : true,
      provenance: { source, cachePath: a.cache?.path ?? null, cacheCreatedAtIso: a.cache?.createdAtIso ?? null, host: null },
    };
  }
  const hosts = a.liveHosts[originId] ?? [];
  const computed = Boolean(plan?.sweep.some((c) => c.attempts.some((x) => x.jobId)));
  const testData = !a.mock && computed && (hosts.length === 0 || hosts.some((h) => isTestDataHost(h, false)));
  const label = (lang: 'ko' | 'en') => [...new Set(hosts.map((h) => hostLabel(h, lang === 'ko' ? tKo : tEn)).filter((x): x is string => Boolean(x)))].join(', ');
  const host = label('ko') ? { ko: label('ko'), en: label('en') } : null;
  return { testData, provenance: { source, cachePath: null, cacheCreatedAtIso: null, host } };
}

function cellsOf(plan: OriginPlan): LmCell[] {
  return plan.sweep.map((c) => ({
    offsetS: c.offsetS,
    verdict: c.skipped === 'window_unsatisfiable' ? 'window_closed' : c.verdict,
    attempts: c.attempts.map((a) => ({ destinationId: a.destinationId, verdict: a.verdict, arrivalS: a.arrivalS })),
  }));
}

/**
 * Field messages are made for villages and care facilities only. Research panel origins are the
 * start road nodes of recorded research missions — not villages or care facilities — so there is
 * no village or facility to address (the data says nothing about who lives near them).
 */
export function isFieldOrigin(p: Pick<Place, 'role'>): boolean {
  return p.role !== 'research_origin';
}

/**
 * One input per village and care facility of the recorded scenario, in the planner's urgency order
 * (`urgencyRank` keeps the planner's position); research panel origins get none (isFieldOrigin).
 */
export function buildLastMileInputs(a: LastMileBuildArgs): LastMileInput[] {
  const origins = scenarioOrigins(a.places, a.scenario.scenarioSetId);
  const byId = new Map(a.places.map((p) => [p.id, p]));
  const fireInputLabel = both((lang) => fireInputBanner({ type: 'recorded' }, a.region.fireYear, lang));
  const ordered = sortByUrgency(origins.map((o) => ({ id: o.id, name: placeName(o, tKo, 'ko'), vulnerable: o.vulnerable, plan: a.plans[o.id] ?? null, o }))).map((x) => x.o);
  return ordered.flatMap((o, i) => {
    if (!isFieldOrigin(o)) return [];
    const plan = a.plans[o.id];
    const destinations: Record<string, LmDestination> = {};
    if (plan) {
      for (const c of plan.sweep) {
        for (const at of c.attempts) {
          if (destinations[at.destinationId]) continue;
          const d = byId.get(at.destinationId);
          destinations[at.destinationId] = d
            ? { id: d.id, name: realName(d), display: display(d), category: category(d) }
            : { id: at.destinationId, name: null, display: { ko: at.destinationId, en: at.destinationId }, category: { ko: '도착지', en: 'destination' } };
        }
      }
    }
    const lmPlan: LastMileInput['plan'] = plan
      ? {
          bestVerdict: plan.bestVerdict,
          latestSafeDepartureS: plan.latestSafeDepartureS,
          contiguousSafeDepartureS: plan.contiguousSafeDepartureS,
          sweep: cellsOf(plan),
          note: plan.note ?? null,
        }
      : !o.checkable
        ? { bestVerdict: 'unresolved', latestSafeDepartureS: null, contiguousSafeDepartureS: null, sweep: [], note: 'not_checkable' }
        : null;
    const prov = originProvenance(plan, o.id, a);
    const input = {
      region: { id: a.region.id, name: { ko: a.region.nameKo, en: a.region.nameEn }, fireYear: a.region.fireYear },
      fireInputLabel,
      replay: true,
      mock: a.mock,
      testData: prov.testData,
      scenario: { ...a.scenario },
      origin: {
        id: o.id,
        name: realName(o),
        display: display(o),
        category: category(o),
        kind: kindOf(o),
        vulnerable: o.vulnerable,
        entryDistanceM: o.entry?.distanceM ?? o.snapDistanceM ?? null,
        sourceTag: o.sourceTag,
      },
      plan: lmPlan,
      destinations,
      urgencyRank: i + 1,
      provenance: prov.provenance,
      generatedAtIso: a.generatedAtIso,
    } satisfies LastMileInput;
    return [input];
  });
}
