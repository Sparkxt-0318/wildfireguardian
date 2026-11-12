/**
 * P-PROTO page (replay only). Fixed order, top to bottom: replay banner → official-orders slot → question → cards.
 * Each card carries its own replay stamp next to its time, so a cropped card still says it is a replay.
 * Presentational parts (Banner, OfficialSlot, Card) are pure and render-tested; the container loads data.
 */
import { useEffect, useMemo, useState } from 'react';
import type { CacheEntry } from '../../domain/types';
import { coordsOf, loadEntries, loadScenario, readSaved, writeSaved, type ReplayScenario } from './load';
import { BANNER, cardFor, DEVICE_NOTE, exampleIds, linkFor, NO_DATA, NOT_IN_MODEL, OFFICIAL_SLOT, parseLink, pick, QUESTION, validPlace, type PublicCard } from './model';
import type { LmLang } from '../lastmile/types';

const ICON: Record<PublicCard['icon'], string> = { clock: '⏱', stop: '⛔', question: '?' };

export function Banner({ lang }: { lang: LmLang }) {
  return (
    <div className="pv-banner" role="alert" data-pv="banner">
      {pick(BANNER, lang)}
    </div>
  );
}

export function OfficialSlot({ lang }: { lang: LmLang }) {
  return (
    <section className="pv-official" data-pv="official">
      {pick(OFFICIAL_SLOT, lang)}
    </section>
  );
}

export function Card({ card, lang, example }: { card: PublicCard; lang: LmLang; example: boolean }) {
  const gpxUrl = useMemo(() => (card.handoff && typeof URL !== 'undefined' && URL.createObjectURL ? URL.createObjectURL(new Blob([card.handoff.gpx], { type: 'application/gpx+xml' })) : null), [card]);
  return (
    <article className={`pv-card pv-${card.tone}`} data-pv="card" data-kind={card.kind}>
      <div className="pv-stamp" data-pv="stamp">
        {example ? (lang === 'ko' ? '예시 · ' : 'Example · ') : ''}
        {pick(card.replayStamp, lang)}
      </div>
      <h2 className="pv-place">{pick(card.place, lang)}</h2>
      {/* Iris: the card leads with the time (never the route); the one-trip line sits with the time so a crop keeps it */}
      {card.time ? (
        <p className="pv-timeline">
          <span className="pv-time" data-pv="time">
            {pick(card.time, lang)}
          </span>{' '}
          <span className="pv-timestamp" data-pv="time-stamp">
            {pick(card.replayStamp, lang)}
          </span>
        </p>
      ) : null}
      {card.oneTrip ? (
        <p className="pv-onetrip" data-pv="one-trip">
          {pick(card.oneTrip, lang)}
        </p>
      ) : null}
      <p className="pv-status">
        <span className="pv-icon" aria-hidden="true">
          {ICON[card.icon]}
        </span>{' '}
        <span data-pv="words">{pick(card.words, lang)}</span>
      </p>
      <p className="pv-age" data-pv="age">
        {pick(card.dataAge, lang)}
      </p>
      <p className="pv-guidance">{pick(card.guidance, lang)}</p>
      {card.handoff ? (
        <details className="pv-handoff" data-pv="handoff">
          <summary>{lang === 'ko' ? '어디로 — 도착지 넘겨받기' : 'Where to — destination hand-off'}</summary>
          <p>{pick(card.handoff.text, lang)}</p>
          {gpxUrl ? (
            <a href={gpxUrl} download={card.handoff.gpxFileName}>
              {lang === 'ko' ? 'GPX 파일 저장 (기록 재현 표시 포함)' : 'Save GPX file (replay-labelled)'}
            </a>
          ) : null}
        </details>
      ) : null}
    </article>
  );
}

export function PublicView() {
  const [lang, setLang] = useState<LmLang>('ko');
  const [entries, setEntries] = useState<CacheEntry[]>([]);
  const [entryPath, setEntryPath] = useState<string | null>(null);
  const [scenario, setScenario] = useState<ReplayScenario | null>(null);
  const [saved, setSaved] = useState<string[]>(() => readSaved());
  const [error, setError] = useState<string | null>(null);
  const [linkPlace, setLinkPlace] = useState<string | null>(null);
  const [indexLoaded, setIndexLoaded] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    loadEntries(ac.signal)
      .then((es) => {
        setEntries(es);
        const link = parseLink(typeof location !== 'undefined' ? location.search : '', es.map((e) => e.path));
        setLinkPlace(link.place);
        setEntryPath((p) => p ?? link.scenario ?? es[0]?.path ?? null);
        if (!es.length) console.warn('[public view] no replay cache index entries (missing or unreadable index)');
      })
      .catch((e) => setError(String(e)))
      .finally(() => setIndexLoaded(true));
    return () => ac.abort();
  }, []);
  useEffect(() => {
    const entry = entries.find((e) => e.path === entryPath);
    if (!entry) return;
    const ac = new AbortController();
    setScenario(null);
    loadScenario(entry, ac.signal).then(setScenario).catch((e) => setError(String(e)));
    return () => ac.abort();
  }, [entries, entryPath]);

  // no replay data on this page (no index, an unreadable index, or a failed load): one line for every cause; the
  // cause goes to the console for staff, never onto the page (Iris)
  const noData = error !== null || (indexLoaded && entries.length === 0);
  useEffect(() => {
    if (error !== null) console.warn(`[public view] replay data failed to load: ${error}`);
  }, [error]);

  const fromLink = !noData && scenario ? validPlace(linkPlace, scenario.inputs) : null;
  const inScenario = scenario ? [...new Set([...(fromLink ? [fromLink] : []), ...saved.filter((id) => scenario.inputs.some((i) => i.origin.id === id))])] : [];
  const showing = scenario ? (inScenario.length ? inScenario : exampleIds(scenario.inputs)) : [];
  const coords = scenario ? coordsOf(scenario.places) : () => null;
  const cards = !noData && scenario ? showing.map((id) => cardFor(scenario.inputs.find((i) => i.origin.id === id)!, coords)) : [];
  const toggle = (id: string) => {
    const next = saved.includes(id) ? saved.filter((x) => x !== id) : [...saved, id];
    setSaved(next);
    writeSaved(next);
  };

  return (
    <div className="pv-root" lang={lang}>
      <Banner lang={lang} />
      <OfficialSlot lang={lang} />
      <header className="pv-header">
        {noData ? null : <h1 className="pv-question">{pick(QUESTION, lang)}</h1>}
        <button className="pv-lang" onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}>
          {lang === 'ko' ? 'English' : '한국어'}
        </button>
      </header>
      {noData ? (
        <p className="pv-nodata" data-pv="no-data">
          {pick(NO_DATA, lang)}
        </p>
      ) : null}
      {noData ? null : (
      <label className="pv-scenario">
        {lang === 'ko' ? '재현할 기록: ' : 'Replayed record: '}
        <select value={entryPath ?? ''} onChange={(e) => setEntryPath(e.target.value)}>
          {entries.map((e) => (
            <option key={e.path} value={e.path}>
              {e.regionId} · {e.inputTime}
            </option>
          ))}
        </select>
      </label>
      )}
      {!noData && !inScenario.length && scenario ? (
        <p className="pv-examples">{lang === 'ko' ? '저장한 장소가 없어 예시 세 곳을 보여 드립니다(각 상태 하나씩).' : 'No saved places: three examples, one of each state.'}</p>
      ) : null}
      <main className="pv-cards">
        {cards.map((c) => (
          <Card key={c.originId} card={c} lang={lang} example={!inScenario.length} />
        ))}
      </main>
      {!noData && scenario ? (
        <section className="pv-places">
          <h2>{lang === 'ko' ? '내 장소 고르기' : 'Choose my places'}</h2>
          <p>{lang === 'ko' ? '예: 우리 집, 부모님 댁, 마을회관. 링크를 공유하면 고른 장소가 함께 전달됩니다.' : 'e.g. home, parents\u2019 home, village hall. Sharing a link reveals the chosen place.'}</p>
          <ul>
            {[...scenario.inputs]
              .sort((a, b) => pick(a.origin.display, lang).localeCompare(pick(b.origin.display, lang)))
              .map((i) => (
                <li key={i.origin.id}>
                  <label>
                    <input type="checkbox" checked={saved.includes(i.origin.id)} onChange={() => toggle(i.origin.id)} /> {pick(i.origin.display, lang)}
                  </label>{' '}
                  {entryPath ? (
                    <a className="pv-link" href={linkFor(entryPath, i.origin.id)}>
                      {lang === 'ko' ? '링크' : 'link'}
                    </a>
                  ) : null}
                </li>
              ))}
          </ul>
        </section>
      ) : null}
      <section className="pv-notin" data-pv="not-in-model">
        <h2>{pick(NOT_IN_MODEL.title, lang)}</h2>
        <ul>
          {NOT_IN_MODEL.items.map((x) => (
            <li key={x.en}>{pick(x, lang)}</li>
          ))}
        </ul>
      </section>
      <footer className="pv-footer">{pick(DEVICE_NOTE, lang)}</footer>
    </div>
  );
}
