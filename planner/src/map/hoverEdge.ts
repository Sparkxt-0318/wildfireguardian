/** Edge classes that keep the hover card inside the map (card is ~2 lines, up to ~340 px wide). */
export function hoverEdgeClass(p: { x: number; y: number }, width: number): string {
  let c = p.x > width - 170 ? ' edge-right' : p.x < 170 ? ' edge-left' : '';
  if (p.y < 64) c += ' edge-top';
  return c;
}
