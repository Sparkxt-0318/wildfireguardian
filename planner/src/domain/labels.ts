/**
 * Fire-input banner (ARCHITECTURE.md §0.5) and MOCK detection rules. Pure functions, unit-tested.
 */
import type { Lang } from './clock';
import type { FireInput } from './types';

/** Banner text for the fire input. Recorded 2025 → "2025년 실제 산불 기록 기반 시나리오 재현". */
export function fireInputBanner(
  fireInput: { type: FireInput['type'] } | null,
  fireYear: number | null,
  lang: Lang = 'ko',
): string {
  if (!fireInput) return lang === 'ko' ? '화재 입력 선택 전' : 'No fire input selected';
  if (fireInput.type === 'spread_zones') {
    return lang === 'ko' ? '사용자 입력 확산 구역 (가정)' : 'User-drawn spread zones (assumption)';
  }
  if (fireYear === null || !Number.isFinite(fireYear)) {
    return lang === 'ko' ? '실제 산불 기록 기반 시나리오 재현' : 'Recorded wildfire · scenario replay';
  }
  return lang === 'ko'
    ? `${fireYear}년 실제 산불 기록 기반 시나리오 재현`
    : `Recorded ${fireYear} wildfire · scenario replay`;
}

export type ApiModeSetting = 'mock' | 'real';

export function parseApiMode(v: unknown): ApiModeSetting {
  return String(v ?? '').trim().toLowerCase() === 'real' ? 'real' : 'mock';
}

/**
 * The MOCK badge is shown when ANY of these holds:
 * - VITE_WFG_API_MODE=mock (the configured switch),
 * - /health reports mode "mock" or mock: true,
 * - any loaded result, plan, cache or provenance carries mock: true.
 * With mode "real", a real API (no markers) and no MOCK-derived results, it disappears.
 */
export function mockActive(signals: { envMode: ApiModeSetting; healthMock: boolean; resultsMock: boolean; realCacheOnly?: boolean }): boolean {
  if (signals.healthMock || signals.resultsMock) return true;
  // Everything on screen comes from a precompute cache made against the real API and no mock server is
  // answering: the build's default mock setting alone does not make that data MOCK.
  if (signals.realCacheOnly) return false;
  return signals.envMode === 'mock';
}
