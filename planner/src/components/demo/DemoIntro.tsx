/**
 * Judge onboarding of the public static demo: a dismissible bilingual introduction (≤ 80 words with
 * its title and the three verdict chips) and a 3-step tour —
 *   1. pick a village or care facility from the urgency list,
 *   2. read its 출발 마감 / leave-by time and the evidence,
 *   3. open the A4 plan sheet.
 * Dismissal is remembered in localStorage (inside try/catch: private windows and blocked storage
 * just show the introduction again). The ribbon's "둘러보기 / Tour" button reopens it.
 */
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import { create } from 'zustand';
import { useLang, useLangStore, useT } from '../../i18n';
import { openDialog } from '../../state/controller';
import { useStore } from '../../state/store';
import { isNarrowScreen, setMobilePane, type MobilePane } from '../MobileNav';
import { StatusChip } from '../StatusChip';
import { CloseIcon } from '../Icons';
import { useRecordedPeriod, useRecordedRegionNames } from './StaticDemo';
import './strings';
import './demo.css';

export const INTRO_STORAGE_KEY = 'wfg.planner.demoIntro.dismissed';

export function introDismissed(storage: Pick<Storage, 'getItem'> | null = safeStorage()): boolean {
  try {
    return storage?.getItem(INTRO_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

export function rememberIntroDismissed(storage: Pick<Storage, 'setItem'> | null = safeStorage()): void {
  try {
    storage?.setItem(INTRO_STORAGE_KEY, '1');
  } catch {
    /* storage unavailable: the introduction just shows again next time */
  }
}

function safeStorage(): Storage | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage : null;
  } catch {
    return null;
  }
}

export type TourStep = 'intro' | 1 | 2 | 3 | null;

export const useTour = create<{ step: TourStep; setStep: (s: TourStep) => void }>((set) => ({
  step: null,
  setStep: (step) => set({ step }),
}));

/** Opens the introduction (ribbon button). */
export function openIntro(): void {
  useTour.getState().setStep('intro');
}

function endTour(): void {
  rememberIntroDismissed();
  useTour.getState().setStep(null);
}

const TARGETS: Record<1 | 2 | 3, { selector: string[]; pane: MobilePane }> = {
  1: { selector: ['.origin-list'], pane: 'list' },
  2: { selector: ['.panel-right .headline', '.panel-right'], pane: 'detail' },
  3: { selector: ['[data-testid="open-plansheet"]'], pane: 'detail' },
};

function findTarget(step: 1 | 2 | 3): HTMLElement | null {
  for (const s of TARGETS[step].selector) {
    const el = document.querySelector<HTMLElement>(s);
    if (el) return el;
  }
  return null;
}

/** The village or facility at the top of the urgency list as shown (step 2 needs one selected). */
function selectTopOfList(): void {
  document.querySelector<HTMLButtonElement>('.origin-list .origin-row')?.click();
}

const CARD_W = 340;

function cardPosition(target: HTMLElement | null): CSSProperties {
  if (!target || isNarrowScreen()) return {};
  const r = target.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const top = Math.max(64, Math.min(r.top + 8, vh - 300));
  if (r.right + 16 + CARD_W <= vw) return { left: r.right + 16, top };
  if (r.left - 16 - CARD_W >= 0) return { left: r.left - 16 - CARD_W, top };
  return { left: Math.max(16, Math.min(r.left, vw - CARD_W - 16)), top: Math.min(r.bottom + 10, vh - 300) };
}

function IntroCard() {
  const t = useT();
  const lang = useLang();
  const setLang = useLangStore((s) => s.setLang);
  const setStep = useTour((s) => s.setStep);
  const period = useRecordedPeriod();
  const regions = useRecordedRegionNames();
  const primary = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    primary.current?.focus();
  }, []);
  return (
    <div className="demo-intro-backdrop" onClick={endTour}>
      <div
        className="demo-intro"
        role="dialog"
        aria-modal="true"
        aria-labelledby="demo-intro-title"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === 'Escape') endTour();
        }}
        data-testid="demo-intro"
      >
        <div className="demo-intro-head">
          <h2 id="demo-intro-title">{t('demo.intro.title')}</h2>
          <div className="seg" role="group" aria-label={t('demo.intro.lang')}>
            <button type="button" aria-pressed={lang === 'ko'} onClick={() => setLang('ko')} lang="ko">
              한국어
            </button>
            <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')} lang="en">
              English
            </button>
          </div>
          <button type="button" className="demo-icon-btn" onClick={endTour} aria-label={t('demo.intro.closeAria')} title={t('demo.intro.closeAria')}>
            <CloseIcon size={16} />
          </button>
        </div>
        <p className="demo-intro-body" data-testid="demo-intro-body">
          {t('demo.intro.body', { period: period ?? '', regions })}
        </p>
        <div className="demo-intro-verdicts" role="group" aria-label={t('demo.intro.verdicts')}>
          <StatusChip verdict="checked_route" />
          <StatusChip verdict="model_no_route" />
          <StatusChip verdict="unresolved" />
        </div>
        <div className="demo-intro-actions">
          <button type="button" className="btn" onClick={endTour} data-testid="demo-intro-close">
            {t('demo.intro.close')}
          </button>
          <button ref={primary} type="button" className="btn btn-ink" onClick={() => setStep(1)} data-testid="demo-tour-start">
            {t('demo.intro.start')}
          </button>
        </div>
      </div>
    </div>
  );
}

function TourCard({ step }: { step: 1 | 2 | 3 }) {
  const t = useT();
  const setStep = useTour((s) => s.setStep);
  const selected = useStore((s) => s.selectedOriginId);
  const [pos, setPos] = useState<CSSProperties>({});
  const startSelected = useRef(selected);

  // step 1 → 2 as soon as the user picks a village or facility themselves
  useEffect(() => {
    if (step === 1) startSelected.current = useStore.getState().selectedOriginId;
  }, [step]);
  useEffect(() => {
    if (step === 1 && selected && selected !== startSelected.current) setStep(2);
  }, [step, selected, setStep]);

  // highlight the step's target (and show its pane on a narrow screen)
  useLayoutEffect(() => {
    if (isNarrowScreen()) setMobilePane(TARGETS[step].pane);
    let el: HTMLElement | null = null;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const attach = () => {
      el = findTarget(step);
      if (!el && tries++ < 20) {
        timer = setTimeout(attach, 100);
        return;
      }
      if (!el) return;
      el.classList.add('tour-target');
      el.scrollIntoView?.({ block: 'nearest' });
      setPos(cardPosition(el));
    };
    attach();
    const onResize = () => setPos(cardPosition(el));
    window.addEventListener('resize', onResize);
    return () => {
      if (timer) clearTimeout(timer);
      window.removeEventListener('resize', onResize);
      el?.classList.remove('tour-target');
    };
  }, [step, selected]);

  const next = () => {
    if (step === 1) {
      if (!useStore.getState().selectedOriginId) selectTopOfList();
      setStep(2);
    } else if (step === 2) setStep(3);
  };
  return (
    <div
      className={`tour-card${pos.left === undefined ? ' centered' : ''}`}
      role="dialog"
      aria-modal="false"
      aria-labelledby="tour-title"
      style={pos}
      data-testid="tour-card"
      data-step={step}
    >
      <div className="tour-step tnum">{t('demo.tour.step', { n: step })}</div>
      <h3 id="tour-title">{t(`demo.tour.${step}.title`)}</h3>
      <p>{t(`demo.tour.${step}.body`)}</p>
      <div className="tour-actions">
        <button type="button" className="btn btn-ghost" onClick={endTour} data-testid="tour-skip">
          {t('demo.tour.skip')}
        </button>
        <span className="tour-spacer" />
        {step > 1 ? (
          <button type="button" className="btn" onClick={() => setStep((step - 1) as 1 | 2)}>
            {t('demo.tour.back')}
          </button>
        ) : null}
        {step < 3 ? (
          <button type="button" className="btn btn-ink" onClick={next} data-testid="tour-next">
            {t('demo.tour.next')}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-ink"
            onClick={() => {
              endTour();
              openDialog('planSheet');
            }}
            data-testid="tour-open-plansheet"
          >
            {t('demo.tour.open')}
          </button>
        )}
      </div>
    </div>
  );
}

/** Mount once (static demo). Shows the introduction on the first visit. */
export function DemoIntro() {
  const step = useTour((s) => s.step);
  const setStep = useTour((s) => s.setStep);
  useEffect(() => {
    if (!introDismissed()) setStep('intro');
  }, [setStep]);
  if (step === null) return null;
  if (step === 'intro') return <IntroCard />;
  return <TourCard step={step} />;
}
