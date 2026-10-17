/**
 * Fire-input banner (exact strings), MOCK badge rule, clock formatting and i18n fallbacks.
 */
import { describe, expect, it } from 'vitest';
import { fireInputBanner, mockActive, parseApiMode } from '../../planner/src/domain/labels';
import { formatElapsed, formatRelative, kstClock, kstDateTime } from '../../planner/src/domain/clock';
import { registerStrings, translate } from '../../planner/src/i18n';

describe('fire-input banner', () => {
  it('recorded scenarios name the fire year', () => {
    expect(fireInputBanner({ type: 'recorded' }, 2025)).toBe('2025년 실제 산불 기록 기반 시나리오 재현');
    expect(fireInputBanner({ type: 'recorded' }, 2022, 'ko')).toBe('2022년 실제 산불 기록 기반 시나리오 재현');
  });
  it('drawn zones are an assumption', () => {
    expect(fireInputBanner({ type: 'spread_zones' }, 2025)).toBe('사용자 입력 확산 구역 (가정)');
  });
  it('has English equivalents', () => {
    expect(fireInputBanner({ type: 'recorded' }, 2025, 'en')).toBe('Recorded 2025 wildfire · scenario replay');
    expect(fireInputBanner({ type: 'spread_zones' }, 2025, 'en')).toBe('User-drawn spread zones (assumption)');
  });
  it('fixed footer and verdict texts', () => {
    expect(translate('ko', 'footer.rule')).toBe('사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.');
    expect(translate('ko', 'verdict.checked_route')).toBe('확인된 경로');
    expect(translate('ko', 'verdict.model_no_route')).toBe('모델상 경로 없음');
    expect(translate('ko', 'verdict.unresolved')).toBe('미확인');
    expect(translate('ko', 'headline.unresolved')).toBe('미확인 — 판단 불가 (안전으로 간주하지 마십시오)');
    expect(translate('ko', 'data.empty')).toBe('계산 결과 없음 — API 연결 또는 사전 계산 캐시가 필요합니다');
    expect(translate('ko', 'travel.title')).toBe('이동시간만 고려한 경로 (비교용)');
    expect(translate('ko', 'headline.caveat', { time: '18:10' })).toBe('앞선 출발 시각 중 확인되지 않은 구간이 있습니다 (연속 확인 기준 18:10)');
  });
});

describe('MOCK badge', () => {
  it('shows with the mock switch, a mock health or any mock result', () => {
    expect(mockActive({ envMode: 'mock', healthMock: false, resultsMock: false })).toBe(true);
    expect(mockActive({ envMode: 'real', healthMock: true, resultsMock: false })).toBe(true);
    expect(mockActive({ envMode: 'real', healthMock: false, resultsMock: true })).toBe(true);
  });
  it('disappears for a real API without markers in real mode', () => {
    expect(mockActive({ envMode: 'real', healthMock: false, resultsMock: false })).toBe(false);
  });
  it('the switch defaults to mock', () => {
    expect(parseApiMode(undefined)).toBe('mock');
    expect(parseApiMode('REAL')).toBe('real');
    expect(parseApiMode('live')).toBe('mock');
  });
});

describe('clock', () => {
  it('KST wall time = input time (UTC) + offset', () => {
    expect(kstClock('2025-03-24T09:00:00Z', 0)).toBe('18:00');
    expect(kstClock('2025-03-24T09:00:00Z', 600)).toBe('18:10');
    expect(kstClock('2025-03-24T09:00:00Z', 2143, { seconds: true })).toBe('18:35:43');
    expect(kstDateTime('2025-03-25T17:00:00Z')).toBe('2025-03-26 02:00 KST');
  });
  it('elapsed and relative formats', () => {
    expect(formatElapsed(2147)).toBe('+35분 47초');
    expect(formatElapsed(2100, 'en')).toBe('+35 min');
    expect(formatRelative(6000)).toBe('T+1:40');
  });
});

describe('i18n', () => {
  it('falls back to Korean, then the key; interpolates', () => {
    registerStrings({ ko: { 'test.only.ko': '한국어 {n}' } });
    expect(translate('en', 'test.only.ko', { n: 3 })).toBe('한국어 3');
    expect(translate('en', 'no.such.key')).toBe('no.such.key');
  });
});

describe('comparison status tokens and JOB_FROZEN have ko and en labels', async () => {
  const { translate } = await import('../../planner/src/i18n');
  it('labels every status token seen in the data, in both languages', () => {
    for (const tok of ['CLEAR', 'DEFINITE_CONTACT', 'CERTIFIED_ADMISSIBLE', 'DEFINITE_REJECT', 'model_no_route', 'unresolved']) {
      const ko = translate('ko', `travel.status.${tok}`);
      const en = translate('en', `travel.status.${tok}`);
      expect(ko).not.toBe(`travel.status.${tok}`);
      expect(en).not.toBe(ko);
      expect(/[가-힣]/.test(ko)).toBe(true);
    }
    expect(translate('en', 'error.JOB_FROZEN')).toContain('unresolved');
    expect(translate('ko', 'error.JOB_FROZEN')).toContain('미확인');
  });
});
