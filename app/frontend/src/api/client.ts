// Typed client for the resident gateway. Mirrors docs/app/ARCHITECTURE.md §5
// EXACTLY — field names verbatim. The UI never shows a number this client did
// not receive from the API (the truth rule).

// ---------------------------------------------------------------------------
// Shared / GeoJSON
// ---------------------------------------------------------------------------

export type AppMode = "demo" | "live";

export interface ApiErrorBody {
  error: string;
  detail_ko: string;
  detail_en: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;
  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.error ?? `http_${status}`);
    this.status = status;
    this.body = body;
  }
  get code(): string {
    return this.body?.error ?? `http_${this.status}`;
  }
}

// Minimal GeoJSON types for the shapes the contract uses.
export interface PointGeometry {
  type: "Point";
  coordinates: [number, number]; // [lon, lat]
}
export interface LineStringGeometry {
  type: "LineString";
  coordinates: [number, number][]; // [[lon, lat], ...]
}
export interface PolygonGeometry {
  type: "Polygon";
  coordinates: [number, number][][];
}
export type AnyGeometry = PointGeometry | LineStringGeometry | PolygonGeometry;

export interface Feature<
  G extends AnyGeometry = AnyGeometry,
  P = Record<string, unknown>,
> {
  type: "Feature";
  geometry: G;
  properties: P;
}

export interface FeatureCollection<
  G extends AnyGeometry = AnyGeometry,
  P = Record<string, unknown>,
> {
  type: "FeatureCollection";
  features: Feature<G, P>[];
}

// ---------------------------------------------------------------------------
// §5 endpoint shapes
// ---------------------------------------------------------------------------

export interface Health {
  ok: boolean;
  mode: AppMode;
  time_utc: string;
}

export interface AppConfig {
  mode: AppMode;
  stripe_publishable_key: string | null;
  tile_url: string;
  demo_banner_ko: string;
  demo_banner_en: string;
}

export type DangerLevel = "SAFE" | "WATCH" | "GO";

export interface Danger {
  level: DangerLevel;
  label_ko: string;
  label_en: string;
  reason_ko: string;
  reason_en: string;
}

export interface FireStatus {
  active: boolean;
  distance_km: number | null;
  bearing_deg: number | null;
  bearing_text_ko: string | null;
  bearing_text_en: string | null;
  detections: number;
  first_detected_utc: string | null;
  last_update_utc: string | null;
}

// The spec example (§5.1) shows values for every field, but the gateway may
// honestly have no weather feed (live mode) and then sends null — the truth
// rule forbids inventing a number, so the client types tolerate null and the
// UI simply omits what the API did not send.
export interface WeatherStatus {
  wind_speed_ms: number | null;
  wind_dir_deg: number | null;
  wind_toward_user: boolean;
  rh_pct: number | null;
  temp_c: number | null;
  days_since_rain: number | null;
}

export type CardKind = "action" | "info" | "route" | "contact";
export type CardIcon =
  | "flame"
  | "wind"
  | "route"
  | "phone"
  | "shelter"
  | "clock"
  | "check"
  | "home";
export type CardActionType = "open_map" | "open_route" | "call" | "none";

export interface CardAction {
  type: CardActionType;
  value: string | null; // e.g. "119" for call
}

export interface Card {
  id: string;
  priority: number;
  kind: CardKind;
  title_ko: string;
  title_en: string;
  body_ko: string;
  body_en: string;
  icon: CardIcon;
  action: CardAction;
}

export interface Situation {
  mode: AppMode;
  generated_utc: string;
  danger: Danger;
  fire: FireStatus;
  weather: WeatherStatus;
  eta_minutes: number | null;
  cards: Card[];
  prediction_available: boolean;
  disclaimer_ko: string;
  disclaimer_en: string;
}

// fire detection features (GET /v1/fires)
export interface FireDetectionProps {
  frp_mw?: number;
  confidence?: string;
  sensor?: string;
  [key: string]: unknown;
}
export type FiresCollection = FeatureCollection<PointGeometry, FireDetectionProps>;

// spread features (GET /v1/spread)
export interface SpreadPolygonProps {
  horizon_hours: 1 | 3 | 6;
  p_level: "likely" | "possible";
  [key: string]: unknown;
}
export interface PathwayProps {
  kind: "pathway";
  bearing_deg: number;
  [key: string]: unknown;
}
export type SpreadCollection = FeatureCollection<
  PolygonGeometry | LineStringGeometry,
  SpreadPolygonProps | PathwayProps
>;

export type RouteStatus = "ok" | "no_safe_walk" | "outside_region";

export interface RouteShelter {
  name_ko: string;
  name_en: string;
  lat: number;
  lon: number;
  distance_km: number;
  walk_minutes: number;
}

export interface RouteStep {
  instruction_ko: string;
  instruction_en: string;
  distance_m: number;
}

export interface RouteResult {
  status: RouteStatus;
  shelter?: RouteShelter | null;
  geometry?: LineStringGeometry | null;
  steps?: RouteStep[];
  warnings_ko: string[];
  warnings_en: string[];
}

export interface Shelter {
  name_ko: string;
  name_en: string;
  lat: number;
  lon: number;
  distance_km: number;
  walk_minutes: number;
}

export interface HistoryPoint {
  t_utc: string;
  detections: number;
  area_ha_est: number;
  wind_speed_ms: number;
  rh_pct: number;
}

export type BillingPlan = "monthly" | "yearly";

export interface CheckoutRequest {
  plan: BillingPlan;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export interface BillingStatus {
  active: boolean;
  plan: string | null;
  renews_utc: string | null;
}

// ---------------------------------------------------------------------------
// HTTP core
// ---------------------------------------------------------------------------

// Same-origin by default: the Vite dev server proxies /v1 → localhost:8100,
// production serves the SPA behind the same gateway. Override for native
// (Capacitor) builds with VITE_API_BASE.
const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch {
    throw new ApiError(0, {
      error: "network",
      detail_ko: "인터넷 연결을 확인해 주세요.",
      detail_en: "Please check your internet connection.",
    });
  }
  if (!res.ok) {
    let body: ApiErrorBody | null = null;
    try {
      const parsed = (await res.json()) as Partial<ApiErrorBody>;
      if (parsed && typeof parsed.error === "string") {
        body = {
          error: parsed.error,
          detail_ko: parsed.detail_ko ?? "",
          detail_en: parsed.detail_en ?? "",
        };
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, body);
  }
  return (await res.json()) as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Endpoints (§5, one function per row)
// ---------------------------------------------------------------------------

export function getHealth(): Promise<Health> {
  return request<Health>("/v1/health");
}

export function getConfig(): Promise<AppConfig> {
  return request<AppConfig>("/v1/config");
}

export function getSituation(
  lat: number,
  lon: number,
  t?: number,
): Promise<Situation> {
  return request<Situation>(`/v1/situation${query({ lat, lon, t })}`);
}

export function getFires(t?: number): Promise<FiresCollection> {
  return request<FiresCollection>(`/v1/fires${query({ t })}`);
}

export function getSpread(
  lat: number,
  lon: number,
  t?: number,
): Promise<SpreadCollection> {
  return request<SpreadCollection>(`/v1/spread${query({ lat, lon, t })}`);
}

export function getRoute(
  lat: number,
  lon: number,
  t?: number,
): Promise<RouteResult> {
  return request<RouteResult>(`/v1/route${query({ lat, lon, t })}`);
}

export async function getShelters(lat: number, lon: number): Promise<Shelter[]> {
  // Contract: nearest shelters sorted by walk distance. Accept either a bare
  // array or a {shelters: [...]} wrapper so a benign envelope difference
  // doesn't break residents.
  const data = await request<Shelter[] | { shelters: Shelter[] }>(
    `/v1/shelters${query({ lat, lon })}`,
  );
  return Array.isArray(data) ? data : (data.shelters ?? []);
}

export async function getHistory(t?: number): Promise<HistoryPoint[]> {
  // Contract (§5): a bare array of history points. Accept a {points: [...]}
  // envelope too, so a benign wrapper difference doesn't hide the chart.
  const data = await request<HistoryPoint[] | { points: HistoryPoint[] }>(
    `/v1/history${query({ t })}`,
  );
  return Array.isArray(data) ? data : (data.points ?? []);
}

export function postCheckout(body: CheckoutRequest): Promise<CheckoutResponse> {
  return request<CheckoutResponse>("/v1/billing/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getBillingStatus(customerId: string): Promise<BillingStatus> {
  return request<BillingStatus>(
    `/v1/billing/status${query({ customer_id: customerId })}`,
  );
}

// ---------------------------------------------------------------------------
// Live situation stream: SSE with a 10 s polling fallback (hard requirement).
// ---------------------------------------------------------------------------

export interface SituationStreamHandle {
  close: () => void;
}

const POLL_INTERVAL_MS = 10_000;
const SSE_RETRY_MS = 60_000;

/**
 * Subscribe to the situation for a coordinate.
 * Primary transport: EventSource on /v1/alerts/stream (event: situation).
 * On SSE error: falls back to polling GET /v1/situation every 10 s, and
 * quietly retries SSE once a minute.
 */
export function subscribeSituation(
  lat: number,
  lon: number,
  onSituation: (s: Situation) => void,
  onError?: (e: unknown) => void,
): SituationStreamHandle {
  let closed = false;
  let es: EventSource | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let sseRetryTimer: ReturnType<typeof setTimeout> | null = null;

  const stopPolling = () => {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const pollOnce = async () => {
    try {
      const s = await getSituation(lat, lon);
      if (!closed) onSituation(s);
    } catch (e) {
      if (!closed) onError?.(e);
    }
  };

  const startPolling = () => {
    if (closed || pollTimer !== null) return;
    void pollOnce();
    pollTimer = setInterval(() => void pollOnce(), POLL_INTERVAL_MS);
  };

  const openSse = () => {
    if (closed) return;
    if (typeof EventSource === "undefined") {
      startPolling();
      return;
    }
    try {
      es = new EventSource(
        `${API_BASE}/v1/alerts/stream${query({ lat, lon })}`,
      );
    } catch {
      startPolling();
      return;
    }
    es.addEventListener("situation", (ev) => {
      try {
        const s = JSON.parse((ev as MessageEvent).data) as Situation;
        stopPolling(); // SSE is delivering — polling not needed
        onSituation(s);
      } catch (e) {
        onError?.(e);
      }
    });
    // heartbeat events keep the connection warm; nothing to do with them.
    es.onerror = () => {
      es?.close();
      es = null;
      if (closed) return;
      startPolling();
      if (sseRetryTimer !== null) clearTimeout(sseRetryTimer);
      sseRetryTimer = setTimeout(openSse, SSE_RETRY_MS);
    };
  };

  // Fetch immediately so the UI has data before the first SSE tick.
  void pollOnce();
  openSse();

  return {
    close: () => {
      closed = true;
      es?.close();
      es = null;
      stopPolling();
      if (sseRetryTimer !== null) {
        clearTimeout(sseRetryTimer);
        sseRetryTimer = null;
      }
    },
  };
}
