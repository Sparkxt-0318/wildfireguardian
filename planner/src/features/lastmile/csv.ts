/**
 * CSV of every field message of one region and recorded input time: one row per origin in the
 * planner's urgency order, Korean and English texts side by side (mail-merge / bulk-SMS ready).
 * Every row carries the data time and its own result source ("결과 출처": the precomputed cache file
 * and its created time, or the live API and the compute host, with "평가 호스트 아님" when not
 * established as evaluated-host output) and, with a reason line, the explanation file it comes from.
 * A text that fails a rule check gets an empty cell (only that text: fail closed per output) and
 * the rule-check column says "검사 실패 — 사용 금지" with the violations; the last columns state each
 * language's native-speaker / field review state.
 * UTF-8 with BOM, CRLF, RFC 4180 quoting and formula neutralising — the same writer as the
 * dispatch list (../exports/exports.ts).
 */
import { compactUtc } from '../../domain/clock';
import { kstDateClock, kstStamp, slug } from '../shared/format';
import { CSV_BOM, csvRow } from '../exports/exports';
import { resultSourceFull } from './compose';
import { allTexts, outputOk, type FieldMessages, type ReasonSource } from './messages';
import { LANGUAGES, SHIPPED_LANGS, UI, type OutputKind } from './strings';
import { EXPLANATION_SCHEMA, type LastMileInput, type LmLang } from './types';

export const LASTMILE_CSV_COLUMNS: Record<LmLang, string[]> = {
  ko: [
    '우선순위',
    '출발지 ID',
    '출발지',
    '구분',
    '모델 판정',
    '안내 종류',
    '출발 마감 (KST)',
    '도착지',
    '자료 시각 (KST)',
    '시나리오',
    '산불 입력',
    'MOCK',
    '시험 데이터',
    '결과 출처',
    '이유 자료',
    '문자 KO',
    '문자 KO 바이트 (EUC-KR · 최대 90)',
    '장문 KO',
    '장문 KO 바이트 (최대 2000)',
    '마을방송 KO',
    '마을방송 KO 예상 초 (최대 60)',
    '전화 대본 KO',
    '문자 EN',
    '문자 EN GSM-7 글자 (최대 160)',
    '장문 EN',
    '마을방송 EN',
    '마을방송 EN 예상 초 (최대 60)',
    '전화 대본 EN',
    '규칙 검사',
    '문구 검토 (원어민·현장)',
    '작성 시각 (KST)',
  ],
  en: [
    'Priority',
    'Origin ID',
    'Origin',
    'Type',
    'Model verdict',
    'Message type',
    'Leave by (KST)',
    'Destination',
    'Data time (KST)',
    'Scenario',
    'Fire input',
    'MOCK',
    'Test data',
    'Result source',
    'Reason data',
    'SMS KO',
    'SMS KO bytes (EUC-KR; max 90)',
    'Long text KO',
    'Long text KO bytes (max 2000)',
    'Broadcast KO',
    'Broadcast KO est. seconds (max 60)',
    'Call script KO',
    'SMS EN',
    'SMS EN GSM-7 characters (max 160)',
    'Long text EN',
    'Broadcast EN',
    'Broadcast EN est. seconds (max 60)',
    'Call script EN',
    'Rule checks',
    'Wording review (native speaker; field)',
    'Prepared (KST)',
  ],
};

const VERDICT_TEXT: Record<string, Record<LmLang, string>> = {
  checked_route: { ko: '확인된 경로', en: 'Checked route' },
  model_no_route: { ko: '모델상 경로 없음', en: 'No route in the model' },
  unresolved: { ko: '미확인', en: 'Unresolved' },
};

/** "uiseong_andong_2025__20250325T170000Z.json (wfg.explanation/1 · 코드 커밋 6855cc61f83e · 생성 2026-11-03 03:14 KST)" */
export function reasonSourceText(r: ReasonSource, lang: LmLang): string {
  const parts = [EXPLANATION_SCHEMA];
  if (r.codeCommit) parts.push(`${lang === 'ko' ? '코드 커밋' : 'code commit'} ${r.codeCommit.slice(0, 12)}`);
  if (r.generatedAtIso) parts.push(`${lang === 'ko' ? '생성' : 'generated'} ${kstStamp(r.generatedAtIso)}`);
  return `${r.file} (${parts.join(' · ')})`;
}

/** "한국어: 검토 전 · English: 검토 전" — every shipped language's native-speaker / field review state. */
export function reviewStatus(lang: LmLang): string {
  return SHIPPED_LANGS.map((l) => `${LANGUAGES[l].label}: ${UI.review[LANGUAGES[l].nativeSpeakerReview][lang]}`).join(' · ');
}

export function fieldMessagesCSV(items: FieldMessages[], opts: { lang?: LmLang } = {}): string {
  const lang = opts.lang ?? 'ko';
  const lines = [csvRow(LASTMILE_CSV_COLUMNS[lang])];
  const sorted = [...items].sort((a, b) => a.urgencyRank - b.urgencyRank || a.originId.localeCompare(b.originId));
  for (const fm of sorted) {
    const input = fm.plan.input;
    const iso = input.scenario.inputTimeIso;
    // a text that fails a rule check is never exported (fail closed per output): its cell stays empty
    const failed = fm.violations.length > 0;
    const texts = (lang: LmLang) => {
      const t = allTexts(fm, lang);
      const keep = (kind: OutputKind) => (outputOk(fm, lang, kind) ? t[kind] : '');
      return { sms: keep('sms'), lms: keep('lms'), broadcast: keep('broadcast'), call: keep('call') };
    };
    const ko = texts('ko');
    const en = texts('en');
    const d = fm.plan.destination;
    lines.push(
      csvRow([
        fm.urgencyRank,
        input.origin.id,
        input.origin.display[lang],
        input.origin.category[lang],
        VERDICT_TEXT[fm.verdict]![lang],
        UI.kindLabel[fm.kind][lang],
        fm.leaveByS !== null ? kstDateClock(iso, fm.leaveByS) : '',
        fm.kind === 'leave_by' && d ? d.display[lang] : '',
        kstDateClock(iso, 0),
        input.scenario.scenarioSetId,
        input.fireInputLabel[lang],
        input.mock ? 'MOCK' : '',
        input.testData ? (lang === 'ko' ? '시험 데이터' : 'test data') : '',
        // per origin: the precomputed cache (file, created time) or the live API (compute host)
        resultSourceFull(input, lang),
        fm.reasonSource ? reasonSourceText(fm.reasonSource, lang) : '',
        ko.sms,
        fm.metrics.ko.smsUnits,
        ko.lms,
        fm.metrics.ko.lmsBytes,
        ko.broadcast,
        fm.metrics.ko.broadcastS,
        ko.call,
        en.sms,
        fm.metrics.en.smsUnits,
        en.lms,
        en.broadcast,
        fm.metrics.en.broadcastS,
        en.call,
        failed ? `${UI.csvFailed[lang]}: ${fm.violations.join(' | ')}` : 'OK',
        reviewStatus(lang),
        kstDateClock(input.generatedAtIso, 0),
      ]),
    );
  }
  return CSV_BOM + lines.join('\r\n') + '\r\n';
}

export function fieldMessagesFileName(input: Pick<LastMileInput, 'region' | 'scenario' | 'mock' | 'testData'>): string {
  const parts = ['wfg', slug(input.region.id), compactUtc(input.scenario.inputTimeIso), 'field_messages'];
  if (input.mock) parts.push('MOCK');
  if (input.testData) parts.push('TEST');
  return `${parts.join('_')}.csv`;
}
