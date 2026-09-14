// Drifting wind chevrons. Rotated to the direction the wind is blowing
// TOWARD (rotation supplied by the caller from API data). CSS animation
// (.drift, tokens.css) — disabled under prefers-reduced-motion.

export function WindArrows({
  size = 48,
  rotateDeg = 0,
}: {
  size?: number;
  /** Degrees clockwise from north — direction the wind is blowing toward. */
  rotateDeg?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-hidden="true"
      className="wind-arrows"
    >
      {/* chevrons drawn pointing right (east); rotate -90 puts them north-up */}
      <g transform={`rotate(${rotateDeg - 90} 24 24)`}>
        <g className="drift">
          <path
            d="M10 14 L18 24 L10 34"
            fill="none"
            stroke="#2A78D6"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M22 14 L30 24 L22 34"
            fill="none"
            stroke="#2A78D6"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.6"
          />
          <path
            d="M34 14 L42 24 L34 34"
            fill="none"
            stroke="#2A78D6"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.3"
          />
        </g>
      </g>
    </svg>
  );
}
