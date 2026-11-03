/**
 * The village or care facility that step 2 of the static demo's tour shows ("read the leave-by
 * time"): among the rows of the urgency list, in order,
 *
 *   1. when the explanation file of the scenario on screen exists — package P2's
 *      data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json, schema wfg.explanation/1,
 *      origins{<id>: {status, reason_code, …}} — the first origin whose explanation is
 *      status "explained" with reason_code "flame_on_route" (a leave-by time set by predicted
 *      flames on the route) and that has a checked route;
 *   2. otherwise (no file, a malformed file or one of another scenario, no such origin): the first
 *      village or care facility with a checked route, a research-panel origin only when none has one.
 *
 * The file is optional and read with the same-origin static loader (null on 404), so nothing here
 * depends on P2 being merged.
 */
import { fetchAppJson } from '../../config/paths';
import { scenarioOrigins } from '../../data/staticData';
import { compactUtc, parseUtc } from '../../domain/clock';
import { sortByUrgency } from '../../domain/plan';
import { selectOrigin } from '../../state/controller';
import { currentScenarioSet } from '../../state/selectors';
import { getState, type PlannerState } from '../../state/store';

export const EXPLANATION_SCHEMA = 'wfg.explanation/1';

/** A row of the urgency list: origin id, whether it has a checked route, whether it is a research-panel origin. */
export interface TourRow {
  id: string;
  checked: boolean;
  research: boolean;
}

export interface TourScenario {
  regionId: string;
  inputTime: string;
  scenarioSetId: string | null;
}

/** data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json */
export function explanationPath(regionId: string, inputTime: string): string {
  return `data/explanations/${encodeURIComponent(regionId)}__${compactUtc(inputTime)}.json`;
}

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => Boolean(x) && typeof x === 'object' && !Array.isArray(x);

/**
 * Ids of the origins whose explanation is "explained" / "flame_on_route"; null when `doc` is not a
 * wfg.explanation/1 document of this scenario (region, input time and — when both name one — scenario set).
 */
export function flameOnRouteOrigins(doc: unknown, scenario: TourScenario): Set<string> | null {
  if (!isObj(doc) || doc.schema !== EXPLANATION_SCHEMA || !isObj(doc.origins)) return null;
  if (doc.region_id !== scenario.regionId) return null;
  if (typeof doc.input_time !== 'string' || parseUtc(doc.input_time) !== parseUtc(scenario.inputTime)) return null;
  if (scenario.scenarioSetId && typeof doc.scenario_set_id === 'string' && doc.scenario_set_id !== scenario.scenarioSetId) return null;
  const ids = new Set<string>();
  for (const [id, o] of Object.entries(doc.origins)) {
    if (isObj(o) && o.status === 'explained' && o.reason_code === 'flame_on_route') ids.add(id);
  }
  return ids;
}

const loaded = new Map<string, Promise<Set<string> | null>>();

/** Reads the scenario's explanation file once (null when it is missing or unusable; never rejects). */
export function loadFlameOnRoute(scenario: TourScenario): Promise<Set<string> | null> {
  const key = `${scenario.regionId}|${scenario.inputTime}|${scenario.scenarioSetId ?? ''}`;
  let p = loaded.get(key);
  if (!p) {
    p = fetchAppJson<unknown>(explanationPath(scenario.regionId, scenario.inputTime)).then(
      (doc) => flameOnRouteOrigins(doc, scenario),
      () => null,
    );
    loaded.set(key, p);
  }
  return p;
}

/** Forgets the files read so far (tests). */
export function forgetExplanations(): void {
  loaded.clear();
}

/** The tour's origin among `rows` (urgency order); null when none has a checked route. */
export function pickTourOrigin(rows: TourRow[], flameOnRoute: Set<string> | null): string | null {
  const checked = rows.filter((r) => r.checked);
  const flame = flameOnRoute ? checked.find((r) => flameOnRoute.has(r.id)) : undefined;
  return (flame ?? checked.find((r) => !r.research) ?? checked[0])?.id ?? null;
}

/** The recorded scenario on screen (null in drawn-zone mode). */
export function tourScenario(s: PlannerState): TourScenario | null {
  const set = currentScenarioSet(s);
  return s.regionId && set ? { regionId: s.regionId, inputTime: set.inputTime, scenarioSetId: set.id } : null;
}

/** The scenario's origins in the urgency order of the list (no filter or search). */
export function urgencyRows(s: PlannerState): TourRow[] {
  const set = currentScenarioSet(s);
  const items = scenarioOrigins(s.places, set?.id ?? null).map((p) => ({
    id: p.id,
    name: p.name ?? p.id,
    vulnerable: p.vulnerable,
    plan: s.plans[p.id] ?? null,
    research: p.role === 'research_origin',
  }));
  return sortByUrgency(items).map((x) => ({ id: x.id, checked: x.plan?.bestVerdict === 'checked_route', research: x.research }));
}

/** The rows of the urgency list as shown (filter and search applied), in order. */
export function shownRows(): TourRow[] {
  if (typeof document === 'undefined') return [];
  const research = new Set(getState().places.filter((p) => p.role === 'research_origin').map((p) => p.id));
  const rows: TourRow[] = [];
  for (const row of document.querySelectorAll<HTMLElement>('.origin-list .origin-row')) {
    const id = /^origin-(.+)$/.exec(row.dataset.testid ?? '')?.[1];
    if (id) rows.push({ id, checked: Boolean(row.querySelector('.status.checked_route')), research: research.has(id) });
  }
  return rows;
}

/**
 * Selects the tour's origin and returns its id (null: no origin of the scenario has a checked
 * route, the selection stays). Uses the list as shown unless the filter or search hides every row
 * with a checked route; then the store's urgency order.
 */
export async function selectTourOrigin(): Promise<string | null> {
  const scenario = tourScenario(getState());
  const flame = scenario ? await loadFlameOnRoute(scenario) : null;
  // the scenario may have changed while the file was read: its explanation no longer applies
  const now = tourScenario(getState());
  const same = Boolean(scenario && now && now.regionId === scenario.regionId && now.scenarioSetId === scenario.scenarioSetId);
  const shown = shownRows();
  const rows = shown.some((r) => r.checked) ? shown : urgencyRows(getState());
  const id = pickTourOrigin(rows, same ? flame : null);
  if (id) selectOrigin(id);
  return id;
}
