// Pulsing flame glyph — used inline and as a Leaflet divIcon (HTML string).
// Animation is pure CSS (.flame-pulse keyframes in theme/tokens.css) and is
// fully disabled under prefers-reduced-motion.

const FLAME_BODY = (
  <>
    <path
      d="M20 4 C24 12 32 15 32 25 C32 33 27 38 20 38 C13 38 8 33 8 25 C8 19 11 16 13.5 12.8 C14.3 17.6 16.3 19.2 17.9 20 C16.7 13.6 17.9 9.2 20 4 Z"
      fill="#E25822"
    />
    <path
      d="M20 17 C22 21 26 23 26 28.6 C26 33 23.2 36.2 20 36.2 C16.8 36.2 14 33 14 28.6 C14 25 16 23 17.2 21 C17.6 23.4 18.8 24.6 19.6 25 C19 21.8 19.2 19.4 20 17 Z"
      fill="#FFD166"
    />
  </>
);

/** Inline React flame (legend, cards). */
export function FlamePulse({ size = 40 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      aria-hidden="true"
      className="wfg-flame-marker"
    >
      <g className="flame-pulse">{FLAME_BODY}</g>
    </svg>
  );
}

/** Raw HTML string of the same glyph, for L.divIcon on the map. */
export function flamePulseHtml(size = 40): string {
  return (
    `<svg width="${size}" height="${size}" viewBox="0 0 40 40" aria-hidden="true">` +
    `<g class="flame-pulse">` +
    `<path d="M20 4 C24 12 32 15 32 25 C32 33 27 38 20 38 C13 38 8 33 8 25 C8 19 11 16 13.5 12.8 C14.3 17.6 16.3 19.2 17.9 20 C16.7 13.6 17.9 9.2 20 4 Z" fill="#E25822"/>` +
    `<path d="M20 17 C22 21 26 23 26 28.6 C26 33 23.2 36.2 20 36.2 C16.8 36.2 14 33 14 28.6 C14 25 16 23 17.2 21 C17.6 23.4 18.8 24.6 19.6 25 C19 21.8 19.2 19.4 20 17 Z" fill="#FFD166"/>` +
    `</g></svg>`
  );
}
