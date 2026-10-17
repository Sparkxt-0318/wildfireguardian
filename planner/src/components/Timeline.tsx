import { useRef, useState, type KeyboardEvent } from 'react';
import { formatElapsed, formatOffsetMinutes, formatRelative, kstClock } from '../domain/clock';
import type { OriginPlan, Place, SweepCell } from '../domain/types';
import { secondsSinceIssue } from '../domain/zones';
import { useLang, useT } from '../i18n';
import type { CellProgress } from '../state/store';
import { placeName, reasonText, rawStatusText } from './format';
import { VerdictIcon, WindowIcon } from './Icons';

type CellLook = 'checked_route' | 'model_no_route' | 'unresolved' | 'window' | 'pending' | 'running';

function lookOf(cell: SweepCell, progress: CellProgress | undefined): CellLook {
  if (progress === 'running') return 'running';
  if (progress === 'pending') return 'pending';
  if (cell.skipped) return 'window';
  return cell.verdict;
}

interface TipState {
  cell: SweepCell;
  x: number;
  y: number;
}

export function Timeline({
  plan,
  inputTime,
  issuedAt = null,
  selectedOffsetS,
  progress,
  places,
  onSelect,
}: {
  plan: OriginPlan;
  inputTime: string;
  /** drawn zones: issue time of the zone forecast (tooltips add "발표 후 T+h:mm") */
  issuedAt?: string | null;
  selectedOffsetS: number | null;
  progress: Record<number, CellProgress> | null;
  places: Map<string, Place>;
  onSelect: (offsetS: number) => void;
}) {
  const t = useT();
  const lang = useLang();
  const [tip, setTip] = useState<TipState | null>(null);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const cells = plan.sweep;
  const showEvery = cells.length > 12 ? 2 : 1;

  const show = (cell: SweepCell, el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    setTip({ cell, x: Math.min(r.left + r.width / 2, window.innerWidth - 150), y: r.top });
  };

  const onKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    let j = i;
    if (e.key === 'ArrowRight') j = Math.min(cells.length - 1, i + 1);
    else if (e.key === 'ArrowLeft') j = Math.max(0, i - 1);
    else if (e.key === 'Home') j = 0;
    else if (e.key === 'End') j = cells.length - 1;
    else return;
    e.preventDefault();
    refs.current[j]?.focus();
  };

  const tipLines = (cell: SweepCell): string[] => {
    const lines: string[] = [];
    if (cell.skipped) {
      lines.push(cell.skipped === 'window_unsatisfiable' ? t('timeline.tip.window') : `${t('verdict.unresolved')} · ${cell.skipped}`);
      return lines;
    }
    if (cell.attempts.length === 0) {
      lines.push(t('timeline.tip.notComputed'));
      return lines;
    }
    const best = cell.best;
    const computes = cell.attempts.map((a) => a.computeS).filter((x): x is number => x !== null);
    if (best) {
      const dest = places.get(best.destinationId);
      lines.push(t('timeline.tip.shelter', { name: dest ? placeName(dest, t, lang) : best.destinationId }));
      if (best.arrivalS !== null) {
        lines.push(t('timeline.tip.arrival', { time: kstClock(inputTime, best.arrivalS, { seconds: true }), elapsed: formatElapsed(best.arrivalS - cell.offsetS, lang) }));
      }
      if (cell.attempts.length > 1) lines.push(t('timeline.tip.attempts', { n: cell.attempts.length }));
    } else {
      lines.push(t('timeline.tip.attempts', { n: cell.attempts.length }));
      const reasons = [...new Set(cell.attempts.map((a) => reasonText(a.reasonCode, t) ?? rawStatusText(a.rawStatus, t)).filter(Boolean))];
      for (const r of reasons.slice(0, 2)) lines.push(t('timeline.tip.reason', { code: r! }));
    }
    if (computes.length) lines.push(t('timeline.tip.compute', { s: computes.map((c) => c.toFixed(1)).join(' / ') }));
    return lines;
  };

  return (
    <div className="section" data-testid="timeline">
      <div className="timeline" role="toolbar" aria-label={t('timeline.title')}>
        {cells.map((cell, i) => {
          const look = lookOf(cell, progress?.[cell.offsetS]);
          const label = `${kstClock(inputTime, cell.offsetS)} ${look === 'window' ? t('verdict.window') : look === 'pending' || look === 'running' ? t('verdict.pending') : t(`verdict.${cell.verdict}`)}`;
          return (
            <button
              key={cell.offsetS}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              className={`tl-cell ${look}`}
              aria-pressed={selectedOffsetS === cell.offsetS}
              aria-label={label}
              onClick={() => onSelect(cell.offsetS)}
              onMouseEnter={(e) => show(cell, e.currentTarget)}
              onMouseLeave={() => setTip(null)}
              onFocus={(e) => show(cell, e.currentTarget)}
              onBlur={() => setTip(null)}
              onKeyDown={(e) => onKey(e, i)}
              data-testid={`tl-${cell.offsetS}`}
            >
              {look === 'window' ? (
                <WindowIcon size={14} />
              ) : look === 'pending' || look === 'running' ? (
                <span style={{ width: 6, height: 6, borderRadius: 3, background: 'currentColor' }} />
              ) : (
                <VerdictIcon verdict={cell.verdict} size={16} color={cell.verdict === 'unresolved' ? '#3A3A3E' : '#FFFFFF'} />
              )}
            </button>
          );
        })}
      </div>
      <div className="tl-labels" aria-hidden="true">
        {cells.map((c, i) => (
          <span key={c.offsetS} className={c.offsetS === plan.latestSafeDepartureS ? 'deadline' : ''}>
            {i % showEvery === 0 || c.offsetS === plan.latestSafeDepartureS ? kstClock(inputTime, c.offsetS) : ''}
          </span>
        ))}
      </div>
      <div className="tl-legend">
        <span>
          <i className="checked_route" />
          {t('verdict.checked_route')}
        </span>
        <span>
          <i className="model_no_route" />
          {t('verdict.model_no_route')}
        </span>
        <span>
          <i className="unresolved" />
          {t('verdict.unresolved')}
        </span>
        <span>
          <i className="window" />
          {t('verdict.window')}
        </span>
      </div>
      {tip ? (
        <div className="tooltip" role="tooltip" style={{ left: tip.x, top: tip.y - 8, transform: 'translate(-50%, -100%)' }}>
          <b className="tnum">
            {t('timeline.tip.offset', { time: kstClock(inputTime, tip.cell.offsetS), rel: formatOffsetMinutes(tip.cell.offsetS, lang) })}
          </b>
          {issuedAt ? <span className="tnum">{t('drawn.clock.rel', { rel: formatRelative(secondsSinceIssue(inputTime, issuedAt, tip.cell.offsetS)) })}</span> : null}
          <span>{tip.cell.skipped ? t('verdict.window') : t(`verdict.${tip.cell.verdict}`)}</span>
          {tipLines(tip.cell).map((l, i) => (
            <span key={i} className="tnum" style={{ color: '#D0D0D4' }}>
              {l}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
