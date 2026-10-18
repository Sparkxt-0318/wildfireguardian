/**
 * Full-screen preview of the 기관용 사전 대피계획서: one A4 portrait page per origin, page
 * navigation, "PDF로 저장" (current sheet) and "전체 마을 PDF" (all sheets) via window.print().
 * Print CSS prints ONLY the sheets, one per page, without app chrome.
 *
 *   <PlanSheetDialog open={open} onClose={close} sheets={sheets} lang={lang} initialOriginId={selectedId} />
 *
 * Automation (planner/scripts/export_plan_pdfs.mjs): with `?print=all` in the URL (or the
 * `prepareAll` prop) every map is rendered up front; the root element then carries
 * `data-wfg-sheets-ready="true"` once all maps are final and fonts are loaded, and
 * `data-wfg-current-ready="true"` once the current sheet is final.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FOOTER_APP, MOCK_BADGE_TITLE, pick, VERDICT_LABEL, type Lang } from '../shared/strings';
import { IconChevronLeft, IconChevronRight, IconClose, IconPages, IconPrint } from '../shared/Icons';
import { MockBadge, VerdictIcon } from '../shared/VerdictIcon';
import { useModal } from '../shared/useModal';
import { PlanSheet } from './PlanSheet';
import { fill } from './sheetLogic';
import { SHEET } from './strings';
import type { PlanSheetData } from './types';
import '../shared/features.css';
import './plansheet.css';

export interface PlanSheetDialogProps {
  open: boolean;
  onClose: () => void;
  sheets: PlanSheetData[];
  lang: Lang;
  initialOriginId?: string;
  /** render every map up front (print-all automation). Default: true when the URL has ?print=all */
  prepareAll?: boolean;
  /** draw maps as SVG only (no WebGL), e.g. for tests */
  forceSvgMaps?: boolean;
}

type PrintScope = 'all' | 'current';

function urlWantsPrintAll(): boolean {
  try {
    return new URLSearchParams(window.location.search).get('print') === 'all';
  } catch {
    return false;
  }
}

const HTML_CLASS = 'wfgf-printing-sheets';

export function PlanSheetDialog(props: PlanSheetDialogProps): JSX.Element | null {
  const { open, onClose, sheets, lang, initialOriginId, forceSvgMaps } = props;
  const ref = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const t = (s: { ko: string; en: string }) => pick(s, lang);

  const initialIndex = useMemo(() => {
    const i = initialOriginId ? sheets.findIndex((s) => s.origin.id === initialOriginId) : -1;
    return i >= 0 ? i : 0;
  }, [initialOriginId, sheets]);
  const [current, setCurrent] = useState(initialIndex);
  const [prepareAll, setPrepareAll] = useState<boolean>(() => props.prepareAll ?? (typeof window !== 'undefined' && urlWantsPrintAll()));
  const [scope, setScope] = useState<PrintScope>('all');
  const [pendingPrint, setPendingPrint] = useState<PrintScope | null>(null);
  const [settled, setSettled] = useState<Set<string>>(() => new Set());
  const [fontsReady, setFontsReady] = useState(false);

  useModal(ref, open, onClose, { initialFocus: ':self' });

  useEffect(() => {
    if (props.prepareAll !== undefined) setPrepareAll(props.prepareAll);
  }, [props.prepareAll]);

  useEffect(() => {
    if (open) setCurrent(initialIndex);
  }, [open, initialIndex]);

  // While the dialog is open, print media shows only the sheets (see plansheet.css).
  useEffect(() => {
    if (!open) return undefined;
    document.documentElement.classList.add(HTML_CLASS);
    return () => document.documentElement.classList.remove(HTML_CLASS);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    const fonts = (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts;
    if (!fonts) setFontsReady(true);
    else fonts.ready.then(() => alive && setFontsReady(true));
    return () => {
      alive = false;
    };
  }, [open]);

  const onSettled = useCallback((originId: string, done: boolean) => {
    setSettled((prev) => {
      if (prev.has(originId) === done) return prev;
      const next = new Set(prev);
      if (done) next.add(originId);
      else next.delete(originId);
      return next;
    });
  }, []);

  const total = sheets.length;
  const doneCount = sheets.filter((s) => settled.has(s.origin.id)).length;
  const allReady = total > 0 && doneCount === total && fontsReady;
  const currentId = sheets[current]?.origin.id;
  const currentReady = Boolean(currentId && settled.has(currentId) && fontsReady);

  const scrollToPage = useCallback((i: number, behavior: ScrollBehavior = 'smooth') => {
    const vp = viewportRef.current;
    const el = vp?.querySelectorAll<HTMLElement>('.wfgf-sheet')[i];
    if (el && typeof el.scrollIntoView === 'function') el.scrollIntoView({ behavior, block: 'start' });
  }, []);

  const go = useCallback(
    (i: number) => {
      const n = Math.max(0, Math.min(total - 1, i));
      setCurrent(n);
      scrollToPage(n);
    },
    [total, scrollToPage],
  );

  // jump to the initial page when opened
  useEffect(() => {
    if (!open) return undefined;
    setCurrent(initialIndex);
    const id = requestAnimationFrame(() => {
      scrollToPage(initialIndex, 'auto');
      ref.current?.querySelectorAll<HTMLElement>('.wfgf-plansheet__item')[initialIndex]?.scrollIntoView?.({ block: 'center' });
    });
    return () => cancelAnimationFrame(id);
  }, [open, initialIndex, scrollToPage]);

  // track the page in view while scrolling
  useEffect(() => {
    if (!open || typeof IntersectionObserver === 'undefined') return undefined;
    const vp = viewportRef.current;
    if (!vp) return undefined;
    const pages = Array.from(vp.querySelectorAll<HTMLElement>('.wfgf-sheet'));
    const io = new IntersectionObserver(
      (entries) => {
        let best: { i: number; r: number } | null = null;
        for (const e of entries) {
          const i = pages.indexOf(e.target as HTMLElement);
          if (e.isIntersecting && i >= 0 && (!best || e.intersectionRatio > best.r)) best = { i, r: e.intersectionRatio };
        }
        if (best && best.r >= 0.35) setCurrent(best.i);
      },
      { root: vp, threshold: [0.35, 0.6, 0.9] },
    );
    pages.forEach((p) => io.observe(p));
    return () => io.disconnect();
  }, [open, sheets]);

  // keyboard paging (ignored while typing)
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') {
        e.preventDefault();
        go(current + 1);
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        e.preventDefault();
        go(current - 1);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, current, go]);

  // print once the requested sheets are ready
  useEffect(() => {
    if (!pendingPrint) return;
    const ready = pendingPrint === 'all' ? allReady : currentReady;
    if (!ready) return;
    setScope(pendingPrint);
    const id = window.setTimeout(() => {
      const reset = () => {
        setScope('all');
        window.removeEventListener('afterprint', reset);
      };
      window.addEventListener('afterprint', reset);
      try {
        window.print();
      } finally {
        setPendingPrint(null);
      }
    }, 60);
    return () => window.clearTimeout(id);
  }, [pendingPrint, allReady, currentReady]);

  if (!open || typeof document === 'undefined') return null;

  const first = sheets[0];
  const fireLabel = sheets[current]?.fireInputLabel ?? first?.fireInputLabel ?? '';
  const anyMock = sheets.some((s) => s.mock);
  const preparing = pendingPrint === 'all' && !allReady;

  const root = (
    <div
      className="wfgf wfgf-plansheet-root"
      data-print-scope={scope}
      data-wfg-sheets-ready={allReady ? 'true' : 'false'}
      data-wfg-current-ready={currentReady ? 'true' : 'false'}
      data-wfg-sheet-count={total}
      lang={lang}
    >
      <style>{'@page { size: A4 portrait; margin: 0; }'}</style>
      <div ref={ref} className="wfgf-plansheet" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} data-testid="plan-sheet-dialog">
        <header className="wfgf-plansheet__bar">
          <div className="wfgf-plansheet__titlewrap">
            <h2 id={titleId} className="wfgf-plansheet__title">
              {t(SHEET.dialogTitle)}
            </h2>
            <div className="wfgf-plansheet__meta">
              {fireLabel && <span className="wfgf-fireinput">{fireLabel}</span>}
              {anyMock && <MockBadge lang={lang} title={t(MOCK_BADGE_TITLE)} />}
            </div>
          </div>
          <div className="wfgf-plansheet__nav" role="group" aria-label={t(SHEET.sheetList)}>
            <button type="button" className="wfgf-iconbtn" onClick={() => go(current - 1)} disabled={current <= 0} aria-label={t(SHEET.prev)} title={t(SHEET.prev)}>
              <IconChevronLeft />
            </button>
            <span className="wfgf-plansheet__pageof wfgf-num" aria-live="polite">
              {total ? fill(t(SHEET.pageOf), { n: current + 1, total }) : '0 / 0'}
            </span>
            <button
              type="button"
              className="wfgf-iconbtn"
              onClick={() => go(current + 1)}
              disabled={current >= total - 1}
              aria-label={t(SHEET.next)}
              title={t(SHEET.next)}
            >
              <IconChevronRight />
            </button>
          </div>
          <div className="wfgf-plansheet__actions">
            {preparing && (
              <span className="wfgf-plansheet__progress wfgf-num" role="status">
                {fill(t(SHEET.preparing), { done: doneCount, total })}
              </span>
            )}
            <button type="button" className="wfgf-btn" onClick={() => setPendingPrint('current')} disabled={total === 0} data-testid="plansheet-print-current">
              <IconPrint size={18} />
              {t(SHEET.savePdf)}
            </button>
            <button
              type="button"
              className="wfgf-btn wfgf-btn--ink"
              onClick={() => {
                setPrepareAll(true);
                setPendingPrint('all');
              }}
              disabled={total === 0}
              data-testid="plansheet-print-all"
            >
              <IconPages size={18} />
              {t(SHEET.saveAll)}
            </button>
            <button type="button" className="wfgf-iconbtn" onClick={onClose} aria-label={t(SHEET.close)} title={t(SHEET.close)}>
              <IconClose />
            </button>
          </div>
        </header>

        <div className="wfgf-plansheet__main">
          <nav className="wfgf-plansheet__list" aria-label={t(SHEET.sheetList)}>
            <p className="wfgf-plansheet__listhead wfgf-num">{fill(t(SHEET.villages), { n: total })}</p>
            <ol>
              {sheets.map((s, i) => (
                <li key={s.origin.id}>
                  <button type="button" className="wfgf-plansheet__item" aria-current={i === current ? 'page' : undefined} onClick={() => go(i)}>
                    <span className="wfgf-plansheet__itemn wfgf-num">{i + 1}</span>
                    <span className="wfgf-plansheet__itemname">
                      {(lang === 'en' ? s.origin.nameEn || s.origin.name : s.origin.name) || s.origin.displayName || `${s.origin.categoryLabel} · ${t(SHEET.unnamed)}`}
                    </span>
                    {/* status = icon + text: the verdict words are the icons' accessible name and tooltip */}
                    <span className="wfgf-plansheet__itemicons" title={s.scenarios.map((sc) => t(VERDICT_LABEL[sc.bestVerdict])).join(' · ')}>
                      {[...new Set(s.scenarios.map((sc) => sc.bestVerdict))].map((v) => (
                        <span key={v} className={`wfgf-plansheet__itemv wfgf-plansheet__itemv--${v}`}>
                          <VerdictIcon verdict={v} size={12} />
                          {t(VERDICT_LABEL[v])}
                        </span>
                      ))}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </nav>
          <div ref={viewportRef} className="wfgf-plansheet__viewport">
            {total === 0 && <p className="wfgf-plansheet__empty">{t(SHEET.empty)}</p>}
            {sheets.map((s, i) => (
              <PlanSheet
                key={s.origin.id}
                sheet={s}
                lang={lang}
                pageNumber={i + 1}
                pageCount={total}
                current={i === current}
                mapActive={fontsReady && (prepareAll || Math.abs(i - current) <= 1)}
                onMapSettled={onSettled}
                forceSvgMap={forceSvgMaps}
              />
            ))}
          </div>
        </div>

        <footer className="wfgf-plansheet__foot wfgf-footer">
          <span>{t(FOOTER_APP)}</span>
          <span>{t(SHEET.printHint)}</span>
        </footer>
      </div>
    </div>
  );
  return createPortal(root, document.body);
}

export default PlanSheetDialog;
