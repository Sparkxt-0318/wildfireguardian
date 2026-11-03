/**
 * Judge onboarding of the public static demo: a dismissible bilingual introduction (≤ 80 words with
 * its title and the three verdict chips) and a 3-step tour —
 *   1. pick a village or care facility from the urgency list,
 *   2. read its 출발 마감 / leave-by time and the evidence (unless the user picked one themselves, the
 *      tour picks an origin with a checked route: one whose leave-by time is set by predicted flames
 *      on the route when the scenario's explanation file says so, else the first village or care
 *      facility in the list — see tourPick.ts),
 *   3. open the A4 plan sheet.
 * Dismissal is remembered in localStorage (inside try/catch: private windows and blocked storage
 * just show the introduction again). The ribbon's "둘러보기 / Tour" button reopens it.
 *
 * Keyboard: the introduction is a modal dialog (focus stays inside it; Escape closes it wherever the
 * focus is). The tour card is a non-modal dialog that takes the focus at every step, so its buttons
 * are the next Tab stops; Escape ends the tour. Closing either returns the focus to the button that
 * opened it (the ribbon's tour button after the first-visit introduction).
 */
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import { create } from 'zustand';
import { useLang, useLangStore, useT } from '../../i18n';
import { openDialog } from '../../state/controller';
import { getState, useStore } from '../../state/store';
import { isNarrowScreen, setMobilePane, type MobilePane } from '../MobileNav';
import { StatusChip } from '../StatusChip';
import { CloseIcon } from '../Icons';
import { useRecordedPeriod, useRecordedRegionNames } from './StaticDemo';
import { loadFlameOnRoute, selectTourOrigin, tourScenario } from './tourPick';
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

/** `opener`: the element that had the focus when the introduction was opened (gets it back on close). */
export const useTour = create<{ step: TourStep; opener: HTMLElement | null; setStep: (s: TourStep) => void }>((set) => ({
  step: null,
  opener: null,
  setStep: (step) => set({ step }),
}));

/** The ribbon's "둘러보기 / Tour" button: where the focus goes when nothing else opened the tour. */
export const TOUR_BUTTON = '[data-testid="demo-tour-open"]';

/** Opens the introduction (ribbon button; the first visit opens it without an opener). */
export function openIntro(opener: HTMLElement | null = null): void {
  useTour.setState({ step: 'intro', opener });
}

/**
 * Ends the introduction or the tour and remembers the dismissal. The focus returns to the opener
 * (or the ribbon's tour button) unless something else takes it next (the plan sheet).
 */
export function endTour({ restoreFocus = true }: { restoreFocus?: boolean } = {}): void {
  rememberIntroDismissed();
  const { opener } = useTour.getState();
  useTour.setState({ step: null, opener: null });
  if (!restoreFocus || typeof document === 'undefined') return;
  const target = opener?.isConnected ? opener : document.querySelector<HTMLElement>(TOUR_BUTTON);
  target?.focus({ preventScroll: true });
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

function hasCheckedRoute(id: string | null): boolean {
  return Boolean(id && getState().plans[id]?.bestVerdict === 'checked_route');
}

/** Another modal dialog (plan sheet, export, about) handles its own keys. */
function otherModalOpen(except: Element | null): boolean {
  return [...document.querySelectorAll('[role="dialog"][aria-modal="true"]')].some((d) => d !== except);
}

const FOCUSABLE = 'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

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
  const dialog = useRef<HTMLDivElement | null>(null);
  const primary = useRef<HTMLButtonElement | null>(null);

  // modal: the focus starts on the primary action and stays inside; Escape closes from anywhere
  useEffect(() => {
    primary.current?.focus();
    const open = () => useTour.getState().step === 'intro';
    const focusables = () => [...(dialog.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])];
    const onKey = (e: KeyboardEvent) => {
      if (!open()) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        endTour();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      const active = document.activeElement;
      const inside = !!active && !!dialog.current?.contains(active);
      if (e.shiftKey && (!inside || active === first)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (!inside || active === last)) {
        e.preventDefault();
        first.focus();
      }
    };
    // focus moved out by other means (a click on the page behind is caught by the backdrop)
    const onFocusIn = (e: FocusEvent) => {
      if (open() && dialog.current && e.target instanceof Node && !dialog.current.contains(e.target)) primary.current?.focus();
    };
    window.addEventListener('keydown', onKey, true);
    document.addEventListener('focusin', onFocusIn);
    return () => {
      window.removeEventListener('keydown', onKey, true);
      document.removeEventListener('focusin', onFocusIn);
    };
  }, []);

  return (
    <div className="demo-intro-backdrop" onClick={() => endTour()}>
      <div
        ref={dialog}
        className="demo-intro"
        role="dialog"
        aria-modal="true"
        aria-labelledby="demo-intro-title"
        aria-describedby="demo-intro-body"
        onClick={(e) => e.stopPropagation()}
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
          <button type="button" className="demo-icon-btn" onClick={() => endTour()} aria-label={t('demo.intro.closeAria')} title={t('demo.intro.closeAria')}>
            <CloseIcon size={16} />
          </button>
        </div>
        <p className="demo-intro-body" id="demo-intro-body" data-testid="demo-intro-body">
          {t('demo.intro.body', { period: period ?? '', regions })}
        </p>
        <div className="demo-intro-verdicts" role="group" aria-label={t('demo.intro.verdicts')}>
          <StatusChip verdict="checked_route" />
          <StatusChip verdict="model_no_route" />
          <StatusChip verdict="unresolved" />
        </div>
        <div className="demo-intro-actions">
          <button type="button" className="btn" onClick={() => endTour()} data-testid="demo-intro-close">
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
  const card = useRef<HTMLDivElement | null>(null);
  const startSelected = useRef(selected);

  // step 1 → 2 as soon as the user picks a village or facility themselves (their pick is kept)
  useEffect(() => {
    if (step !== 1) return;
    startSelected.current = useStore.getState().selectedOriginId;
    // read the scenario's explanation file now, so "Next" has it at once (optional; null on 404)
    const scenario = tourScenario(getState());
    if (scenario) void loadFlameOnRoute(scenario);
  }, [step]);
  useEffect(() => {
    if (step === 1 && selected && selected !== startSelected.current) setStep(2);
  }, [step, selected, setStep]);

  // every step takes the focus: its buttons are the next Tab stops (no hunt through the page)
  useEffect(() => {
    card.current?.focus({ preventScroll: true });
  }, [step]);

  // Escape ends the tour, wherever the focus is (another open modal dialog handles its own keys)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented || otherModalOpen(null)) return;
      e.preventDefault();
      endTour();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

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

  const next = async () => {
    if (step === 1) {
      if (!hasCheckedRoute(useStore.getState().selectedOriginId)) await selectTourOrigin();
      // the tour may have been ended while the explanation file was read
      if (useTour.getState().step === 1) setStep(2);
    } else if (step === 2) setStep(3);
  };
  return (
    <div
      ref={card}
      className={`tour-card${pos.left === undefined ? ' centered' : ''}`}
      role="dialog"
      aria-modal="false"
      aria-labelledby="tour-title"
      aria-describedby="tour-body"
      tabIndex={-1}
      style={pos}
      data-testid="tour-card"
      data-step={step}
    >
      <div className="tour-step tnum">{t('demo.tour.step', { n: step })}</div>
      <h3 id="tour-title">{t(`demo.tour.${step}.title`)}</h3>
      <p id="tour-body">{t(`demo.tour.${step}.body`)}</p>
      <div className="tour-actions">
        <button type="button" className="btn btn-ghost" onClick={() => endTour()} data-testid="tour-skip">
          {t('demo.tour.skip')}
        </button>
        <span className="tour-spacer" />
        {step > 1 ? (
          <button type="button" className="btn" onClick={() => setStep((step - 1) as 1 | 2)} data-testid="tour-back">
            {t('demo.tour.back')}
          </button>
        ) : null}
        {step < 3 ? (
          <button type="button" className="btn btn-ink" onClick={() => void next()} data-testid="tour-next">
            {t('demo.tour.next')}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-ink"
            onClick={() => {
              endTour({ restoreFocus: false }); // the plan sheet takes the focus
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

/** Mount once (static demo), right after the ribbon: the tour card's buttons follow it in Tab order. */
export function DemoIntro() {
  const step = useTour((s) => s.step);
  useEffect(() => {
    if (!introDismissed()) openIntro(null);
  }, []);
  if (step === null) return null;
  if (step === 'intro') return <IntroCard />;
  return <TourCard step={step} />;
}
