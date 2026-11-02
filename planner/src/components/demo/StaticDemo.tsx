/**
 * Public static demo chrome (VITE_WFG_API_MODE=static, see config/env.ts):
 *
 * - DemoRibbon: "DEMO · recorded March 2025 scenarios · research prototype" (period derived from the
 *   cache index, never hard-coded), the tour button and the feedback link;
 * - StaticNote: why live computation is not offered here, with a link to the local-run instructions;
 * - StaticApiStatus: top-bar status "정적 데모 · API 없음" instead of "offline";
 * - FeedbackLink: "의견 보내기 / Feedback" → VITE_FEEDBACK_URL (default: the repository's
 *   planner-feedback issue template). No personal e-mail address is ever shown.
 */
import { useMemo } from 'react';
import { CONFIG } from '../../config/env';
import { kstDate } from '../../domain/clock';
import { useLang, useT, type Lang, type TFunction } from '../../i18n';
import { useStore } from '../../state/store';
import { InfoIcon } from '../Icons';
import { monthParts } from './strings';
import './strings';
import './demo.css';

/** README section with the local Route-Check API instructions (documentation link, never fetched). */
export function localRunUrl(repoUrl: string = CONFIG.repoUrl): string {
  return `${repoUrl}/blob/HEAD/planner/README.md#real-route-check-api`;
}

/** KST months ("2025-03") of the recorded input times in the cache index, sorted, unique. */
export function recordedMonths(inputTimes: string[]): string[] {
  const out = new Set<string>();
  for (const t of inputTimes) {
    const d = kstDate(t);
    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) out.add(d.slice(0, 7));
  }
  return [...out].sort();
}

/** "March 2025" / "2025년 3월" (or a range "March 2022–March 2025"); null without recorded times. */
export function periodLabel(inputTimes: string[], t: TFunction): string | null {
  const months = recordedMonths(inputTimes);
  const fmt = (ym: string) => {
    const p = monthParts(ym);
    return p ? t('demo.period', { year: p.year, month: p.month, monthName: p.monthName }) : ym;
  };
  if (!months.length) return null;
  if (months.length === 1) return fmt(months[0]!);
  return t('demo.periodRange', { from: fmt(months[0]!), to: fmt(months[months.length - 1]!) });
}

/** "의성·안동, 영덕" / "Uiseong–Andong and Yeongdeok". */
export function joinNames(names: string[], lang: Lang): string {
  if (names.length <= 1) return names[0] ?? '';
  if (lang === 'ko') return names.join(', ');
  return names.length === 2 ? `${names[0]} and ${names[1]}` : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/** Period of the recorded scenarios that the cache holds (KST months of the input times). */
export function useRecordedPeriod(): string | null {
  const t = useT();
  const cacheIndex = useStore((s) => s.cacheIndex);
  return useMemo(() => periodLabel(cacheIndex.map((e) => e.inputTime), t), [cacheIndex, t]);
}

/** Names of the listed regions that have recorded results in the cache. */
export function useRecordedRegionNames(): string {
  const lang = useLang();
  const regions = useStore((s) => s.regionIndex);
  const cacheIndex = useStore((s) => s.cacheIndex);
  return useMemo(() => {
    const names = regions.filter((r) => cacheIndex.some((e) => e.regionId === r.id)).map((r) => (lang === 'en' ? r.nameEn : r.nameKo));
    return joinNames(names, lang);
  }, [regions, cacheIndex, lang]);
}

export function FeedbackLink({ className = 'btn' }: { className?: string }) {
  const t = useT();
  if (!CONFIG.feedbackUrl) return null;
  return (
    <a className={className} href={CONFIG.feedbackUrl} target="_blank" rel="noopener noreferrer" title={t('demo.feedbackTitle')} data-testid="feedback-link">
      {t('demo.feedback')}
      <span aria-hidden="true" className="demo-ext">
        ↗
      </span>
    </a>
  );
}

/** The thin strip under the top bar in the static demo. */
export function DemoRibbon({ onTour }: { onTour: () => void }) {
  const t = useT();
  const period = useRecordedPeriod();
  return (
    <div className="demo-ribbon" role="note" data-testid="demo-ribbon">
      <span className="demo-chip" title={t('demo.chipTitle')} data-testid="demo-chip">
        <b>{t('demo.chip')}</b>
        <span className="demo-chip-sep" aria-hidden="true">
          ·
        </span>
        <span>{period ? t('demo.chipText', { period }) : t('demo.chipTextNoPeriod')}</span>
      </span>
      <span className="demo-ribbon-note">{t('demo.noLive')}</span>
      <span className="demo-ribbon-spacer" />
      <button type="button" className="demo-ribbon-btn" onClick={onTour} data-testid="demo-tour-open">
        <InfoIcon size={13} />
        {t('demo.tour')}
      </button>
      <FeedbackLink className="demo-ribbon-btn" />
    </div>
  );
}

/** Replaces "needs the API" hints in the static demo: what is not offered and where to run it. */
export function StaticNote({ compact = false }: { compact?: boolean }) {
  const t = useT();
  return (
    <div className={`static-note${compact ? ' compact' : ''}`} data-testid="static-note">
      <span className="static-note-title">{t('demo.static.title')}</span>
      {compact ? null : <span className="static-note-body">{t('demo.static.body')}</span>}
      <a href={localRunUrl()} target="_blank" rel="noopener noreferrer">
        {t('demo.static.link')}
      </a>
    </div>
  );
}

/** Top-bar API status in the static demo (grey, never "connected"). */
export function StaticApiStatus() {
  const t = useT();
  return (
    <span className="api-status offline" title={t('demo.apiTitle')} data-testid="api-status">
      <span className="led" aria-hidden="true" />
      {t('demo.api')}
    </span>
  );
}
