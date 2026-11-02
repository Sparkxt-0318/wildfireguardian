/**
 * Build-time configuration (planner/.env.example documents every key).
 *
 * VITE_WFG_API_MODE=mock|real|static is the one switch. In mock and real mode the browser calls
 * same-origin /api/v1/*, which vite.config.ts proxies to the mock (http://127.0.0.1:8765) or to
 * VITE_WFG_API_TARGET. In static mode (also `vite build --mode static`) there is no API: every
 * result comes from the committed precompute cache and static files, and nothing that needs live
 * computation is offered.
 */
import { normalizeShelterCount, normalizeStepMin } from '../domain/plan';
import { parseApiMode, type ApiModeSetting } from '../domain/labels';

export interface PlannerConfig {
  apiMode: ApiModeSetting;
  apiTarget: string;
  stepMin: number;
  sheltersPerOrigin: number;
  vworldKey: string | null;
  /**
   * VITE_WFG_ALLOW_BATCH (default 1). 0: against a real API, a scenario without a precomputed
   * cache never offers "점검 시작" (booth: nobody can start hours of checks by browsing).
   */
  allowBatch: boolean;
  /** "의견 보내기 / Feedback" link (VITE_FEEDBACK_URL); null hides the button outside the static demo */
  feedbackUrl: string | null;
  /** repository web URL (VITE_REPO_URL) for links to the local-run instructions */
  repoUrl: string;
}

/** Public repository of this project (links to documentation only; never fetched). */
export const DEFAULT_REPO_URL = 'https://github.com/Sparkxt-0318/wildfireguardian';

/** `vite build --mode static` or VITE_WFG_API_MODE=static → 'static'. */
export function resolveApiMode(e: { MODE?: string; VITE_WFG_API_MODE?: string }): ApiModeSetting {
  return e.MODE === 'static' ? 'static' : parseApiMode(e.VITE_WFG_API_MODE);
}

/** Only https:// links are accepted for the feedback / repository links. */
function httpsUrl(v: unknown): string | null {
  const s = String(v ?? '').trim();
  return /^https:\/\/[^\s"'<>]+$/i.test(s) ? s : null;
}

const env = import.meta.env;
const apiMode = resolveApiMode(env);
const repoUrl = (httpsUrl(env.VITE_REPO_URL) ?? DEFAULT_REPO_URL).replace(/\/+$/, '');

export const CONFIG: PlannerConfig = {
  apiMode,
  apiTarget: apiMode === 'static' ? '' : apiMode === 'mock' ? 'http://127.0.0.1:8765' : env.VITE_WFG_API_TARGET || 'http://127.0.0.1:8765',
  stepMin: normalizeStepMin(env.VITE_DEPARTURE_STEP_MIN ?? 10),
  sheltersPerOrigin: normalizeShelterCount(env.VITE_SHELTERS_PER_ORIGIN ?? 3),
  // the static demo never offers the internet raster (and never ships a key in its public bundle)
  vworldKey: apiMode !== 'static' && env.VWORLD_API_KEY && env.VWORLD_API_KEY.trim() ? env.VWORLD_API_KEY.trim() : null,
  allowBatch: String(env.VITE_WFG_ALLOW_BATCH ?? '1').trim() !== '0',
  feedbackUrl: httpsUrl(env.VITE_FEEDBACK_URL) ?? (apiMode === 'static' ? `${repoUrl}/issues/new?template=planner-feedback.md` : null),
  repoUrl,
};

/** Public static demo: no Route-Check API; results only from the committed cache. */
export const STATIC_DEMO = CONFIG.apiMode === 'static';
