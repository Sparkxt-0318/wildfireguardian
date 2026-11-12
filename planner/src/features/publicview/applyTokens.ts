/** Sets the CSS variables of publicview.css from tokens.ts (CSSOM; no inline <style>, CSP-compatible). */
import { DARK, LIGHT, SIZE, type Theme } from './tokens';

export function tokenVars(t: Theme): Record<string, string> {
  return {
    '--pv-bg': t.bg, '--pv-text': t.text, '--pv-muted': t.muted,
    '--pv-banner-bg': t.banner.bg, '--pv-banner-text': t.banner.text,
    '--pv-official-bg': t.official.bg, '--pv-official-text': t.official.text,
    '--pv-leave': t.tone.leave.accent, '--pv-stop': t.tone.stop.accent, '--pv-unknown': t.tone.unknown.accent,
    '--pv-base': `${SIZE.base}px`, '--pv-words': `${SIZE.words}px`, '--pv-time': `${SIZE.time}px`,
    '--pv-age': `${SIZE.dataAge}px`, '--pv-stamp': `${SIZE.stamp}px`, '--pv-question': `${SIZE.question}px`,
  };
}

export function applyTokens(root: HTMLElement, dark: boolean): void {
  for (const [k, v] of Object.entries(tokenVars(dark ? DARK : LIGHT))) root.style.setProperty(k, v);
  root.style.background = (dark ? DARK : LIGHT).bg;
}
