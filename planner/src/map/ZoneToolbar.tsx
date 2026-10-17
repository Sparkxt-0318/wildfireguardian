/**
 * Map toolbar of the spread-zone editor (drawn-zone mode only): pick the zone (5시간 / 8시간 구역),
 * draw, close / cancel, undo, clear the zone, reset. Keyboard shortcuts are listed in the hint
 * line; every action is also a focusable button. Notices are announced in a polite live region.
 */
import { useEffect, useMemo, useState } from 'react';
import type { Map as MLMap } from 'maplibre-gl';
import { hasAnyZone, zoneSummary, type ZoneKey } from '../domain/zones';
import { useT } from '../i18n';
import { useZoneIssues } from '../state/selectors';
import { useStore } from '../state/store';
import * as za from '../state/zoneActions';
import { pluralKey } from '../components/format';

const NOTICE_MS = 8000;

function Swatch({ zone }: { zone: ZoneKey }) {
  return <span className={`zone-swatch ${zone === 'h5' ? 'z5' : 'z8'}`} aria-hidden="true" />;
}

export function ZoneToolbar({ map }: { map: MLMap | null }) {
  const t = useT();
  const zones = useStore((s) => s.drawn.zones);
  const edit = useStore((s) => s.drawn.edit);
  const history = useStore((s) => s.drawn.history.length);
  const noticeState = useStore((s) => s.drawn.notice);
  const issues = useZoneIssues();
  const active = edit.active;
  const summary = useMemo(() => zoneSummary(zones[active]), [zones, active]);
  const activeIssues = issues.filter((i) => i.zone === active);
  const codes = [...new Set(activeIssues.map((i) => i.code))];
  const focusMap = () => map?.getCanvas().focus();
  // notices stay visible for 8 s (the live region announces them once)
  const [, tick] = useState(0);
  useEffect(() => {
    if (!noticeState) return;
    const left = noticeState.at + NOTICE_MS - Date.now();
    if (left <= 0) return;
    const id = setTimeout(() => tick((n) => n + 1), left + 50);
    return () => clearTimeout(id);
  }, [noticeState]);
  const noticeText = noticeState ? t(noticeState.key, noticeState.vars) : '';
  const noticeVisible = Boolean(noticeState && Date.now() - noticeState.at < NOTICE_MS);

  return (
    <div className="map-overlay zone-toolbar" role="region" aria-label={t('zones.toolbar.title')} data-testid="zone-toolbar">
      <div className="zt-head">
        <span className="zt-title">{t('zones.toolbar.title')}</span>
        <span className="tag outline">{t('zones.assumed')}</span>
      </div>
      <div className="zt-seg" role="group" aria-label={t('zones.pick')}>
        {(['h5', 'h8'] as ZoneKey[]).map((k) => {
          const n = zones[k].polygons.length;
          return (
            <button key={k} type="button" aria-pressed={active === k} onClick={() => za.setActiveZone(k)} data-testid={`zone-pick-${k}`}>
              <Swatch zone={k} />
              <span>{t(`zones.${k}`)}</span>
              <span className="zt-count tnum">{n ? zoneSummary(zones[k]).vertices : '—'}</span>
            </button>
          );
        })}
      </div>
      <div className="zt-actions">
        {edit.drawing ? (
          <>
            <button type="button" className="btn btn-ink" onClick={() => za.closeDrawing()} disabled={edit.draft.length < 3} data-testid="zone-close" title="Enter">
              {t('zones.close')}
            </button>
            <button type="button" className="btn" onClick={() => za.cancelDrawing()} data-testid="zone-cancel" title="Esc">
              {t('zones.cancel')}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => {
                if (!map) return;
                const c = map.getCenter();
                za.addDraftVertex([c.lng, c.lat]);
              }}
              title="Space"
            >
              {t('zones.addCenter')}
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-ink"
              onClick={() => {
                za.startDrawing();
                focusMap();
              }}
              data-testid="zone-draw"
            >
              {t('zones.draw')}
            </button>
            <button type="button" className="btn" onClick={() => za.undo()} disabled={history === 0} title="Ctrl+Z" data-testid="zone-undo">
              {t('zones.undo')}
            </button>
            <button type="button" className="btn" onClick={() => za.clearActiveZone()} disabled={!zones[active].polygons.length} data-testid="zone-clear">
              {t('zones.clear')}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => za.resetZones()} disabled={!hasAnyZone(zones)} data-testid="zone-reset">
              {t('zones.reset')}
            </button>
          </>
        )}
      </div>
      <div className="zt-status tnum">
        {edit.drawing ? (
          <span>{t(pluralKey('zones.drawingStatus', edit.draft.length), { zone: t(`zones.${active}`), n: edit.draft.length })}</span>
        ) : summary.polygons ? (
          <span>{t(pluralKey('zones.status', summary.polygons), { p: summary.polygons, v: summary.vertices, a: summary.areaKm2.toFixed(1) })}</span>
        ) : (
          <span className="muted">{t('zones.status.empty', { zone: t(`zones.${active}`) })}</span>
        )}
      </div>
      {codes.length && !edit.drawing ? (
        <ul className="zt-issues">
          {codes.map((c) => (
            <li key={c} className={activeIssues.find((i) => i.code === c)?.severity === 'error' ? 'err' : 'warn'}>
              {t(`zones.issue.${c}`)}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="zt-hint">{edit.drawing ? t('zones.hint.draw') : t('zones.hint.edit')}</p>
      <div className="sr-only" role="status" aria-live="polite">
        {noticeText}
      </div>
      {noticeText && noticeVisible ? (
        <p className="zt-notice" key={noticeState?.at}>
          {noticeText}
        </p>
      ) : null}
    </div>
  );
}

/** Crosshair at the map centre while drawing (Space adds a vertex there). */
export function DrawCrosshair() {
  const drawing = useStore((s) => s.drawn.edit.drawing);
  if (!drawing) return null;
  return <div className="draw-crosshair" aria-hidden="true" />;
}
