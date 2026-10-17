/**
 * Application state (zustand). Actions with I/O live in ./controller.ts; components read state
 * with selectors and call controller functions.
 */
import { create } from 'zustand';
import type {
  ApiRegion,
  CacheData,
  CacheEntry,
  ForecastData,
  HealthInfo,
  OriginPlan,
  Place,
  ProvenanceInfo,
  RegionIndexEntry,
  RouteDetail,
} from '../domain/types';
import { DEFAULT_MARGIN_MIN, emptyZones, type DrawnZones, type LonLat, type VertexRef, type ZoneKey } from '../domain/zones';
import type { Footprint } from '../data/staticData';

export const DRAWN_SCENARIO = 'drawn';

export type ApiStatus = 'checking' | 'online' | 'offline';

export interface ApiErrorInfo {
  code: string;
  message: string;
  status?: number;
}

export interface BatchState {
  state: 'idle' | 'confirm' | 'running' | 'done' | 'error' | 'cancelled';
  key: string | null;
  done: number;
  total: number;
  dispatchPlans: number;
  researchChecks: number;
  origins: number;
  error: ApiErrorInfo | null;
  startedAt: number | null;
  finishedAt: number | null;
}

export type CellProgress = 'pending' | 'running' | 'done';

export interface RecomputeState {
  originId: string;
  state: 'running' | 'done' | 'error' | 'cancelled';
  total: number;
  done: number;
  /** per departure offset */
  cells: Record<number, CellProgress>;
  error: ApiErrorInfo | null;
  startedAt: number;
  finishedAt: number | null;
}

export interface TravelOnlyState {
  state: 'loading' | 'ready' | 'error';
  /** job id of the full-policy check this comparison belongs to */
  forJobId: string | null;
  detail: RouteDetail | null;
  error: ApiErrorInfo | null;
  source: 'cache' | 'live';
}

export interface ForecastState {
  state: 'idle' | 'loading' | 'ready' | 'unavailable' | 'error';
  key: string | null;
  data: ForecastData | null;
  error: ApiErrorInfo | null;
}

export type OriginFilter = 'all' | 'vulnerable' | 'needs_alternative' | 'in_zone';

/** Fire-input settings of drawn zones (contract SpreadZonesFireInput scope v1.1+). */
export interface DrawnSettings {
  /** one of the region's RECORDED input times (grid, clock, burning cells; hazard horizon 1 h) */
  inputTime: string | null;
  /** issued_at = input_time − issueOffsetH (0–8 h) */
  issueOffsetH: number;
  /** margin_min (0–120, default 60) — 보수적 조기 점화 여유 */
  marginMin: number;
}

export interface ZoneEditState {
  active: ZoneKey;
  drawing: boolean;
  /** vertices of the polygon being drawn */
  draft: LonLat[];
  selected: VertexRef | null;
}

export interface DrawnNotice {
  key: string;
  vars?: Record<string, string | number>;
  at: number;
}

/** Zones as submitted with the results currently shown (fire_input of those checks). */
export interface SubmittedZones {
  key: string;
  inputTime: string;
  issuedAt: string;
  marginMin: number;
  burningScenarioSetId: string | null;
  zones: { key: ZoneKey; arrivalHMax: number; polygons: number; vertices: number; areaKm2: number; presetTime: string | null; edited: boolean }[];
  submittedAt: string;
}

export interface DrawnDispatchInfo {
  jobId: string;
  assumptions: Record<string, unknown> | null;
  provenance: ProvenanceInfo | null;
  mock: boolean;
  origins: number;
}

export interface DrawnState {
  /** region the zones belong to (zones are kept per region in localStorage) */
  regionId: string | null;
  loaded: boolean;
  zones: DrawnZones;
  /** undo stack (most recent last) */
  history: DrawnZones[];
  settings: DrawnSettings;
  edit: ZoneEditState;
  footprints: { regionId: string | null; state: 'idle' | 'loading' | 'ready' | 'error'; items: Footprint[]; error: string | null };
  notice: DrawnNotice | null;
  /** fire-input fingerprint of the drawn results in `plans` (null = nothing computed) */
  resultsKey: string | null;
  submitted: SubmittedZones | null;
  dispatch: DrawnDispatchInfo[];
  rightTab: 'zones' | 'origin';
}

export const DEFAULT_DRAWN: DrawnState = {
  regionId: null,
  loaded: false,
  zones: emptyZones(),
  history: [],
  settings: { inputTime: null, issueOffsetH: 0, marginMin: DEFAULT_MARGIN_MIN },
  edit: { active: 'h5', drawing: false, draft: [], selected: null },
  footprints: { regionId: null, state: 'idle', items: [], error: null },
  notice: null,
  resultsKey: null,
  submitted: null,
  dispatch: [],
  rightTab: 'zones',
};

export interface PlannerState {
  regionIndex: RegionIndexEntry[];
  regionIndexError: string | null;

  apiStatus: ApiStatus;
  health: HealthInfo | null;
  apiError: ApiErrorInfo | null;
  apiRegions: Record<string, ApiRegion>;

  cacheIndex: CacheEntry[];

  regionId: string | null;
  scenarioId: string | null;
  places: Place[];
  placesState: 'idle' | 'loading' | 'ready' | 'error';

  dataSource: 'cache' | 'live' | 'none';
  dataLoading: boolean;
  dataError: string | null;
  cache: CacheData | null;
  plans: Record<string, OriginPlan>;
  /** live-fetched route details by job id */
  routes: Record<string, RouteDetail>;
  routeErrors: Record<string, ApiErrorInfo>;
  travelOnly: Record<string, TravelOnlyState>;
  batch: BatchState;
  recompute: RecomputeState | null;
  forecast: ForecastState;

  selectedOriginId: string | null;
  selectedOffsetS: number | null;
  hoverOriginId: string | null;
  filter: OriginFilter;
  search: string;
  clockS: number;
  playing: boolean;
  showForecast: boolean;
  showVworld: boolean;
  dialogs: { about: boolean; planSheet: boolean; export: boolean };
  /** user-drawn spread zones (사용자 입력 확산 구역, 가정) */
  drawn: DrawnState;
}

export const IDLE_BATCH: BatchState = {
  state: 'idle',
  key: null,
  done: 0,
  total: 0,
  dispatchPlans: 0,
  researchChecks: 0,
  origins: 0,
  error: null,
  startedAt: null,
  finishedAt: null,
};

export const useStore = create<PlannerState>(() => ({
  regionIndex: [],
  regionIndexError: null,
  apiStatus: 'checking',
  health: null,
  apiError: null,
  apiRegions: {},
  cacheIndex: [],
  regionId: null,
  scenarioId: null,
  places: [],
  placesState: 'idle',
  dataSource: 'none',
  dataLoading: false,
  dataError: null,
  cache: null,
  plans: {},
  routes: {},
  routeErrors: {},
  travelOnly: {},
  batch: IDLE_BATCH,
  recompute: null,
  forecast: { state: 'idle', key: null, data: null, error: null },
  selectedOriginId: null,
  selectedOffsetS: null,
  hoverOriginId: null,
  filter: 'all',
  search: '',
  clockS: 0,
  playing: false,
  showForecast: true,
  showVworld: false,
  dialogs: { about: false, planSheet: false, export: false },
  drawn: DEFAULT_DRAWN,
}));

export const setState = useStore.setState;
export const getState = useStore.getState;
