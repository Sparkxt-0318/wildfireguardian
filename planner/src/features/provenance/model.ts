/**
 * Deadline provenance flags (stream 3; design by Iris, data by Richard, verified by Owen). STAFF OUTPUTS ONLY: never a
 * resident message, never the public page.
 *
 * Each staff leave-by deadline is labelled with what set it, from the F-3.1 exact field:
 * - window: the scenario window and travel time set it; fire does not change it. It says nothing about after the
 *   1-hour window (Owen limit 2).
 * - present_fire: fire already burning sets it; unchanged without forecast new ignitions.
 * - forecast_dependent: it rests on the fire forecast and may move earlier at the next update. The gap to the
 *   present-fire-only value is given in minutes, as "not extra time" and not a checked route (Owen limit 3). It is
 *   never given as a second clock time.
 * Fail closed: the label shows only when the plan's headline kind is a deadline, the file belongs to this exact cache
 * (region, input time, cache sha256), a record exists, and the headline time T ≤ the record's exact leave_by_s.
 * Otherwise "not established", or "not computed" when there is no record. An unresolved place never gets a label with
 * a time or "no route"; where the exact field proves no route, staff get Richard's timeout-versus-proof note.
 * Schema-driven, independent of the 1-hour file (the horizon is read from the file).
 */
import type { LmLang, LmText } from '../lastmile/types';

export const PROVENANCE_SCHEMA = 'wfg.planner.deadline_provenance/1';

export type ProvenanceKind = 'window' | 'present_fire' | 'forecast_dependent' | 'no_checked_route' | 'not_computed';

export interface ProvenanceRecord {
  kind: 'dispatch' | 'research';
  leave_by_s: number | null;
  fire_free_leave_by_s: number | null;
  provenance: ProvenanceKind;
  leave_by_with_forecast_s?: number;
  leave_by_present_fire_only_s?: number;
}

export interface ProvenanceFile {
  schema: typeof PROVENANCE_SCHEMA;
  source: { schema: string; commit: string; path: string; sha256: string; verified: string };
  horizon_s: number;
  region_id: string;
  input_time: string;
  cache: { path: string; sha256: string };
  records: Record<string, ProvenanceRecord>;
}

/** Accepts only a planner provenance file for exactly this cache (path and sha256 from the cache index). */
export function parseProvenanceFile(raw: unknown, cache: { path: string; sha256: string | null | undefined }): ProvenanceFile | null {
  if (!raw || typeof raw !== 'object') return null;
  const d = raw as Partial<ProvenanceFile>;
  if (d.schema !== PROVENANCE_SCHEMA || !d.cache || !d.records || typeof d.records !== 'object') return null;
  if (d.cache.path !== cache.path || !cache.sha256 || d.cache.sha256 !== cache.sha256) return null;
  if (typeof d.horizon_s !== 'number' || !d.source?.sha256) return null;
  return d as ProvenanceFile;
}

export type StaffProvenance =
  | { kind: 'window' | 'present_fire'; horizonS: number }
  | { kind: 'forecast_dependent'; laterMin: number; horizonS: number }
  | { kind: 'not_established'; why: 'no_record_time' | 'after_exact' | 'file' }
  | { kind: 'not_computed' }
  | { kind: 'unresolved_proven_no_route' }
  | { kind: 'none' };

/** The plan facts the label needs: the staff headline (deadlineHeadline) kind and time. */
export interface HeadlineFacts {
  kind: 'deadline' | 'partial' | 'no_route' | 'unresolved';
  deadlineS: number | null;
}

/** The staff label for one place. `file` undefined = not loaded yet / no file: "not computed" for a deadline. */
export function staffProvenance(h: HeadlineFacts, originId: string, file: ProvenanceFile | null | undefined, plan: { source?: string; mock?: boolean } | null = null): StaffProvenance {
  // the field was computed on the recorded cache: a live or MOCK result on screen is not what it describes
  if (plan && (plan.source === 'live' || plan.mock)) return h.kind === 'deadline' ? { kind: 'not_established', why: 'file' } : { kind: 'none' };
  const r = file?.records[originId];
  if (h.kind === 'unresolved') return r && r.provenance === 'no_checked_route' ? { kind: 'unresolved_proven_no_route' } : { kind: 'none' };
  if (h.kind !== 'deadline' || h.deadlineS === null) return { kind: 'none' };
  if (file === null) return { kind: 'not_established', why: 'file' };
  if (!file || !r || r.provenance === 'not_computed') return { kind: 'not_computed' };
  if (r.leave_by_s === null || r.provenance === 'no_checked_route') return { kind: 'not_established', why: 'no_record_time' };
  if (h.deadlineS > r.leave_by_s) return { kind: 'not_established', why: 'after_exact' };
  if (r.provenance === 'forecast_dependent') {
    const a = r.leave_by_with_forecast_s;
    const b = r.leave_by_present_fire_only_s;
    // the file's direction: with forecast ≤ present fire only; anything else is not established
    if (typeof a !== 'number' || typeof b !== 'number' || a > b || a !== r.leave_by_s) return { kind: 'not_established', why: 'no_record_time' };
    return { kind: 'forecast_dependent', laterMin: Math.floor((b - a) / 60), horizonS: file.horizon_s };
  }
  return { kind: r.provenance, horizonS: file.horizon_s };
}

const H = (s: number) => Math.round(s / 3600);

/** Staff text (Iris wording; Korean pending Sofia). Never contains a clock time. */
export function provenanceText(p: StaffProvenance, lang: LmLang): string | null {
  const T: Record<string, LmText> = {
    window: { ko: '시나리오 시간창이 정한 시각입니다. 불은 이 시각을 바꾸지 않습니다. {h}시간 시나리오 이후는 계산하지 않았습니다.', en: 'Set by the scenario window; fire does not change it. Nothing after the {h}-hour scenario was computed.' },
    present_fire: { ko: '이미 타고 있는 불이 정한 시각입니다 (예측된 새 발화를 빼도 같습니다).', en: 'Set by fire already burning (the same without forecast new ignitions).' },
    forecast_dependent: {
      ko: '산불 예측에 따라 달라지는 시각입니다. 예측이 바뀔 때마다 다시 확인하십시오. 더 빨라질 수 있습니다. 예측된 새 발화를 빼면 모델 시각이 {n}분 늦어지지만, 그것은 여유 시간이 아니며 점검된 경로도 아닙니다.',
      en: 'Depends on the fire forecast. Re-check at every update; it may move earlier. Without forecast new ignitions the model time would be {n} min later; that is not extra time and not a checked route.',
    },
    not_established: { ko: '출처 확인 안 됨 — 이 시각의 근거를 정할 수 없습니다.', en: 'Provenance not established — what set this time cannot be determined.' },
    not_computed: { ko: '출처 계산 안 됨.', en: 'Provenance not computed.' },
    unresolved_proven_no_route: {
      ko: '경로 점검이 시간 초과로 끝났습니다. 이후의 정밀 분석에서는 모델 안 어느 출발 시각에도 점검된 경로가 없습니다.',
      en: 'The route check timed out; an exact later analysis finds no checked route at any departure in the model.',
    },
  };
  if (p.kind === 'none') return null;
  const t = T[p.kind]![lang];
  const h = 'horizonS' in p ? H(p.horizonS) : 1;
  if (p.kind === 'forecast_dependent' && p.laterMin === 0) {
    // under a minute: never "0 min later"
    return t.replace('{n}분 늦어지지만', '1분 미만 늦어지지만').replace('{n} min later', 'less than 1 min later');
  }
  return t.replace('{h}', String(h)).replace('{n}', p.kind === 'forecast_dependent' ? String(p.laterMin) : '');
}

export const PROVENANCE_FOOTER: LmText = {
  ko: '1시간 재현 기준의 모델 근거 표시이며 실제 상황에 쓸 수 없습니다. 이해도는 시험하지 않았습니다.',
  en: 'Model provenance on the 1-hour replay; not fit for live use. Comprehension is untested.',
};

/** The short tag for lists, the A4 sheet and the CSV (no later value in any form). */
export const PROVENANCE_TAG: Record<Exclude<StaffProvenance['kind'], 'none'>, LmText> = {
  window: { ko: '시간창', en: 'window-set' },
  present_fire: { ko: '타는 불', en: 'fire already burning' },
  forecast_dependent: { ko: '예측 의존', en: 'forecast-dependent' },
  not_established: { ko: '출처 확인 안 됨', en: 'not established' },
  not_computed: { ko: '출처 계산 안 됨', en: 'not computed' },
  unresolved_proven_no_route: { ko: '시간 초과 · 정밀 분석상 경로 없음', en: 'timed out · exact analysis: no route' },
};

/** Compact tags for the A4 sheet's sub line (no room for another line). Never a time or a later value. */
export const PROVENANCE_SHEET_TAG: Record<Exclude<StaffProvenance['kind'], 'none'>, LmText> = {
  window: { ko: '시간창', en: 'window' },
  present_fire: { ko: '타는 불', en: 'burning fire' },
  forecast_dependent: { ko: '예측 의존', en: 'forecast' },
  not_established: { ko: '확인 안 됨', en: 'not established' },
  not_computed: { ko: '계산 안 됨', en: 'not computed' },
  unresolved_proven_no_route: { ko: '정밀 분석상 경로 없음', en: 'exact: no route' },
};
