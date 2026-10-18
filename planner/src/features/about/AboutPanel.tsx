/**
 * About panel: a calm full-height side sheet (Esc closes, focus trap, aria-modal) that explains
 * what the tool answers, the method, the three verdicts, Ready-Set-Go, the honest limitations,
 * data sources/licences and version identities.
 *
 *   <AboutPanel open={open} onClose={() => setOpen(false)} lang={lang} apiVersion={health?.apiVersion} />
 *
 * Optional `fireInputLabel` / `mock` repeat the app's fire-input banner inside the sheet, because
 * the sheet covers part of the top bar.
 */
import { useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { VERDICTS } from '../../domain/types';
import { FIXED_IDENTITY, FOOTER_APP, LIMITATIONS, MOCK_BADGE_TITLE, pick, VERDICT_DEFINITION, VERDICT_LABEL, type Lang } from '../shared/strings';
import { IconClose } from '../shared/Icons';
import { MockBadge, VerdictIcon } from '../shared/VerdictIcon';
import { useModal } from '../shared/useModal';
import { MethodDiagram } from './MethodDiagram';
import { ABOUT, SOURCES } from './strings';
import '../shared/features.css';
import './about.css';

export interface AboutPanelProps {
  open: boolean;
  onClose: () => void;
  lang: Lang;
  /** Route-Check API contract version reported by /health (e.g. "1.5.0"); omitted → "no API connected". */
  apiVersion?: string;
  /** optional: the fire-input banner text of the current screen */
  fireInputLabel?: string;
  /** optional: show the MOCK badge */
  mock?: boolean;
}

export function AboutPanel(props: AboutPanelProps): JSX.Element | null {
  const { open, onClose, lang, apiVersion, fireInputLabel, mock } = props;
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useModal(ref, open, onClose, { initialFocus: ':self' });
  if (!open || typeof document === 'undefined') return null;
  const t = (s: { ko: string; en: string }) => pick(s, lang);

  const panel = (
    <div className="wfgf wfgf-about-root" lang={lang}>
      <div className="wfgf-scrim" onClick={onClose} aria-hidden="true" />
      <div
        ref={ref}
        className="wfgf-sheetpanel wfgf-about"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid="about-panel"
      >
        <header className="wfgf-about__head">
          <div>
            <p className="wfgf-about__eyebrow">{t(ABOUT.subtitle)}</p>
            <h2 id={titleId} className="wfgf-about__title">
              {t(ABOUT.title)}
            </h2>
            {(fireInputLabel || mock) && (
              <p className="wfgf-about__fire">
                {fireInputLabel && <span className="wfgf-fireinput">{fireInputLabel}</span>}
                {mock && <MockBadge lang={lang} title={t(MOCK_BADGE_TITLE)} />}
              </p>
            )}
          </div>
          <button type="button" className="wfgf-iconbtn" onClick={onClose} aria-label={t(ABOUT.close)} title={t(ABOUT.close)}>
            <IconClose />
          </button>
        </header>

        <div className="wfgf-about__body">
          <section className="wfgf-about__section" aria-labelledby={`${titleId}-answers`}>
            <h3 id={`${titleId}-answers`}>{t(ABOUT.answersTitle)}</h3>
            <ol className="wfgf-about__answers">
              {ABOUT.answers.map((a, i) => (
                <li key={i}>
                  <span className="wfgf-about__answer-n">{i + 1}</span>
                  <span>{t(a)}</span>
                </li>
              ))}
            </ol>
            <p className="wfgf-about__muted">{t(ABOUT.answersNote)}</p>
          </section>

          <section className="wfgf-about__section" aria-labelledby={`${titleId}-method`}>
            <h3 id={`${titleId}-method`}>{t(ABOUT.methodTitle)}</h3>
            <MethodDiagram lang={lang} />
            <p className="wfgf-about__muted">{t(ABOUT.methodCaption)}</p>
            <p className="wfgf-about__muted">{t(ABOUT.benchmark)}</p>
          </section>

          <section className="wfgf-about__section" aria-labelledby={`${titleId}-verdicts`}>
            <h3 id={`${titleId}-verdicts`}>{t(ABOUT.verdictsTitle)}</h3>
            <dl className="wfgf-about__verdicts">
              {VERDICTS.map((v) => (
                <div key={v} className={`wfgf-about__verdict wfgf-about__verdict--${v}`} data-verdict={v}>
                  <dt>
                    <VerdictIcon verdict={v} size={22} />
                    <span>{t(VERDICT_LABEL[v])}</span>
                  </dt>
                  <dd>{t(VERDICT_DEFINITION[v])}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="wfgf-about__section" aria-labelledby={`${titleId}-rsg`}>
            <h3 id={`${titleId}-rsg`}>{t(ABOUT.rsgTitle)}</h3>
            <div className="wfgf-about__rsg">
              {[ABOUT.rsgSet, ABOUT.rsgGo].map((s, i) => (
                <div key={i} className={`wfgf-about__rsg-item wfgf-about__rsg-item--${i === 0 ? 'set' : 'go'}`}>
                  <span className="wfgf-about__rsg-ring" aria-hidden="true">
                    {i === 0 ? '8h' : '5h'}
                  </span>
                  <div>
                    <strong>{t(s.label)}</strong>
                    <span>{t(s.text)}</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="wfgf-about__muted">{t(ABOUT.rsgNote)}</p>
          </section>

          <section className="wfgf-about__section" aria-labelledby={`${titleId}-limits`}>
            <h3 id={`${titleId}-limits`}>{t(ABOUT.limitsTitle)}</h3>
            <ul className="wfgf-about__limits">
              {LIMITATIONS.map((l) => (
                <li key={l.id} data-limit={l.id}>
                  {t(l.text)}
                </li>
              ))}
            </ul>
          </section>

          <section className="wfgf-about__section" aria-labelledby={`${titleId}-sources`}>
            <h3 id={`${titleId}-sources`}>{t(ABOUT.sourcesTitle)}</h3>
            <ul className="wfgf-about__sources">
              {SOURCES.map((s, i) => (
                <li key={i}>
                  <div className="wfgf-about__source-head">
                    <strong>{t(s.what)}</strong>
                    <span className="wfgf-about__licence">{t(s.licence)}</span>
                  </div>
                  <p>{t(s.detail)}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="wfgf-about__section" aria-labelledby={`${titleId}-versions`}>
            <h3 id={`${titleId}-versions`}>{t(ABOUT.versionsTitle)}</h3>
            <dl className="wfgf-about__versions">
              <div>
                <dt>{t(ABOUT.vCheckpoint)}</dt>
                <dd className="wfgf-about__mono">{FIXED_IDENTITY.checkpoint}</dd>
              </div>
              <div>
                <dt>{t(ABOUT.vPackage)}</dt>
                <dd>
                  {FIXED_IDENTITY.packageName} {FIXED_IDENTITY.packageVersion}
                </dd>
              </div>
              <div>
                <dt>{t(ABOUT.vKit)}</dt>
                <dd>kit {FIXED_IDENTITY.kit}</dd>
              </div>
              <div>
                <dt>{t(ABOUT.vArm)}</dt>
                <dd>RDA_CAND</dd>
              </div>
              <div>
                <dt>{t(ABOUT.vApi)}</dt>
                <dd>{apiVersion ? `v${apiVersion.replace(/^v/, '')}` : <span className="wfgf-about__muted-inline">{t(ABOUT.vApiUnknown)}</span>}</dd>
              </div>
            </dl>
          </section>
        </div>

        <footer className="wfgf-about__foot wfgf-footer">{t(FOOTER_APP)}</footer>
      </div>
    </div>
  );
  return createPortal(panel, document.body);
}

export default AboutPanel;
