/**
 * Strings shared by the feature modules (About panel, plan sheet, exports). Korean first, English
 * variant for every string. Kept here (not in src/i18n) so the feature builder never edits core files.
 *
 * Honesty wording (ARCHITECTURE.md §0.4): unresolved is never described as safe; model_no_route is
 * "no route in the model", not "no escape in reality".
 */
import type { Lang } from '../../domain/clock';
import type { Verdict } from '../../domain/types';

export type { Lang };

export type L10n = Record<Lang, string>;

export function pick(s: L10n, lang: Lang): string {
  return s[lang] ?? s.ko;
}

export const VERDICT_LABEL: Record<Verdict, L10n> = {
  checked_route: { ko: '확인된 경로', en: 'Checked route' },
  model_no_route: { ko: '모델상 경로 없음', en: 'No route in the model' },
  unresolved: { ko: '미확인', en: 'Unresolved' },
};

/** Long definitions (About panel, plan-sheet legend). */
export const VERDICT_DEFINITION: Record<Verdict, L10n> = {
  checked_route: {
    ko: '운행·대기·대피소 체류(120초)를 포함한 전체 여정이 4개 위험 시나리오 모두에서 화염 접촉 없이 순간 복사열 10 kW/m²·누적 노출 100 kJ/m² 한계 안으로 점검된 경로입니다.',
    en: 'The whole journey — driving, waiting and the 120 s stay at the shelter — was checked in all four hazard scenarios: no flame contact, instantaneous heat flux within 10 kW/m² and cumulative exposure within 100 kJ/m².',
  },
  model_no_route: {
    ko: '완화 탐색까지 모두 소진했지만 이 모델과 입력 범위 안에서는 조건을 만족하는 차량 경로가 없습니다. 현실에서 탈출이 불가능하다는 뜻은 아니며, 대체 계획이 필요하다는 신호입니다.',
    en: 'The relaxed search was exhausted: within this model and its inputs no vehicle route meets the conditions. It does not mean escape is impossible in reality; it signals that an alternative plan is needed.',
  },
  unresolved: {
    ko: '시간 초과·탐색 상한·점검 미완료·점검 실패 등으로 판단하지 못했습니다. 절대 안전으로 해석하지 마십시오. 출발 마감 계산에도 포함하지 않습니다.',
    en: 'No decision: time-out, search cap, unfinished or failed check, and similar. Never read it as safe. It never counts toward a departure deadline.',
  },
};

export const WINDOW_CLOSED_LABEL: L10n = { ko: '도착 허용 시간 밖 (점검 안 함)', en: 'Outside the arrival window (not checked)' };

/** Alternative-plan wording (plan sheet section 대체 계획 필요 시나리오, CSV 비고). */
export const ALT_PLAN_TEXT: Record<'model_no_route' | 'unresolved', L10n> = {
  model_no_route: {
    ko: '차량 대피 경로를 확인하지 못함: 조기 대피 또는 실내 대피(대피 장소 사전 지정) 등 대안 필요',
    en: 'No vehicle evacuation route could be confirmed: an alternative is needed, such as earlier evacuation or sheltering indoors (designate the refuge in advance)',
  },
  unresolved: {
    ko: '판단 불가 — 안전으로 간주하지 말 것',
    en: 'Undetermined — do not treat as safe',
  },
};

/** Unresolved reason codes (contract ReasonCode, v1.0 + v1.1). Unknown codes are shown verbatim. */
export const REASON_LABEL: Record<string, L10n> = {
  TIMEOUT: { ko: '30초 계산 예산 초과', en: '30 s compute budget exceeded' },
  STATE_CAP: { ko: '탐색 상태 상한 도달', en: 'search state cap reached' },
  MEMORY_CAP: { ko: '메모리 상한 도달', en: 'memory guard reached' },
  CHECK_NOT_FINISHED: { ko: '점검 미완료', en: 'check not finished' },
  CHECK_FAILED: { ko: '점검 실패·거부', en: 'check failed or refused' },
  WORKER_ERROR: { ko: '작업자 비정상 종료', en: 'worker ended abnormally' },
  CLEANUP_UNCONFIRMED: { ko: '프로세스 정리 미확인', en: 'process clean-up not confirmed' },
  INTERNAL_ERROR: { ko: 'API 내부 오류', en: 'API internal error' },
  OTHER: { ko: '기타', en: 'other' },
  INPUT_REJECTED: { ko: '엔진이 입력을 거부', en: 'engine rejected the input' },
  AT_ISSUE_FAILURE: { ko: '출발 시점에 이미 한계 초과', en: 'already over a limit at departure' },
  DISCONNECTED: { ko: '도로망상 도달 불가 (화재와 무관)', en: 'unreachable in the road graph (not fire related)' },
};

export function reasonText(code: string | null | undefined, lang: Lang): string | null {
  if (!code) return null;
  const l = REASON_LABEL[code];
  return l ? `${pick(l, lang)} (${code})` : code;
}

/** Planner-side notes for origins the API was never asked about. */
export const NOTE_LABEL: Record<'not_checkable' | 'rejected' | 'not_computed', L10n> = {
  not_checkable: { ko: '도로망 300 m 밖 — 점검 불가', en: 'More than 300 m from the road graph — cannot be checked' },
  rejected: { ko: 'API가 요청을 거부함 — 점검 안 됨', en: 'Rejected by the API — not checked' },
  not_computed: { ko: '아직 계산하지 않음', en: 'Not computed yet' },
};

export const FOOTER_APP: L10n = {
  ko: '사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.',
  en: 'Planning aid only — not for live evacuation operations.',
};

export const MOCK_BADGE_TITLE: L10n = {
  ko: 'MOCK 서버의 기록 결과입니다 (새로 계산하지 않음)',
  en: 'Recorded results served by the MOCK server (nothing recomputed)',
};

/** Honest limitations — the About panel shows all, the plan sheet a compact version. */
export interface Limitation {
  id: string;
  text: L10n;
  short: L10n;
}

export const LIMITATIONS: Limitation[] = [
  {
    id: 'vehicle_only',
    text: { ko: '차량 이동만 고려합니다 (도보·대중교통 제외).', en: 'Vehicle travel only (no walking or public transport).' },
    short: { ko: '차량 이동만 고려 (도보·대중교통 제외)', en: 'Vehicle travel only (no walking, no public transport)' },
  },
  {
    id: 'traffic',
    text: { ko: '교통 혼잡·도로 통제·사고는 반영하지 않습니다.', en: 'Traffic congestion, road closures and crashes are not modelled.' },
    short: { ko: '교통 혼잡·도로 통제·사고 미반영', en: 'No congestion, closures or crashes' },
  },
  {
    id: 'scenarios',
    text: {
      ko: '시나리오는 가능한 모든 산불이 아닙니다 — 기록된 4개 위험 시나리오 또는 사용자가 가정한 확산 구역만 점검합니다.',
      en: 'The scenarios are not every possible fire — only the four recorded hazard scenarios or user-assumed spread zones are checked.',
    },
    short: { ko: '시나리오는 가능한 모든 산불이 아님', en: 'Scenarios are not every possible fire' },
  },
  {
    id: 'not_validated',
    text: { ko: '주민·현장 검증 전입니다 (not validated with residents).', en: 'Not yet validated with residents or in the field.' },
    short: { ko: '주민·현장 검증 전', en: 'Not validated with residents' },
  },
  {
    id: 'smoke',
    text: { ko: '연기와 비화(불똥)는 반영하지 않습니다.', en: 'Smoke and ember spotting are not modelled.' },
    short: { ko: '연기·비화 미반영', en: 'No smoke or embers' },
  },
  {
    id: 'osm_snapshot',
    text: {
      ko: '도로 그래프는 과거 OSM 스냅샷이고, 마을·시설·대피소(POI)는 현재 OSM 기준입니다.',
      en: 'The road graph is a historical OSM snapshot; villages, facilities and shelters (POIs) come from current OSM.',
    },
    short: { ko: '그래프는 과거 OSM 스냅샷, 장소는 현재 OSM', en: 'Graph: past OSM snapshot; places: current OSM' },
  },
  {
    id: 'snap_300',
    text: {
      ko: '도로까지 300 m를 넘는 장소는 도로망에 연결할 수 없어 점검하지 못합니다.',
      en: 'Places more than 300 m from the road graph cannot be connected and are not checked.',
    },
    short: { ko: '도로까지 300 m 초과 장소는 점검 불가', en: 'Places > 300 m from a road: not checked' },
  },
  {
    id: 'unresolved_not_safe',
    text: { ko: '미확인은 안전이 아닙니다.', en: 'Unresolved is not safe.' },
    short: { ko: '미확인은 안전이 아님', en: 'Unresolved is not safe' },
  },
  {
    id: 'planning_only',
    text: {
      ko: '사전 계획 보조 도구이며 실시간 대피 지휘·운영용이 아닙니다.',
      en: 'A pre-season planning aid, not a tool for live evacuation command or operations.',
    },
    short: { ko: '계획 보조 도구 · 실시간 운영용 아님', en: 'Planning aid · not for live operations' },
  },
];

/** Fixed identities of the evaluated research configuration (ARCHITECTURE.md §1). */
export const FIXED_IDENTITY = {
  checkpoint: 'c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843',
  packageName: 'wfg_latest',
  packageVersion: '1.0.0',
  kit: 'v3',
  releaseTags: ['research-final-20261015', 'routing-ablation-final-inputs-20261016'],
} as const;
