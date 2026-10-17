/**
 * The sheet's 경로 지도: a static image of a MapLibre render (see staticMap.ts) or, without WebGL,
 * an inline SVG of the route geometry with a scale bar. Only checked routes are drawn; the
 * travel-only comparison is dashed and labelled as "not an evacuation route" in the legend.
 */
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject, type SyntheticEvent } from 'react';
import { pick, type Lang } from '../shared/strings';
import { COLORS } from '../shared/VerdictIcon';
import { drawableRoute, drawableTravelOnly, sheetBounds, sheetMapKey, sheetShelters } from './sheetLogic';
import { fitProjection, niceScale, renderStaticMap, webglAvailable, type StaticMapSpec } from './staticMap';
import { SHEET } from './strings';
import type { PlanSheetData } from './types';

const MM_TO_PX = 96 / 25.4;

export interface StaticRouteMapProps {
  sheet: PlanSheetData;
  lang: Lang;
  /** start rendering (the dialog activates the visible pages, or all pages before printing) */
  active: boolean;
  /** size used when the box cannot be measured (jsdom, hidden) */
  widthMm: number;
  heightMm: number;
  /** measure the box and fill it (the sheet lets the map take the page's remaining height) */
  fill?: boolean;
  /** called with true when the map is final (decoded image or SVG fallback), false if it must re-render */
  onSettled?: (originId: string, settled: boolean) => void;
  /** force the SVG fallback (tests, or no WebGL) */
  forceFallback?: boolean;
}

type MapState = { kind: 'pending' } | { kind: 'image'; url: string } | { kind: 'fallback' };

function buildSpec(sheet: PlanSheetData, widthPx: number, heightPx: number): StaticMapSpec | null {
  const bounds = sheetBounds(sheet);
  if (!bounds) return null;
  const checked: [number, number][][] = [];
  const travelOnly: [number, number][][] = [];
  for (const s of sheet.scenarios) {
    const r = drawableRoute(s);
    if (!r) continue;
    checked.push(r.geometry.coordinates.map((c) => [c[0]!, c[1]!] as [number, number]));
    const t = drawableTravelOnly(s);
    if (t) travelOnly.push(t.geometry.coordinates.map((c) => [c[0]!, c[1]!] as [number, number]));
  }
  return {
    key: sheetMapKey(sheet, widthPx, heightPx),
    regionId: sheet.region.id,
    widthPx,
    heightPx,
    pixelRatio: 2,
    bounds,
    checked,
    travelOnly,
    origin: Number.isFinite(sheet.origin.lon) ? [sheet.origin.lon, sheet.origin.lat] : null,
    shelters: sheetShelters(sheet).map((s) => [s.lon, s.lat] as [number, number]),
    pointZoom: 13,
  };
}

/** Legend glyphs matching the map symbology (inline SVG, no gradients). */
export function MapLegendGlyph({ kind }: { kind: 'origin' | 'shelter' | 'checked' | 'travel_only' }) {
  if (kind === 'origin') {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="4.6" fill={COLORS.ink} stroke="#fff" strokeWidth="1.4" />
      </svg>
    );
  }
  if (kind === 'shelter') {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="4.4" fill="#fff" stroke={COLORS.accent} strokeWidth="2" />
        <circle cx="6" cy="6" r="1.5" fill={COLORS.accentHover} />
      </svg>
    );
  }
  if (kind === 'checked') {
    return (
      <svg width="26" height="8" viewBox="0 0 26 8" aria-hidden="true">
        <path d="M2 4H24" stroke={COLORS.accent} strokeWidth="3.4" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg width="26" height="8" viewBox="0 0 26 8" aria-hidden="true">
      <path d="M1 4H25" stroke={COLORS.ink} strokeOpacity="0.6" strokeWidth="1.8" strokeDasharray="4.5 3" />
    </svg>
  );
}

export function RouteSvg({ spec, lang }: { spec: StaticMapSpec; lang: Lang }) {
  const W = spec.widthPx;
  const H = spec.heightPx;
  const proj = fitProjection(spec.bounds, W, H, 28);
  const path = (coords: [number, number][]) =>
    coords
      .map((c, i) => {
        const [x, y] = proj.project(c[0], c[1]);
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join('');
  const scale = niceScale(proj.metresPerPx, W * 0.18);
  const o = spec.origin ? proj.project(spec.origin[0], spec.origin[1]) : null;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      height="100%"
      role="img"
      aria-label={pick(SHEET.mapFallback, lang)}
      data-map-fallback="svg"
      preserveAspectRatio="xMidYMid meet"
    >
      <rect x="0" y="0" width={W} height={H} fill={COLORS.surface} />
      {spec.travelOnly.map((c, i) => (
        <path key={`t${i}`} d={path(c)} fill="none" stroke={COLORS.ink} strokeOpacity="0.6" strokeWidth="2" strokeDasharray="6 4" strokeLinejoin="round" />
      ))}
      {spec.checked.map((c, i) => (
        <g key={`c${i}`}>
          <path d={path(c)} fill="none" stroke="#fff" strokeWidth="7" strokeLinejoin="round" strokeLinecap="round" />
          <path d={path(c)} fill="none" stroke={COLORS.accent} strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" />
        </g>
      ))}
      {spec.shelters.map((s, i) => {
        const [x, y] = proj.project(s[0], s[1]);
        return (
          <g key={`s${i}`}>
            <circle cx={x} cy={y} r="7" fill="#fff" stroke={COLORS.accent} strokeWidth="3" />
            <circle cx={x} cy={y} r="2.4" fill={COLORS.accentHover} />
          </g>
        );
      })}
      {o && <circle cx={o[0]} cy={o[1]} r="6.5" fill={COLORS.ink} stroke="#fff" strokeWidth="2.5" />}
      <g transform={`translate(${16} ${H - 18})`}>
        <rect x="-6" y="-16" width={scale.px + 12 + 46} height="26" rx="6" fill="#fff" opacity="0.92" />
        <path d={`M0 0V-5M0 0H${scale.px}V-5`} fill="none" stroke={COLORS.ink} strokeWidth="1.5" />
        <text x={scale.px + 8} y="1" fontSize="11" fill={COLORS.ink} style={{ fontVariantNumeric: 'tabular-nums' }}>
          {scale.label}
        </text>
      </g>
      <g transform={`translate(${W - 26} 26)`} aria-hidden="true">
        <circle r="13" fill="#fff" opacity="0.92" />
        <path d="M0 -8L4.5 5L0 2L-4.5 5Z" fill={COLORS.ink} />
      </g>
      <text x={W - 12} y={H - 10} textAnchor="end" fontSize="10.5" fill={COLORS.secondary}>
        {pick(SHEET.mapFallback, lang)}
      </text>
    </svg>
  );
}

/** Measured box size in px, rounded to 8 px so small reflows do not re-render the map. */
function useBoxSize(ref: RefObject<HTMLDivElement | null>, enabled: boolean): { w: number; h: number } | null {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!enabled || !el) return undefined;
    const measure = () => {
      const w = Math.round(el.clientWidth / 8) * 8;
      const h = Math.round(el.clientHeight / 8) * 8;
      if (w > 0 && h > 0) setSize((prev) => (prev && prev.w === w && prev.h === h ? prev : { w, h }));
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, enabled]);
  return size;
}

export function StaticRouteMap(props: StaticRouteMapProps) {
  const { sheet, lang, active, widthMm, heightMm, fill = false, forceFallback } = props;
  const boxRef = useRef<HTMLDivElement>(null);
  const measured = useBoxSize(boxRef, fill);
  const widthPx = measured?.w ?? Math.round(widthMm * MM_TO_PX);
  const heightPx = measured?.h ?? Math.round(heightMm * MM_TO_PX);
  // with `fill`, wait for the measurement (if layout gives one) before rendering
  const sizeKnown = !fill || measured !== null || typeof ResizeObserver === 'undefined';
  const spec = useMemo(() => buildSpec(sheet, widthPx, heightPx), [sheet, widthPx, heightPx]);
  const [state, setState] = useState<MapState>({ kind: 'pending' });
  const settledRef = useRef(false);
  const onSettledRef = useRef(props.onSettled);
  onSettledRef.current = props.onSettled;
  const key = spec?.key ?? null;

  useEffect(() => {
    setState({ kind: 'pending' });
    if (settledRef.current) {
      settledRef.current = false;
      onSettledRef.current?.(sheet.origin.id, false);
    }
  }, [key, sheet.origin.id]);

  useEffect(() => {
    if (!spec || !active || !sizeKnown || state.kind !== 'pending') return undefined;
    if (forceFallback || !webglAvailable()) {
      setState({ kind: 'fallback' });
      return undefined;
    }
    let alive = true;
    renderStaticMap(spec).then(
      (url) => alive && setState({ kind: 'image', url }),
      (err) => {
        if (!alive) return;
        console.warn('[plansheet] static map failed, using SVG fallback:', err);
        setState({ kind: 'fallback' });
      },
    );
    return () => {
      alive = false;
    };
  }, [spec, active, sizeKnown, state.kind, forceFallback]);

  const settle = () => {
    if (settledRef.current) return;
    settledRef.current = true;
    onSettledRef.current?.(sheet.origin.id, true);
  };

  useEffect(() => {
    // no geometry at all, or the SVG fallback: final immediately (images settle on decode below)
    if (!spec || state.kind === 'fallback') settle();
  });

  const onImgLoad = (e: SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const done = () => settle();
    if (typeof img.decode === 'function') img.decode().then(done, done);
    else done();
  };

  return (
    <div
      ref={boxRef}
      className={`wfgf-sheetmap${fill ? ' wfgf-sheetmap--fill' : ''}`}
      style={fill ? undefined : { width: `${widthMm}mm`, height: `${heightMm}mm` }}
      data-map-state={spec ? state.kind : 'none'}
    >
      {!spec && <div className="wfgf-sheetmap__empty">—</div>}
      {spec && state.kind === 'image' && (
        <>
          <img src={state.url} alt={pick(SHEET.mapTitle, lang)} width={widthPx} height={heightPx} draggable={false} decoding="sync" onLoad={onImgLoad} onError={() => setState({ kind: 'fallback' })} />
          <span className="wfgf-sheetmap__attr">{pick(SHEET.mapAttribution, lang)}</span>
        </>
      )}
      {spec && state.kind === 'fallback' && <RouteSvg spec={spec} lang={lang} />}
      {spec && state.kind === 'pending' && <div className="wfgf-sheetmap__loading">{pick(SHEET.mapLoading, lang)}</div>}
    </div>
  );
}
