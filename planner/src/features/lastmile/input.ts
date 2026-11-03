/**
 * Planner internal model → last-mile inputs (pure; no store, no I/O). The app calls it through
 * ./connect.ts with the store's contents; the tests call it with planner/cache/** loaded by the
 * app's own cache reader (src/api/cache.ts) and places parser (src/data/staticData.ts).
 *
 * Names come only from the places file (OSM) or the planner's descriptors; an origin without a
 * result is unresolved (never safe), with the planner's note (not checkable / not computed).
 */
import { scenarioOrigins } from '../../data/staticData';
import { fireInputBanner } from '../../domain/labels';
import { sortByUrgency } from '../../domain/plan';
import type { OriginPlan, Place } from '../../domain/types';
import { categoryLabel, placeName } from '../../components/format';
import { translate } from '../../i18n';
import type { LastMileInput, LmCell, LmDestination, LmOriginKind, LmText } from './types';

export interface LastMileBuildArgs {
  region: { id: string; nameKo: string; nameEn: string; fireYear: number | null };
  scenario: { scenarioSetId: string; inputTimeIso: string; horizonS: number };
  places: Place[];
  plans: Record<string, OriginPlan>;
  mock: boolean;
  testData: boolean;
  source: 'cache' | 'live';
  cacheCreatedAtIso: string | null;
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

function cellsOf(plan: OriginPlan): LmCell[] {
  return plan.sweep.map((c) => ({
    offsetS: c.offsetS,
    verdict: c.skipped === 'window_unsatisfiable' ? 'window_closed' : c.verdict,
    attempts: c.attempts.map((a) => ({ destinationId: a.destinationId, verdict: a.verdict, arrivalS: a.arrivalS })),
  }));
}

/** Research origins (recorded mission start points) are not places where people live or stay. */
export function isFieldOrigin(p: Pick<Place, 'role'>): boolean {
  return p.role !== 'research_origin';
}

/**
 * One input per village and care facility of the recorded scenario, in the planner's urgency order
 * (`urgencyRank` keeps the planner's position). Research origins get no field messages: nobody
 * there would be addressed as a resident.
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
    const input = {
      region: { id: a.region.id, name: { ko: a.region.nameKo, en: a.region.nameEn }, fireYear: a.region.fireYear },
      fireInputLabel,
      replay: true,
      mock: a.mock,
      testData: a.testData,
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
      provenance: { cacheCreatedAtIso: a.cacheCreatedAtIso, source: a.source },
      generatedAtIso: a.generatedAtIso,
    } satisfies LastMileInput;
    return [input];
  });
}
