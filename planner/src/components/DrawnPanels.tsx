/**
 * Drawn spread-zone UI pieces (사용자 입력 확산 구역, 가정):
 *   - DrawnSettings: left-panel fire-input controls (기준 기록 시각, 구역 예보 발표 시각, 보수적 조기 점화 여유);
 *   - DrawnStrip: left-panel status / progress of the drawn batch;
 *   - RsgTagView: Ready-Set-Go tag (planner-side point-in-polygon only);
 *   - DrawnZonesTab: right-panel zone summaries, recorded-footprint presets, "구역 안·주변 마을 계산";
 *   - AssumptionsBlock: the API's `assumptions` object VERBATIM + provenance.approximation;
 *   - SubmittedZonesCard: what was sent with the results on screen.
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { flattenAssumptions, mockAssumptionText } from '../domain/assumptions';
import { kstDate, kstClock, kstDateTime } from '../domain/clock';
import { defaultPresetTimes, issuedAtFor, isNested, MAX_ISSUE_OFFSET_H, MAX_MARGIN_MIN, NEAR_ZONE_M, zoneSummary, type RsgTag, type ZoneKey } from '../domain/zones';
import { CONFIG } from '../config/env';
import { useLang, useT } from '../i18n';
import { cancelBatch, drawnBatchPreview, prepareDrawnBatch, startDrawnBatch } from '../state/controller';
import { useDrawnFireKey, useRecordedInputTimes, useZoneIssues } from '../state/selectors';
import { getState, useStore, type DrawnDispatchInfo, type SubmittedZones } from '../state/store';
import { applyPreset, setDrawnSettings } from '../state/zoneActions';
import { drawnReadiness } from '../state/selectors';
import { errorText } from './format';
import { UnresolvedIcon } from './Icons';
import { MockBadge } from './TopBar';

/** "10:00" (same KST day as the base) or "03-23 22:00" (another day). */
function issuedLabel(iso: string, base: string): string {
  return kstDate(iso) === kstDate(base) ? kstClock(iso, 0) : `${kstDate(iso).slice(5)} ${kstClock(iso, 0)}`;
}

// ---------------------------------------------------------------- left: settings

export function DrawnSettings() {
  const t = useT();
  const times = useRecordedInputTimes();
  const settings = useStore((s) => s.drawn.settings);
  const it = settings.inputTime;
  const ids = { input: 'ds-input', issued: 'ds-issued', margin: 'ds-margin' };
  return (
    <section className="drawn-settings" aria-label={t('drawn.settings.title')} data-testid="drawn-settings">
      <div className="ds-title">
        <span>{t('drawn.settings.title')}</span>
      </div>
      <div className="ds-grid">
        <label htmlFor={ids.input}>{t('drawn.settings.inputTime')}</label>
        <select
          id={ids.input}
          className="select select-s"
          value={it ?? ''}
          disabled={!times.length}
          onChange={(e) => setDrawnSettings({ inputTime: e.target.value || null })}
          title={t('drawn.settings.inputTime.tip')}
          data-testid="ds-input-time"
        >
          {!times.length ? <option value="">{t('drawn.settings.noTimes')}</option> : null}
          {times.map((x) => (
            <option key={x} value={x}>
              {kstDateTime(x)}
            </option>
          ))}
        </select>
        <label htmlFor={ids.issued}>{t('drawn.settings.issued')}</label>
        <select id={ids.issued} className="select select-s" value={settings.issueOffsetH} disabled={!it} onChange={(e) => setDrawnSettings({ issueOffsetH: Number(e.target.value) })} data-testid="ds-issued">
          {Array.from({ length: MAX_ISSUE_OFFSET_H + 1 }, (_, h) => (
            <option key={h} value={h}>
              {it ? (h === 0 ? t('drawn.settings.issuedSame', { time: issuedLabel(it, it) }) : t('drawn.settings.issuedOpt', { h, time: issuedLabel(issuedAtFor(it, h), it) })) : `${h}`}
            </option>
          ))}
        </select>
        <label htmlFor={ids.margin}>{t('drawn.settings.margin')}</label>
        <select id={ids.margin} className="select select-s" value={settings.marginMin} onChange={(e) => setDrawnSettings({ marginMin: Number(e.target.value) })} data-testid="ds-margin">
          {Array.from({ length: MAX_MARGIN_MIN / 10 + 1 }, (_, i) => i * 10).map((m) => (
            <option key={m} value={m}>
              {t('drawn.settings.marginOpt', { m })}
            </option>
          ))}
        </select>
      </div>
      <p className="ds-note">{t('drawn.settings.note')}</p>
    </section>
  );
}

// ---------------------------------------------------------------- left: status strip

export function DrawnStrip() {
  const t = useT();
  const batch = useStore((s) => s.batch);
  const plans = useStore((s) => s.plans);
  const resultsKey = useStore((s) => s.drawn.resultsKey);
  const hasZone = useStore((s) => s.drawn.zones.h5.polygons.length + s.drawn.zones.h8.polygons.length > 0);
  const computed = useMemo(() => Object.values(plans).filter((p) => p.note !== 'not_computed' && p.note !== 'not_checkable' && p.sweep.some((c) => c.attempts.length)).length, [plans]);
  if (batch.state === 'running' || batch.state === 'done' || batch.state === 'error' || batch.state === 'cancelled') {
    const pct = batch.total ? Math.round((batch.done / batch.total) * 100) : 0;
    return (
      <div className="data-strip" data-testid="batch-progress">
        <div className="progress-row">
          <span>{batch.state === 'running' ? t('drawn.strip.running') : batch.state === 'done' ? t('drawn.strip.done') : batch.state === 'error' ? t('batch.error') : t('batch.cancelled')}</span>
          <span>{t('batch.progress', { done: batch.done, total: batch.total })}</span>
        </div>
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={batch.total} aria-valuenow={batch.done}>
          <div style={{ width: `${pct}%` }} />
        </div>
        {batch.state === 'running' ? (
          <div>
            <button type="button" className="btn" onClick={cancelBatch}>
              {t('batch.cancel')}
            </button>
          </div>
        ) : null}
        {batch.error ? <span style={{ color: 'var(--ink)' }}>{errorText(batch.error, t)}</span> : null}
      </div>
    );
  }
  // nothing to report before the first computation (the settings above and the panels say what to do)
  if (hasZone && !(resultsKey && computed)) return null;
  return (
    <div className="data-strip" data-testid="drawn-strip">
      <span>{!hasZone ? t('drawn.strip.noZone') : t('drawn.strip.computed', { n: computed })}</span>
    </div>
  );
}

// ---------------------------------------------------------------- Ready-Set-Go tag

export function RsgTagView({ tag, full = true }: { tag: RsgTag; full?: boolean }) {
  const t = useT();
  return (
    <span className={`rsg ${tag}`} title={`${t(`rsg.${tag}`)} · ${t('rsg.note')}`} data-testid={`rsg-${tag}`}>
      <span className={`zone-swatch ${tag === 'go' ? 'z5' : 'z8'}`} aria-hidden="true" />
      {full ? t(`rsg.${tag}`) : t(`rsg.${tag}.short`)}
    </span>
  );
}

// ---------------------------------------------------------------- assumptions (verbatim)

/** "근사 — 전문가 검토 필요"; `text` = the API's provenance.approximation when a result carries it. */
export function ApproxWarning({ text, note }: { text?: string | null; note?: string }) {
  const t = useT();
  return (
    <div className="assume-warn" role="note" data-testid="approx-warning">
      <UnresolvedIcon size={14} color="#0B0B0C" style={{ flex: '0 0 auto', marginTop: 1 }} />
      <span className="aw-text">
        <b>{t('assume.approx')}</b>
        {text ? <span className="mono">provenance.approximation = “{text}”</span> : null}
        {note ? <span className="muted">{note}</span> : null}
      </span>
    </div>
  );
}

/**
 * The API's assumptions object shown verbatim (keys and values as sent; numbers via String(n)).
 * With the MOCK the object is {mock: true, evaluated: false, text: …}: its text is shown too.
 */
export function AssumptionsBlock({ assumptions, approximation, mock, source }: { assumptions: Record<string, unknown> | null; approximation: string | null; mock: boolean; source: ReactNode }) {
  const t = useT();
  const lang = useLang();
  const rows = useMemo(() => flattenAssumptions(assumptions), [assumptions]);
  const mockText = mockAssumptionText(assumptions, lang);
  return (
    <section className="assume" data-testid="assumptions">
      <div className="assume-head">
        <span>{t('assume.title')}</span>
        {mock ? <MockBadge /> : null}
      </div>
      {approximation ? <ApproxWarning text={approximation} /> : null}
      {mockText ? (
        <p className="assume-mock" data-testid="assume-mock-text">
          {mockText}
        </p>
      ) : null}
      {assumptions ? (
        <dl className="assume-kv">
          {rows.map((r) =>
            r.kind === 'group' ? (
              <dt key={r.path} className="grp" style={{ paddingLeft: r.depth * 12 }}>
                {r.key}
              </dt>
            ) : (
              <div key={r.path} className={`assume-row${(r.value?.length ?? 0) > 48 ? ' long' : ''}`} style={{ paddingLeft: r.depth * 12 }}>
                <dt className="mono">{r.key}</dt>
                <dd className={`mono v-${r.kind}`}>{r.value}</dd>
              </div>
            ),
          )}
        </dl>
      ) : (
        <p className="small-note">{t('assume.null')}</p>
      )}
      <p className="small-note">
        {t('assume.verbatim')} · {source}
      </p>
    </section>
  );
}

// ---------------------------------------------------------------- submitted zones

export function SubmittedZonesCard({ submitted, horizonS }: { submitted: SubmittedZones; horizonS: number }) {
  const t = useT();
  return (
    <section className="card submitted" data-testid="submitted-zones">
      <div className="section-title">{t('submitted.title')}</div>
      {submitted.zones.map((z) => (
        <div key={z.key} className="sz-zone">
          <span className="sz-head">
            <span className={`zone-swatch ${z.key === 'h5' ? 'z5' : 'z8'}`} aria-hidden="true" />
            <b>{t(`zones.${z.key}`)}</b>
            <span className="mono">arrival_h_max {z.arrivalHMax}</span>
          </span>
          <span className="small-note tnum" style={{ color: 'var(--ink)' }}>
            {t('zones.status', { p: z.polygons, v: z.vertices, a: z.areaKm2.toFixed(1) })}
          </span>
          <span className="small-note">
            {z.presetTime ? t('drawn.zone.source.preset', { time: kstDateTime(z.presetTime) }) : t('drawn.zone.source.drawn')}
            {z.presetTime && z.edited ? ` ${t('drawn.zone.edited')}` : ''}
          </span>
        </div>
      ))}
      <dl className="kv">
        <dt>{t('submitted.issued')}</dt>
        <dd className="tnum">
          {kstDateTime(submitted.issuedAt)}
          <br />
          <span className="mono muted">{submitted.issuedAt}</span>
        </dd>
        <dt>{t('submitted.input')}</dt>
        <dd className="tnum">
          {kstDateTime(submitted.inputTime)}
          <br />
          <span className="mono muted">{submitted.inputTime}</span>
        </dd>
        <dt>{t('submitted.margin')}</dt>
        <dd className="tnum">{t('drawn.settings.marginOpt', { m: submitted.marginMin })}</dd>
        <dt>{t('submitted.burning')}</dt>
        <dd className="mono">{submitted.burningScenarioSetId ?? '—'}</dd>
        <dt>{t('submitted.horizon')}</dt>
        <dd className="tnum">{t('submitted.horizonValue', { m: Math.round(horizonS / 60) })}</dd>
      </dl>
    </section>
  );
}

// ---------------------------------------------------------------- right: zones tab

function ZoneCard({ zone }: { zone: ZoneKey }) {
  const t = useT();
  const z = useStore((s) => s.drawn.zones[zone]);
  const issues = useZoneIssues().filter((i) => i.zone === zone);
  const sum = zoneSummary(z);
  const codes = [...new Set(issues.map((i) => i.code))];
  return (
    <div className="zone-card" data-testid={`zone-card-${zone}`}>
      <div className="zc-head">
        <span className={`zone-swatch ${zone === 'h5' ? 'z5' : 'z8'}`} aria-hidden="true" />
        <span className="zc-name">{t(`zones.${zone}`)}</span>
        <span className="mono muted">arrival_h_max {z.arrivalHMax}</span>
      </div>
      {sum.polygons ? (
        <>
          <span className="small-note tnum" style={{ color: 'var(--ink)' }}>
            {t('zones.status', { p: sum.polygons, v: sum.vertices, a: sum.areaKm2.toFixed(1) })}
            {sum.holes ? ` · ${t('zones.holes', { n: sum.holes })}` : ''}
          </span>
          <span className="small-note">
            {z.preset ? t('drawn.zone.source.preset', { time: kstDateTime(z.preset.inputTime) }) : t('drawn.zone.source.drawn')}
            {z.preset && z.edited ? ` ${t('drawn.zone.edited')}` : ''}
          </span>
          {z.preset ? <span className="small-note tnum">{t('drawn.zone.simplified', { before: z.preset.verticesBefore, after: z.preset.verticesAfter, tol: z.preset.toleranceM })}</span> : null}
        </>
      ) : (
        <span className="small-note">{t('zones.status.empty', { zone: t(`zones.${zone}`) })}</span>
      )}
      {codes.map((c) => (
        <span key={c} className={`zc-issue ${issues.find((i) => i.code === c)?.severity === 'error' ? 'err' : 'warn'}`}>
          {t(`zones.issue.${c}`)}
        </span>
      ))}
    </div>
  );
}

function PresetCard() {
  const t = useT();
  const fp = useStore((s) => s.drawn.footprints);
  const inputTime = useStore((s) => s.drawn.settings.inputTime);
  const items = fp.items;
  const defaults = useMemo(
    () =>
      defaultPresetTimes(
        items.map((f) => f.inputTime),
        inputTime,
      ),
    [items, inputTime],
  );
  const [h5, setH5] = useState<string>('');
  const [h8, setH8] = useState<string>('');
  useEffect(() => {
    setH5(defaults.h5 ?? '');
    setH8(defaults.h8 ?? '');
  }, [defaults.h5, defaults.h8]);
  const [report, setReport] = useState<string | null>(null);
  if (fp.state === 'loading') return <div className="card preset">{t('preset.loading')}</div>;
  const opt = (x: (typeof items)[number]) => t('preset.opt', { time: kstDateTime(x.inputTime), area: x.areaKm2 !== null ? x.areaKm2.toFixed(1) : '—' });
  return (
    <section className="card preset" aria-labelledby="preset-title" data-testid="preset-card">
      <div className="section-title" id="preset-title">
        {t('preset.title')}
      </div>
      <p className="small-note">{t('preset.body')}</p>
      {items.length === 0 ? (
        <span className="small-note">{fp.state === 'error' ? `${t('preset.error')} ${fp.error ?? ''}` : t('preset.empty')}</span>
      ) : (
        <>
          <div className="ds-grid">
            <label htmlFor="preset-h5">{t('preset.for5')}</label>
            <select id="preset-h5" className="select select-s" value={h5} onChange={(e) => setH5(e.target.value)} data-testid="preset-h5">
              <option value="">{t('preset.none')}</option>
              {items.map((x) => (
                <option key={x.inputTime} value={x.inputTime}>
                  {opt(x)}
                </option>
              ))}
            </select>
            <label htmlFor="preset-h8">{t('preset.for8')}</label>
            <select id="preset-h8" className="select select-s" value={h8} onChange={(e) => setH8(e.target.value)} data-testid="preset-h8">
              <option value="">{t('preset.none')}</option>
              {items.map((x) => (
                <option key={x.inputTime} value={x.inputTime}>
                  {opt(x)}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-ink"
              disabled={!h5 && !h8}
              data-testid="preset-apply"
              onClick={() => {
                const r = applyPreset({ h5: items.find((x) => x.inputTime === h5) ?? null, h8: items.find((x) => x.inputTime === h8) ?? null });
                const parts: string[] = [];
                if (r.h5) parts.push(t('preset.reportZone', { zone: t('zones.h5'), before: r.h5.before, after: r.h5.after }));
                if (r.h8) parts.push(t('preset.reportZone', { zone: t('zones.h8'), before: r.h8.before, after: r.h8.after }));
                setReport(parts.join(' · '));
              }}
            >
              {t('preset.apply')}
            </button>
            <span className="small-note">{t('preset.replaceNote')}</span>
          </div>
          {report ? (
            <span className="small-note tnum" role="status" style={{ color: 'var(--ink)' }}>
              {report}
            </span>
          ) : null}
        </>
      )}
    </section>
  );
}

function BatchCard() {
  const t = useT();
  const batch = useStore((s) => s.batch);
  const health = useStore((s) => s.health);
  const zones = useStore((s) => s.drawn.zones);
  const places = useStore((s) => s.places);
  const fireKey = useDrawnFireKey();
  const apiStatus = useStore((s) => s.apiStatus);
  const issues = useZoneIssues();
  const inputTime = useStore((s) => s.drawn.settings.inputTime);
  // recomputed when the zones, settings, places or API status change (reads the store snapshot)
  const readiness = useMemo(() => drawnReadiness(getState()), [zones, fireKey, apiStatus, issues, inputTime]);
  const preview = useMemo(() => (readiness.ok ? drawnBatchPreview() : null), [readiness.ok, fireKey, places, zones]);
  const workers = Math.max(1, health?.workers ?? 1);
  const running = batch.state === 'running';
  return (
    <section className="card batch" aria-labelledby="dbatch-title" data-testid="drawn-batch">
      <div className="section-title" id="dbatch-title">
        {t('drawn.batch.title')}
      </div>
      {!readiness.ok ? (
        <div className="small-note">{readiness.problems.map((p) => t(`drawn.problem.${p}`)).join(' · ')}</div>
      ) : preview ? (
        <span className="small-note" style={{ color: 'var(--ink)' }}>
          {t('drawn.batch.body', { inside: preview.inside, near: preview.near, km: NEAR_ZONE_M / 1000, k: CONFIG.sheltersPerOrigin, plans: preview.plans })}
        </span>
      ) : null}
      {batch.state === 'confirm' && preview ? (
        <div className="notice" data-testid="drawn-batch-confirm">
          <div className="notice-title tnum">{t('drawn.batch.confirm', { n: batch.total })}</div>
          <div className="notice-body tnum">{t('drawn.batch.bound', { w: workers, min: Math.max(1, Math.ceil((batch.total * 30) / workers / 60)) })}</div>
          {health?.mock ? <div className="notice-body">{t('drawn.batch.mockNote')}</div> : null}
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="btn btn-ink" onClick={() => void startDrawnBatch()} disabled={apiStatus !== 'online'} data-testid="drawn-batch-start">
              {t('drawn.batch.start')}
            </button>
            <button type="button" className="btn" onClick={cancelBatch}>
              {t('drawn.batch.cancel')}
            </button>
          </div>
        </div>
      ) : running ? (
        <div className="small-note tnum">{t('batch.progress', { done: batch.done, total: batch.total })}</div>
      ) : (
        <div>
          <button type="button" className="btn btn-block" disabled={!readiness.ok || !preview || preview.checks === 0} onClick={prepareDrawnBatch} data-testid="drawn-batch-prepare">
            {preview && preview.checks === 0 ? t('drawn.batch.none') : t('drawn.batch.prepare')}
          </button>
        </div>
      )}
    </section>
  );
}

function DispatchAssumptions({ list }: { list: DrawnDispatchInfo[] }) {
  const t = useT();
  const first = list[0];
  if (!first) return null;
  return (
    <AssumptionsBlock
      assumptions={first.assumptions}
      approximation={first.provenance?.approximation ?? null}
      mock={first.mock}
      source={
        <span className="mono">
          {t('assume.dispatch', { n: list.length })} · {list.slice(0, 2).map((d) => d.jobId).join(', ')}
          {list.length > 2 ? ` ${t('assume.more', { n: list.length - 2 })}` : ''}
        </span>
      }
    />
  );
}

export function DrawnZonesTab({ horizonS }: { horizonS: number }) {
  const t = useT();
  const zones = useStore((s) => s.drawn.zones);
  const dispatch = useStore((s) => s.drawn.dispatch);
  const submitted = useStore((s) => s.drawn.submitted);
  const nested = zones.h5.polygons.length && zones.h8.polygons.length ? isNested(zones.h5, zones.h8) : null;
  return (
    <div className="rp" data-testid="drawn-zones-tab">
      <div className="rp-head">
        <div className="title">{t('drawn.intro.title')}</div>
        <div className="sub">{t('drawn.intro.body')}</div>
      </div>
      <ApproxWarning note={t('drawn.intro.approxNote')} />
      <div className="section">
        <div className="section-title">{t('drawn.zones.title')}</div>
        <ZoneCard zone="h5" />
        <ZoneCard zone="h8" />
        {nested !== null ? <span className="small-note">{nested ? t('drawn.nested.yes') : t('drawn.nested.no')}</span> : null}
      </div>
      <PresetCard />
      <BatchCard />
      {dispatch.length ? <DispatchAssumptions list={dispatch} /> : null}
      {submitted ? <SubmittedZonesCard submitted={submitted} horizonS={horizonS} /> : null}
    </div>
  );
}
