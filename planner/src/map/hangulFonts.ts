/**
 * Waits until the Pretendard aliases for the basemap font stacks (styles/map-hangul-fonts.css) are loaded, so
 * MapLibre's client-side Hangul glyphs are drawn with them from the first frame. MapLibre caches each glyph
 * once drawn, so drawing before the font is ready would keep a fallback font for the session. Never blocks
 * longer than `timeoutMs`; on failure the browser's Korean fallback font is used.
 */
const STACKS = ['Noto Sans Regular', 'Noto Sans Medium', 'Noto Sans Italic'];

export async function loadHangulMapFonts(timeoutMs = 4000): Promise<void> {
  if (typeof document === 'undefined' || !document.fonts?.load) return;
  const load = Promise.all(STACKS.map((f) => document.fonts.load(`16px '${f}'`, '가나다'))).then(() => undefined);
  const timeout = new Promise<void>((resolve) => setTimeout(resolve, timeoutMs));
  try {
    await Promise.race([load, timeout]);
  } catch {
    /* fall back to system Korean fonts */
  }
}
