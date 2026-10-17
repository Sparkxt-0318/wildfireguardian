import { fireInputBanner } from '../domain/labels';
import { kstDateTime } from '../domain/clock';
import { useLang, useLangStore, useT } from '../i18n';
import { openDialog } from '../state/controller';
import { useCurrentScenarioSet, useMockActive, useRegionEntry } from '../state/selectors';
import { DRAWN_SCENARIO, useStore } from '../state/store';
import { DocumentIcon, ExportIcon, InfoIcon, ProductMark } from './Icons';
import { TestDataChip } from './StatusChip';

export function FireInputBanner() {
  const t = useT();
  const lang = useLang();
  const scenarioId = useStore((s) => s.scenarioId);
  const region = useRegionEntry();
  const set = useCurrentScenarioSet();
  const drawn = scenarioId === DRAWN_SCENARIO;
  const offlineEmpty = useStore((s) => s.apiStatus === 'offline' && s.dataSource !== 'cache');
  const text = fireInputBanner(drawn ? { type: 'spread_zones' } : set ? { type: 'recorded' } : null, region?.fireYear ?? null, lang);
  return (
    <div className={`banner${drawn ? ' assumed' : ''}${offlineEmpty ? ' offline' : ''}`} role="status" aria-live="polite" data-testid="fire-banner">
      <span className="dot" aria-hidden="true" />
      <span className="banner-text" title={text}>{text}</span>
      {offlineEmpty ? <span className="banner-time" data-testid="banner-offline">· {t('banner.offlineNoResult')}</span> : null}
      {!drawn && set ? <span className="banner-time tnum">· {t('banner.inputTime', { time: kstDateTime(set.inputTime) })}</span> : null}
    </div>
  );
}

export function MockBadge() {
  const t = useT();
  const offlineEmpty = useStore((s) => s.apiStatus === 'offline' && s.dataSource !== 'cache');
  if (offlineEmpty)
    return (
      <span className="mock-badge offline" title={t('mock.offlineTooltip')} aria-label={`MOCK — ${t('mock.offlineTooltip')}`} data-testid="mock-badge">
        {t('mock.offlineBadge')}
      </span>
    );
  return (
    <span className="mock-badge" title={t('mock.tooltip')} aria-label={`MOCK — ${t('mock.tooltip')}`} data-testid="mock-badge">
      {t('mock.badge')}
    </span>
  );
}

function ApiStatusLabel() {
  const t = useT();
  const status = useStore((s) => s.apiStatus);
  const health = useStore((s) => s.health);
  const err = useStore((s) => s.apiError);
  const usingCache = useStore((s) => s.dataSource === 'cache');
  let cls = 'offline';
  let text = t('api.checking');
  let title = '';
  if (status === 'online' && health) {
    cls = health.mock ? 'mock' : 'online';
    text = health.mock ? t('api.mock') : t('api.online');
    if (health.status === 'degraded') text += ` · ${t('api.degraded')}`;
    title = t('api.tooltip.online', { version: health.apiVersion, workers: health.workers, queued: health.queued ?? '—' });
    if (health.issues.length) title += `\n${health.issues.join('\n')}`;
  } else if (status === 'offline') {
    text = usingCache ? t('api.offlineCache') : t('api.offline');
    title = t('api.tooltip.offline', { code: err?.code ?? '', message: err?.message ?? '' });
  }
  return (
    <span className={`api-status ${cls}`} title={title} data-testid="api-status">
      <span className="led" aria-hidden="true" />
      {text}
    </span>
  );
}

export function TopBar() {
  const t = useT();
  const lang = useLang();
  const setLang = useLangStore((s) => s.setLang);
  const mock = useMockActive();
  // a cache computed on a non-evaluation host (e.g. a Linux container) is test data, never the booth cache
  const testData = useStore((s) => s.dataSource === 'cache' && s.scenarioId !== DRAWN_SCENARIO && s.cache?.meta.testData === true);
  return (
    <header className="topbar">
      <div className="brand">
        <ProductMark />
        <div className="brand-text">
          <span className="brand-title">{t('app.title')}</span>
          <span className="brand-sub">{t('app.subtitle')}</span>
        </div>
      </div>
      <div className="topbar-mid">
        <FireInputBanner />
        {mock ? <MockBadge /> : null}
        {testData ? <TestDataChip short /> : null}
      </div>
      <div className="topbar-right">
        <ApiStatusLabel />
        <div className="seg" role="group" aria-label={t('top.lang')}>
          <button type="button" aria-pressed={lang === 'ko'} onClick={() => setLang('ko')} lang="ko">
            한국어
          </button>
          <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')} lang="en">
            English
          </button>
        </div>
        <button type="button" className="btn" onClick={() => openDialog('planSheet')}>
          <DocumentIcon size={14} />
          {t('top.planSheet')}
        </button>
        <button type="button" className="btn" onClick={() => openDialog('export')}>
          <ExportIcon size={14} />
          {t('top.export')}
        </button>
        <button type="button" className="btn" onClick={() => openDialog('about')}>
          <InfoIcon size={14} />
          {t('top.about')}
        </button>
      </div>
    </header>
  );
}

export function Footer() {
  const t = useT();
  return (
    <footer className="footer">
      <span className="rule">{t('footer.rule')}</span>
      <span className="spacer" />
      <span>{t('footer.build')}</span>
      <span>{t('footer.attribution')}</span>
    </footer>
  );
}
