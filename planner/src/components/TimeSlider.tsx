/**
 * Time slider docked at the map bottom: the scenario clock 0…horizon_s in 1-minute steps with
 * ticks at the departure offsets (KST labels), play/pause, and chips that jump between the
 * region's recorded input times.
 */
import { useEffect, useMemo, useRef } from 'react';
import { formatRelative, kstClock, kstDate } from '../domain/clock';
import { useT } from '../i18n';
import { selectScenario, setClock, setPlaying } from '../state/controller';
import { useClockBase, useCurrentScenarioSet, useHorizon, useRoute, useScenarioSets, useSelectedPlan, useShownAttempt } from '../state/selectors';
import { DRAWN_SCENARIO, getState, useStore } from '../state/store';
import { secondsSinceIssue } from '../domain/zones';
import { kstDateTime } from '../domain/clock';
import { ChevronIcon, PauseIcon, PlayIcon } from './Icons';

/** Scenario seconds advanced per real second while playing. */
const PLAY_RATE = 90;

export function TimeSlider() {
  const t = useT();
  const set = useCurrentScenarioSet();
  const sets = useScenarioSets();
  const horizon = useHorizon();
  const clockS = useStore((s) => s.clockS);
  const playing = useStore((s) => s.playing);
  const scenarioId = useStore((s) => s.scenarioId);
  const plan = useSelectedPlan();
  const { attempt } = useShownAttempt();
  const route = useRoute(attempt?.jobId);
  const clock = useClockBase();
  const raf = useRef<number | null>(null);

  const offsets = useMemo(() => (plan ? plan.sweep.map((c) => c.offsetS) : []), [plan]);
  const gridTicks = useMemo(() => {
    const out: number[] = [];
    for (let s = 0; s <= horizon; s += 600) out.push(s);
    return out;
  }, [horizon]);

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      const cur = getState().clockS;
      const next = Math.min(horizon, cur + dt * PLAY_RATE);
      setClock(next);
      if (next >= horizon) {
        setPlaying(false);
        return;
      }
      raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
    };
  }, [playing, horizon]);

  const drawn = scenarioId === DRAWN_SCENARIO;
  const baseTime = drawn ? clock.inputTime : set?.inputTime ?? null;
  if (!baseTime) {
    return (
      <div className="slider-dock">
        <div className="slider-row">
          <span className="small-note">{t('slider.clock')} —</span>
        </div>
      </div>
    );
  }
  const idx = set ? sets.findIndex((s) => s.id === set.id) : -1;
  const vehicle = route?.timesS?.length
    ? clockS < route.timesS[0]!
      ? t('slider.vehicle.waiting')
      : clockS >= route.timesS[route.timesS.length - 1]!
        ? t('slider.vehicle.arrived')
        : t('slider.vehicle.driving')
    : null;
  const pct = (s: number) => `${(Math.max(0, Math.min(horizon, s)) / horizon) * 100}%`;
  return (
    <div className="slider-dock" data-testid="time-slider">
      <div className="slider-row">
        <button
          type="button"
          className="play-btn"
          aria-label={playing ? t('slider.pause') : t('slider.play')}
          onClick={() => {
            if (!playing && clockS >= horizon) setClock(0);
            setPlaying(!playing);
          }}
        >
          {playing ? <PauseIcon size={14} /> : <PlayIcon size={14} />}
        </button>
        <div className="clock">
          <span className="big">{kstClock(baseTime, clockS)} KST</span>
          <span className="small">
            {kstDate(baseTime, clockS)} · {drawn && clock.issuedAt ? t('drawn.clock.rel', { rel: formatRelative(secondsSinceIssue(baseTime, clock.issuedAt, clockS)) }) : formatRelative(clockS)}
          </span>
        </div>
        <div className="track">
          <input
            type="range"
            min={0}
            max={horizon}
            step={60}
            value={Math.round(clockS / 60) * 60}
            aria-label={t('slider.clock')}
            aria-valuetext={`${kstClock(baseTime, clockS)} KST`}
            onChange={(e) => {
              setPlaying(false);
              setClock(Number(e.target.value));
            }}
          />
          <div className="ticks" aria-hidden="true">
            {gridTicks.map((s) => (
              <span key={`g${s}`} className="tick" style={{ left: pct(s) }}>
                <i />
                {kstClock(baseTime, s)}
              </span>
            ))}
            {offsets
              .filter((s) => !gridTicks.includes(s))
              .map((s) => (
                <span key={`o${s}`} className="tick dep" style={{ left: pct(s) }}>
                  <i />
                </span>
              ))}
            {plan?.latestSafeDepartureS !== null && plan?.latestSafeDepartureS !== undefined ? (
              <span className="tick deadline" style={{ left: pct(plan.latestSafeDepartureS) }}>
                <i />
              </span>
            ) : null}
          </div>
        </div>
      </div>
      {drawn ? (
        <div className="input-chips">
          <span>{t('slider.drawnBase', { input: kstDateTime(baseTime), issued: clock.issuedAt ? kstDateTime(clock.issuedAt) : '—' })}</span>
          {vehicle ? <span className="vehicle-state">{t('slider.vehicle', { state: vehicle })}</span> : null}
        </div>
      ) : (
      <div className="input-chips">
        <span>{t('slider.recorded')}</span>
        <button type="button" className="btn btn-ghost" style={{ height: 24, padding: '0 4px' }} aria-label={t('slider.prev')} disabled={idx <= 0} onClick={() => idx > 0 && void selectScenario(sets[idx - 1]!.id)}>
          <ChevronIcon dir="left" size={12} />
        </button>
        {sets.map((s) => (
          <button key={s.id} type="button" className="chip tnum" aria-pressed={s.id === set?.id} onClick={() => void selectScenario(s.id)}>
            {kstDate(s.inputTime).slice(5)} {kstClock(s.inputTime, 0)}
          </button>
        ))}
        <button type="button" className="btn btn-ghost" style={{ height: 24, padding: '0 4px' }} aria-label={t('slider.next')} disabled={idx < 0 || idx >= sets.length - 1} onClick={() => idx < sets.length - 1 && void selectScenario(sets[idx + 1]!.id)}>
          <ChevronIcon dir="right" size={12} />
        </button>
        {vehicle ? <span className="vehicle-state">{t('slider.vehicle', { state: vehicle })}</span> : null}
      </div>
      )}
    </div>
  );
}
