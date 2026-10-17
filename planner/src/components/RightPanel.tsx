import { CONFIG } from '../config/env';
import { formatElapsed, formatRelative, kstClock } from '../domain/clock';
import { DEFAULT_DWELL_S, deadlineHeadline, gridOffsets } from '../domain/plan';
import type { Attempt, OriginPlan, Place, RouteDetail, SweepCell } from '../domain/types';
import { secondsSinceIssue } from '../domain/zones';
import { useLang, useT, type TFunction } from '../i18n';
import { useEffect } from 'react';
import { cancelRecompute, ensureRoute, ensureTravelOnly, originCheckCount, recomputeOrigin, selectOffset } from '../state/controller';
import { drawnReadiness, routeById, travelOnlyDetail, useClockBase, useCurrentScenarioSet, useHorizon, useRoute, useRsgTags, useScenarioPlaces, useSelectedPlace, useSelectedPlan, useShownAttempt } from '../state/selectors';
import { DRAWN_SCENARIO, getState, useStore } from '../state/store';
import { setRightTab } from '../state/zoneActions';
import { AssumptionsBlock, DrawnZonesTab, RsgTagView, SubmittedZonesCard } from './DrawnPanels';
import { categoryLabel, computeLabel, errorText, fmtKstStamp, fmtNum, hostLabel, placeName, short, sourceTag, unresolvedReasonText } from './format';
import { ChevronIcon, NoRouteIcon, RefreshIcon, UnresolvedIcon, CheckIcon } from './Icons';
import { StatusChip } from './StatusChip';
import { Timeline } from './Timeline';

function entryLabelKey(p: Place): string {
  if (p.role === 'research_origin' || p.role === 'research_destination') return 'entry.research';
  if (p.role === 'destination') return 'entry.shelter';
  return p.category === 'village' || p.category === 'hamlet' ? 'entry.village' : 'entry.facility';
}

function Header({ place, plan }: { place: Place; plan: OriginPlan | null }) {
  const t = useT();
  const lang = useLang();
  const node = place.entry?.node ?? place.snapNode;
  const dist = place.entry?.distanceM ?? place.snapDistanceM;
  const apiConfirmed = Boolean(plan?.apiSnap && node && plan.apiSnap.nodeId === node);
  const isResearch = place.role === 'research_origin' || place.role === 'research_destination';
  const entry =
    node && isResearch
      ? t(entryLabelKey(place))
      : node && dist !== null
      ? t('entry.distance', { label: t(entryLabelKey(place)), m: Math.round(dist) })
      : plan?.apiSnap
        ? t('snap.api', { m: Math.round(plan.apiSnap.distanceM) })
        : null;
  return (
    <div className="rp-head">
      <div className="title" data-testid="rp-title">
        {placeName(place, t, lang)}
      </div>
      <div className="sub">
        <span>{categoryLabel(place, t)}</span>
        {place.vulnerable ? <span className="tag grey">{t('list.vulnerable')}</span> : null}
        {entry ? (
          <span title={t('entry.tip')} data-testid="entry">
            · {entry}
            {apiConfirmed ? <span className="tag grey" style={{ marginLeft: 6 }}>{t('entry.apiConfirmed')}</span> : null}
          </span>
        ) : null}
      </div>
      {!isResearch && node && dist !== null && dist > 0 ? (
        <span className="small-note entry-gap" data-testid="entry-gap">
          {t('entry.gapNote', { m: Math.round(dist) })}
        </span>
      ) : null}
      <div className="mono">
        {sourceTag(place)}
        {node && place.role === 'origin' ? ` · → ${node}` : ''}
      </div>
    </div>
  );
}

function Headline({ place, plan, inputTime, issuedAt = null, computing = false }: { place: Place; plan: OriginPlan | null; inputTime: string; issuedAt?: string | null; computing?: boolean }) {
  const t = useT();
  const h = deadlineHeadline(plan);
  if (h.kind === 'deadline' && h.deadlineS !== null) {
    return (
      <div className="headline deadline" data-testid="headline">
        <div className="h-main">
          <CheckIcon size={22} color="#1A9E55" />
          {t('headline.deadline', { time: kstClock(inputTime, h.deadlineS) })}
        </div>
        <div className="h-sub">{t('headline.deadlineSub')}</div>
        {issuedAt ? <div className="h-sub tnum">{t('drawn.headline.rel', { rel: formatRelative(secondsSinceIssue(inputTime, issuedAt, h.deadlineS)), m: Math.round(h.deadlineS / 60) })}</div> : null}
        {h.caveat ? (
          <div className="caveat" data-testid="caveat">
            <UnresolvedIcon size={14} color="#6E6E73" style={{ flex: '0 0 auto', marginTop: 1 }} />
            <span>{t('headline.caveat', { time: h.caveat.contiguousS === null ? t('headline.none') : kstClock(inputTime, h.caveat.contiguousS) })}</span>
          </div>
        ) : null}
      </div>
    );
  }
  if (h.kind === 'no_route') {
    return (
      <div className="headline no_route" data-testid="headline">
        <div className="h-main">
          <NoRouteIcon size={20} color="#FFFFFF" />
          {t('headline.noRoute')}
        </div>
        <div className="h-sub">{t('headline.noRouteSub')}</div>
      </div>
    );
  }
  let sub = t('headline.unresolvedSub');
  if (!place.checkable || plan?.note === 'not_checkable') sub = t('list.notCheckable') + ' — ' + t('headline.notCheckableSub');
  else if (plan?.note === 'rejected' && plan.rejectReason) sub = t('headline.rejectedSub', { code: plan.rejectReason.code, message: plan.rejectReason.message });
  else if (plan?.note === 'not_computed') sub = issuedAt ? t('drawn.notComputedSub') : t('headline.notComputedSub');
  else if (plan && plan.mock && plan.sweep.some((c) => c.attempts.some((a) => a.rawStatus === 'MOCK_SPREAD_ZONES_NOT_EVALUATED'))) sub = t('drawn.mockUnresolvedSub');
  else if (plan && plan.mock && plan.sweep.some((c) => c.attempts.some((a) => a.rawStatus === 'MOCK_NO_RECORDED_RESULT'))) sub = t('headline.mockNoRecordSub');
  // departure times whose recorded result IS "no route in the model" (the origin stays unresolved)
  const noRouteAt = plan ? plan.sweep.filter((c) => c.verdict === 'model_no_route').map((c) => kstClock(inputTime, c.offsetS)) : [];
  const showNoRoute = noRouteAt.length > 0 && plan?.bestVerdict === 'unresolved' && !computing;
  if (computing && plan && plan.bestVerdict === 'unresolved') sub = t('headline.computingSub');
  const full = t('headline.unresolved');
  const cut = full.indexOf(' (');
  return (
    <div className="headline unresolved" data-testid="headline" aria-label={full}>
      <div className="h-main">
        <UnresolvedIcon size={20} color="#0B0B0C" />
        <span className="h-text">
          {cut > 0 ? full.slice(0, cut) : full}
          {cut > 0 ? <span className="h-warn">{full.slice(cut + 1)}</span> : null}
        </span>
      </div>
      {showNoRoute ? (
        <div className="h-noroute" data-testid="headline-noroute">
          <NoRouteIcon size={14} color="#FFFFFF" style={{ flex: '0 0 auto' }} />
          <span>{t('headline.recordedNoRoute', { times: noRouteAt.join(', ') })}</span>
        </div>
      ) : null}
      <div className="h-sub">{sub}</div>
    </div>
  );
}

function ShelterCard({ route, attemptDest, departS, arrivalS, inputTime, places, loading }: { route: RouteDetail | null; attemptDest: string; departS: number; arrivalS: number | null; inputTime: string; places: Map<string, Place>; loading: boolean }) {
  const t = useT();
  const lang = useLang();
  const dest = places.get(attemptDest);
  const arr = route?.arrivalS ?? arrivalS;
  return (
    <div className="card" data-testid="shelter-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>{dest ? placeName(dest, t, lang) : attemptDest}</span>
        <span className="small-note">{dest ? categoryLabel(dest, t) : ''}</span>
      </div>
      {dest ? <span className="mono muted">{sourceTag(dest)}</span> : null}
      <div className="arrive">
        <span className="t">{arr !== null ? t('shelter.arrival', { time: kstClock(inputTime, arr, { seconds: true }) }) : '—'}</span>
        {arr !== null ? <span className="e">{formatElapsed(arr - departS, lang)}</span> : null}
      </div>
      <span className="small-note tnum">
        {t('shelter.depart', { time: kstClock(inputTime, departS) })} · {t('shelter.dwell', { s: route?.dwellS ?? DEFAULT_DWELL_S })}
        {route?.lengthM ? ` · ${t('shelter.length', { km: (route.lengthM / 1000).toFixed(1), n: route.segmentCount ?? '—' })}` : route?.segmentCount ? ` · ${t('shelter.legs', { n: route.segmentCount })}` : ''}
      </span>
      {!route ? <span className="small-note">{loading ? t('shelter.loading') : t('shelter.unavailable')}</span> : null}
    </div>
  );
}

function ExposureTable({ route, t }: { route: RouteDetail; t: TFunction }) {
  if (!route.exposure.length) return null;
  const basis = [...new Set(route.exposure.map((e) => e.basis).filter(Boolean))] as string[];
  return (
    <div className="section" data-testid="exposure">
      <div className="section-title">{t('exposure.title')}</div>
      <table className="exp">
        <thead>
          <tr>
            <th scope="col" />
            <th scope="col">{t('exposure.peak')} kW/m²</th>
            <th scope="col">{t('exposure.dose')} kJ/m²</th>
            <th scope="col">{t('exposure.contact')}</th>
          </tr>
        </thead>
        <tbody>
          {route.exposure.map((e) => (
            <tr key={e.scenarioId} title={e.scenarioId}>
              <td>{t('exposure.member', { n: e.member })}</td>
              <td title={`${e.peakKwM2}${e.peakUpperKwM2 !== null ? ` ≤ ${e.peakUpperKwM2}` : ''}`}>
                {fmtNum(e.peakKwM2, 3)}
                {e.peakUpperKwM2 !== null && fmtNum(e.peakUpperKwM2, 3) !== fmtNum(e.peakKwM2, 3) ? <span className="muted"> ≤ {fmtNum(e.peakUpperKwM2, 3)}</span> : null}
              </td>
              <td title={`${e.doseKjM2}${e.doseUpperKjM2 !== null ? ` ≤ ${e.doseUpperKjM2}` : ''}`}>
                {fmtNum(e.doseKjM2, 2)}
                {e.doseUpperKjM2 !== null && fmtNum(e.doseUpperKjM2, 2) !== fmtNum(e.doseKjM2, 2) ? <span className="muted"> ≤ {fmtNum(e.doseUpperKjM2, 2)}</span> : null}
              </td>
              <td style={{ fontWeight: e.contact ? 700 : 400 }}>{e.contact ? t('exposure.contactYes') : t('exposure.contactNo')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {route.limits ? (
        <span className="small-note tnum">
          {t('exposure.limits', { peak: fmtNum(route.limits.peakKwM2, 0), dose: fmtNum(route.limits.doseKjM2, route.limits.doseKjM2 % 1 ? 2 : 0) })}
          {route.limits.incurredDoseKjM2 ? ` · ${t('exposure.incurred', { dose: fmtNum(route.limits.incurredDoseKjM2, 1) })}` : ''}
        </span>
      ) : null}
      {basis.length ? (
        <span className="small-note">
          {t('exposure.basis')}: {basis.map((b) => (t(`exposure.basis.${b}`) !== `exposure.basis.${b}` ? `${t(`exposure.basis.${b}`)} (${b})` : b)).join(', ')}
          {route.exposure.some((e) => e.peakUpperKwM2 !== null) ? ` · ≤ ${t('exposure.upper')}` : ''}
        </span>
      ) : null}
    </div>
  );
}

function TravelOnly({ originId, inputTime, places, hasBest, shownOffsetS }: { originId: string; inputTime: string; places: Map<string, Place>; hasBest: boolean; shownOffsetS: number | null }) {
  const t = useT();
  const lang = useLang();
  const st = useStore((s) => s.travelOnly[originId]);
  const apiOnline = useStore((s) => s.apiStatus === 'online');
  // only the comparison of the origin's current best checked attempt (never a late one of another run)
  const d = useStore((s) => travelOnlyDetail(s, originId));
  return (
    <div className="compare" data-testid="travel-only">
      <div className="c-head">
        <span className="lg-line dashed" aria-hidden="true" />
        {t('travel.title')}
      </div>
      <div className="c-note">{t('travel.note')}</div>
      {d ? (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontWeight: 700, fontSize: 13 }}>
              {d.verdict === 'checked_route' ? t('travel.found') : d.verdict === 'model_no_route' ? t('travel.notFound') : t('travel.unresolved')}
              <span className="small-note" style={{ marginLeft: 6, fontWeight: 500 }}>
                {t('travel.policyTag')}
              </span>
            </span>
            {d.arrivalS !== null && d.departOffsetS !== null ? (
              <span className="small-note tnum">
                {t('travel.forDeparture', { time: kstClock(inputTime, d.departOffsetS), shelter: (() => {
                  const dest = [...places.values()].find((p) => p.snapNode && d.snap && p.snapNode === d.snap.destination.nodeId && (p.role === 'destination' || p.role === 'research_destination'));
                  return dest ? placeName(dest, t, lang) : d.snap?.destination.nodeId ?? '—';
                })() })}{' '}
                · {t('travel.arrival', { time: kstClock(inputTime, d.arrivalS, { seconds: true }), elapsed: formatElapsed(d.arrivalS - d.departOffsetS, lang) })}
              </span>
            ) : null}
            {d.verdict === 'unresolved' ? <span className="small-note">{unresolvedReasonText(d.reasonCode, d.rawStatus, t)}</span> : null}
            {d.coordinates && d.departOffsetS !== null && shownOffsetS !== d.departOffsetS ? (
              <span className="small-note" data-testid="travel-map-note">
                {t('travel.mapOnlyWith', { time: kstClock(inputTime, d.departOffsetS) })}
              </span>
            ) : null}
          </div>
          {d.exposure.length ? (
            <div>
              <div className="small-note" style={{ marginBottom: 4 }}>{t('travel.contact')}</div>
              <div className="flag-row">
                {d.exposure.map((e) => (
                  <span key={e.scenarioId} className={`flag${e.contact ? ' on' : ''}`} title={`${e.scenarioId} · peak ${fmtNum(e.peakKwM2, 3)} kW/m² · dose ${fmtNum(e.doseKjM2, 2)} kJ/m²`}>
                    {t('travel.flagContact', { n: e.member, state: e.contact ? t('exposure.contactYes') : t('exposure.contactNo') })}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {d.fullPolicy ? (
            <div className="fp">
              <div className="fp-head">
                <span className="small-note">{t('travel.fullPolicy')}</span>
                <span className={`flag${d.fullPolicy.pass === false ? ' on' : ''}`}>
                  {d.fullPolicy.pass === true ? t('travel.fullPass') : d.fullPolicy.pass === false ? t('travel.fullFail') : t('travel.fullUnknown')}
                </span>
                {d.fullPolicy.components.length ? <span className="small-note" title={d.fullPolicy.components.join(', ')}>{d.fullPolicy.components.map((c) => { const l = t(`travel.comp.${c}`); return l === `travel.comp.${c}` ? c : l; }).join(', ')}</span> : null}
              </div>
              {Object.entries(d.fullPolicy.details)
                .filter(([k]) => /status$/.test(k))
                .map(([k, v]) => {
                  const label = t(`travel.detail.${k}`);
                  return (
                    <span key={k} className="small-note">
                      {label !== `travel.detail.${k}` ? `${label}: ` : `${k}: `}
                      <StatusToken v={v} />
                    </span>
                  );
                })}
            </div>
          ) : null}
          <span className="small-note">{computeLabel(d.computeS, d.provenance?.host, t)} · {st?.source === 'cache' ? t('prov.cache') : 'API'}</span>
        </>
      ) : st?.state === 'loading' ? (
        <span className="small-note">{t('travel.loading')}</span>
      ) : st?.state === 'error' ? (
        <span className="small-note">{errorText(st.error, t)}</span>
      ) : !hasBest ? (
        <span className="small-note">{t('travel.none')}</span>
      ) : apiOnline ? (
        <div>
          <button type="button" className="btn" onClick={() => void ensureTravelOnly(originId, true)}>
            {t('travel.request')}
          </button>
        </div>
      ) : (
        <span className="small-note">{t('shelter.unavailable')}</span>
      )}
    </div>
  );
}

function FragmentKV({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="mono">{k}</dt>
      <dd className="mono">{v}</dd>
    </>
  );
}

function Windows({ plan, inputTime }: { plan: OriginPlan; inputTime: string }) {
  const t = useT();
  return (
    <div className="section">
      <div className="section-title">{t('windows.title')}</div>
      <div className="win-list">
        {plan.windows.map((w) => (
          <div key={w.fromS} className="w">
            <span className="range">{w.fromS === w.toS ? kstClock(inputTime, w.fromS) : t('windows.range', { from: kstClock(inputTime, w.fromS), to: kstClock(inputTime, w.toS) })}</span>
            <StatusChip verdict={w.skipped ? 'window' : w.verdict} />
          </div>
        ))}
      </div>
    </div>
  );
}

/** "Recorded refusal scope: {…}" → prefix text + parsed JSON (shown collapsed); null when not JSON. */
function splitJsonNote(n: string): { head: string; json: unknown } | null {
  const i = n.indexOf('{');
  if (i < 0 || !n.trimEnd().endsWith('}')) return null;
  try {
    return { head: n.slice(0, i).trim(), json: JSON.parse(n.slice(i)) };
  } catch {
    return null;
  }
}

/**
 * The API's raw reason (English, verbatim) beside the raw status: marked lang="en" with the
 * "(API 원문, 영어)" hint; JSON in it is collapsed under "원문 JSON 보기" (whole text kept there).
 */
function RawReason({ text }: { text: string }) {
  const t = useT();
  const lang = useLang();
  const j = splitJsonNote(text);
  const brace = text.indexOf('{');
  const head = j ? j.head : brace >= 0 ? text.slice(0, brace).trim() : text;
  return (
    <span className="raw-reason" data-testid="raw-reason">
      {' · '}
      <span lang="en">{head}</span> <span lang={lang} className="small-note">{t('prov.notesHint')}</span>
      {j || brace >= 0 ? (
        <details className="note-json">
          <summary lang={lang}>{t('prov.rawJson')}</summary>
          <pre className="mono" lang="en">{j ? JSON.stringify(j.json, null, 2) : text}</pre>
        </details>
      ) : null}
    </span>
  );
}

/** Comparison status token (e.g. CLEAR, DEFINITE_CONTACT): a label in the UI language, the token kept small. */
function StatusToken({ v }: { v: unknown }) {
  const t = useT();
  const raw = String(v);
  const key = `travel.status.${raw}`;
  const label = t(key);
  if (label === key) return <span className="mono" lang="en">{raw}</span>;
  return (
    <span title={raw}>{label}</span>
  );
}

function NoteItem({ n }: { n: string }) {
  const t = useT();
  const lang = useLang();
  const j = splitJsonNote(n);
  if (!j) return <li>{n}</li>;
  return (
    <li>
      {j.head}
      <details className="note-json">
        <summary lang={lang}>{t('prov.rawJson')}</summary>
        <pre className="mono">{JSON.stringify(j.json, null, 2)}</pre>
      </details>
    </li>
  );
}

function Provenance({ route, plan, recheckOf = null }: { route: RouteDetail | null; plan: OriginPlan; recheckOf?: string | null }) {
  const t = useT();
  const cache = useStore((s) => s.cache);
  const health = useStore((s) => s.health);
  const p = route?.provenance ?? null;
  const hashes = p ? Object.entries(p.inputHashes) : [];
  return (
    <details className="prov" open data-testid="provenance">
      <summary>
        <ChevronIcon size={12} />
        {t('prov.title')}
      </summary>
      <dl className="kv" style={{ marginTop: 8 }}>
        <dt>{t('prov.checkpoint')}</dt>
        <dd className="mono" title={p?.checkpoint ?? health?.checkpoint ?? ''}>{short(p?.checkpoint ?? health?.checkpoint ?? cache?.meta.health?.checkpoint ?? null, 16)}</dd>
        <dt>{t('prov.package')}</dt>
        <dd className="mono">
          {p ? `${p.packageName ?? 'wfg_latest'} ${p.packageVersion ?? ''} · kit ${p.kit ?? ''}` : health ? `wfg_latest ${health.packageVersion} · kit ${health.kit}` : '—'}
          {p?.apiVersion ? ` · API ${p.apiVersion}` : ''}
        </dd>
        <dt>{t('prov.graph')}</dt>
        <dd className="mono">{p?.graphId ?? '—'}</dd>
        <dt>{t('prov.scenarioSet')}</dt>
        <dd className="mono">{p?.scenarioSetId ?? '—'}</dd>
        <dt>{t('prov.commit')}</dt>
        <dd className="mono">
          {short(p?.gitCommit ?? null, 12)}
          {p?.gitDirty ? ' (dirty)' : ''}
        </dd>
        {hashes.slice(0, 3).map(([k, v]) => (
          <FragmentKV key={k} k={`${t('prov.inputHash')} · ${k}`} v={short(v, 12)} />
        ))}
        {route ? (
          <>
            <dt>{t('prov.policy')}</dt>
            <dd className="mono">
              {route.policy}
              {p?.evaluatedConfiguration !== null && p?.evaluatedConfiguration !== undefined ? ` · ${t('prov.evaluated')} ${p.evaluatedConfiguration ? t('prov.yes') : t('prov.no')}` : ''}
            </dd>
            {p?.recordedMissionMatch ? (
              <>
                <dt>{t('prov.match')}</dt>
                <dd className="mono">{p.recordedMissionMatch}</dd>
              </>
            ) : null}
            <dt>{t('prov.raw')}</dt>
            <dd className="mono">
              {route.rawStatus ?? '—'}
              {route.rawReason ? <RawReason text={route.rawReason} /> : null}
            </dd>
            <dt>{t('prov.job')}</dt>
            <dd className="mono">{route.jobId}</dd>
            {recheckOf ? (
              <>
                <dt>{t('prov.recheck')}</dt>
                <dd className="mono" data-testid="recheck-of">
                  {t('recheck.note', { id: recheckOf })}
                </dd>
              </>
            ) : null}
          </>
        ) : null}
        <dt>{t('prov.source')}</dt>
        <dd className="mono">
          {plan.source === 'cache' && cache ? `${cache.meta.entry.path} · ${fmtKstStamp(cache.meta.createdAt)}` : 'API'}
        </dd>
        {plan.source === 'cache' && cache ? (
          <>
            <dt>{t('prov.cacheMode')}</dt>
            <dd className="mono">
              {cache.meta.apiMode}
              {cache.meta.apiBase ? ` · ${cache.meta.apiBase}` : ''}
            </dd>
            <dt>{t('prov.clientHost')}</dt>
            <dd className="mono">{cache.meta.clientHost ?? '—'}</dd>
          </>
        ) : null}
      </dl>
      {route?.notes.length ? (
        <>
          <div className="small-note" style={{ marginTop: 8 }}>
            <b>{t('prov.notes')}</b> <span>{t('prov.notesHint')}</span>
          </div>
          {/* the API's notes stay verbatim (English) and always visible */}
          <ul className="notes" lang="en">
            {route.notes.map((n, i) => (
              <NoteItem key={i} n={n} />
            ))}
          </ul>
        </>
      ) : null}
    </details>
  );
}

function Recompute({ place, drawn = false }: { place: Place; drawn?: boolean }) {
  const t = useT();
  const apiOnline = useStore((s) => s.apiStatus === 'online');
  const mock = useStore((s) => Boolean(s.health?.mock));
  const rc = useStore((s) => (s.recompute && s.recompute.originId === place.id ? s.recompute : null));
  const running = rc?.state === 'running';
  const horizon = useHorizon();
  // re-render on zone / setting changes (drawn readiness and counts read the store)
  useStore((s) => s.drawn.zones);
  useStore((s) => s.drawn.settings);
  const n = originCheckCount(place.id);
  const ready = drawn ? drawnReadiness(getState()) : { ok: true, problems: [] };
  const offsets = gridOffsets(horizon, CONFIG.stepMin).length;
  return (
    <div className="section">
      {running && rc ? (
        <>
          <div className="progress-row" style={{ fontSize: 12 }}>
            <span>{t('recompute.progress', { done: rc.done, total: rc.total })}</span>
            <button type="button" className="btn" onClick={cancelRecompute}>
              {t('recompute.cancel')}
            </button>
          </div>
          <div className="progress">
            <div style={{ width: `${rc.total ? (rc.done / rc.total) * 100 : 0}%` }} />
          </div>
        </>
      ) : (
        <button
          type="button"
          className={`btn btn-block${drawn ? ' btn-ink' : ''}`}
          disabled={!apiOnline || !place.checkable || !ready.ok || n === 0}
          onClick={() => void recomputeOrigin(place.id)}
          data-testid="recompute"
        >
          <RefreshIcon size={14} />
          {drawn ? t('drawn.compute.button') : t('recompute.button')}
        </button>
      )}
      {!place.checkable ? (
        <span className="small-note">{t('recompute.notCheckable')}</span>
      ) : !apiOnline ? (
        <span className="small-note">{t('recompute.offline')}</span>
      ) : drawn && !ready.ok ? (
        <span className="small-note">{ready.problems.map((p) => t(`drawn.problem.${p}`)).join(' · ')}</span>
      ) : drawn && !running ? (
        <span className="small-note tnum">
          {t('drawn.compute.hint', { n, o: offsets, k: offsets ? Math.round(n / offsets) : 0 })}
          {mock ? ` · ${t('drawn.batch.mockNote')}` : ''}
        </span>
      ) : !mock && !running ? (
        <span className="small-note">{t('recompute.realHint', { n })}</span>
      ) : null}
      {rc?.error ? <span className="small-note">{errorText(rc.error, t)}</span> : null}
    </div>
  );
}

/** First attempt with a compute time (earliest offset), e.g. the recorded refusal at 04:00. */
function firstComputed(attempts: Attempt[]): Attempt | null {
  return [...attempts].filter((a) => a.computeS !== null).sort((a, b) => a.offsetS - b.offsetS)[0] ?? null;
}

/** Window text only for "시간창 밖"; a refused request names its code (never the window explanation). */
function skipText(cell: SweepCell, t: TFunction): string {
  if (cell.skipped === 'window_unsatisfiable') return t('timeline.tip.window');
  if (cell.skipped) return t('timeline.tip.rejected', { code: cell.skipped });
  return t('shelter.noRoute');
}

/**
 * Compute time of every departure time that has no checked route (default view of an origin
 * without a checked route): "04:00 출발 · 계산 9.3초 · Apple M5 Pro (기록)".
 */
function ComputeList({ plan, inputTime }: { plan: OriginPlan; inputTime: string }) {
  const t = useT();
  const routes = useStore((s) => s.routes);
  const cache = useStore((s) => s.cache);
  const rows = plan.sweep
    .filter((c) => c.verdict !== 'checked_route')
    .map((c) => ({ c, a: firstComputed(c.attempts) }))
    .filter((x): x is { c: SweepCell; a: Attempt } => x.a !== null);
  if (!rows.length) return null;
  return (
    <div className="section" data-testid="compute-list">
      <div className="section-title">{t('compute.listTitle')}</div>
      {rows.map(({ c, a }) => {
        const host = routeById({ routes, cache }, a.jobId)?.provenance?.host ?? cache?.meta.computeHost ?? null;
        return (
          <span key={c.offsetS} className="small-note tnum">
            <StatusChip verdict={c.skipped === 'window_unsatisfiable' ? 'window' : c.verdict} />{' '}
            {t('compute.at', { time: kstClock(inputTime, c.offsetS), s: a.computeS!.toFixed(1), host: hostLabel(host, t) ?? '—' })}
          </span>
        );
      })}
    </div>
  );
}

/** Detail of the selected origin (recorded scenario or drawn zones). */
function OriginDetail({ place, inputTime, issuedAt, drawn }: { place: Place; inputTime: string; issuedAt: string | null; drawn: boolean }) {
  const t = useT();
  const plan = useSelectedPlan();
  const selectedOffsetS = useStore((s) => s.selectedOffsetS);
  const recompute = useStore((s) => s.recompute);
  const submitted = useStore((s) => s.drawn.submitted);
  const horizon = useHorizon();
  const { byId } = useScenarioPlaces();
  const { cell, attempt } = useShownAttempt();
  const route = useRoute(attempt?.jobId);
  // evidence for a cell without a checked route: the first attempt's check (raw status, provenance);
  // with no cell selected, the earliest check of this origin that has a compute time
  const allAttempts = plan ? plan.sweep.flatMap((c) => c.attempts) : [];
  const evidenceAttempt = attempt
    ? null
    : cell
      ? (cell.attempts.find((a) => a.jobId && a.computeS !== null) ?? cell.attempts.find((a) => a.jobId) ?? null)
      : (firstComputed(allAttempts.filter((a) => a.jobId)) ?? allAttempts.find((a) => a.jobId) ?? null);
  const evidenceJob = evidenceAttempt?.jobId ?? null;
  const evidence = useRoute(evidenceJob);
  const routeError = useStore((s) => (attempt?.jobId ? s.routeErrors[attempt.jobId] : undefined));
  const apiOnline = useStore((s) => s.apiStatus === 'online');
  const rsg = useRsgTags().get(place.id) ?? null;
  const bestJob = plan?.best?.jobId ?? null;
  const placeId = place.id;
  // results can arrive after the selection (live batch / recompute): fetch the shown route and the comparison then
  useEffect(() => {
    if (attempt?.jobId) void ensureRoute(attempt.jobId);
  }, [attempt?.jobId]);
  useEffect(() => {
    if (evidenceJob) void ensureRoute(evidenceJob);
  }, [evidenceJob]);
  useEffect(() => {
    if (placeId && bestJob) void ensureTravelOnly(placeId, false);
  }, [placeId, bestJob]);
  // any check of this origin (drawn mode: its assumptions object)
  const anyJob = drawn ? (attempt?.jobId ?? evidenceJob ?? plan?.sweep.flatMap((c) => c.attempts).find((a) => a.jobId)?.jobId ?? null) : null;
  const anyRoute = useRoute(anyJob);
  useEffect(() => {
    if (anyJob) void ensureRoute(anyJob);
  }, [anyJob]);
  const progress = recompute && recompute.originId === place.id && recompute.state === 'running' ? recompute.cells : null;
  const notComputed = !plan || plan.sweep.every((c) => c.attempts.length === 0);
  const assumptionsRoute = route ?? evidence ?? anyRoute;
  const exposureEl = route && route.verdict === 'checked_route' ? <ExposureTable route={route} t={t} /> : null;
  const cellComputed = cell ? firstComputed(cell.attempts) : null;
  const computeEl =
    attempt || route ? (
      <div className="small-note tnum" data-testid="compute">
        {computeLabel(route?.computeS ?? attempt?.computeS ?? null, route?.provenance?.host ?? null, t)}
        {route?.withinBudget === true ? ` · ${t('compute.budget')}` : route?.withinBudget === false ? ` · ${t('compute.overBudget')}` : ''}
      </div>
    ) : !cell && plan ? (
      <ComputeList plan={plan} inputTime={inputTime} />
    ) : null;
  const recheckOf = attempt?.recheckOf ?? evidenceAttempt?.recheckOf ?? null;
  const assumeEl =
    drawn && assumptionsRoute ? (
      <AssumptionsBlock
        assumptions={assumptionsRoute.assumptions}
        approximation={assumptionsRoute.provenance?.approximation ?? null}
        mock={assumptionsRoute.mock}
        source={<span className="mono">{t('assume.job', { id: assumptionsRoute.jobId })}</span>}
      />
    ) : null;
  const submittedEl = drawn && submitted && !notComputed ? <SubmittedZonesCard submitted={submitted} horizonS={horizon} /> : null;
  const travelEl = plan && !notComputed && (!drawn || plan.best) ? <TravelOnly originId={place.id} inputTime={inputTime} places={byId} hasBest={Boolean(plan.best)} shownOffsetS={attempt?.jobId === plan.best?.jobId ? attempt?.offsetS ?? null : null} /> : null;
  const windowCell = cell?.skipped === 'window_unsatisfiable';
  return (
    <div className="rp">
      <Header place={place} plan={plan} />
      {rsg ? (
        <div className="rsg-block" data-testid="rsg-detail">
          <RsgTagView tag={rsg} />
          <span className="small-note">{t('rsg.note')}</span>
        </div>
      ) : drawn ? (
        <span className="small-note">{t('rsg.outside')}</span>
      ) : null}
      <Headline place={place} plan={plan} inputTime={inputTime} issuedAt={issuedAt} computing={Boolean(progress)} />
      {drawn && notComputed && !progress ? <Recompute place={place} drawn /> : null}
      {plan && plan.sweep.length ? (
        <div className="section">
          <div className="section-title">
            <span>{t('timeline.title')}</span>
            <span style={{ fontWeight: 500 }}>{t('timeline.hint')}</span>
          </div>
          <Timeline plan={plan} inputTime={inputTime} issuedAt={issuedAt} selectedOffsetS={selectedOffsetS} progress={progress} places={byId} onSelect={selectOffset} />
        </div>
      ) : null}
      {cell && attempt ? (
        <div className="section">
          <div className="section-title">{t('shelter.title')}</div>
          <ShelterCard route={route} attemptDest={attempt.destinationId} departS={cell.offsetS} arrivalS={attempt.arrivalS} inputTime={inputTime} places={byId} loading={apiOnline && !routeError} />
          {attempt.recheckOf ? <span className="small-note">{t('recheck.note', { id: attempt.recheckOf })}</span> : null}
        </div>
      ) : cell && cell.attempts.length ? (
        <div className="card" data-testid="cell-card">
          <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <StatusChip verdict={windowCell ? 'window' : cell.verdict} />
            <span className="tnum" style={{ fontWeight: 600 }}>{kstClock(inputTime, cell.offsetS)}</span>
          </span>
          <span className="small-note">{skipText(cell, t)}</span>
          {[...new Set(cell.attempts.map((a) => unresolvedReasonText(a.reasonCode, a.rawStatus, t)).filter(Boolean))].map((r) => (
            <span key={r} className="small-note">{r}</span>
          ))}
          <span className="small-note tnum" data-testid="cell-compute">
            {computeLabel(cellComputed?.computeS ?? null, evidence?.provenance?.host ?? null, t)}
          </span>
          {evidenceAttempt?.recheckOf ? <span className="small-note">{t('recheck.note', { id: evidenceAttempt.recheckOf })}</span> : null}
        </div>
      ) : cell && !drawn ? (
        <div className="card" data-testid="cell-card">
          <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <StatusChip verdict={windowCell ? 'window' : cell.verdict} />
            <span className="tnum" style={{ fontWeight: 600 }}>{kstClock(inputTime, cell.offsetS)}</span>
          </span>
          <span className="small-note">{skipText(cell, t)}</span>
        </div>
      ) : null}
      {drawn ? (
        <>
          {exposureEl}
          {computeEl}
          {assumeEl}
          {submittedEl}
          {travelEl}
        </>
      ) : (
        <>
          {travelEl}
          {exposureEl}
          {computeEl}
        </>
      )}
      {plan && plan.windows.length && !notComputed ? <Windows plan={plan} inputTime={inputTime} /> : null}
      {plan && (!drawn || !notComputed) ? <Provenance route={route ?? evidence ?? (drawn ? anyRoute : null)} plan={plan} recheckOf={recheckOf} /> : null}
      {!drawn || !notComputed || progress ? <Recompute place={place} drawn={drawn} /> : null}
      {routeError ? <span className="small-note">{errorText(routeError, t)}</span> : null}
    </div>
  );
}

function DrawnRightPanel() {
  const t = useT();
  const lang = useLang();
  const tab = useStore((s) => s.drawn.rightTab);
  const place = useSelectedPlace();
  const clock = useClockBase();
  const horizon = useHorizon();
  const showOrigin = tab === 'origin' && place && clock.inputTime;
  return (
    <aside className="panel panel-right" aria-label={t('drawn.intro.title')} data-testid="right-panel">
      <div className="rp-tabs" role="tablist" aria-label={t('drawn.intro.title')}>
        <button type="button" role="tab" aria-selected={!showOrigin} onClick={() => setRightTab('zones')} data-testid="tab-zones">
          {t('drawn.tab.zones')}
        </button>
        <button type="button" role="tab" aria-selected={Boolean(showOrigin)} disabled={!place} onClick={() => setRightTab('origin')} data-testid="tab-origin">
          {place ? placeName(place, t, lang) : t('drawn.tab.origin')}
        </button>
      </div>
      {showOrigin ? <OriginDetail place={place} inputTime={clock.inputTime!} issuedAt={clock.issuedAt} drawn /> : <DrawnZonesTab horizonS={horizon} />}
    </aside>
  );
}

export function RightPanel() {
  const t = useT();
  const place = useSelectedPlace();
  const set = useCurrentScenarioSet();
  const scenarioId = useStore((s) => s.scenarioId);
  if (scenarioId === DRAWN_SCENARIO) return <DrawnRightPanel />;
  if (!place || !set) {
    return (
      <aside className="panel panel-right">
        <div className="rp-empty">
          <span className="title">{t('right.empty')}</span>
          <span>{t('right.emptyHint')}</span>
          <div className="read-guide">
            <div className="section-title">{t('right.readTitle')}</div>
            {(['checked_route', 'model_no_route', 'unresolved', 'window'] as const).map((v) => (
              <div key={v} className="read-row">
                <StatusChip verdict={v} />
                <span>{t(`right.read.${v}`)}</span>
              </div>
            ))}
            <div className="read-row small-note">{t('right.read.deadline')}</div>
          </div>
        </div>
      </aside>
    );
  }
  return (
    <aside className="panel panel-right" aria-label={placeName(place, t, 'ko')}>
      <OriginDetail place={place} inputTime={set.inputTime} issuedAt={null} drawn={false} />
    </aside>
  );
}
