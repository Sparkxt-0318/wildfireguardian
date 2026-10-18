/**
 * One A4 portrait page (210 × 297 mm, 16 mm margins) of the 기관용 사전 대피계획서 for one origin.
 * Status is always icon + text; unresolved never reads as safe; only checked routes are drawn.
 */
import { kstDateTime } from '../../domain/clock';
import { clockAt, formatCoord, formatDistanceM, formatSeconds, kstStamp, sweepStepMin } from '../shared/format';
import { FIXED_IDENTITY, LIMITATIONS, NOTE_LABEL, pick, VERDICT_LABEL, WINDOW_CLOSED_LABEL, type Lang } from '../shared/strings';
import { MockBadge, SweepCellGlyph, VerdictBadge, VerdictIcon } from '../shared/VerdictIcon';
import {
  alternativePlanItems,
  arrivalCell,
  deadlineCell,
  exposureSummary,
  exposureText,
  fill,
  partialCheckedScenarios,
  partialCheckedText,
  scenarioReasonText,
  scenarioTag,
} from './sheetLogic';
import { MapLegendGlyph, StaticRouteMap } from './StaticRouteMap';
import { SHEET } from './strings';
import type { PlanSheetData, PlanSheetScenario } from './types';

export const SHEET_MAP_MM = { width: 178, height: 62 } as const;
const MAX_FACILITIES = 5;

export interface PlanSheetProps {
  sheet: PlanSheetData;
  lang: Lang;
  pageNumber: number;
  pageCount: number;
  /** start rendering the map image */
  mapActive: boolean;
  current?: boolean;
  onMapSettled?: (originId: string, settled: boolean) => void;
  forceSvgMap?: boolean;
}

function originName(sheet: PlanSheetData, lang: Lang): string | null {
  return (lang === 'en' ? sheet.origin.nameEn || sheet.origin.name : sheet.origin.name) || null;
}

/** Title: the OSM name, the app's descriptor ("기록 임무 FD1 출발점"), or "{category} · 이름 없음" — a name is never invented. */
function originTitle(sheet: PlanSheetData, lang: Lang): string {
  return originName(sheet, lang) ?? sheet.origin.displayName ?? `${sheet.origin.categoryLabel} · ${pick(SHEET.unnamed, lang)}`;
}

/** "마을 진입 지점까지" + "1.2 km (이 구간 미반영)"; research origins start at their recorded node (no gap). */
function entryFact(sheet: PlanSheetData, lang: Lang): { label: string; value: string } {
  const kind = sheet.origin.entryKind ?? (sheet.origin.vulnerable ? 'facility' : 'village');
  if (kind === 'research') return { label: pick(SHEET.entryResearch, lang), value: sheet.origin.entryNode ?? '—' };
  const label = pick(kind === 'facility' ? SHEET.entryFacility : SHEET.entryVillage, lang);
  const d = sheet.origin.snapDistanceM;
  if (d === null || !Number.isFinite(d)) return { label, value: '—' };
  return { label, value: d > 0 ? `${formatDistanceM(d, lang)} ${pick(SHEET.entryGap, lang)}` : formatDistanceM(d, lang) };
}

function SweepStrip({ s, lang }: { s: PlanSheetScenario; lang: Lang }) {
  const cells = [...s.sweep].sort((a, b) => a.offsetS - b.offsetS);
  if (cells.length === 0) return null;
  const base = { inputTimeIso: s.inputTimeIso, issuedAtIso: s.issuedAtIso ?? null };
  const step = sweepStepMin(cells.map((c) => c.offsetS));
  const label = step ? fill(pick(SHEET.sweepLabel, lang), { step }) : pick(SHEET.sweepLabelNoStep, lang);
  return (
    <div className="wfgf-sheet__sweep" data-sweep-strip="true">
      <span className="wfgf-sheet__sweep-label">{label}</span>
      <span className="wfgf-sheet__sweep-time">{clockAt(base, cells[0]!.offsetS)}</span>
      <span className="wfgf-sheet__sweep-cells">
        {cells.map((c) => {
          const v = c.verdict;
          const name = v === 'window_closed' ? pick(WINDOW_CLOSED_LABEL, lang) : pick(VERDICT_LABEL[v], lang);
          return <SweepCellGlyph key={c.offsetS} verdict={v} width={11} height={11} title={`${clockAt(base, c.offsetS)} ${name}`} />;
        })}
      </span>
      <span className="wfgf-sheet__sweep-time">{clockAt(base, cells[cells.length - 1]!.offsetS)}</span>
    </div>
  );
}

function ScenarioRows({ s, i, lang, drawnSheet }: { s: PlanSheetScenario; i: number; lang: Lang; drawnSheet: boolean }) {
  const dl = deadlineCell(s, lang);
  const ex = exposureSummary(s);
  const checked = s.bestVerdict === 'checked_route';
  // the narrow table cell carries the reason text; the raw code is in 대체 계획 필요 시나리오
  const reason = s.bestVerdict === 'unresolved' ? [s.note ? pick(NOTE_LABEL[s.note], lang) : null, scenarioReasonText(s, lang, { short: true })].filter(Boolean).join(' · ') : '';
  const shelterName = s.shelter ? s.shelter.name || pick(SHEET.unnamed, lang) : null;
  return (
    <>
      <tr className="wfgf-sheet__row" data-scenario={s.scenarioSetId} data-verdict={s.bestVerdict}>
        <td>
          <span className="wfgf-sheet__stag">{scenarioTag(i)}</span>
          <span className="wfgf-num wfgf-sheet__nowrap">{kstDateTime(s.issuedAtIso || s.inputTimeIso, 0).replace(' KST', '')}</span>
          {s.issuedAtIso ? (
            <div className="wfgf-sheet__sub" data-row-kind="spread_zones">
              {pick(SHEET.rowDrawn, lang)}
            </div>
          ) : drawnSheet ? (
            <div className="wfgf-sheet__sub" data-row-kind="recorded">
              {pick(SHEET.rowRecordedCompare, lang)}
            </div>
          ) : null}
        </td>
        <td>
          <VerdictBadge verdict={s.bestVerdict} lang={lang} size={13} />
          {reason && <div className="wfgf-sheet__sub">{`${pick(SHEET.reason, lang)}: ${reason}`}</div>}
        </td>
        <td>
          <div className="wfgf-sheet__deadline wfgf-num">{dl.main}</div>
          {dl.sub && <div className="wfgf-sheet__sub">{dl.sub}</div>}
        </td>
        <td>
          {checked && s.shelter ? (
            <>
              <div className="wfgf-sheet__strong">{shelterName}</div>
              <div className="wfgf-sheet__sub wfgf-sheet__tag">{s.shelter.sourceTag}</div>
            </>
          ) : (
            '—'
          )}
        </td>
        <td className="wfgf-num">{arrivalCell(s)}</td>
        <td>
          {ex ? (
            <>
              <div className="wfgf-num">{exposureText(ex, lang)}</div>
              <div className="wfgf-sheet__sub">
                {fill(pick(SHEET.exposureOf, lang), { pl: ex.limits.peakKwM2, dl: ex.limits.doseKjM2 })}
                {ex.anyContact === null ? '' : ` · ${pick(ex.anyContact ? SHEET.contactSome : SHEET.contactNone, lang)}`}
              </div>
            </>
          ) : (
            <span className="wfgf-sheet__sub">{checked ? '—' : pick(SHEET.exposureNone, lang)}</span>
          )}
        </td>
      </tr>
      <tr className="wfgf-sheet__row-sweep">
        <td colSpan={6}>
          <SweepStrip s={s} lang={lang} />
        </td>
      </tr>
    </>
  );
}

function apiModeText(sheet: PlanSheetData, lang: Lang): string {
  const p = sheet.provenance;
  if (p.apiMode === 'mock') {
    // the MOCK evaluates no user zones and replays only recorded executions
    if (sheet.fireInputType === 'spread_zones') return pick(SHEET.modeMockZones, lang);
    return pick(p.mockNothingReplayed ? SHEET.modeMockNone : SHEET.modeMock, lang);
  }
  if (p.apiMode === 'live') return pick(SHEET.modeLive, lang);
  if (p.cacheApiMode) return fill(pick(SHEET.modeCacheOf, lang), { mode: p.cacheApiMode === 'mock' ? 'MOCK' : 'live API' });
  return pick(SHEET.modeCache, lang);
}

export function PlanSheet(props: PlanSheetProps) {
  const { sheet, lang, pageNumber, pageCount, mapActive, current, onMapSettled, forceSvgMap } = props;
  const t = (s: { ko: string; en: string }) => pick(s, lang);
  const regionName = lang === 'en' ? sheet.region.nameEn : sheet.region.nameKo;
  const alt = alternativePlanItems(sheet, lang);
  // checked scenarios with unresolved earlier departures always get a caveat line, whatever else
  // the section lists (never answer the heading "none" while a scenario needs a plan)
  const partial = partialCheckedScenarios(sheet);
  // dense pages (many scenarios, facilities and alternative plans) drop the table footnote and list
  // fewer facilities so the page still fits A4 with a readable map
  const dense = sheet.scenarios.length + Math.min(sheet.facilities.length, MAX_FACILITIES) + alt.length + partial.length >= 9;
  const facilities = sheet.facilities.slice(0, dense ? 3 : MAX_FACILITIES);
  const moreFacilities = sheet.facilities.length - facilities.length;
  const anyRoute = sheet.scenarios.some((s) => s.bestVerdict === 'checked_route' && s.route);
  const anyTravel = sheet.scenarios.some((s) => s.bestVerdict === 'checked_route' && s.route && s.travelOnlyRoute);
  const hosts = sheet.scenarios
    .map((s, i) => {
      if (s.computeS === null && !s.host) return null;
      const base = { inputTimeIso: s.inputTimeIso, issuedAtIso: s.issuedAtIso ?? null };
      const at = s.computeOffsetS !== null && s.computeOffsetS !== undefined ? ` · ${clockAt(base, s.computeOffsetS)}` : '';
      return `${scenarioTag(i)}${at} ${formatSeconds(s.computeS)}${s.host ? ` (${s.host})` : ''}`;
    })
    .filter(Boolean) as string[];
  const entry = entryFact(sheet, lang);

  return (
    <article
      className={`wfgf-sheet${dense ? ' wfgf-sheet--dense' : ''}`}
      data-sheet-origin={sheet.origin.id}
      data-region={sheet.region.id}
      data-input-time={sheet.scenarios[0]?.inputTimeIso ?? ''}
      data-mock={sheet.mock ? 'true' : 'false'}
      data-current={current ? 'true' : 'false'}
      aria-label={`${t(SHEET.docTitle)} — ${originTitle(sheet, lang)}`}
      lang={lang}
    >
      <header className="wfgf-sheet__head">
        <div className="wfgf-sheet__doc">
          <span className="wfgf-sheet__doctitle">{t(SHEET.docTitle)}</span>
          <span className="wfgf-sheet__dot" aria-hidden="true">
            ·
          </span>
          <span>{regionName}</span>
          <span className="wfgf-sheet__dot" aria-hidden="true">
            ·
          </span>
          <span className="wfgf-sheet__fire" data-fire-input="true">
            {sheet.fireInputLabel}
          </span>
          {sheet.mock && <MockBadge lang={lang} />}
        </div>
        <div className="wfgf-sheet__created">
          {t(SHEET.createdAt)} <span className="wfgf-num">{kstStamp(sheet.generatedAtIso)}</span>
        </div>
      </header>

      <section className="wfgf-sheet__titleblock">
        <div className="wfgf-sheet__titleline">
          <h1 className="wfgf-sheet__title">{originTitle(sheet, lang)}</h1>
          {originName(sheet, lang) && <span className="wfgf-sheet__cat">{sheet.origin.categoryLabel}</span>}
          {sheet.origin.vulnerable && <span className="wfgf-sheet__vuln">{t(SHEET.vulnerableOrigin)}</span>}
          {sheet.rsgLabel && (
            <span className="wfgf-sheet__rsg" title={t(SHEET.rsgTitle)} data-rsg="true">
              {sheet.rsgLabel}
            </span>
          )}
        </div>
        <dl className="wfgf-sheet__facts">
          <div>
            <dt>{t(SHEET.sourceTag)}</dt>
            <dd className="wfgf-sheet__tag">{sheet.origin.sourceTag}</dd>
          </div>
          <div>
            <dt>{t(SHEET.coords)}</dt>
            <dd className="wfgf-num">{formatCoord(sheet.origin.lon, sheet.origin.lat)}</dd>
          </div>
          <div data-entry-fact="true">
            <dt>{entry.label}</dt>
            <dd className="wfgf-num">{entry.value}</dd>
          </div>
        </dl>
      </section>

      <section className="wfgf-sheet__section">
        <h2>{t(SHEET.facilitiesTitle)}</h2>
        {facilities.length === 0 ? (
          <p className="wfgf-sheet__muted">{t(SHEET.facilitiesNone)}</p>
        ) : (
          <ul className="wfgf-sheet__facilities">
            {facilities.map((f) => (
              <li key={f.id}>
                <span className="wfgf-sheet__strong">{f.name || t(SHEET.unnamed)}</span>
                <span className="wfgf-sheet__muted">{f.categoryLabel}</span>
                <span className="wfgf-sheet__tag">{f.sourceTag}</span>
                <span className="wfgf-num wfgf-sheet__dist">{formatDistanceM(f.distanceM, lang)}</span>
              </li>
            ))}
            {moreFacilities > 0 && <li className="wfgf-sheet__muted">{fill(t(SHEET.facilitiesMore), { n: moreFacilities })}</li>}
          </ul>
        )}
      </section>

      <section className="wfgf-sheet__section">
        <h2>{t(SHEET.scenariosTitle)}</h2>
        <table className="wfgf-sheet__table">
          <colgroup>
            <col style={{ width: '33mm' }} />
            <col style={{ width: '27mm' }} />
            <col style={{ width: '24mm' }} />
            <col style={{ width: '37mm' }} />
            <col style={{ width: '12mm' }} />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">{t(SHEET.colScenario)}</th>
              <th scope="col">{t(SHEET.colVerdict)}</th>
              <th scope="col">{t(SHEET.colDeadline)}</th>
              <th scope="col">{t(SHEET.colShelter)}</th>
              <th scope="col">{t(SHEET.colArrival)}</th>
              <th scope="col">{t(SHEET.colExposure)}</th>
            </tr>
          </thead>
          <tbody>
            {sheet.scenarios.map((s, i) => (
              <ScenarioRows key={`${s.scenarioSetId}-${i}`} s={s} i={i} lang={lang} drawnSheet={sheet.fireInputType === 'spread_zones'} />
            ))}
          </tbody>
        </table>
        <div className="wfgf-sheet__legend" aria-label="legend">
          {(['checked_route', 'model_no_route', 'unresolved', 'window_closed'] as const).map((v) => (
            <span key={v}>
              <SweepCellGlyph verdict={v} width={10} height={10} />
              {v === 'window_closed' ? t(WINDOW_CLOSED_LABEL) : t(VERDICT_LABEL[v])}
            </span>
          ))}
        </div>
        {!dense && <p className="wfgf-sheet__note">{t(SHEET.tableNote)}</p>}
      </section>

      <section className="wfgf-sheet__section wfgf-sheet__mapsec">
        <h2>{t(SHEET.mapTitle)}</h2>
        <StaticRouteMap
          sheet={sheet}
          lang={lang}
          active={mapActive}
          widthMm={SHEET_MAP_MM.width}
          heightMm={SHEET_MAP_MM.height}
          fill
          onSettled={onMapSettled}
          forceFallback={forceSvgMap}
        />
        <div className="wfgf-sheet__maplegend">
          <span>
            <MapLegendGlyph kind="origin" />
            {t(SHEET.mapLegendOrigin)}
          </span>
          {anyRoute ? (
            <>
              <span>
                <MapLegendGlyph kind="checked" />
                {t(SHEET.mapLegendChecked)}
              </span>
              <span>
                <MapLegendGlyph kind="shelter" />
                {t(SHEET.mapLegendShelter)}
              </span>
              {anyTravel && (
                <span>
                  <MapLegendGlyph kind="travel_only" />
                  {t(SHEET.mapLegendTravel)}
                </span>
              )}
            </>
          ) : (
            <span className="wfgf-sheet__muted">{t(SHEET.mapNoRoute)}</span>
          )}
        </div>
      </section>

      <section className="wfgf-sheet__section wfgf-sheet__alt" data-alt-plan="true">
        <h2>{t(SHEET.altTitle)}</h2>
        {alt.length === 0 && partial.length === 0 ? (
          <p className="wfgf-sheet__muted" data-alt-none="true">
            {t(SHEET.altNone)}
          </p>
        ) : (
          <ul>
            {alt.map((a) => (
              <li key={`${a.scenarioSetId}-${a.index}`} data-alt-scenario={a.scenarioSetId} data-alt-verdict={a.verdict}>
                <VerdictIcon verdict={a.verdict} size={13} />
                <span className="wfgf-sheet__stag">{a.tag}</span>
                <span className="wfgf-num">{kstDateTime(a.issuedAtIso || a.inputTimeIso, 0)}</span>
                <span className="wfgf-sheet__strong">{t(VERDICT_LABEL[a.verdict])}</span>
                <span className="wfgf-sheet__alttext">
                  {a.text}
                  {a.reason ? <> ({t(SHEET.reason)}: <ReasonWithCode text={a.reason} />)</> : ''}
                </span>
              </li>
            ))}
            {partial.map((p) => (
              <li key={`caveat-${p.scenarioSetId}-${p.index}`} className="wfgf-sheet__altcaveat" data-alt-caveat={p.scenarioSetId} data-alt-verdict="unresolved">
                <VerdictIcon verdict="unresolved" size={13} />
                <span className="wfgf-sheet__alttext">{partialCheckedText(p, lang)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="wfgf-sheet__section wfgf-sheet__basis">
        <h2>{t(SHEET.basisTitle)}</h2>
        <div className="wfgf-sheet__basisgrid">
          <dl className="wfgf-sheet__prov">
            <div className="wfgf-sheet__prov-wide">
              <dt>{t(SHEET.pCheckpoint)}</dt>
              <dd className="wfgf-sheet__mono">{sheet.provenance.checkpoint || FIXED_IDENTITY.checkpoint}</dd>
            </div>
            <div>
              <dt>{t(SHEET.pPackage)}</dt>
              <dd>
                {FIXED_IDENTITY.packageName} {sheet.provenance.packageVersion} · kit {sheet.provenance.kit.replace(/^kit\s*/i, '')}
              </dd>
            </div>
            <div>
              <dt>{t(SHEET.pApi)}</dt>
              <dd>
                {apiModeText(sheet, lang)}
                {sheet.provenance.apiVersion ? ` · v${sheet.provenance.apiVersion.replace(/^v/, '')}` : ''}
              </dd>
            </div>
            {sheet.provenance.cacheCreatedAtIso && (
              <div>
                <dt>{t(SHEET.pCache)}</dt>
                <dd className="wfgf-num">{kstStamp(sheet.provenance.cacheCreatedAtIso)}</dd>
              </div>
            )}
            {hosts.length > 0 && (
              <div className="wfgf-sheet__prov-wide">
                <dt>{t(SHEET.pHost)}</dt>
                <dd className="wfgf-num">{hosts.join(' · ')}</dd>
              </div>
            )}
            {sheet.provenance.testData && (
              <div className="wfgf-sheet__prov-wide" data-test-data="true">
                <dt>{t(SHEET.pTestData)}</dt>
                <dd>{t(SHEET.testData)}</dd>
              </div>
            )}
            {sheet.provenance.approximation && (
              <div className="wfgf-sheet__prov-wide">
                <dt>{t(SHEET.pApprox)}</dt>
                <dd>{t(SHEET.approxGloss)} <span className="wfgf-muted" lang="en">(API: “{sheet.provenance.approximation}”)</span></dd>
              </div>
            )}
            {sheet.provenance.recordedMissionMatch && (
              <div>
                <dt>{t(SHEET.pMission)}</dt>
                <dd className="wfgf-sheet__mono">{sheet.provenance.recordedMissionMatch}</dd>
              </div>
            )}
            {sheet.provenance.gitCommit && (
              <div>
                <dt>{t(SHEET.pCommit)}</dt>
                <dd className="wfgf-sheet__mono">{sheet.provenance.gitCommit.slice(0, 12)}</dd>
              </div>
            )}
          </dl>
          <ul className="wfgf-sheet__limits">
            {LIMITATIONS.map((l) => (
              <li key={l.id} data-limit={l.id}>
                {t(l.short)}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="wfgf-sheet__foot">
        <span>{t(SHEET.footer)}</span>
        <span className="wfgf-num">{fill(t(SHEET.page), { n: pageNumber, total: pageCount })}</span>
      </footer>
    </article>
  );
}

/** Reason text with any API code "(MOCK_…)" moved into a small grey code, not running Korean prose. */
function ReasonWithCode({ text }: { text: string }) {
  const parts = text.split(/\s*\(([A-Z][A-Z0-9_]{3,})\)/g);
  return (
    <>
      {parts.map((p, i) => (i % 2 === 1 ? <span key={i} className="wfgf-sheet__code" title={p}> [{p}]</span> : <span key={i}>{p}</span>))}
    </>
  );
}
