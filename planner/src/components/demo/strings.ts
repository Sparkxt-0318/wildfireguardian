/**
 * Strings of the public static demo (DEMO ribbon, judge intro + 3-step tour, "no live computation"
 * notes, feedback link). New keys only — nothing in src/i18n/strings.ts is overridden. Registered
 * on import (registerStrings).
 *
 * Wording rules (planner/docs/ARCHITECTURE.md §0): exactly three results; never "safe"; scenario
 * members are fire scenarios from the forecast, not simulations of the actual fire.
 */
import { registerStrings } from '../../i18n';

export const DEMO_STRINGS = {
  ko: {
    'demo.chip': 'DEMO',
    'demo.chipText': '{period} 기록 시나리오 · 연구 프로토타입',
    'demo.chipTextNoPeriod': '기록 시나리오 · 연구 프로토타입',
    'demo.chipShort': '{period} 기록 · 연구 프로토타입',
    'demo.period': '{year}년 {month}월',
    'demo.periodShort': '{year}년 {month}월',
    'demo.periodRange': '{from}–{to}',
    'demo.chipTitle': '공개 정적 데모: 평가 호스트에서 Route-Check API로 미리 계산해 저장소에 넣어 둔 결과만 재생합니다. 이 화면에서는 아무것도 새로 계산하지 않습니다.',
    'demo.noLive': '실시간 계산 없음',
    'demo.feedback': '의견 보내기',
    'demo.feedbackTitle': 'GitHub 이슈 양식이 새 탭에서 열립니다 (GitHub 계정 필요). 이름·전화번호 등 개인정보는 적지 마십시오.',
    'demo.tour': '둘러보기',
    'demo.api': '정적 데모 · API 없음',
    'demo.apiTitle': 'Route-Check API에 연결하지 않습니다. 화면의 모든 결과는 저장소에 포함된 사전 계산 캐시(평가 호스트에서 계산)에서 읽습니다.',
    'demo.static.title': '정적 데모에서는 새로 계산하지 않습니다',
    'demo.static.body': '이 공개 데모는 미리 계산해 둔 결과만 보여 줍니다. 다시 계산하기, 비교 경로 계산, 확산 구역 점검에는 로컬에서 실행하는 Route-Check API가 필요합니다.',
    'demo.static.link': '로컬 실행 방법 (README)',
    'demo.static.forecast': '이 시나리오의 예측 격자 파일이 정적 데모에 없습니다',
    'demo.drawn.notComputedSub': '이 구역으로는 계산하지 않았습니다. 정적 데모에서는 확산 구역을 점검할 수 없습니다 (로컬 Route-Check API 필요).',
    'demo.sheetLabel': 'DEMO · {period} 기록 시나리오 재생 · 연구 프로토타입',
    'demo.sheetLabelNoPeriod': 'DEMO · 기록 시나리오 재생 · 연구 프로토타입',
    'demo.sheetLabelDrawn': 'DEMO · 정적 데모 · 연구 프로토타입',
    'error.STATIC_DEMO': '정적 데모: Route-Check API 없음 (요청을 보내지 않음)',
    'error.FORECAST_MISMATCH': '예측 격자 파일이 이 시나리오와 맞지 않아 표시하지 않습니다',

    'demo.intro.title': 'WildfireGuardian 공개 데모',
    // ≤ 80 words together with the title and the three verdict chips (see tests/planner/staticDemo.test.ts)
    'demo.intro.body':
      '지자체 안전 담당자와 요양시설 관리자를 위한 산불 사전 대피계획 보조 도구입니다(실시간 대피 지휘·운영용 아님). 이 연구 프로토타입은 {period} {regions} 산불에 대해, 예보에서 만든 화재 시나리오별로 미리 점검해 둔 결과를 재생합니다. 마을·시설마다 출발 마감(모델 안에서 점검된 차량 경로가 남은 가장 늦은 출발 시각)과 그 근거를 보여 줍니다. 이 화면에서는 아무것도 새로 계산하지 않습니다.',
    'demo.intro.verdicts': '결과는 세 가지뿐입니다',
    'demo.intro.and': ', ',
    'demo.intro.start': '3단계 둘러보기',
    'demo.intro.close': '바로 살펴보기',
    'demo.intro.closeAria': '소개 닫기',
    'demo.intro.lang': '화면 언어',

    'demo.tour.step': '{n} / 3단계',
    'demo.tour.1.title': '마을·요양시설 고르기',
    'demo.tour.1.body': '출발지 목록은 급한 순서입니다: 모델상 경로 없음 → 미확인 → 출발 마감이 이른 곳. 마을이나 요양시설을 하나 고르십시오.',
    'demo.tour.2.title': '출발 마감과 근거 읽기',
    'demo.tour.2.body': '출발 마감은 모델 안에서 점검된 차량 경로가 남아 있는 가장 늦은 출발 시각입니다. 아래에 출발 시각별 결과, 점검된 경로, 시나리오별 열 노출과 출처가 있습니다. 점검된 경로가 있는 출발 시각이 없으면 시각 대신 그 결과(모델상 경로 없음 또는 미확인)를 표시합니다.',
    'demo.tour.3.title': 'A4 계획서 열기',
    'demo.tour.3.body': '계획서는 마을·시설마다 A4 한 장에 출발 마감, 대피 장소, 경로 지도, 대안 계획과 한계를 담습니다. 인쇄하거나 PDF로 저장할 수 있습니다.',
    'demo.tour.next': '다음',
    'demo.tour.back': '이전',
    'demo.tour.open': '계획서 열기',
    'demo.tour.skip': '그만 보기',
  },
  en: {
    'demo.chip': 'DEMO',
    'demo.chipText': 'recorded {period} scenarios · research prototype',
    'demo.chipTextNoPeriod': 'recorded scenarios · research prototype',
    'demo.chipShort': '{period} replay · research prototype',
    'demo.period': '{monthName} {year}',
    'demo.periodShort': '{monthShort} {year}',
    'demo.periodRange': '{from}–{to}',
    'demo.chipTitle': 'Public static demo: replays results that the Route-Check API computed beforehand on the evaluated host and that are committed to the repository. Nothing is computed on this page.',
    'demo.noLive': 'nothing computed live',
    'demo.feedback': 'Feedback',
    'demo.feedbackTitle': 'Opens a GitHub issue form in a new tab (GitHub account needed). Please do not include names, phone numbers or other personal data.',
    'demo.tour': 'Tour',
    'demo.api': 'Static demo · no API',
    'demo.apiTitle': 'No Route-Check API is contacted. Every result on screen is read from the precompute cache committed to the repository (computed on the evaluated host).',
    'demo.static.title': 'Nothing is computed in the static demo',
    'demo.static.body': 'This public demo shows precomputed results only. Recomputing, comparison routes and checks of drawn spread zones need the Route-Check API running locally.',
    'demo.static.link': 'How to run it locally (README)',
    'demo.static.forecast': 'No forecast-cell file for this scenario in the static demo',
    'demo.drawn.notComputedSub': 'Not computed with these zones. The static demo cannot check drawn spread zones (needs a local Route-Check API).',
    'demo.sheetLabel': 'DEMO · recorded {period} scenario replay · research prototype',
    'demo.sheetLabelNoPeriod': 'DEMO · recorded scenario replay · research prototype',
    'demo.sheetLabelDrawn': 'DEMO · static demo · research prototype',
    'error.STATIC_DEMO': 'Static demo: no Route-Check API (nothing was sent)',
    'error.FORECAST_MISMATCH': 'The forecast file does not match this scenario, so it is not shown',

    'demo.intro.title': 'WildfireGuardian public demo',
    // ≤ 80 words together with the title and the three verdict chips (see tests/planner/staticDemo.test.ts)
    'demo.intro.body':
      'A pre-season evacuation planning aid — not for live operations — for local safety staff and care-facility managers. This research prototype replays results checked in advance for the {period} {regions} wildfires, using fire scenarios from the forecast. For each village and care facility it shows the leave-by time (the latest departure with a checked vehicle route within the model) and its evidence. Nothing is computed live.',
    'demo.intro.verdicts': 'There are exactly three results',
    'demo.intro.and': ' and ',
    'demo.intro.start': 'Take the 3-step tour',
    'demo.intro.close': 'Explore on my own',
    'demo.intro.closeAria': 'Close the introduction',
    'demo.intro.lang': 'Language',

    'demo.tour.step': 'Step {n} of 3',
    'demo.tour.1.title': 'Pick a village or care facility',
    'demo.tour.1.body': 'The list of origins is sorted by urgency: no route in the model, then unresolved, then the earliest leave-by time. Pick a village or a care facility.',
    'demo.tour.2.title': 'Read the leave-by time and the evidence',
    'demo.tour.2.body': 'The leave-by time (출발 마감) is the latest departure that still has a checked vehicle route within the model. Below it: the result per departure time, the checked route, heat exposure per fire scenario and the provenance. If no departure time has a checked route, it shows that result (no route in the model, or unresolved) instead of a time.',
    'demo.tour.3.title': 'Open the A4 plan sheet',
    'demo.tour.3.body': 'The plan sheet gives each village or facility one A4 page: leave-by time, shelter, route map, alternative plans and limitations — ready to print or save as PDF.',
    'demo.tour.next': 'Next',
    'demo.tour.back': 'Back',
    'demo.tour.open': 'Open the plan sheet',
    'demo.tour.skip': 'End tour',
  },
} as const;

registerStrings({ ko: { ...DEMO_STRINGS.ko }, en: { ...DEMO_STRINGS.en } });

const MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "2025-03" → {year: 2025, month: 3, monthName: "March", monthShort: "Mar"} (null when not YYYY-MM). */
export function monthParts(ym: string): { year: number; month: number; monthName: string; monthShort: string } | null {
  const m = /^(\d{4})-(\d{2})$/.exec(ym);
  if (!m) return null;
  const month = Number(m[2]);
  if (month < 1 || month > 12) return null;
  const monthName = MONTHS_EN[month - 1]!;
  return { year: Number(m[1]), month, monthName, monthShort: monthName.slice(0, 3) };
}
