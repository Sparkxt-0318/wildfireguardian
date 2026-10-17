/**
 * Store mutations for user-drawn spread zones (사용자 입력 확산 구역, 가정): editing with undo,
 * presets copied from recorded footprints, fire-input settings and per-region persistence in
 * localStorage (wrapped in try/catch: a booth reload keeps the zones; private mode just forgets).
 *
 * Geometry/settings changes call the registered fire-input listener (the controller), which drops
 * drawn results that no longer match the zones on screen.
 */
import {
  addPolygon,
  clampIssueOffsetH,
  clampMarginMin,
  clearZone,
  deleteVertex,
  emptyZones,
  hasAnyZone,
  insertVertex,
  moveVertex,
  parseStoredZones,
  presetZone,
  sameRef,
  vertexRefs,
  type DrawnZones,
  type LonLat,
  type StoredZones,
  type VertexRef,
  type ZoneKey,
} from '../domain/zones';
import { kstDateTime } from '../domain/clock';
import type { Footprint } from '../data/staticData';
import { DEFAULT_DRAWN, getState, setState, type DrawnSettings, type DrawnState, type ZoneEditState } from './store';

const HISTORY_MAX = 50;
const STORAGE_PREFIX = 'wfg.planner.zones.';

type Listener = () => void;
let fireInputListener: Listener | null = null;

/** The controller registers here to invalidate drawn results when zones or settings change. */
export function onFireInputChange(fn: Listener): void {
  fireInputListener = fn;
}

function drawn(): DrawnState {
  return getState().drawn;
}

function patch(p: Partial<DrawnState>): void {
  setState((s) => ({ drawn: { ...s.drawn, ...p } }));
}

function patchEdit(p: Partial<ZoneEditState>): void {
  setState((s) => ({ drawn: { ...s.drawn, edit: { ...s.drawn.edit, ...p } } }));
}

export function notice(key: string, vars?: Record<string, string | number>): void {
  patch({ notice: { key, vars, at: Date.now() } });
}

export function clearNotice(): void {
  patch({ notice: null });
}

// ---------------------------------------------------------------- persistence

function storageKey(regionId: string): string {
  return STORAGE_PREFIX + regionId;
}

export function readStoredZones(regionId: string): StoredZones | null {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(storageKey(regionId)) : null;
    return raw ? parseStoredZones(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

export function persist(): void {
  const d = drawn();
  if (!d.regionId || !d.loaded) return;
  try {
    const body: StoredZones = { version: 1, zones: d.zones, settings: d.settings, savedAt: new Date().toISOString() };
    localStorage.setItem(storageKey(d.regionId), JSON.stringify(body));
  } catch {
    /* storage unavailable or full: zones just are not remembered */
  }
}

function forget(regionId: string): void {
  try {
    localStorage.removeItem(storageKey(regionId));
  } catch {
    /* ignore */
  }
}

/**
 * Loads the region's zones and settings (once per region). `defaultInputTime` is used when nothing
 * was stored or the stored input time is not one of `recordedInputTimes`.
 */
export function loadZonesForRegion(regionId: string, recordedInputTimes: string[], defaultInputTime: string | null): void {
  const d = drawn();
  if (d.regionId === regionId && d.loaded) {
    if (!d.settings.inputTime || !recordedInputTimes.includes(d.settings.inputTime)) {
      patch({ settings: { ...d.settings, inputTime: defaultInputTime } });
    }
    return;
  }
  const stored = readStoredZones(regionId);
  const inputTime = stored?.settings.inputTime && recordedInputTimes.includes(stored.settings.inputTime) ? stored.settings.inputTime : defaultInputTime;
  setState({
    drawn: {
      ...DEFAULT_DRAWN,
      regionId,
      loaded: true,
      zones: stored?.zones ?? emptyZones(),
      settings: { inputTime, issueOffsetH: stored?.settings.issueOffsetH ?? 0, marginMin: stored?.settings.marginMin ?? DEFAULT_DRAWN.settings.marginMin },
      footprints: d.footprints.regionId === regionId ? d.footprints : DEFAULT_DRAWN.footprints,
    },
  });
}

/** When the recorded input times arrive later (API came online), keep the setting valid. */
export function ensureInputTime(recordedInputTimes: string[], fallback: string | null): void {
  const d = drawn();
  if (d.settings.inputTime && recordedInputTimes.includes(d.settings.inputTime)) return;
  if (!fallback) return;
  patch({ settings: { ...d.settings, inputTime: fallback } });
  fireInputListener?.();
}

// ---------------------------------------------------------------- geometry changes

function commit(next: DrawnZones, opts: { history?: boolean } = {}): void {
  const d = drawn();
  const history = opts.history === false ? d.history : [...d.history, d.zones].slice(-HISTORY_MAX);
  patch({ zones: next, history });
  persist();
  fireInputListener?.();
}

/** Snapshot before a continuous change (vertex drag, keyboard nudges). */
export function beginChange(): void {
  const d = drawn();
  patch({ history: [...d.history, d.zones].slice(-HISTORY_MAX) });
}

/** Live update during a drag (no history entry; persisted on `endChange`). */
export function moveVertexLive(ref: VertexRef, p: LonLat): void {
  patch({ zones: moveVertex(drawn().zones, ref, p) });
}

export function endChange(): void {
  persist();
  fireInputListener?.();
}

export function undo(): void {
  const d = drawn();
  if (d.edit.drawing && d.edit.draft.length) {
    patchEdit({ draft: d.edit.draft.slice(0, -1) });
    return;
  }
  const prev = d.history[d.history.length - 1];
  if (!prev) return;
  patch({ zones: prev, history: d.history.slice(0, -1), edit: { ...d.edit, selected: null } });
  persist();
  fireInputListener?.();
  notice('zones.notice.undone');
}

export function setActiveZone(key: ZoneKey): void {
  const d = drawn();
  if (d.edit.drawing && d.edit.draft.length) cancelDrawing();
  patchEdit({ active: key, selected: null });
}

export function startDrawing(key?: ZoneKey): void {
  const d = drawn();
  patchEdit({ active: key ?? d.edit.active, drawing: true, draft: [], selected: null });
  const k = key ?? d.edit.active;
  notice(d.zones[k].polygons.length ? 'zones.notice.drawAdd' : 'zones.notice.draw');
}

export function cancelDrawing(): void {
  patchEdit({ drawing: false, draft: [] });
  notice('zones.notice.cancelled');
}

export function addDraftVertex(p: LonLat): void {
  const d = drawn();
  if (!d.edit.drawing) return;
  patchEdit({ draft: [...d.edit.draft, [p[0], p[1]]] });
}

/** Closes the polygon being drawn (≥ 3 vertices) and adds it to the active zone. */
export function closeDrawing(): boolean {
  const d = drawn();
  if (!d.edit.drawing) return false;
  if (d.edit.draft.length < 3) {
    notice('zones.notice.needThree');
    return false;
  }
  const key = d.edit.active;
  const next = addPolygon(d.zones, key, d.edit.draft);
  patchEdit({ drawing: false, draft: [] });
  commit(next);
  notice('zones.notice.closed', { zone: key === 'h5' ? 5 : 8, n: d.edit.draft.length });
  return true;
}

export function selectVertex(ref: VertexRef | null): void {
  const d = drawn();
  if (sameRef(d.edit.selected, ref) || (!ref && !d.edit.selected)) return;
  patchEdit({ selected: ref, active: ref ? ref.zone : d.edit.active });
}

export function insertVertexAt(ref: VertexRef, p: LonLat): VertexRef {
  const d = drawn();
  const r = insertVertex(d.zones, ref, p);
  commit(r.zones);
  patchEdit({ selected: r.ref });
  return r.ref;
}

export function deleteSelectedVertex(): void {
  const d = drawn();
  const ref = d.edit.selected;
  if (!ref) return;
  const r = deleteVertex(d.zones, ref);
  commit(r.zones);
  patchEdit({ selected: null });
  notice(r.removed === 'vertex' ? 'zones.notice.vertexDeleted' : r.removed === 'ring' ? 'zones.notice.ringDeleted' : 'zones.notice.polygonDeleted');
}

/** [ / ] — previous / next vertex of the active zone. */
export function cycleVertex(step: 1 | -1): void {
  const d = drawn();
  const zone = d.zones[d.edit.selected?.zone ?? d.edit.active];
  const refs = vertexRefs(zone);
  if (!refs.length) return;
  const cur = refs.findIndex((r) => sameRef(r, d.edit.selected));
  const next = refs[(cur < 0 ? (step > 0 ? 0 : refs.length - 1) : (cur + step + refs.length) % refs.length)]!;
  patchEdit({ selected: next, active: zone.key });
}

export function clearActiveZone(key?: ZoneKey): void {
  const d = drawn();
  const k = key ?? d.edit.active;
  if (!d.zones[k].polygons.length) return;
  commit(clearZone(d.zones, k));
  patchEdit({ selected: null });
  notice('zones.notice.cleared', { zone: k === 'h5' ? 5 : 8 });
}

/** 초기화: both zones empty, settings back to defaults (undo restores the zones). */
export function resetZones(): void {
  const d = drawn();
  const next = emptyZones();
  patch({
    zones: next,
    history: hasAnyZone(d.zones) ? [...d.history, d.zones].slice(-HISTORY_MAX) : d.history,
    settings: { ...d.settings, issueOffsetH: 0, marginMin: DEFAULT_DRAWN.settings.marginMin },
    edit: { ...d.edit, drawing: false, draft: [], selected: null },
  });
  if (d.regionId) forget(d.regionId);
  fireInputListener?.();
  notice('zones.notice.reset');
}

// ---------------------------------------------------------------- presets (recorded footprints)

export interface PresetChoice {
  h5: Footprint | null;
  h8: Footprint | null;
}

/** Copies the chosen recorded footprints into the zones (vertex reduction only; never buffered or scaled). */
export function applyPreset(choice: PresetChoice): { h5: { before: number; after: number } | null; h8: { before: number; after: number } | null } {
  const d = drawn();
  let next: DrawnZones = { h5: d.zones.h5, h8: d.zones.h8 };
  const report: { h5: { before: number; after: number } | null; h8: { before: number; after: number } | null } = { h5: null, h8: null };
  for (const key of ['h5', 'h8'] as const) {
    const fp = choice[key];
    if (!fp) continue;
    const zone = presetZone(key, fp);
    next = { ...next, [key]: zone };
    report[key] = { before: zone.preset!.verticesBefore, after: zone.preset!.verticesAfter };
  }
  if (!report.h5 && !report.h8) return report;
  patchEdit({ drawing: false, draft: [], selected: null });
  commit(next);
  const parts: string[] = [];
  if (report.h5) parts.push(`5h ${report.h5.before}→${report.h5.after}`);
  if (report.h8) parts.push(`8h ${report.h8.before}→${report.h8.after}`);
  notice('zones.notice.preset', { report: parts.join(' · '), time: choice.h5 ? kstDateTime(choice.h5.inputTime) : kstDateTime(choice.h8!.inputTime) });
  return report;
}

export function setFootprints(p: DrawnState['footprints']): void {
  patch({ footprints: p });
}

// ---------------------------------------------------------------- settings

export function setDrawnSettings(p: Partial<DrawnSettings>): void {
  const d = drawn();
  const next: DrawnSettings = {
    inputTime: p.inputTime !== undefined ? p.inputTime : d.settings.inputTime,
    issueOffsetH: p.issueOffsetH !== undefined ? clampIssueOffsetH(p.issueOffsetH) : d.settings.issueOffsetH,
    marginMin: p.marginMin !== undefined ? clampMarginMin(p.marginMin) : d.settings.marginMin,
  };
  if (next.inputTime === d.settings.inputTime && next.issueOffsetH === d.settings.issueOffsetH && next.marginMin === d.settings.marginMin) return;
  patch({ settings: next });
  persist();
  fireInputListener?.();
}

export function setRightTab(tab: DrawnState['rightTab']): void {
  patch({ rightTab: tab });
}
