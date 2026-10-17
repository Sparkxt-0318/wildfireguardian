/** About panel copy (Korean first, English variant for every string). */
import type { L10n } from '../shared/strings';

export const ABOUT = {
  title: { ko: '이 도구에 대하여', en: 'About this tool' },
  subtitle: { ko: 'WildfireGuardian 마을별 사전 대피계획 도구', en: 'WildfireGuardian pre-season village evacuation planner' },
  close: { ko: '닫기', en: 'Close' },
  answersTitle: { ko: '무엇을 알려 주나요', en: 'What it answers' },
  answers: [
    {
      ko: '마을·취약시설마다, 차량으로 출발해 점검된 경로로 대피소에 도착할 수 있는 가장 늦은 출발 시각 — 출발 마감.',
      en: 'For each village or care facility: the latest vehicle departure that still reaches a shelter on a checked route — the departure deadline.',
    },
    {
      ko: '모델 안에서 경로가 없는 시나리오 — 조기 대피나 실내 대피 장소 지정 같은 대체 계획이 필요한 곳.',
      en: 'Which scenarios have no route in the model — where an alternative plan is needed, such as earlier evacuation or a designated indoor refuge.',
    },
  ] as L10n[],
  answersNote: {
    ko: '산불 시즌 전에 지자체·산림청·소방·돌봄시설 담당자가 마을별 대피 계획을 준비하도록 돕는 계획 보조 도구입니다.',
    en: 'A planning aid that helps local-government, forest-service, fire-department and care-facility staff prepare village evacuation plans before the fire season.',
  },
  methodTitle: { ko: '방법', en: 'Method' },
  methodCaption: {
    ko: '모든 경로 판정은 동결된 연구 패키지를 감싼 Route-Check API가 내립니다. 이 앱은 경로를 직접 계산하지 않습니다.',
    en: 'Every route verdict comes from the Route-Check API, which wraps the frozen research package. This app never computes routes itself.',
  },
  verdictsTitle: { ko: '세 가지 판정', en: 'Three verdicts' },
  rsgTitle: { ko: 'Ready-Set-Go — 산림청 대피 지침', en: 'Ready-Set-Go — Korea Forest Service guidance' },
  rsgSet: {
    label: { ko: '준비 (Set)', en: 'Set' },
    text: {
      ko: '8시간 확산 예측권 안: 노약자·취약시설 우선 대피',
      en: 'Inside the 8-hour spread forecast zone: evacuate older people and vulnerable facilities first',
    },
  },
  rsgGo: {
    label: { ko: '실행 (Go)', en: 'Go' },
    text: { ko: '5시간 권역: 전원 대피', en: 'Inside the 5-hour zone: everyone evacuates' },
  },
  rsgNote: {
    ko: '사용자가 그린 확산 구역(가정)에서는 마을 위치가 8시간·5시간 구역 안에 있는지만 평면상으로 판정합니다. 실제 대피 명령은 관계 기관의 판단을 따릅니다.',
    en: 'With user-drawn spread zones (an assumption) the tool only tests whether a village point lies inside the 8 h and 5 h zones. Actual evacuation orders follow the responsible authorities.',
  },
  limitsTitle: { ko: '한계 — 꼭 알아 두세요', en: 'Limitations — please read' },
  sourcesTitle: { ko: '데이터 출처와 라이선스', en: 'Data sources and licences' },
  versionsTitle: { ko: '버전 정보', en: 'Version identities' },
  vCheckpoint: { ko: '예측 체크포인트 (c651)', en: 'Forecast checkpoint (c651)' },
  vPackage: { ko: '경로 연구 패키지', en: 'Routing research package' },
  vKit: { ko: '실행 키트', en: 'Execution kit' },
  vArm: { ko: '평가 구성', en: 'Evaluated configuration' },
  vApi: { ko: 'Route-Check API 계약', en: 'Route-Check API contract' },
  vApiUnknown: { ko: '연결된 API 정보 없음', en: 'no API connected' },
  benchmark: {
    ko: '기록된 계산 시간: Apple M5 Pro 네이티브 벤치마크에서 점검 1건당 중앙값 약 8초.',
    en: 'Recorded compute time: about 8 s median per check on an Apple M5 Pro (native benchmark).',
  },
  fireInputPrefix: { ko: '산불 입력', en: 'Fire input' },
} as const;

export interface SourceRow {
  what: L10n;
  detail: L10n;
  licence: L10n;
}

export const SOURCES: SourceRow[] = [
  {
    what: { ko: '도로 그래프 · 마을 · 시설 · 대피소', en: 'Road graph · villages · facilities · shelters' },
    detail: {
      ko: '© OpenStreetMap 기여자. 도로 그래프는 연구에 쓰인 과거 스냅샷, 장소(POI)는 현재 OSM 추출본입니다.',
      en: '© OpenStreetMap contributors. The road graph is the historical snapshot used in the study; places (POIs) are a current OSM extract.',
    },
    licence: { ko: 'ODbL 1.0', en: 'ODbL 1.0' },
  },
  {
    what: { ko: '오프라인 배경지도', en: 'Offline basemap' },
    detail: {
      ko: 'Protomaps Basemap 타일(일일 빌드 20261016)을 지역 범위로 잘라 로컬에서 제공합니다. 지도 데이터는 OSM(ODbL).',
      en: 'Protomaps Basemap tiles (daily build 20261016) cut to each region and served locally. Map data is OSM (ODbL).',
    },
    licence: { ko: 'BSD-3-Clause · ODbL 1.0', en: 'BSD-3-Clause · ODbL 1.0' },
  },
  {
    what: { ko: '글꼴', en: 'Fonts' },
    detail: { ko: 'Pretendard (본문·지도 한글), Noto Sans (지도 라틴 글리프).', en: 'Pretendard (text and Hangul map labels), Noto Sans (Latin map glyphs).' },
    licence: { ko: 'SIL OFL 1.1', en: 'SIL OFL 1.1' },
  },
  {
    what: { ko: '지도 엔진', en: 'Map engine' },
    detail: { ko: 'MapLibre GL JS, PMTiles.', en: 'MapLibre GL JS, PMTiles.' },
    licence: { ko: 'BSD-3-Clause', en: 'BSD-3-Clause' },
  },
  {
    what: { ko: '연구 기록 (시나리오·판정·계산 시간)', en: 'Research records (scenarios, verdicts, compute time)' },
    detail: {
      ko: '이 저장소의 GitHub Release 자산 — 태그 research-final-20261015 (평가 입력·최종 독립 패널), routing-ablation-final-inputs-20261016 (정책 축소 비교). 사용 전 SHA-256 검증.',
      en: 'GitHub Release assets of this repository — tags research-final-20261015 (evaluated inputs, final independent panel) and routing-ablation-final-inputs-20261016 (policy ablation). Verified by SHA-256 before use.',
    },
    licence: { ko: '저장소 공개 자산', en: 'public repository assets' },
  },
];

/** Method diagram steps (one SVG). */
export const METHOD_STEPS: { title: L10n; sub: L10n | null }[] = [
  {
    title: { ko: '기록된 c651 1시간 신규 연소 확률', en: 'Recorded c651 next-hour new-burn probability' },
    sub: { ko: '375 m 격자 · 기록된 입력 시각', en: '375 m cells · recorded input time' },
  },
  {
    title: { ko: '시나리오 4개 위험 구성', en: 'Four-scenario hazard construction' },
    sub: { ko: '시나리오별 착화 시각 → 화염·복사열', en: 'per-scenario ignition times → flame and heat flux' },
  },
  {
    title: { ko: '시간 의존 도로 경로 탐색', en: 'Time-dependent road routing' },
    sub: { ko: 'wfg_latest 1.0.0 · kit v3', en: 'wfg_latest 1.0.0 · kit v3' },
  },
  {
    title: { ko: '전체 여정 점검', en: 'Whole-journey check' },
    sub: {
      ko: '화염 접촉 · 순간 10 kW/m² · 누적 노출 · 120초 체류 포함',
      en: 'flame contact · instantaneous 10 kW/m² · cumulative dose · incl. 120 s stay',
    },
  },
  { title: { ko: '세 가지 판정', en: 'Three verdicts' }, sub: null },
  {
    title: { ko: '출발 시각 스윕', en: 'Departure-time sweep' },
    sub: { ko: '10분 간격으로 같은 점검 반복', en: 'the same check every 10 minutes' },
  },
  {
    title: { ko: '출발 마감', en: 'Departure deadline' },
    sub: {
      ko: '점검된 경로가 있는 가장 늦은 출발 시각 (연속 확인 기준 병기)',
      en: 'latest departure with a checked route (contiguous basis shown too)',
    },
  },
];
