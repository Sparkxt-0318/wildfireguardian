/**
 * "현장 전달 문구 / Field messages" dialog: for the chosen origin, the Korean and English SMS,
 * long text, village broadcast script and family call script with copy buttons, length counters
 * and rule checks; a card preview with print (A5 / A4 / every origin) and a CSV of every message
 * of the region and input time. Presentational: the entry (FieldMessagesEntry) builds the items.
 *
 * Fail closed: a text whose rule checks fail is shown greyed with the violations and cannot be
 * copied. Works offline (no network: everything is built in the browser).
 */
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { IconClose, IconDownload, IconPrint } from '../shared/Icons';
import { FOOTER_APP, MOCK_BADGE_TITLE, pick, type Lang } from '../shared/strings';
import { MockBadge, VerdictBadge } from '../shared/VerdictIcon';
import { useModal } from '../shared/useModal';
import { downloadText } from '../exports/download';
import { MIME } from '../exports/exports';
import { hm } from './compose';
import { fieldMessagesCSV, fieldMessagesFileName } from './csv';
import { BROADCAST_MAX_S, EN_WORDS_PER_S, KO_SYLLABLES_PER_S, LMS_MAX_BYTES } from './encoding';
import type { ExplanationState } from './explanation';
import { FieldCard, type CardSize } from './FieldCard';
import { allTexts, enabledLangs, type FieldMessages } from './messages';
import { LANGUAGES, lmFill, UI } from './strings';
import type { LmLang } from './types';
import '../shared/features.css';
import './lastmile.css';

export interface FieldMessagesDialogProps {
  open: boolean;
  onClose: () => void;
  /** UI language */
  lang: Lang;
  /** every origin of the scenario, urgency order */
  items: FieldMessages[];
  initialOriginId?: string | null;
  explanation: ExplanationState;
}

type TextKind = 'sms' | 'lms' | 'broadcast' | 'call';
const TEXT_KINDS: TextKind[] = ['sms', 'lms', 'broadcast', 'call'];

interface PrintJob {
  size: CardSize;
  lang: LmLang;
  scope: 'one' | 'all';
}

const HTML_CLASS = 'wfgl-printing-cards';

/** Clipboard with a textarea fallback (older browsers, http); never throws. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  } catch {
    return false;
  }
}

function counterText(fm: FieldMessages, lang: LmLang, kind: TextKind, ui: Lang): string {
  const m = fm.metrics[lang];
  if (kind === 'sms') {
    return m.smsUnit === 'bytes' ? lmFill(pick(UI.bytes, ui), { n: m.smsUnits, max: m.smsLimit }) : lmFill(pick(UI.gsm, ui), { n: m.smsUnits, max: m.smsLimit });
  }
  if (kind === 'lms') return lmFill(pick(UI.bytes, ui), { n: m.lmsBytes, max: LMS_MAX_BYTES });
  if (kind === 'broadcast') {
    return lmFill(pick(UI.seconds, ui), { s: m.broadcastS, max: BROADCAST_MAX_S, rate: lang === 'ko' ? KO_SYLLABLES_PER_S : EN_WORDS_PER_S });
  }
  return lmFill(pick(UI.callSeconds, ui), { s: m.callS });
}

function explanationText(st: ExplanationState, fm: FieldMessages | null, ui: Lang): string {
  if (st.state === 'loading') return pick(UI.explanationLoading, ui);
  if (st.state === 'absent') return pick(UI.explanationAbsent, ui);
  if (st.state === 'invalid') return pick(UI.explanationInvalid, ui);
  return `${pick(UI.explanationReady, ui)} · ${pick(fm?.reason ? UI.explanationUsed : UI.explanationNotUsed, ui)}`;
}

export function FieldMessagesDialog(props: FieldMessagesDialogProps): JSX.Element | null {
  const { open, onClose, lang, items, initialOriginId, explanation } = props;
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const t = (s: { ko: string; en: string }) => pick(s, lang);
  const langs = enabledLangs();
  const [selected, setSelected] = useState<string | null>(initialOriginId ?? null);
  const [cardLang, setCardLang] = useState<LmLang>(lang === 'en' ? 'en' : 'ko');
  const [status, setStatus] = useState<{ key: string; text: string } | null>(null);
  const [printJob, setPrintJob] = useState<PrintJob | null>(null);
  useModal(ref, open, onClose, { initialFocus: ':self' });

  useEffect(() => {
    if (open) setSelected(initialOriginId ?? null);
  }, [open, initialOriginId]);

  const current = useMemo(() => items.find((x) => x.originId === selected) ?? items[0] ?? null, [items, selected]);

  // print: once the print root is in the DOM (and fonts are ready), print only the cards
  useEffect(() => {
    if (!printJob) return undefined;
    let alive = true;
    document.documentElement.classList.add(HTML_CLASS);
    const done = () => {
      document.documentElement.classList.remove(HTML_CLASS);
      window.removeEventListener('afterprint', done);
      if (alive) setPrintJob(null);
    };
    const fonts = (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts;
    const go = () => {
      if (!alive) return;
      window.addEventListener('afterprint', done);
      try {
        window.print();
      } finally {
        // some browsers do not fire afterprint: clear the job after the dialog returns
        window.setTimeout(done, 1000);
      }
    };
    const id = window.setTimeout(() => (fonts ? fonts.ready.then(go, go) : go()), 80);
    return () => {
      alive = false;
      window.clearTimeout(id);
      document.documentElement.classList.remove(HTML_CLASS);
      window.removeEventListener('afterprint', done);
    };
  }, [printJob]);

  if (!open || typeof document === 'undefined') return null;

  const anyMock = items.some((x) => x.plan.input.mock);
  const first = items[0]?.plan.input ?? null;
  const fireLabel = current ? current.plan.input.fireInputLabel[lang === 'en' ? 'en' : 'ko'] : '';

  const doCopy = async (key: string, text: string) => {
    const ok = await copyText(text);
    setStatus({ key, text: t(ok ? UI.copied : UI.copyFailed) });
  };

  const doCsv = () => {
    if (!first) return;
    try {
      const name = fieldMessagesFileName(first);
      downloadText(name, MIME.csv, fieldMessagesCSV(items, { lang: lang === 'en' ? 'en' : 'ko' }));
      setStatus({ key: 'csv', text: lmFill(t(UI.csvSaved), { name }) });
    } catch (e) {
      setStatus({ key: 'csv', text: lmFill(t(UI.csvError), { msg: e instanceof Error ? e.message : String(e) }) });
    }
  };

  const failed = Boolean(current && current.violations.length);

  const dialog = (
    <div className="wfgf wfgl-root" lang={lang}>
      <div className="wfgf-scrim" onClick={onClose} aria-hidden="true" />
      <div ref={ref} className="wfgl-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} data-testid="field-messages-dialog">
        <header className="wfgl-dialog__head">
          <div className="wfgl-dialog__titlewrap">
            <h2 id={titleId}>{t(UI.dialogTitle)}</h2>
            <p className="wfgl-dialog__meta">
              {fireLabel ? <span className="wfgf-fireinput">{fireLabel}</span> : null}
              {anyMock ? <MockBadge lang={lang} title={t(MOCK_BADGE_TITLE)} /> : null}
            </p>
          </div>
          <button type="button" className="wfgf-iconbtn" onClick={onClose} aria-label={t(UI.close)} title={t(UI.close)}>
            <IconClose />
          </button>
        </header>

        <div className="wfgl-dialog__body">
          <p className="wfgl-dialog__lead">{t(UI.dialogLead)}</p>
          {first?.replay ? <p className="wfgl-dialog__note">{t(UI.replayNote)}</p> : null}

          <div className="wfgl-dialog__pick">
            <label>
              <span>{t(UI.origin)}</span>
              <select value={current?.originId ?? ''} onChange={(e) => setSelected(e.target.value)} data-testid="field-messages-origin">
                {items.map((x) => (
                  <option key={x.originId} value={x.originId}>
                    {`${x.urgencyRank}. ${x.plan.input.origin.display[lang === 'en' ? 'en' : 'ko']}`}
                  </option>
                ))}
              </select>
            </label>
            <p className="wfgl-dialog__explain" data-explanation-state={explanation.state}>
              <b>{t(UI.explanation)}:</b> {explanationText(explanation, current, lang)}
            </p>
          </div>

          {current ? (
            <>
              <div className="wfgl-dialog__status" data-kind={current.kind} data-verdict={current.verdict}>
                <span>
                  {t(UI.verdict)}: <VerdictBadge verdict={current.verdict} lang={lang} size={16} />
                </span>
                <span>
                  {t(UI.kind)}: <b>{t(UI.kindLabel[current.kind])}</b>
                  {current.leaveByS !== null ? <b className="wfgf-num"> · {hm(current.plan.input.scenario.inputTimeIso, current.leaveByS)}</b> : null}
                </span>
                <span className={failed ? 'wfgl-checks wfgl-checks--fail' : 'wfgl-checks'} role="status" data-testid="field-messages-checks">
                  {failed ? `${t(UI.checksFailed)}: ${current.violations.join(' | ')}` : t(UI.checksOk)}
                </span>
              </div>

              {TEXT_KINDS.map((kind) => (
                <section key={kind} className="wfgl-block" aria-label={t(UI[kind])} data-block={kind}>
                  <h3>{t(UI[kind])}</h3>
                  <div className="wfgl-block__cols">
                    {langs.map((l) => {
                      const text = allTexts(current, l)[kind];
                      const key = `${current.originId}:${kind}:${l}`;
                      return (
                        <div key={l} className="wfgl-text" data-lang={l}>
                          <div className="wfgl-text__head">
                            <span className="wfgl-text__lang">{LANGUAGES[l].label}</span>
                            <span className="wfgl-text__count wfgf-num">{counterText(current, l, kind, lang)}</span>
                            <button type="button" className="wfgf-btn wfgl-text__copy" disabled={failed} onClick={() => void doCopy(key, text)} data-testid={`copy-${kind}-${l}`}>
                              {t(UI.copy)}
                            </button>
                          </div>
                          <pre className={`wfgl-text__body${failed ? ' wfgl-text__body--failed' : ''}`} lang={l}>
                            {text}
                          </pre>
                          {status?.key === key ? (
                            <span className="wfgl-text__status" role="status">
                              {status.text}
                            </span>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </section>
              ))}

              <section className="wfgl-block" aria-label={t(UI.card)} data-block="card">
                <h3>{t(UI.card)}</h3>
                <div className="wfgl-cardtools">
                  <div className="wfgl-seg" role="group" aria-label={t(UI.cardLang)}>
                    {langs.map((l) => (
                      <button key={l} type="button" aria-pressed={cardLang === l} onClick={() => setCardLang(l)}>
                        {LANGUAGES[l].label}
                      </button>
                    ))}
                  </div>
                  <button type="button" className="wfgf-btn" disabled={failed} onClick={() => setPrintJob({ size: 'a5', lang: cardLang, scope: 'one' })} data-testid="print-card-a5">
                    <IconPrint size={18} />
                    {t(UI.printA5)}
                  </button>
                  <button type="button" className="wfgf-btn" disabled={failed} onClick={() => setPrintJob({ size: 'a4', lang: cardLang, scope: 'one' })} data-testid="print-card-a4">
                    <IconPrint size={18} />
                    {t(UI.printA4)}
                  </button>
                  <button
                    type="button"
                    className="wfgf-btn wfgf-btn--ink"
                    disabled={items.some((x) => x.violations.length)}
                    onClick={() => setPrintJob({ size: 'a5', lang: cardLang, scope: 'all' })}
                    data-testid="print-card-all"
                  >
                    <IconPrint size={18} />
                    {t(UI.printAll)}
                  </button>
                </div>
                <div className="wfgl-preview">
                  <div className="wfgl-preview__scale">
                    <FieldCard card={current.text[cardLang].card} size="a5" originId={current.originId} />
                  </div>
                </div>
              </section>
            </>
          ) : (
            <p className="wfgl-dialog__lead">{t(UI.noData)}</p>
          )}
        </div>

        <footer className="wfgl-dialog__foot">
          <button type="button" className="wfgf-btn wfgf-btn--ink" onClick={doCsv} disabled={!items.length} data-testid="field-messages-csv">
            <IconDownload size={18} />
            {lmFill(t(UI.csv), { n: items.length })}
          </button>
          {status?.key === 'csv' ? (
            <span className="wfgl-text__status" role="status">
              {status.text}
            </span>
          ) : null}
          <span className="wfgf-footer">{t(FOOTER_APP)}</span>
        </footer>
      </div>
    </div>
  );

  const printCards = printJob ? (printJob.scope === 'all' ? items : current ? [current] : []) : [];
  const printRoot = printJob ? (
    <div className="wfgf wfgl-print-root" data-print-size={printJob.size} data-testid="field-card-print-root">
      <style>{`@page { size: ${printJob.size === 'a4' ? 'A4' : 'A5'} portrait; margin: 0; }`}</style>
      {printCards.map((x) => (
        <FieldCard key={x.originId} card={x.text[printJob.lang].card} size={printJob.size} originId={x.originId} />
      ))}
    </div>
  ) : null;

  return (
    <>
      {createPortal(dialog, document.body)}
      {printRoot ? createPortal(printRoot, document.body) : null}
    </>
  );
}

export default FieldMessagesDialog;
