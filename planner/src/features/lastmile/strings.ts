/**
 * Fixed wording of the last-mile kit (현장 전달 문구): language registry, mandatory lines, words the
 * outputs must never contain, and the panel's UI labels. The message templates themselves are in
 * ./templates/ko.ts (source text) and ./templates/en.ts.
 *
 * Adding a language: write ./templates/<code>.ts against the same TemplateSet, register it below
 * with `nativeSpeakerReview: 'pending'` and its SMS encoding; it stays out of the panel, the CSV and
 * every output (`enabled: false`) until a native speaker has reviewed it and the flag is 'done'.
 * No further language is shipped before that review (tests/planner/lastmile.test.ts checks the flags).
 */
import type { LmLang, LmText } from './types';

export interface LanguageMeta {
  code: string;
  label: string;
  /** 'source' = the text everything else is translated from */
  role: 'source' | 'translation';
  /** a native speaker reviewed the wording for older listeners and field use */
  nativeSpeakerReview: 'done' | 'pending';
  /** shown in the panel, the CSV and the outputs */
  enabled: boolean;
  /** single-SMS encoding and limit used for this language */
  sms: { encoding: 'euc-kr' | 'gsm7' | 'ucs2'; limit: number; unit: 'bytes' | 'chars' };
  note: string;
}

export const LANGUAGES: Record<LmLang, LanguageMeta> = {
  ko: {
    code: 'ko',
    label: '한국어',
    role: 'source',
    nativeSpeakerReview: 'pending',
    enabled: true,
    sms: { encoding: 'euc-kr', limit: 90, unit: 'bytes' },
    note: 'Source text, written for older listeners (plain, polite). Field review with village heads and care staff is still pending — see planner/docs/LASTMILE.md.',
  },
  en: {
    code: 'en',
    label: 'English',
    role: 'translation',
    nativeSpeakerReview: 'pending',
    enabled: true,
    sms: { encoding: 'gsm7', limit: 160, unit: 'chars' },
    note: 'Translation of the Korean source, written by the project with AI assistance (not produced by a translation engine); native-speaker review pending.',
  },
};

/** Languages shipped in this build (the brief requires Korean source + English). */
export const SHIPPED_LANGS: readonly LmLang[] = ['ko', 'en'];

// ---------------------------------------------------------------- mandatory lines

/** Verbatim lines every written output (card, long text) carries. */
export const OFFICIAL_FIRST: LmText = { ko: '공식 대피 명령이 우선합니다.', en: 'Official evacuation orders come first.' };
export const MODEL_NOT_LIVE: LmText = { ko: '모델 기반 계획 정보 · 실시간 아님', en: 'Model-based planning information · not live' };

/**
 * Short forms used ONLY in the single SMS, where the verbatim lines cannot fit: a Korean SMS is
 * 90 bytes (45 Hangul) in total, and the two lines alone take 62 bytes (28 + 34). The long text
 * (LMS) and the card carry both lines verbatim; the broadcast and the call script say OFFICIAL_FIRST
 * as it is and MODEL_NOT_LIVE as a sentence (MODEL_PLAN_SPOKEN, MODEL_NOT_LIVE_SPOKEN), never in its
 * written "· 실시간 아님" form.
 */
export const OFFICIAL_FIRST_SMS: LmText = { ko: '공식명령 우선', en: 'Official orders come first.' };
export const MODEL_NOT_LIVE_SMS: LmText = { ko: '실시간 아님', en: 'not live' };
/** The SMS's model attribution ("모델상 02:20까지 차로 출발", "Model-based plan: …"). */
export const MODEL_SMS: LmText = { ko: '모델', en: 'Model-based plan' };

/** "Model-based planning information" on its own (a replay broadcast says it is not a real situation instead of "not live"). */
export const MODEL_PLAN_SPOKEN: LmText = { ko: '모델 기반 계획 정보', en: 'model-based planning information' };

/** Spoken form of MODEL_NOT_LIVE (scripts read aloud). */
export const MODEL_NOT_LIVE_SPOKEN: LmText = {
  ko: '모델 기반 계획 정보이며, 실시간 정보가 아닙니다',
  en: 'model-based planning information',
};

/** First sentence of a replay broadcast (B1 of the P3 review: a replay must never sound like a live alert). */
export const NOT_REAL: LmText = { ko: '이 방송은 실제 상황이 아닙니다.', en: 'This is not a real emergency.' };

export type OutputKind = 'sms' | 'lms' | 'broadcast' | 'call' | 'card';

/**
 * Phrases each output must contain (besides the data time and, for a recorded scenario, the
 * replay note, which are checked separately). Checked by checkFieldMessages().
 */
export function requiredPhrases(kind: OutputKind, lang: LmLang, replay: boolean): string[] {
  switch (kind) {
    case 'sms':
      return [OFFICIAL_FIRST_SMS[lang], MODEL_NOT_LIVE_SMS[lang], MODEL_SMS[lang]];
    case 'lms':
    case 'card':
      return [OFFICIAL_FIRST[lang], MODEL_NOT_LIVE[lang]];
    case 'broadcast':
      return [OFFICIAL_FIRST[lang], MODEL_PLAN_SPOKEN[lang], replay ? NOT_REAL[lang] : lang === 'ko' ? '실시간 정보가 아닙니다' : 'not live'];
    case 'call':
      return [OFFICIAL_FIRST[lang], MODEL_NOT_LIVE_SPOKEN[lang], ...(lang === 'en' ? ['not live'] : []), ...(replay ? [lang === 'ko' ? '실제 상황이 아니라' : 'not a real emergency'] : [])];
  }
}

/** Replay note markers (recorded fire input): the year plus one of these words. */
export const REPLAY_WORDS: LmText = { ko: '재현', en: 'replay' };

/**
 * Words the outputs never contain (case-insensitive, substring): no "safe", no promise of a
 * pickup, vehicle or rescue, no shelter-in-place or other tactical advice, no reassurance.
 * Names coming from data (places, roads) are masked before this check.
 */
export const FORBIDDEN: Record<LmLang, string[]> = {
  ko: [
    '안전',
    '구조',
    '구출',
    '데리러',
    '모시러',
    '모시고 가',
    '태워',
    '픽업',
    '차량을 보내',
    '차를 보내',
    '버스를 보내',
    '차량 지원',
    '이송해 드',
    '실내 대피',
    '옥내 대피',
    '집 안에',
    '집에 머',
    '머무르십시오',
    '대기하십시오',
    '기다리십시오',
    '보장',
    '안심',
    '걱정',
    '괜찮',
    '확실',
    '무사',
  ],
  en: [
    'safe',
    'rescue',
    'pick up',
    'pickup',
    'pick-up',
    'we will send',
    'will be sent',
    'vehicle will',
    'bus will',
    'transport will',
    'shelter in place',
    'shelter-in-place',
    'stay indoors',
    'stay inside',
    'stay home',
    'stay put',
    'wait for help',
    'guarantee',
    'certain',
    "don't worry",
    'do not worry',
    'no danger',
    'secure',
  ],
};

/**
 * "Call 119 now" said to residents or families: only the long text and the card, addressed to the
 * 이장 / facility staff, carry it; the SMS, broadcast and call script say "follow the official
 * instructions; in an emergency, report to 119".
 */
export const RESIDENT_119_NOW: Record<LmLang, RegExp> = {
  ko: /(지금 바로|즉시)\s*119/,
  en: /call 119 (now|immediately|right away)|119 or the eup\/myeon office now/i,
};

/** A departure instruction (allowed only when a checked departure window exists). */
export const DEPARTURE_INSTRUCTION: Record<LmLang, RegExp> = {
  ko: /까지\s*(차로\s*)?출발|출발하(십시오|세요)|출발 마감/,
  en: /\bleave by\b|\bleave (now|before|no later)\b|\bdepart by\b|\bdrive (out|away)\b/i,
};

// ---------------------------------------------------------------- panel UI

export const UI = {
  sectionTitle: { ko: '현장 전달 문구', en: 'Field messages' },
  open: { ko: '문자·방송·전화·카드 만들기', en: 'Texts, broadcast, call script, card' },
  sectionNote: {
    ko: '이장·돌봄 인력이 주민과 가족에게 전할 문구 · 공식 대피 명령이 우선합니다',
    en: 'Wording for village heads and care staff · official evacuation orders come first',
  },
  drawnDisabled: {
    ko: '사용자 입력 확산 구역(가정)으로는 현장 문구를 만들지 않습니다. 기록된 시나리오를 고르십시오.',
    en: 'Field messages are not made from user-drawn spread zones (an assumption). Choose a recorded scenario.',
  },
  noData: { ko: '결과가 없어 현장 문구를 만들 수 없습니다.', en: 'No results, so no field messages can be made.' },
  researchNote: {
    ko: '연구 패널 출발점에는 현장 문구를 만들지 않습니다(기록 임무의 출발 도로 지점 — 마을·돌봄 시설이 아님). 마을과 돌봄 시설의 문구는 열어서 볼 수 있습니다.',
    en: "No field messages for research panel origins (a recorded mission's start road node, not a village or care facility). Messages for villages and care facilities can be opened here.",
  },
  dialogTitle: { ko: '현장 전달 문구', en: 'Field messages' },
  /** what each output carries (requiredPhrases + the data-time check in checks.ts; tested) */
  dialogLead: {
    ko: '이장·돌봄 인력이 주민과 가족에게 전할 문구입니다. 모든 문구에 자료 시각과 "공식 대피 명령이 우선합니다", "모델 기반 계획 정보 · 실시간 아님"이 들어 있습니다. 장문과 카드는 이 두 줄을 그대로, 단문 문자는 줄인 말("공식명령 우선", "모델", "실시간 아님")로 싣고, 마을방송과 전화 대본은 말로 풀어 전합니다(기록 재현 방송은 "실시간 아님" 대신 "실제 상황이 아닙니다"). 정해진 틀로만 만들며 실시간 정보가 아닙니다.',
    en: 'Wording for village heads and care staff to pass on. Every text carries the data time and the notices "Official evacuation orders come first" and "Model-based planning information · not live": verbatim in the long text and the card, as short forms in the SMS ("Official orders come first.", "Model-based plan", "not live"), spoken in the broadcast and call script (a replay broadcast says "This is not a real emergency" instead of "not live"). Built from fixed templates only; not live information.',
  },
  close: { ko: '닫기', en: 'Close' },
  origin: { ko: '출발지', en: 'Origin' },
  verdict: { ko: '모델 판정', en: 'Model verdict' },
  kind: { ko: '안내 종류', en: 'Message type' },
  /** per origin: precomputed cache (file, created time) or API checks of this session (compute host); "no result for this origin" when there is none */
  resultSource: { ko: '결과 출처', en: 'Result source' },
  kindLabel: {
    leave_by: { ko: '출발 마감 안내', en: 'Leave-by message' },
    no_route: { ko: '모델상 경로 없음 · 즉시 연락', en: 'No route in the model · contact now' },
    unresolved: { ko: '미확인 · 공식 안내 따르기', en: 'Unresolved · follow official guidance' },
    partial: { ko: '부분 확인 · 공식 안내 따르기', en: 'Partly checked · follow official guidance' },
  },
  explanation: { ko: '이유 설명 자료', en: 'Deadline explanations' },
  explanationReady: { ko: '있음 — 확인된 항목만 이유 문장에 씀', en: 'loaded — only consistent entries are used' },
  explanationUsed: { ko: '이 출발지: 이유 문장 포함', en: 'this origin: reason line included' },
  explanationNotUsed: { ko: '이 출발지: 이유 문장 없음', en: 'this origin: no reason line' },
  explanationAbsent: { ko: '없음 — 이유 문장 없이 만듦', en: 'not available — messages carry no reason line' },
  explanationInvalid: { ko: '사용할 수 없음 — 이유 문장 없이 만듦', en: 'unusable — messages carry no reason line' },
  explanationLoading: { ko: '확인 중…', en: 'checking…' },
  sms: { ko: '문자 (단문 SMS)', en: 'Text message (SMS)' },
  lms: { ko: '문자 (장문 LMS)', en: 'Long text' },
  broadcast: { ko: '마을방송 원고', en: 'Village broadcast script' },
  call: { ko: '가족 전화 대본 (돌봄 인력용)', en: 'Phone script for care staff calling families' },
  card: { ko: '출발지 카드 (인쇄용)', en: 'Origin card (print)' },
  copy: { ko: '복사', en: 'Copy' },
  copied: { ko: '복사했습니다', en: 'Copied' },
  copyFailed: { ko: '복사하지 못했습니다 — 글을 직접 선택해 복사하십시오', en: 'Could not copy — select the text and copy it' },
  bytes: { ko: '{n} / {max}바이트 (EUC-KR)', en: '{n} / {max} bytes (EUC-KR)' },
  gsm: { ko: '{n} / {max}자 (GSM-7)', en: '{n} / {max} characters (GSM-7)' },
  seconds: {
    ko: '읽는 시간 약 {s}초 / 최대 {max}초 (초당 {rate}음절 가정)',
    en: 'about {s} s to read / max {max} s (assumes {rate} words per second)',
  },
  callSeconds: { ko: '읽는 시간 약 {s}초', en: 'about {s} s to read' },
  checksOk: { ko: '검사 통과: 길이·필수 문구·금지어', en: 'Checks passed: length, mandatory lines, forbidden words' },
  csvFailed: { ko: '검사 실패 — 사용 금지', en: 'Check failed — do not use' },
  review: {
    done: { ko: '원어민·현장 검토 완료', en: 'reviewed by native speakers and in the field' },
    pending: { ko: '원어민·현장 검토 전', en: 'not yet reviewed by native speakers or in the field' },
  },
  checksFailed: { ko: '검사 실패 — 회색으로 표시된 문구는 쓰지 마십시오', en: 'Check failed — do not use the greyed texts' },
  cardLang: { ko: '카드 언어', en: 'Card language' },
  printA5: { ko: '이 카드 인쇄 (A5)', en: 'Print this card (A5)' },
  printA4: { ko: '이 카드 인쇄 (A4)', en: 'Print this card (A4)' },
  printAll: { ko: '전체 출발지 카드 인쇄 (A5)', en: 'Print all origin cards (A5)' },
  printAllLeftOut: { ko: '검사 실패로 인쇄하지 않는 카드 {n}곳: {list}', en: '{n} cards left out (check failed): {list}' },
  csv: { ko: '전체 문구 CSV ({n}곳)', en: 'All messages CSV ({n} origins)' },
  csvSaved: { ko: '저장됨: {name}', en: 'Saved: {name}' },
  csvError: { ko: '저장하지 못했습니다: {msg}', en: 'Could not save: {msg}' },
  replayNote: {
    ko: '기록된 산불 시나리오를 재현한 자료입니다. 실제 상황에 쓰려면 실시간 자료로 다시 계산해야 합니다.',
    en: 'Replay of recorded wildfire scenarios. Real use would need a fresh computation from live data.',
  },
} as const;

export function lmFill(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function lmPick(t: LmText, lang: LmLang): string {
  return t[lang] ?? t.ko;
}
