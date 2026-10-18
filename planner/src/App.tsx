import { useEffect, useMemo, useRef } from 'react';
import { AboutPanel } from './features/about/AboutPanel';
import { ExportDialog } from './features/exports/ExportDialog';
import { PlanSheetDialog } from './features/plansheet/PlanSheetDialog';
import { fireInputBanner } from './domain/labels';
import { useLang, useT } from './i18n';
import { Footer, TopBar } from './components/TopBar';
import { LeftPanel } from './components/LeftPanel';
import { RightPanel } from './components/RightPanel';
import { TimeSlider } from './components/TimeSlider';
import { MapView } from './map/MapView';
import { closeDialog, initApp, openDialog } from './state/controller';
import { buildExportInput, buildPlanSheets } from './state/featureData';
import { useMockActive, useRegionEntry } from './state/selectors';
import { DRAWN_SCENARIO, getState, useStore } from './state/store';

function Dialogs() {
  const t = useT();
  const lang = useLang();
  const dialogs = useStore((s) => s.dialogs);
  const health = useStore((s) => s.health);
  const scenarioId = useStore((s) => s.scenarioId);
  const selectedOriginId = useStore((s) => s.selectedOriginId);
  // rebuild the feature inputs only while a dialog is open (they read the whole store)
  const plans = useStore((s) => s.plans);
  const routes = useStore((s) => s.routes);
  const travelOnly = useStore((s) => s.travelOnly);
  const drawn = useStore((s) => s.drawn);
  const region = useRegionEntry();
  const mock = useMockActive();
  const sheets = useMemo(
    () => (dialogs.planSheet ? buildPlanSheets(getState(), t, lang) : []),
    [dialogs.planSheet, plans, routes, travelOnly, scenarioId, drawn.zones, drawn.settings, drawn.submitted, t, lang],
  );
  const exportInput = useMemo(
    () => (dialogs.export ? buildExportInput(getState(), t, lang) : null),
    [dialogs.export, plans, routes, travelOnly, scenarioId, selectedOriginId, drawn.zones, drawn.settings, drawn.submitted, t, lang],
  );
  const label = fireInputBanner(scenarioId === DRAWN_SCENARIO ? { type: 'spread_zones' } : { type: 'recorded' }, region?.fireYear ?? null, lang);
  return (
    <>
      <AboutPanel open={dialogs.about} onClose={() => closeDialog('about')} lang={lang} apiVersion={health?.apiVersion} fireInputLabel={label} mock={mock} />
      <PlanSheetDialog open={dialogs.planSheet} onClose={() => closeDialog('planSheet')} sheets={sheets} lang={lang} initialOriginId={selectedOriginId ?? undefined} />
      {exportInput ? <ExportDialog open={dialogs.export} onClose={() => closeDialog('export')} input={exportInput} lang={lang} /> : dialogs.export ? <NoExport /> : null}
    </>
  );
}

function NoExport() {
  const t = useT();
  return (
    <div className="modal-backdrop" onClick={() => closeDialog('export')}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h2>{t('top.export')}</h2>
        <p className="muted">{t('data.empty')}</p>
        <div>
          <button type="button" className="btn" onClick={() => closeDialog('export')}>
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * html[data-wfg-data-ready] = "true" once the selected scenario's results are loaded (cache read,
 * live batch finished or waiting for confirmation, or the honest empty state) — in drawn-zone mode
 * once the region's zones, settings and recorded footprints are loaded and no drawn batch is
 * running — and "false" while loading. Automation (scripts/export_plan_pdfs.mjs,
 * scripts/screenshots.mjs) waits for it. With ?print=all the plan sheet opens once data is ready.
 */
function useDataReadyFlag() {
  const ready = useStore((s) => {
    if (s.placesState !== 'ready' && s.placesState !== 'error') return false;
    if (s.apiStatus === 'checking' || s.dataLoading || !s.scenarioId) return false;
    if (s.scenarioId === DRAWN_SCENARIO) {
      const fp = s.drawn.footprints;
      return s.drawn.loaded && s.drawn.regionId === s.regionId && fp.regionId === s.regionId && (fp.state === 'ready' || fp.state === 'error') && s.batch.state !== 'running';
    }
    if (s.dataSource === 'cache') return true;
    return s.batch.state !== 'running';
  });
  useEffect(() => {
    document.documentElement.dataset.wfgDataReady = ready ? 'true' : 'false';
  }, [ready]);
  const printOpened = useRef(false);
  useEffect(() => {
    if (!ready || printOpened.current || typeof window === 'undefined') return;
    if (new URLSearchParams(window.location.search).get('print') === 'all') {
      printOpened.current = true;
      openDialog('planSheet');
    }
  }, [ready]);
}

export function App() {
  const lang = useLang();
  useDataReadyFlag();
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  useEffect(() => {
    void initApp();
  }, []);
  return (
    <div className="app">
      <TopBar />
      <div className="main">
        <LeftPanel />
        <main className="center">
          <MapView />
          <TimeSlider />
        </main>
        <RightPanel />
      </div>
      <Footer />
      <Dialogs />
    </div>
  );
}
