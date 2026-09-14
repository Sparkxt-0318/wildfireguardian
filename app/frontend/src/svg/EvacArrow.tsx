// Evacuation arrow with a marching dashed shaft (legend + route affordances).
// CSS animation (.march, tokens.css) — disabled under prefers-reduced-motion.

export function EvacArrow({ size = 48 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={(size * 24) / 48}
      viewBox="0 0 48 24"
      aria-hidden="true"
      className="evac-arrow"
    >
      <path
        className="march"
        d="M4 12 L34 12"
        fill="none"
        stroke="#1C5CAB"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path d="M32 4 L44 12 L32 20 Z" fill="#1C5CAB" />
    </svg>
  );
}

/** Rotatable arrowhead HTML for map pathway tips (L.divIcon). */
export function arrowheadHtml(bearingDeg: number, size = 26): string {
  // SVG triangle points up (north); rotate clockwise by bearing.
  return (
    `<svg width="${size}" height="${size}" viewBox="0 0 26 26" aria-hidden="true" class="wfg-arrowhead" style="transform: rotate(${bearingDeg}deg)">` +
    `<path d="M13 2 L23 22 L13 17 L3 22 Z" fill="#B91C1C" stroke="#FFFFFF" stroke-width="1.5"/>` +
    `</svg>`
  );
}
