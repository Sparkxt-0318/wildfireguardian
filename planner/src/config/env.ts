/**
 * Build-time configuration (planner/.env.example documents every key).
 *
 * VITE_WFG_API_MODE=mock|real is the one switch. The browser always calls same-origin /api/v1/*;
 * vite.config.ts proxies it to the mock (http://127.0.0.1:8765) or to VITE_WFG_API_TARGET.
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
}

const env = import.meta.env;

export const CONFIG: PlannerConfig = {
  apiMode: parseApiMode(env.VITE_WFG_API_MODE),
  apiTarget: parseApiMode(env.VITE_WFG_API_MODE) === 'mock' ? 'http://127.0.0.1:8765' : env.VITE_WFG_API_TARGET || 'http://127.0.0.1:8765',
  stepMin: normalizeStepMin(env.VITE_DEPARTURE_STEP_MIN ?? 10),
  sheltersPerOrigin: normalizeShelterCount(env.VITE_SHELTERS_PER_ORIGIN ?? 3),
  vworldKey: env.VWORLD_API_KEY && env.VWORLD_API_KEY.trim() ? env.VWORLD_API_KEY.trim() : null,
  allowBatch: String(env.VITE_WFG_ALLOW_BATCH ?? '1').trim() !== '0',
};
