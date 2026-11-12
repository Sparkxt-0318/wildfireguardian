/**
 * P-PROTO page (replay only). Fixed order, top to bottom: replay banner → official-orders slot → question → cards.
 * Each card carries its own replay stamp next to its time, so a cropped card still says it is a replay.
 * Presentational parts (Banner, OfficialSlot, Card) are pure and render-tested; the container loads data.
 */
import { useEffect, useMemo, useState } from 'react';
import type { CacheEntry } from '../../domain/types';
import { coordsOf, loadEntries, loadScenario, readSaved, writeSaved, type ReplayScenario } from './load';
import { BANNER, cardFor, DEVICE_NOTE, exampleIds, OFFICIAL_SLOT, pick, QUESTION, type PublicCard } from './model';
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
      <p className="pv-status">
        <span className="pv-icon" aria-hidden="true">
          {ICON[card.icon]}
        </span>{' '}
        <span data-pv="words">{pick(card.words, lang)}</span>
      </p>
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

  useEffect(() => {
    const ac = new AbortController();
    loadEntries(ac.signal)
      .then((es) => {
        setEntries(es);
        setEntryPath((p) => p ?? es[0]?.path ?? null);
      })
      .catch((e) => setError(String(e)));
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

  const inScenario = scenario ? saved.filter((id) => scenario.inputs.some((i) => i.origin.id === id)) : [];
  const showing = scenario ? (inScenario.length ? inScenario : exampleIds(scenario.inputs)) : [];
  const coords = scenario ? coordsOf(scenario.places) : () => null;
  const cards = scenario ? showing.map((id) => cardFor(scenario.inputs.find((i) => i.origin.id === id)!, coords)) : [];
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
        <h1 className="pv-question">{pick(QUESTION, lang)}</h1>
        <button className="pv-lang" onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}>
          {lang === 'ko' ? 'English' : '한국어'}
        </button>
      </header>
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
      {error ? <p className="pv-error">{error}</p> : null}
      {!inScenario.length && scenario ? (
        <p className="pv-examples">{lang === 'ko' ? '저장한 장소가 없어 예시 세 곳을 보여 드립니다(각 상태 하나씩).' : 'No saved places: three examples, one of each state.'}</p>
      ) : null}
      <main className="pv-cards">
        {cards.map((c) => (
          <Card key={c.originId} card={c} lang={lang} example={!inScenario.length} />
        ))}
      </main>
      {scenario ? (
        <section className="pv-places">
          <h2>{lang === 'ko' ? '내 장소 고르기' : 'Choose my places'}</h2>
          <ul>
            {[...scenario.inputs]
              .sort((a, b) => pick(a.origin.display, lang).localeCompare(pick(b.origin.display, lang)))
              .map((i) => (
                <li key={i.origin.id}>
                  <label>
                    <input type="checkbox" checked={saved.includes(i.origin.id)} onChange={() => toggle(i.origin.id)} /> {pick(i.origin.display, lang)}
                  </label>
                </li>
              ))}
          </ul>
        </section>
      ) : null}
      <footer className="pv-footer">{pick(DEVICE_NOTE, lang)}</footer>
    </div>
  );
}
