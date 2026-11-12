/**
 * "왜 이 시각인가요? / Why this time?" — the origin detail panel block and the plan-sheet section.
 * Renders text built from the structured fields only (text.ts). Falls back to a plain line when the explanation file
 * is absent, the origin is missing, the explanation belongs to other results, or it is not_explainable.
 * Sentences and exit-list items resting on values computed for the explanation end with a mark; the panel explains the
 * mark and says where the file was computed, the plan sheet says both once in its section footer.
 */
import { useEffect, useState } from 'react';
import { scenarioTag } from '../plansheet/sheetLogic';
import type { PlanSheetData, PlanSheetScenario } from '../plansheet/types';
import { pick, type Lang } from '../shared/strings';
import { loadExplanationFile, settledExplanation } from './load';
import { EXPLAIN } from './strings';
import { explainView, fill, type ExplainDots, type ExplainView } from './text';
import type { ExplFile, ShownPlan } from './types';
import './explain.css';
import { headlineDepartureS } from '../../domain/plan';

export interface ExplanationState {
  state: 'idle' | 'loading' | 'ready' | 'absent';
  file: ExplFile | null;
}

/** State of one file from the in-memory cache: settled files render synchronously, others are loading. */
function cachedState(regionId: string, inputTime: string): ExplanationState {
  const hit = settledExplanation(regionId, inputTime);
  return hit === undefined ? { state: 'loading', file: null } : { state: hit ? 'ready' : 'absent', file: hit };
}

/** Loads (once per region and input time) and returns the explanation file. */
export function useExplanationFile(regionId: string | null, inputTime: string | null): ExplanationState {
  const known = regionId && inputTime ? settledExplanation(regionId, inputTime) : undefined;
  const [st, setSt] = useState<ExplanationState>(() =>
    !regionId || !inputTime ? { state: 'idle', file: null } : known === undefined ? { state: 'loading', file: null } : { state: known ? 'ready' : 'absent', file: known },
  );
  useEffect(() => {
    if (!regionId || !inputTime) {
      setSt({ state: 'idle', file: null });
      return;
    }
    let live = true;
    const hit = settledExplanation(regionId, inputTime);
    if (hit !== undefined) {
      setSt({ state: hit ? 'ready' : 'absent', file: hit });
      return;
    }
    setSt({ state: 'loading', file: null });
    void loadExplanationFile(regionId, inputTime).then((f) => {
      if (live) setSt({ state: f ? 'ready' : 'absent', file: f });
    });
    return () => {
      live = false;
    };
  }, [regionId, inputTime]);
  return st;
}

/**
 * Loads the explanation files of one region for several input times (the rows of one plan sheet) and returns their
 * state per input time, so that one render sees every row (the sheet footer depends on all of them).
 */
export function useExplanationFiles(regionId: string | null, inputTimes: string[]): Record<string, ExplanationState> {
  const [loaded, setLoaded] = useState<Record<string, ExplanationState>>({});
  const out: Record<string, ExplanationState> = {};
  for (const it of inputTimes) {
    out[it] = !regionId ? { state: 'idle', file: null } : (loaded[`${regionId}|${it}`] ?? cachedState(regionId, it));
  }
  // the input times this render shows as loading; the loader returns the same (possibly settled) promise per file, so
  // a file that settles between this render and the effect still updates the rows
  const waiting = [...new Set(inputTimes.filter((it) => out[it]!.state === 'loading'))].join('|');
  useEffect(() => {
    if (!regionId || !waiting) return;
    let live = true;
    for (const it of waiting.split('|')) {
      void loadExplanationFile(regionId, it).then((f) => {
        if (live) setLoaded((prev) => ({ ...prev, [`${regionId}|${it}`]: { state: f ? 'ready' : 'absent', file: f } }));
      });
    }
    return () => {
      live = false;
    };
  }, [regionId, waiting]);
  return out;
}

export function MemberDots({ dots }: { dots: ExplainDots }) {
  return (
    <span className="wfgx-dots" role="img" aria-label={dots.text} data-members={dots.members.join(',')}>
      {Array.from({ length: dots.total }, (_, i) => (
        <span key={i} className={dots.members.includes(i) ? 'wfgx-dot wfgx-dot--on' : 'wfgx-dot'} aria-hidden="true" />
      ))}
    </span>
  );
}

function viewFor(st: ExplanationState, originId: string, inputTime: string, lang: Lang, shown: ShownPlan | null): ExplainView {
  return explainView({ state: st.state === 'ready' ? 'ready' : st.state === 'absent' ? 'absent' : 'loading', file: st.file, originId, inputTime, lang, shown });
}

export interface ExplainBlockProps {
  regionId: string | null;
  inputTime: string | null;
  originId: string;
  lang: Lang;
  /** what the planner shows for this origin; the explanation is shown only if it matches */
  shown: ShownPlan | null;
}

/** Origin detail panel block (recorded scenarios). */
export function ExplainBlock({ regionId, inputTime, originId, lang, shown }: ExplainBlockProps) {
  const st = useExplanationFile(regionId, inputTime);
  if (!regionId || !inputTime || st.state === 'idle') return null;
  const v = viewFor(st, originId, inputTime, lang, shown);
  const full = v.kind === 'explained' || v.kind === 'explained_partial';
  return (
    <section className="section wfgx" data-testid="explain" data-explain-state={v.kind} data-explain-reason={v.reason ?? ''} lang={lang}>
      <div className="section-title">
        <span>{v.title}</span>
        {v.statusLabel ? <span className={`wfgx-status wfgx-status--${v.kind}`}>{v.statusLabel}</span> : null}
      </div>
      {full || v.kind === 'not_explainable' ? (
        <div className={full ? 'card wfgx-card' : 'wfgx-plain'}>
          {v.lines.map((l, i) => (
            <p key={i} className="wfgx-line">
              {l}
            </p>
          ))}
          {v.dots ? (
            <div className="wfgx-dotsrow">
              <MemberDots dots={v.dots} />
              <span>{v.dots.text}</span>
            </div>
          ) : null}
          {v.list.length ? (
            <ul className="wfgx-list">
              {v.list.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          ) : null}
          {v.basis ? <p className="small-note wfgx-basis">{v.basis}</p> : null}
          {v.computedNote ? <p className="small-note wfgx-note" data-explain-note="computed">{v.computedNote}</p> : null}
          {v.host ? <p className="small-note wfgx-host" data-explain-note="host">{v.host}</p> : null}
          {v.provenance ? <p className="small-note wfgx-prov">{v.provenance}</p> : null}
        </div>
      ) : (
        <span className="small-note wfgx-fallback">{v.lines[0]}</span>
      )}
    </section>
  );
}

/** Route-check job id of the route printed on the sheet (routeFeature properties.job_id), else null. */
export function printedJobId(s: PlanSheetScenario): string | null {
  const v = (s.route?.properties as Record<string, unknown> | null | undefined)?.['job_id'];
  return typeof v === 'string' && v ? v : null;
}

function SheetRow({ s, index, v }: { s: PlanSheetScenario; index: number; v: ExplainView }) {
  const full = v.kind === 'explained' || v.kind === 'explained_partial';
  return (
    <li className="wfgx-sheet__row" data-explain-state={v.kind} data-explain-reason={v.reason ?? ''} data-scenario={s.scenarioSetId}>
      <span className="wfgf-sheet__stag">{scenarioTag(index)}</span>
      <span className={full ? 'wfgx-sheet__text' : 'wfgx-sheet__text wfgf-sheet__muted'}>
        {v.lines.join(' ')}
        {v.list.length ? ` ${v.list.join(' · ')}` : ''}
      </span>
      {v.dots ? <MemberDots dots={v.dots} /> : null}
    </li>
  );
}

/**
 * Plan-sheet section: one line per recorded scenario row (drawn-zone rows have no explanation). The footer states the
 * forecast basis and — once per sheet, when a printed sentence carries the mark — what the mark means and where it
 * was computed (one note per distinct computing host among the marked rows; the committed files share one).
 */
export function ExplainSheetSection({ sheet, lang }: { sheet: PlanSheetData; lang: Lang }) {
  const rows = sheet.fireInputType === 'spread_zones' ? [] : sheet.scenarios.map((s, i) => ({ s, i })).filter(({ s }) => !s.issuedAtIso);
  const files = useExplanationFiles(rows.length ? sheet.region.id : null, rows.map(({ s }) => s.inputTimeIso));
  if (!rows.length) return null;
  const views = rows.map(({ s, i }) => {
    // like the panel: the explanation is printed only for the very route check whose route is printed
    // the printed deadline is the staff headline time (Iris E); an explanation recorded for a later departure after a
    // gap does not match it and is not printed (matchesShown fails closed)
    const shown: ShownPlan = { bestVerdict: s.bestVerdict, deadlineS: s.bestVerdict === 'checked_route' ? headlineDepartureS(s) : s.latestSafeDepartureS, bestDestinationId: s.shelter?.id ?? null, bestJobId: printedJobId(s) };
    return { s, i, v: viewFor(files[s.inputTimeIso]!, sheet.origin.id, s.inputTimeIso, lang, shown) };
  });
  const total = rows.map(({ s }) => files[s.inputTimeIso]?.file?.provenance.members?.length).find((n) => n) ?? null;
  // the note names the computing host of the file: rows from files computed on different hosts get one note each
  const notes = [...new Set(views.map(({ v }) => v.sheetNote).filter((n): n is string => Boolean(n)))];
  return (
    <section className="wfgf-sheet__section wfgx-sheet" data-explain-sheet="true">
      <h2>{pick(EXPLAIN.sheetTitle, lang)}</h2>
      <ul className="wfgx-sheet__list">
        {views.map(({ s, i, v }) => (
          <SheetRow key={`${s.scenarioSetId}-${i}`} s={s} index={i} v={v} />
        ))}
      </ul>
      {total || notes.length ? (
        <p className="wfgf-sheet__muted wfgx-sheet__basis">
          {total ? fill(pick(EXPLAIN.basis, lang), { total }) : null}
          {notes.map((note, k) => (
            <span key={note} className="wfgx-sheet__note" data-explain-note="computed">
              {total || k > 0 ? ' ' : ''}
              {note}
            </span>
          ))}
        </p>
      ) : null}
    </section>
  );
}
