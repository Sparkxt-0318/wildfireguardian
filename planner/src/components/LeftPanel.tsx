import { useEffect, useMemo, useRef } from 'react';
import { kstClock, kstDate, kstDateTime } from '../domain/clock';
import { sortByUrgency, summarize } from '../domain/plan';
import type { OriginPlan, Place } from '../domain/types';
import { sortDrawn, type RsgTag } from '../domain/zones';
import { useLang, useT } from '../i18n';
import { cancelBatch, selectOrigin, selectRegion, selectScenario, startBatch } from '../state/controller';
import { useClockBase, useRsgTags, useScenarioPlaces, useScenarioSets } from '../state/selectors';
import { DRAWN_SCENARIO, setState, useStore, type OriginFilter } from '../state/store';
import { DrawnSettings, DrawnStrip, RsgTagView } from './DrawnPanels';
import { batchCounter, categoryLabel, errorText, fmtKstClock, fmtKstStamp, hostLabel, placeName, sourceTag } from './format';
import { OriginGlyph, SearchIcon, VerdictIcon } from './Icons';
import { StatusChip, TestDataChip } from './StatusChip';
import { findCacheEntry } from '../api/cache';

function RegionSelector() {
  const t = useT();
  const lang = useLang();
  const regions = useStore((s) => s.regionIndex);
  const regionId = useStore((s) => s.regionId);
  return (
    <div>
      <div className="field-label">{t('left.region')}</div>
      <div className="region-list" role="group" aria-label={t('left.region')}>
        {[regions.filter((r) => r.demo), regions.filter((r) => !r.demo)].map((group, gi) =>
          group.length ? (
            <div key={gi} className="region-row">
              {group.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className="region-btn"
                  aria-pressed={r.id === regionId}
                  onClick={() => void selectRegion(r.id)}
                  title={`${lang === 'en' ? r.nameEn : r.nameKo}${r.fireYear ? ` · ${r.fireYear}` : ''}${r.eventId ? ` · ${r.eventId}` : ''}`}
                  data-testid={`region-${r.id}`}
                >
                  <span className="name">{lang === 'en' ? r.nameEn : r.nameKo}</span>
                  {r.demo ? <span className="tag">{t('left.demoTag')}</span> : null}
                </button>
              ))}
            </div>
          ) : null,
        )}
      </div>
    </div>
  );
}

function ScenarioSelector() {
  const t = useT();
  const sets = useScenarioSets();
  const scenarioId = useStore((s) => s.scenarioId);
  const regionId = useStore((s) => s.regionId);
  const cacheIndex = useStore((s) => s.cacheIndex);
  const current = sets.find((s) => s.id === scenarioId) ?? null;
  return (
    <div>
      <div className="field-label">{t('left.scenario')}</div>
      <div className="scenario-grid" role="group" aria-label={t('left.scenario')} style={{ gridTemplateColumns: `repeat(${Math.max(1, Math.min(3, sets.length))}, 1fr)` }}>
        {sets.map((s) => {
          const cached = regionId ? findCacheEntry(cacheIndex, regionId, s.id) : null;
          const full = t('scenario.recorded', { time: kstDateTime(s.inputTime), n: s.scenarioIds.length || 4 });
          return (
            <button key={s.id} type="button" className="scenario-btn" aria-pressed={s.id === scenarioId} onClick={() => void selectScenario(s.id)} title={`${full}\n${s.id}`} aria-label={full} data-testid={`scenario-${s.inputTime}`}>
              <span className="d tnum">{kstDate(s.inputTime)}</span>
              <span className="c tnum">{kstClock(s.inputTime, 0)} KST</span>
              {cached ? <span className="cached-dot" title={t('scenario.cached')} aria-label={t('scenario.cached')} /> : null}
            </button>
          );
        })}
      </div>
      {current ? (
        <div className="scenario-caption tnum" data-testid="scenario-caption">
          {t('scenario.recorded', { time: kstDateTime(current.inputTime), n: current.scenarioIds.length || 4 })}
          {regionId && findCacheEntry(cacheIndex, regionId, current.id) ? <span className="tag grey">{t('scenario.cached')}</span> : null}
        </div>
      ) : null}
      <button type="button" className="scenario-btn drawn" aria-pressed={scenarioId === DRAWN_SCENARIO} onClick={() => void selectScenario(DRAWN_SCENARIO)} data-testid="scenario-drawn">
        <span className="radio" aria-hidden="true" />
        <span className="label">{t('scenario.drawn')}</span>
      </button>
    </div>
  );
}

function DataStrip() {
  const t = useT();
  const scenarioId = useStore((s) => s.scenarioId);
  const dataSource = useStore((s) => s.dataSource);
  const dataLoading = useStore((s) => s.dataLoading);
  const dataError = useStore((s) => s.dataError);
  const cache = useStore((s) => s.cache);
  const batch = useStore((s) => s.batch);
  const apiStatus = useStore((s) => s.apiStatus);
  const health = useStore((s) => s.health);
  const plans = useStore((s) => s.plans);
  // MOCK: how many checks matched a recorded execution (the rest computed nothing)
  const mockCounts = useMemo(() => {
    let n = 0;
    let k = 0;
    for (const p of Object.values(plans)) {
      for (const c of p.sweep) {
        for (const a of c.attempts) {
          n += 1;
          if (a.rawStatus !== 'MOCK_NO_RECORDED_RESULT' && a.jobId) k += 1;
        }
      }
    }
    return { n, k };
  }, [plans]);
  if (scenarioId === DRAWN_SCENARIO) return <DrawnStrip />;
  if (dataLoading) return <div className="data-strip">{t('data.loading')}</div>;
  if (dataSource === 'cache' && cache) {
    const host = hostLabel(cache.meta.computeHost, t) ?? cache.meta.clientHost ?? '—';
    return (
      <div className="data-strip" data-testid="data-source">
        <span>{t('data.cacheLabel', { time: fmtKstStamp(cache.meta.createdAt), host })}</span>
        {cache.meta.testData ? <TestDataChip /> : null}
      </div>
    );
  }
  if (batch.state === 'disabled') {
    return (
      <div className="data-strip">
        <div className="notice outline" data-testid="batch-disabled">
          <div className="notice-title">{t('batch.disabled')}</div>
          <div className="notice-body">{t('batch.disabledBody')}</div>
        </div>
      </div>
    );
  }
  if (batch.state === 'confirm') {
    const budget = health?.budgetS ?? 30;
    const workers = Math.max(1, health?.workers ?? 1);
    const minutes = Math.ceil((batch.total * budget) / workers / 60);
    return (
      <div className="data-strip">
        <div className="notice">
          <div className="notice-title">{t('batch.confirmTitle')}</div>
          <div className="notice-body">
            {t('batch.confirmBody', { origins: batch.origins, plans: batch.dispatchPlans, research: batch.researchChecks, checks: batch.total, b: Math.round(budget) })}
          </div>
          <div className="notice-body tnum" data-testid="batch-bound">
            {t('batch.bound', { b: Math.round(budget), w: workers, min: minutes })}
          </div>
          <div className="notice-body">{t('batch.confirmNote')}</div>
          <div>
            <button type="button" className="btn btn-ink" onClick={() => void startBatch()} disabled={apiStatus !== 'online'}>
              {t('batch.start')}
            </button>
          </div>
        </div>
      </div>
    );
  }
  if (batch.state === 'running' || batch.state === 'done' || batch.state === 'error' || batch.state === 'cancelled') {
    const pct = batch.total ? Math.round((batch.done / batch.total) * 100) : 0;
    const rejPct = batch.total ? Math.round(((batch.rejected ?? 0) / batch.total) * 100) : 0;
    const allRejected = batch.done === 0 && (batch.rejected ?? 0) > 0 && batch.state !== 'running';
    const mock = Boolean(health?.mock);
    const doneLabel = (batch.rejected ?? 0) > 0 ? t('batch.doneWithRejects') : mock ? t('data.mockLabel', { n: mockCounts.n, k: mockCounts.k }) : t('data.liveLabel');
    const label =
      batch.state === 'running' ? t('batch.running') : allRejected ? t('batch.allRejected') : batch.state === 'done' ? doneLabel : batch.state === 'error' ? t('batch.error') : t('batch.cancelled');
    return (
      <div className="data-strip" data-testid="batch-progress">
        <div className="progress-row">
          <span>{label}</span>
          <span>{batchCounter(batch, t)}</span>
        </div>
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={batch.total} aria-valuenow={batch.done}>
          <div style={{ width: `${pct}%` }} />
          {rejPct > 0 ? <div className="rejected" style={{ width: `${rejPct}%` }} /> : null}
        </div>
        {batch.state === 'done' && mock && (batch.rejected ?? 0) > 0 ? <span>{t('data.mockLabel', { n: mockCounts.n, k: mockCounts.k })}</span> : null}
        {batch.state === 'running' ? (
          <div>
            <button type="button" className="btn" onClick={cancelBatch}>
              {t('batch.cancel')}
            </button>
          </div>
        ) : null}
        {batch.state === 'error' || batch.state === 'cancelled' || (batch.state === 'done' && batch.error) ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {batch.error ? <span style={{ color: 'var(--ink)' }}>{errorText(batch.error, t)}</span> : null}
            {batch.state !== 'done' ? (
              <div>
                <button type="button" className="btn" onClick={() => void startBatch()} disabled={apiStatus !== 'online'}>
                  {t('batch.retry')}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }
  if (dataError) return <div className="data-strip">{t('data.error', { message: dataError })}</div>;
  if (apiStatus === 'checking') return <div className="data-strip">{t('data.loading')}</div>;
  return (
    <div className="data-strip">
      <div className="notice outline" data-testid="empty-state">
        <div className="notice-title">{t('data.empty')}</div>
      </div>
    </div>
  );
}

function Summary({ plans }: { plans: (OriginPlan | undefined)[] }) {
  const t = useT();
  const c = summarize(plans);
  const items = [
    { v: 'checked_route' as const, n: c.checked_route, color: '#1A9E55' },
    { v: 'model_no_route' as const, n: c.model_no_route, color: '#0B0B0C' },
    { v: 'unresolved' as const, n: c.unresolved, color: '#6E6E73' },
  ];
  return (
    <div className="summary" aria-label={t('left.summary')} data-testid="summary">
      {items.map((i) => (
        <div key={i.v} className="summary-cell">
          <span className="n">{i.n}</span>
          <span className="l">
            <VerdictIcon verdict={i.v} size={12} color={i.color} />
            {t(`verdict.${i.v}`)}
          </span>
        </div>
      ))}
    </div>
  );
}

function glyphKind(p: Place): 'village' | 'facility' | 'not_checkable' | 'research' {
  if (!p.checkable) return 'not_checkable';
  if (p.role === 'research_origin') return 'research';
  return p.vulnerable ? 'facility' : 'village';
}

function OriginRow({ place, plan, selected, inputTime, rsg, index }: { place: Place; plan: OriginPlan | undefined; selected: boolean; inputTime: string | null; rsg: RsgTag | null; index: number }) {
  const t = useT();
  const lang = useLang();
  const ref = useRef<HTMLButtonElement | null>(null);
  // keep the selected origin visible (map clicks and deep links select rows far down the list)
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: 'nearest' });
  }, [selected, index]);
  const it = inputTime;
  const verdict = plan?.bestVerdict ?? 'unresolved';
  let deadline: string;
  if (verdict === 'checked_route' && plan?.latestSafeDepartureS !== null && plan?.latestSafeDepartureS !== undefined) {
    deadline = t('list.deadline', { time: fmtKstClock(it, plan.latestSafeDepartureS) });
  } else if (verdict === 'model_no_route') {
    deadline = t('list.noDeparture');
  } else {
    deadline = t('list.unresolved');
  }
  const caveat = verdict === 'checked_route' && plan && plan.contiguousSafeDepartureS !== plan.latestSafeDepartureS;
  const note = !place.checkable
    ? t('list.notCheckable')
    : plan?.note === 'rejected' && plan.rejectReason
      ? t('list.rejected', { code: plan.rejectReason.code })
      : plan?.note === 'not_computed'
        ? t('list.notComputed')
        : null;
  return (
    <button
      ref={ref}
      type="button"
      role="option"
      aria-selected={selected}
      className="origin-row"
      onClick={() => selectOrigin(place.id)}
      onMouseEnter={() => setState({ hoverOriginId: place.id })}
      onMouseLeave={() => setState({ hoverOriginId: null })}
      data-testid={`origin-${place.id}`}
    >
      <span className="glyph">
        <OriginGlyph kind={glyphKind(place)} />
      </span>
      <span className="name">{placeName(place, t, lang)}</span>
      <span className="right">
        <StatusChip verdict={verdict} label={deadline} />
        {caveat ? <span className="caveat-mark" title={t('headline.caveat', { time: plan!.contiguousSafeDepartureS === null ? t('headline.none') : fmtKstClock(it, plan!.contiguousSafeDepartureS) })}>{t('list.caveatShort')}</span> : null}
      </span>
      <span className="meta">
        <span>{categoryLabel(place, t)}</span>
        {place.vulnerable ? <span className="tag grey">{t('list.vulnerable')}</span> : null}
        <span className="mono" title={sourceTag(place)}>
          {sourceTag(place)}
        </span>
      </span>
      {rsg ? (
        <span className="meta rsg-line">
          <RsgTagView tag={rsg} />
          {note ? <span className="note-inline">{note}</span> : null}
        </span>
      ) : note ? (
        <span className="meta note">{note}</span>
      ) : null}
    </button>
  );
}

const FILTERS: OriginFilter[] = ['all', 'vulnerable', 'needs_alternative'];
const DRAWN_FILTERS: OriginFilter[] = ['all', 'vulnerable', 'needs_alternative', 'in_zone'];

export function LeftPanel() {
  const t = useT();
  const lang = useLang();
  const { origins } = useScenarioPlaces();
  const plans = useStore((s) => s.plans);
  const filter = useStore((s) => s.filter);
  const search = useStore((s) => s.search);
  const selected = useStore((s) => s.selectedOriginId);
  const scenarioId = useStore((s) => s.scenarioId);
  const clock = useClockBase();
  const drawn = scenarioId === DRAWN_SCENARIO;
  const rsg = useRsgTags();

  const sorted = useMemo(() => {
    const items = origins.map((p) => ({ id: p.id, name: placeName(p, (k, v) => t(k, v), lang), vulnerable: p.vulnerable, plan: plans[p.id] ?? null, place: p, rsg: rsg.get(p.id) ?? null }));
    // drawn zones: inside zones first (Go before Set), then the urgency order
    return drawn ? sortDrawn(items) : sortByUrgency(items);
  }, [origins, plans, t, lang, rsg, drawn]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return sorted.filter((i) => {
      if (filter === 'vulnerable' && !i.vulnerable) return false;
      if (filter === 'needs_alternative' && i.plan?.bestVerdict === 'checked_route') return false;
      if (filter === 'in_zone' && (!drawn || !i.rsg)) return false;
      if (!q) return true;
      const p = i.place;
      return [i.name, p.name, p.nameEn, p.id, p.caseId, p.sourceTag].some((s) => s && s.toLowerCase().includes(q));
    });
  }, [sorted, filter, search, drawn]);
  const filters = drawn ? DRAWN_FILTERS : FILTERS;

  return (
    <aside className="panel-left" aria-label={t('left.origins')}>
      <div className="left-head">
        <RegionSelector />
        <ScenarioSelector />
      </div>
      {drawn ? <DrawnSettings /> : null}
      <DataStrip />
      {
        <div className="left-head" style={{ paddingTop: 12 }}>
          <Summary plans={origins.map((o) => plans[o.id])} />
          <div className="chips" role="group" aria-label="filter">
            {filters.map((f) => (
              <button
                key={f}
                type="button"
                className="chip"
                aria-pressed={filter === f}
                onClick={() => setState({ filter: f })}
                title={f === 'needs_alternative' ? t('filter.needs_alternative.tip') : f === 'in_zone' ? t('filter.in_zone.tip') : undefined}
                data-testid={`filter-${f}`}
              >
                {t(`filter.${f}`)}
                {f === 'in_zone' ? <span className="chip-n tnum">{rsg.size}</span> : null}
              </button>
            ))}
          </div>
          <label className="search">
            <SearchIcon size={14} />
            <span className="sr-only">{t('search.placeholder')}</span>
            <input type="search" value={search} placeholder={t('search.placeholder')} onChange={(e) => setState({ search: e.target.value })} />
          </label>
        </div>
      }
      {
        <div className="origin-list" role="listbox" aria-label={t('left.origins')}>
          <div className="list-head">
            <span>{drawn ? t('left.originsDrawn') : t('left.origins')}</span>
            <span className="tnum">{t('list.count', { n: visible.length })}</span>
          </div>
          {visible.map((i, n) => (
            <OriginRow key={i.id} place={i.place} plan={i.plan ?? undefined} selected={i.id === selected} inputTime={clock.inputTime} rsg={i.rsg} index={n} />
          ))}
          {visible.length === 0 ? <div className="list-head">{t('list.empty')}</div> : null}
        </div>
      }
    </aside>
  );
}
