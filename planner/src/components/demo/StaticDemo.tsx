/**
 * Public static demo chrome (VITE_WFG_API_MODE=static, see config/env.ts):
 *
 * - DemoRibbon: "DEMO · recorded March 2025 scenarios · research prototype" (period derived from the
 *   cache index, never hard-coded; one short line on phones), the tour button and the feedback link;
 * - StaticNote: why live computation is not offered here, with a link to the local-run instructions;
 * - StaticApiStatus: top-bar status "정적 데모 · API 없음" instead of "offline";
 * - FeedbackLink: "의견 보내기 / Feedback" → VITE_FEEDBACK_URL (default: the repository's
 *   planner-feedback issue template). No personal e-mail address is ever shown.
 */
import { useMemo, type MouseEvent } from 'react';
import { CONFIG } from '../../config/env';
import { useLang, useT } from '../../i18n';
import { useStore } from '../../state/store';
import { joinNames, localRunUrl, periodLabel } from './labels';
import './strings';
import './demo.css';

export { joinNames, localRunUrl, periodLabel, recordedMonths } from './labels';

/** Period of the recorded scenarios that the cache holds (KST months of the input times). */
export function useRecordedPeriod(short = false): string | null {
  const t = useT();
  const cacheIndex = useStore((s) => s.cacheIndex);
  return useMemo(() => periodLabel(cacheIndex.map((e) => e.inputTime), t, short), [cacheIndex, t, short]);
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

/** Tour: a signpost (the top bar's About keeps the ⓘ). */
function TourGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M8 1.25v13.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M8 2.6h4.9L15 4.75 12.9 6.9H8z" fill="currentColor" />
      <path d="M8 8.1H3.1L1 10.25l2.1 2.15H8z" fill="currentColor" />
    </svg>
  );
}

function FeedbackGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

export function FeedbackLink({ className = 'btn' }: { className?: string }) {
  const t = useT();
  if (!CONFIG.feedbackUrl) return null;
  return (
    <a className={className} href={CONFIG.feedbackUrl} target="_blank" rel="noopener noreferrer" title={t('demo.feedbackTitle')} data-testid="feedback-link">
      <span className="demo-icon-only" aria-hidden="true">
        <FeedbackGlyph />
      </span>
      <span className="demo-btn-label">{t('demo.feedback')}</span>
      <span aria-hidden="true" className="demo-ext">
        ↗
      </span>
    </a>
  );
}

/** The thin strip under the top bar in the static demo. */
export function DemoRibbon({ onTour }: { onTour: (opener: HTMLElement | null) => void }) {
  const t = useT();
  const period = useRecordedPeriod();
  const periodShort = useRecordedPeriod(true);
  return (
    <div className="demo-ribbon" role="note" data-testid="demo-ribbon">
      <span className="demo-chip" title={t('demo.chipTitle')} data-testid="demo-chip">
        <b>{t('demo.chip')}</b>
        <span className="demo-chip-sep" aria-hidden="true">
          ·
        </span>
        <span className="demo-chip-full">{period ? t('demo.chipText', { period }) : t('demo.chipTextNoPeriod')}</span>
        {/* phones (≤ 480 px, styles/mobile.css): the same three facts on one short line; the hidden
            variant is display: none, so assistive technology reads exactly one of them */}
        <span className="demo-chip-short">
          {periodShort ? t('demo.chipShort', { period: periodShort }) : t('demo.chipTextNoPeriod')}
        </span>
      </span>
      <span className="demo-ribbon-note">{t('demo.noLive')}</span>
      <span className="demo-ribbon-spacer" />
      <button
        type="button"
        className="demo-ribbon-btn"
        onClick={(e: MouseEvent<HTMLButtonElement>) => onTour(e.currentTarget)}
        title={t('demo.tour')}
        data-testid="demo-tour-open"
      >
        <TourGlyph />
        <span className="demo-btn-label">{t('demo.tour')}</span>
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
