/**
 * "왜 이 시각인가요? / Why this time?" — the origin detail panel block and the plan-sheet section.
 * Renders text built from the structured fields only (text.ts). Falls back to a plain line when the explanation file
 * is absent, the origin is missing, the explanation belongs to other results, or it is not_explainable.
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

export interface ExplanationState {
  state: 'idle' | 'loading' | 'ready' | 'absent';
  file: ExplFile | null;
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

function SheetRow({ regionId, originId, s, index, lang }: { regionId: string; originId: string; s: PlanSheetScenario; index: number; lang: Lang }) {
  const st = useExplanationFile(regionId, s.inputTimeIso);
  // like the panel: the explanation is printed only for the very route check whose route is printed
  const shown: ShownPlan = { bestVerdict: s.bestVerdict, deadlineS: s.latestSafeDepartureS, bestDestinationId: s.shelter?.id ?? null, bestJobId: printedJobId(s) };
  const v = viewFor(st, originId, s.inputTimeIso, lang, shown);
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

/** Plan-sheet section: one line per recorded scenario row (drawn-zone rows have no explanation). */
export function ExplainSheetSection({ sheet, lang }: { sheet: PlanSheetData; lang: Lang }) {
  const rows = sheet.fireInputType === 'spread_zones' ? [] : sheet.scenarios.map((s, i) => ({ s, i })).filter(({ s }) => !s.issuedAtIso);
  const first = useExplanationFile(rows.length ? sheet.region.id : null, rows[0]?.s.inputTimeIso ?? null);
  if (!rows.length) return null;
  const total = first.file?.provenance.members?.length ?? null;
  return (
    <section className="wfgf-sheet__section wfgx-sheet" data-explain-sheet="true">
      <h2>{pick(EXPLAIN.sheetTitle, lang)}</h2>
      <ul className="wfgx-sheet__list">
        {rows.map(({ s, i }) => (
          <SheetRow key={`${s.scenarioSetId}-${i}`} regionId={sheet.region.id} originId={sheet.origin.id} s={s} index={i} lang={lang} />
        ))}
      </ul>
      {total ? <p className="wfgf-sheet__muted wfgx-sheet__basis">{fill(pick(EXPLAIN.basis, lang), { total })}</p> : null}
    </section>
  );
}
