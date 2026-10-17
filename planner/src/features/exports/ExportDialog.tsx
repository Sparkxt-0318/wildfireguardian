/**
 * Export dialog: GeoJSON / KML of the selected (checked) route and the CSV dispatch list.
 * Files are generated client-side (cache/offline use) and downloaded via Blob + anchor.
 *
 *   <ExportDialog open={open} onClose={close} input={exportInput} lang={lang} />
 */
import { useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { VERDICTS, type Verdict } from '../../domain/types';
import { clockAt } from '../shared/format';
import { IconClose, IconDownload, IconGlobe, IconRoute, IconTable } from '../shared/Icons';
import { FOOTER_APP, MOCK_BADGE_TITLE, pick, VERDICT_LABEL, type Lang } from '../shared/strings';
import { MockBadge, VerdictBadge, VerdictIcon } from '../shared/VerdictIcon';
import { useModal } from '../shared/useModal';
import { downloadText } from './download';
import { dispatchListCSV, exportFileName, isExportable, MIME, placeLabel, routeToGeoJSON, routeToKML, zonesToGeoJSON } from './exports';
import { EXP } from './strings';
import type { ExportInput } from './types';
import '../shared/features.css';
import './exports.css';

export interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  input: ExportInput;
  lang: Lang;
}

function fillVars(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function ExportDialog(props: ExportDialogProps): JSX.Element | null {
  const { open, onClose, input, lang } = props;
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const [withComparison, setWithComparison] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  useModal(ref, open, onClose, { initialFocus: ':self' });
  const t = (s: { ko: string; en: string }) => pick(s, lang);

  const route = input.selectedRoute;
  const routeOk = isExportable(route) && route?.role === 'evacuation_route';
  const comparisonOk = routeOk && isExportable(input.comparisonRoute ?? null) && input.comparisonRoute?.role === 'travel_only_comparison';
  const counts = useMemo(() => {
    const c: Record<Verdict, number> = { checked_route: 0, model_no_route: 0, unresolved: 0 };
    for (const o of input.origins) c[o.plan?.bestVerdict ?? 'unresolved'] += 1;
    return c;
  }, [input.origins]);

  if (!open || typeof document === 'undefined') return null;

  const run = (fn: () => { name: string; mime: string; text: string }) => {
    try {
      const { name, mime, text } = fn();
      downloadText(name, mime, text);
      setStatus({ ok: true, text: fillVars(t(EXP.saved), { name }) });
    } catch (e) {
      setStatus({ ok: false, text: fillVars(t(EXP.error), { msg: e instanceof Error ? e.message : String(e) }) });
    }
  };
  const comparison = withComparison && comparisonOk ? (input.comparisonRoute ?? null) : null;
  const base = { inputTimeIso: input.scenario.inputTimeIso, issuedAtIso: input.scenario.issuedAtIso ?? null };

  const dialog = (
    <div className="wfgf wfgf-export-root" lang={lang}>
      <div className="wfgf-scrim" onClick={onClose} aria-hidden="true" />
      <div ref={ref} className="wfgf-export" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} data-testid="export-dialog">
        <header className="wfgf-export__head">
          <div>
            <h2 id={titleId}>{t(EXP.title)}</h2>
            <p className="wfgf-export__meta">
              <span className="wfgf-fireinput">{input.fireInputLabel}</span>
              {input.mock && <MockBadge lang={lang} title={t(MOCK_BADGE_TITLE)} />}
            </p>
          </div>
          <button type="button" className="wfgf-iconbtn" onClick={onClose} aria-label={t(EXP.close)} title={t(EXP.close)}>
            <IconClose />
          </button>
        </header>

        <div className="wfgf-export__body">
          <section className="wfgf-export__card" aria-labelledby={`${titleId}-route`}>
            <div className="wfgf-export__cardhead">
              <span className="wfgf-export__glyph" aria-hidden="true">
                <IconRoute />
              </span>
              <div>
                <h3 id={`${titleId}-route`}>{t(EXP.routeTitle)}</h3>
                <p className="wfgf-export__desc">{t(EXP.routeDesc)}</p>
              </div>
            </div>
            {route ? (
              <div className="wfgf-export__route" data-exportable={routeOk ? 'true' : 'false'}>
                <div className="wfgf-export__routeline">
                  <strong>{placeLabel(route.origin, lang)}</strong>
                  <span aria-hidden="true">→</span>
                  <strong>{placeLabel(route.shelter, lang)}</strong>
                </div>
                <div className="wfgf-export__ids">
                  {route.origin.sourceTag} → {route.shelter.sourceTag}
                </div>
                <div className="wfgf-export__routefacts">
                  <VerdictBadge verdict={route.verdict} lang={lang} size={15} />
                  {routeOk && (
                    <span className="wfgf-num">
                      {t(EXP.routeFrom)} {clockAt(base, route.departureS)} · {t(EXP.routeArrive)} {clockAt(base, route.arrivalS)}
                    </span>
                  )}
                </div>
                {!routeOk && <p className="wfgf-export__refused" role="note">{t(EXP.routeRefused)}</p>}
              </div>
            ) : input.selectedOrigin ? (
              // an origin is selected but has no checked route: say so, with its verdict
              <div className="wfgf-export__route" data-exportable="false" data-testid="export-route-refused">
                <div className="wfgf-export__routeline">
                  <strong>{placeLabel(input.selectedOrigin.place, lang)}</strong>
                </div>
                <div className="wfgf-export__ids">{input.selectedOrigin.place.sourceTag}</div>
                <div className="wfgf-export__routefacts">
                  <VerdictBadge verdict={input.selectedOrigin.verdict} lang={lang} size={15} />
                </div>
                <p className="wfgf-export__refused" role="note">
                  {input.selectedOrigin.verdict === 'checked_route' ? t(EXP.routeUnavailable) : t(EXP.routeRefused)}
                </p>
              </div>
            ) : (
              <p className="wfgf-export__refused">{t(EXP.routeNone)}</p>
            )}
            {comparisonOk && (
              <label className="wfgf-export__check">
                <input type="checkbox" checked={withComparison} onChange={(e) => setWithComparison(e.target.checked)} />
                <span>{t(EXP.includeComparison)}</span>
              </label>
            )}
            <div className="wfgf-export__buttons">
              <button
                type="button"
                className="wfgf-btn wfgf-btn--primary"
                disabled={!routeOk}
                data-testid="export-geojson"
                onClick={() =>
                  run(() => ({
                    name: exportFileName(input, 'route', 'geojson', route!.origin.id),
                    mime: MIME.geojson,
                    text: JSON.stringify(routeToGeoJSON(input, route, { comparison, lang }), null, 1),
                  }))
                }
              >
                <IconDownload size={18} />
                {t(EXP.geojson)}
              </button>
              <button
                type="button"
                className="wfgf-btn"
                disabled={!routeOk}
                data-testid="export-kml"
                onClick={() =>
                  run(() => ({
                    name: exportFileName(input, 'route', 'kml', route!.origin.id),
                    mime: MIME.kml,
                    text: routeToKML(input, route, { comparison, lang }),
                  }))
                }
              >
                <IconGlobe size={18} />
                {t(EXP.kml)}
              </button>
            </div>
          </section>

          <section className="wfgf-export__card" aria-labelledby={`${titleId}-csv`}>
            <div className="wfgf-export__cardhead">
              <span className="wfgf-export__glyph" aria-hidden="true">
                <IconTable />
              </span>
              <div>
                <h3 id={`${titleId}-csv`}>{t(EXP.csvTitle)}</h3>
                <p className="wfgf-export__desc">{t(EXP.csvDesc)}</p>
              </div>
            </div>
            <div className="wfgf-export__counts">
              <span className="wfgf-num wfgf-export__total">{fillVars(t(EXP.csvCount), { n: input.origins.length })}</span>
              {VERDICTS.map((v) => (
                <span key={v} className="wfgf-export__count" data-verdict={v}>
                  <VerdictIcon verdict={v} size={14} />
                  {t(VERDICT_LABEL[v])} <b className="wfgf-num">{counts[v]}</b>
                </span>
              ))}
            </div>
            <div className="wfgf-export__buttons">
              <button
                type="button"
                className="wfgf-btn wfgf-btn--ink"
                disabled={input.origins.length === 0}
                data-testid="export-csv"
                onClick={() =>
                  run(() => ({ name: exportFileName(input, 'dispatch', 'csv'), mime: MIME.csv, text: dispatchListCSV(input, { lang }) }))
                }
              >
                <IconDownload size={18} />
                {t(EXP.csv)}
              </button>
            </div>
          </section>

          {input.fireInputType === 'spread_zones' && input.zones && input.zones.features.length > 0 ? (
            <section className="wfgf-export__card" aria-labelledby={`${titleId}-zones`} data-testid="export-zones-card">
              <div className="wfgf-export__cardhead">
                <span className="wfgf-export__glyph" aria-hidden="true">
                  <IconGlobe />
                </span>
                <div>
                  <h3 id={`${titleId}-zones`}>{t(EXP.zonesTitle)}</h3>
                  <p className="wfgf-export__desc">{t(EXP.zonesDesc)}</p>
                </div>
              </div>
              <div className="wfgf-export__counts">
                <span className="wfgf-num wfgf-export__total">{fillVars(t(EXP.zonesCount), { n: input.zones.features.length })}</span>
                {input.zones.features.map((f, i) => (
                  <span key={i} className="wfgf-export__count wfgf-num">
                    arrival_h_max {String((f.properties as Record<string, unknown> | null)?.arrival_h_max ?? '—')}
                  </span>
                ))}
              </div>
              <div className="wfgf-export__buttons">
                <button
                  type="button"
                  className="wfgf-btn"
                  data-testid="export-zones"
                  onClick={() =>
                    run(() => ({ name: exportFileName(input, 'zones', 'geojson'), mime: MIME.geojson, text: JSON.stringify(zonesToGeoJSON(input, { lang }), null, 1) }))
                  }
                >
                  <IconDownload size={18} />
                  {t(EXP.zonesGeojson)}
                </button>
              </div>
            </section>
          ) : null}

          <p className="wfgf-export__note">{t(EXP.note)}</p>
          <p className="wfgf-export__note">{t(EXP.apiNote)}</p>
          {status && (
            <p className={`wfgf-export__status${status.ok ? '' : ' wfgf-export__status--err'}`} role="status">
              {status.text}
            </p>
          )}
        </div>
        <footer className="wfgf-export__foot wfgf-footer">{t(FOOTER_APP)}</footer>
      </div>
    </div>
  );
  return createPortal(dialog, document.body);
}

export default ExportDialog;
