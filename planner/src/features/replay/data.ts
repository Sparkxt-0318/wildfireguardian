/**
 * Replay state derived from the store: which pack the shown scenario belongs to, the pack's issue
 * hours for the region, and the six-place timeline file (data/replay/<pack>.named_places.json,
 * written by scripts/build_replay_named_places.mjs from research/kcf-replay/per_place.csv).
 */
import { useEffect, useMemo, useState } from 'react';
import { fetchAppJson } from '../../config/paths';
import { REPLAY_PACKS, packOfScenario, type ReplayPack } from '../../data/replayPacks';
import type { ScenarioSet } from '../../domain/types';
import { useScenarioSets } from '../../state/selectors';
import { useStore } from '../../state/store';

export interface NamedHour {
  issue_utc: string;
  state: string;
  step: string | null;
  latest_safe_departure_utc: string | null;
  shelter_name: string | null;
  route_cut_before_departure: boolean | null;
}

export interface ReportedItem {
  kst: string;
  utc: string | null;
  approx: boolean;
  scope: 'village' | 'myeon' | 'county' | 'road';
  flags: string[];
  ko: string;
  en: string;
  source: { id: string; outlet: string; outlet_en: string; date: string; url: string };
}

export interface NamedPlace {
  place_id: string;
  name: string;
  sigungu: string | null;
  hours: NamedHour[];
  reported: ReportedItem[];
  reported_note_ko: string | null;
  reported_note_en: string | null;
}

export interface NamedPlacesDoc {
  schema: 'wfg.replay.named_places/1';
  pack: string;
  standin: string;
  horizon: string;
  region_id: string;
  issue_hours_utc: string[];
  places: NamedPlace[];
}

/** Replay pack of the shown scenario (null for booth results and drawn zones). */
export function useActivePack(): ReplayPack | null {
  const scenarioId = useStore((s) => s.scenarioId);
  return useMemo(() => packOfScenario(scenarioId), [scenarioId]);
}

/** The scenario sets of one pack in the current region, by issue time. */
export function packSets(sets: ScenarioSet[], packId: string): ScenarioSet[] {
  return sets.filter((s) => s.pack === packId).sort((a, b) => a.inputTime.localeCompare(b.inputTime));
}

export function usePackSets(packId: string | null): ScenarioSet[] {
  const sets = useScenarioSets();
  return useMemo(() => (packId ? packSets(sets, packId) : []), [sets, packId]);
}

/** Packs to list in the selector: every registered pack (pending ones are shown as not available). */
export function listedPacks(): readonly ReplayPack[] {
  return REPLAY_PACKS;
}

const docs = new Map<string, Promise<NamedPlacesDoc | null>>();

export function parseNamedPlaces(raw: unknown, packId: string): NamedPlacesDoc | null {
  if (!raw || typeof raw !== 'object') return null;
  const d = raw as Partial<NamedPlacesDoc>;
  if (d.schema !== 'wfg.replay.named_places/1' || d.pack !== packId || !Array.isArray(d.places) || !Array.isArray(d.issue_hours_utc)) return null;
  return d as NamedPlacesDoc;
}

export function useNamedPlaces(pack: ReplayPack | null): { state: 'none' | 'loading' | 'ready' | 'error'; doc: NamedPlacesDoc | null; error: string | null } {
  const [st, setSt] = useState<{ key: string | null; doc: NamedPlacesDoc | null; error: string | null }>({ key: null, doc: null, error: null });
  const path = pack?.namedPlaces ?? null;
  useEffect(() => {
    if (!pack || !path) return;
    let alive = true;
    let p = docs.get(path);
    if (!p) {
      p = fetchAppJson(path).then((raw) => parseNamedPlaces(raw, pack.id));
      docs.set(path, p);
    }
    p.then(
      (doc) => alive && setSt({ key: path, doc, error: doc ? null : 'unexpected content' }),
      (e: unknown) => {
        docs.delete(path);
        if (alive) setSt({ key: path, doc: null, error: e instanceof Error ? e.message : String(e) });
      },
    );
    return () => {
      alive = false;
    };
  }, [pack, path]);
  if (!pack || !path) return { state: 'none', doc: null, error: null };
  if (st.key !== path) return { state: 'loading', doc: null, error: null };
  return st.doc ? { state: 'ready', doc: st.doc, error: null } : { state: 'error', doc: null, error: st.error };
}
