/**
 * 25 March 2025 replay (research/kcf-replay), mounted by the left panel and the time slider dock:
 *
 * - ReplaySelector: one button per replay pack (src/data/replayPacks.ts). A pending pack (the
 *   MEASURED R(h) arms) is listed but disabled, with why.
 * - ReplayNotice: the reconstruction label and method line, shown while a pack scenario is on screen
 *   (the data strip above it keeps the "시험 데이터 · 평가 호스트 아님" badge from the cache host).
 * - ReplayHourSlider: a range over the pack's 13 issue hours (12:00–24:00 KST); moving it switches the
 *   scenario to that hour's cache file (the selected place is kept).
 * - NamedPlacesPanel: the six named places of RESULTS.md §4 with the latest safe departure at each
 *   issue hour, and their reported (documented) times with the source, labelled "not outcomes".
 */
import { useEffect, useMemo, useRef } from 'react';
import { compactUtc, kstClock } from '../../domain/clock';
import type { ReplayPack } from '../../data/replayPacks';
import { useLang, useT } from '../../i18n';
import { selectOrigin, selectRegion, selectScenario } from '../../state/controller';
import { useScenarioSets } from '../../state/selectors';
import { useStore } from '../../state/store';
import { ChevronIcon } from '../../components/Icons';
import { listedPacks, packSets, useActivePack, useNamedPlaces, usePackSets, type NamedHour, type NamedPlace, type ReportedItem } from './data';
import './strings';
import './replay.css';

function hourLabel(iso: string): string {
  const c = kstClock(iso, 0);
  // 2025-03-26 00:00 KST is the end of the 25 March window: "24:00"
  return c === '00:00' ? '24:00' : c;
}

/** Same issue hour in another pack or region, else the first hour. */
function pickHour(sets: { id: string; inputTime: string }[], inputTime: string | null): string | null {
  return (inputTime ? sets.find((s) => s.inputTime === inputTime)?.id : undefined) ?? sets[0]?.id ?? null;
}

export function ReplaySelector() {
  const t = useT();
  const sets = useScenarioSets();
  const active = useActivePack();
  const scenarioId = useStore((s) => s.scenarioId);
  const current = sets.find((s) => s.id === scenarioId) ?? null;
  const packs = listedPacks();
  return (
    <div className="replay-select" data-testid="replay-selector">
      <div className="field-label">{t('replay.section')}</div>
      <div className="replay-packs" role="group" aria-label={t('replay.section')}>
        {packs.map((p) => {
          const mine = packSets(sets, p.id);
          const pending = p.status !== 'available';
          return (
            <button
              key={p.id}
              type="button"
              className="scenario-btn replay-pack"
              aria-pressed={active?.id === p.id}
              disabled={pending || mine.length === 0}
              title={pending ? t('replay.pendingBody') : undefined}
              onClick={() => {
                const id = pickHour(mine, current?.inputTime ?? null);
                if (id) void selectScenario(id);
              }}
              data-testid={`replay-pack-${p.id}`}
            >
              <span className="radio" aria-hidden="true" />
              <span className="label">{t(`replay.pack.${p.id}`)}</span>
            </button>
          );
        })}
      </div>
      {packs.some((p) => p.status !== 'available') ? (
        <details className="replay-pending" data-testid="replay-pending">
          <summary>{t('replay.pendingTitle')}</summary>
          {t('replay.pendingBody')}
        </details>
      ) : null}
    </div>
  );
}

export function ReplayNotice({ pack }: { pack: ReplayPack }) {
  const t = useT();
  return (
    <div className="replay-notice" role="note" data-testid="replay-notice">
      <div className="replay-label">{t('replay.label')}</div>
      <details className="replay-how">
        <summary>{t('replay.how')}</summary>
        <div className="replay-method">{t('replay.method', { rate: pack.rate ?? pack.standin })}</div>
        <div className="replay-method mono">
          <bdi dir="ltr">{t('replay.results', { path: pack.results })}</bdi>
        </div>
      </details>
    </div>
  );
}

export function ReplayHourSlider({ pack }: { pack: ReplayPack }) {
  const t = useT();
  const sets = usePackSets(pack.id);
  const scenarioId = useStore((s) => s.scenarioId);
  const idx = sets.findIndex((s) => s.id === scenarioId);
  if (!sets.length || idx < 0) return null;
  const cur = sets[idx]!;
  const go = (i: number) => {
    const s = sets[Math.max(0, Math.min(sets.length - 1, i))];
    if (s && s.id !== scenarioId) void selectScenario(s.id);
  };
  return (
    <div className="replay-hour" data-testid="replay-hour-slider">
      <span className="replay-hour-label">{t('replay.hour')}</span>
      <button type="button" className="btn btn-ghost replay-step prev" aria-label={t('replay.prevHour')} disabled={idx <= 0} onClick={() => go(idx - 1)}>
        <ChevronIcon dir="left" size={12} />
      </button>
      <div className="replay-track">
        <input
          type="range"
          min={0}
          max={sets.length - 1}
          step={1}
          value={idx}
          aria-label={t('replay.hour')}
          aria-valuetext={`${t('replay.hourValue', { time: hourLabel(cur.inputTime) })} · ${t('replay.hourOf', { i: idx + 1 })}`}
          onChange={(e) => go(Number(e.target.value))}
          data-testid="replay-hour-input"
        />
        <div className="replay-ticks" aria-hidden="true">
          {sets.map((s, i) => (
            <span
              key={s.id}
              className={`replay-tick${i === idx ? ' on' : ''}${i === 0 || i === sets.length - 1 ? ' edge' : ''}${i % 2 === 0 ? ' even' : ''}`}
              style={{ left: `${(i / Math.max(1, sets.length - 1)) * 100}%` }}
            >
              <i />
              <b>{hourLabel(s.inputTime)}</b>
            </span>
          ))}
        </div>
      </div>
      <button type="button" className="btn btn-ghost replay-step next" aria-label={t('replay.nextHour')} disabled={idx >= sets.length - 1} onClick={() => go(idx + 1)}>
        <ChevronIcon dir="right" size={12} />
      </button>
      <span className="replay-hour-value tnum" data-testid="replay-hour-value">
        {t('replay.hourValue', { time: hourLabel(cur.inputTime) })}
      </span>
    </div>
  );
}

function cellText(h: NamedHour | undefined, t: (k: string) => string): string {
  if (!h) return '—';
  if (h.latest_safe_departure_utc) return kstClock(h.latest_safe_departure_utc, 0);
  if (h.state === 'INSIDE_KNOWN_FIRE_AREA') return t('replay.inside');
  if (h.state === 'NOT_CUT_WITHIN_H') return t('replay.notCut');
  return t('replay.noDeparture');
}

function Reported({ item }: { item: ReportedItem }) {
  const t = useT();
  const lang = useLang();
  const time = item.kst.slice(6);
  return (
    <li className="replay-reported-item" data-testid="replay-reported-item">
      <span className="replay-reported-time tnum">
        <span className="replay-reported-tag">{t('replay.reported.label')}</span>
        {item.approx ? t('replay.reported.approx') : ''}
        {time}
        {item.kst.startsWith('03-26') ? <span className="replay-day">+1</span> : null}
      </span>
      <span className="replay-reported-text">
        {lang === 'en' ? item.en : item.ko}
        <span className="replay-reported-meta">
          {t(`replay.scope.${item.scope}`)} · {item.flags.map((f) => t(`replay.flag.${f}`)).join(' · ')} ·{' '}
          <a href={item.source.url} target="_blank" rel="noopener noreferrer">
            {t('replay.source', { outlet: lang === 'en' ? item.source.outlet_en : item.source.outlet, date: item.source.date })}
            <span aria-hidden="true"> ↗</span>
          </a>
        </span>
      </span>
    </li>
  );
}

function PlaceRow({ place, hours, curIdx, selected, onPick }: { place: NamedPlace; hours: string[]; curIdx: number; selected: boolean; onPick: () => void }) {
  const t = useT();
  return (
    <tr className={selected ? 'sel' : undefined} data-testid={`replay-place-${place.name}`}>
      <th scope="row">
        <button type="button" className="replay-place-btn" onClick={onPick} title={t('replay.selectPlace')}>
          {place.name}
        </button>
      </th>
      {hours.map((iu, i) => {
        const h = place.hours.find((x) => x.issue_utc === iu);
        const inside = h?.state === 'INSIDE_KNOWN_FIRE_AREA';
        const title = !h
          ? ''
          : inside
            ? t('replay.cellTitleInside', { place: place.name, hour: hourLabel(iu) })
            : t('replay.cellTitle', {
                place: place.name,
                hour: hourLabel(iu),
                time: cellText(h, t),
                shelter: h.shelter_name ?? '—',
                step: t(`replay.step.${h.step ?? 'NONE'}`),
              }) + (h.route_cut_before_departure ? ` · ${t('replay.cutEarlier')}` : '');
        return (
          <td key={iu} className={`${i === curIdx ? 'cur' : ''}${inside ? ' inside' : ''}${h?.step === 'LEAVE_NOW' ? ' leave' : ''}`} title={title} data-hour={hourLabel(iu)}>
            <span className="tnum">{cellText(h, t)}</span>
            {h?.route_cut_before_departure ? (
              <span className="replay-cut" aria-label={t('replay.cutEarlierShort')}>
                ●
              </span>
            ) : null}
          </td>
        );
      })}
    </tr>
  );
}

export function NamedPlacesPanel({ pack }: { pack: ReplayPack }) {
  const t = useT();
  const lang = useLang();
  const { state, doc, error } = useNamedPlaces(pack);
  const scenarioId = useStore((s) => s.scenarioId);
  const regionId = useStore((s) => s.regionId);
  const selected = useStore((s) => s.selectedOriginId);
  const sets = usePackSets(pack.id);
  const curInput = sets.find((s) => s.id === scenarioId)?.inputTime ?? null;
  const hours = doc?.issue_hours_utc ?? [];
  const curIdx = useMemo(() => hours.findIndex((h) => Date.parse(h) === Date.parse(curInput ?? '')), [hours, curInput]);
  const scroller = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = scroller.current?.querySelector<HTMLElement>('th.cur');
    if (el && scroller.current) scroller.current.scrollLeft = Math.max(0, el.offsetLeft - scroller.current.clientWidth / 2);
  }, [curIdx, state]);
  if (state === 'none') return <div className="replay-places muted">{t('replay.places.none')}</div>;
  if (state === 'loading') return <div className="replay-places muted">{t('replay.places.loading')}</div>;
  if (state === 'error' || !doc) return <div className="replay-places muted">{t('replay.places.error', { message: error ?? '' })}</div>;
  const inRegion = regionId === doc.region_id;
  // the same issue hour of this pack in the six places' region (scenario ids carry the compact time)
  const sameHourThere = curInput ? `${pack.scenarioPrefix}${compactUtc(curInput)}` : undefined;
  const pick = (p: NamedPlace) => {
    if (inRegion) selectOrigin(p.place_id);
    else void selectRegion(doc.region_id, { scenarioId: sameHourThere, originId: p.place_id });
  };
  const selPlace = doc.places.find((p) => p.place_id === selected) ?? null;
  return (
    <section className="replay-places" aria-label={t('replay.places.title')} data-testid="replay-named-places">
      <h3>{t('replay.places.title')}</h3>
      {!inRegion ? (
        <div className="replay-other-region">
          {t('replay.places.otherRegion')}{' '}
          <button type="button" className="btn" onClick={() => void selectRegion(doc.region_id, { scenarioId: sameHourThere })}>
            {t('replay.places.show')}
          </button>
        </div>
      ) : null}
      <div className="replay-table-wrap" ref={scroller}>
        <table className="replay-table">
          <thead>
            <tr>
              <th scope="col">{t('replay.places.place')}</th>
              {hours.map((iu, i) => (
                <th key={iu} scope="col" className={i === curIdx ? 'cur' : undefined}>
                  {inRegion ? (
                    <button
                      type="button"
                      className="replay-hour-btn tnum"
                      aria-pressed={i === curIdx}
                      onClick={() => {
                        const s = sets.find((x) => Date.parse(x.inputTime) === Date.parse(iu));
                        if (s) void selectScenario(s.id);
                      }}
                    >
                      {hourLabel(iu)}
                    </button>
                  ) : (
                    <span className="tnum">{hourLabel(iu)}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {doc.places.map((p) => (
              <PlaceRow key={p.place_id} place={p} hours={hours} curIdx={curIdx} selected={p.place_id === selected} onPick={() => pick(p)} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="replay-foot">
        {t('replay.places.note')} <span className="replay-cut">●</span> = {t('replay.cutEarlier')}.
      </p>
      <h4>{t('replay.reported.title')}</h4>
      <p className="replay-foot">{t('replay.reported.note')}</p>
      {doc.places.map((p) => (
        <details key={p.place_id} className="replay-reported" open={selPlace ? selPlace.place_id === p.place_id : undefined} data-testid={`replay-reported-${p.name}`}>
          <summary>
            {p.name} <span className="muted">· {p.reported.length}</span>
          </summary>
          <ul>
            {p.reported.map((it, i) => (
              <Reported key={i} item={it} />
            ))}
          </ul>
          {(lang === 'en' ? p.reported_note_en : p.reported_note_ko) ? <p className="replay-foot">{lang === 'en' ? p.reported_note_en : p.reported_note_ko}</p> : null}
        </details>
      ))}
    </section>
  );
}
