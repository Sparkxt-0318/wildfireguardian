/**
 * P-PROTO at 320 CSS px (≈ a phone at 200% zoom) in Chromium: the cards with the LONGEST place name and the LONGEST time
 * string in the caches (plus a synthetic cross-midnight time) never push the in-card replay stamp out of view and never
 * scroll horizontally (Iris). Rendered with the page's own CSS and token variables, with the bundled Pretendard font and
 * again with system fallback fonts. Skipped only when Playwright / Chromium is unavailable.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { tokenVars } from '../../planner/src/features/publicview/applyTokens';
import { cardFor, pick, type PublicCard } from '../../planner/src/features/publicview/model';
import { LIGHT } from '../../planner/src/features/publicview/tokens';
import type { LastMileInput } from '../../planner/src/features/lastmile/types';
import { loadBoothCaches } from './lastmile.cachedata';
import { generateCases } from './lastmile.generator';
import { synInput } from './lastmile.fixture';

const PLANNER = new URL('../../planner/', import.meta.url);
const req = createRequire(new URL('package.json', PLANNER));
const React = req('react') as { createElement: (t: unknown, p?: Record<string, unknown>) => unknown };
const { renderToStaticMarkup } = req('react-dom/server') as { renderToStaticMarkup: (el: unknown) => string };

type Page = { setContent: (h: string, o?: Record<string, unknown>) => Promise<void>; evaluate: <T>(fn: string) => Promise<T>; close: () => Promise<void> };
type Browser = { newPage: (o?: Record<string, unknown>) => Promise<Page>; close: () => Promise<void> };
let browser: Browser | null = null;
let skip = '';
let Card: unknown;
let worst: { label: string; card: PublicCard }[] = [];

function loadPw(): { chromium: { launch: (o?: Record<string, unknown>) => Promise<Browser> } } | null {
  const tries = [process.env.PLAYWRIGHT_MODULE, 'playwright'].filter(Boolean) as string[];
  try {
    tries.push(`${execFileSync('npm', ['root', '-g'], { encoding: 'utf8', timeout: 10_000 }).trim()}/playwright`);
  } catch {
    /* no npm */
  }
  for (const t of tries) {
    try {
      return req(t) as ReturnType<typeof loadPw>;
    } catch {
      /* next */
    }
  }
  return null;
}

beforeAll(async () => {
  Card = ((await import(/* @vite-ignore */ '../../planner/src/features/publicview/PublicView')) as { Card: unknown }).Card;
  const inputs: LastMileInput[] = [...loadBoothCaches().flatMap((c) => c.inputs), ...generateCases(20261102, 600).map((g) => g.input)];
  const cards = inputs.map((i) => cardFor(i, () => ({ lat: 36.5, lon: 129.4 })));
  const by = (f: (c: PublicCard) => number) => cards.reduce((a, b) => (f(b) > f(a) ? b : a));
  const midnight = cardFor(synInput({ scenario: { ...synInput().scenario, inputTimeIso: '2025-03-24T14:45:00Z' } }));
  worst = [
    { label: 'longest place name (ko)', card: by((c) => c.place.ko.length) },
    { label: 'longest place name (en)', card: by((c) => c.place.en.length) },
    { label: 'longest time string', card: by((c) => (c.time ? c.time.ko.length + c.time.en.length : -1)) },
    { label: 'longest words', card: by((c) => c.words.ko.length) },
    { label: 'cross-midnight time', card: midnight },
  ];
  const pw = loadPw();
  if (!pw) {
    skip = 'Playwright is not installed';
    return;
  }
  try {
    browser = await pw.chromium.launch({ headless: true });
  } catch (e) {
    skip = `Chromium could not start: ${String(e).split('\n')[0]}`;
  }
}, 300_000);

afterAll(async () => {
  await browser?.close();
});

function html(cards: PublicCard[], lang: 'ko' | 'en', withFont: boolean): string {
  const css = readFileSync(new URL('src/features/publicview/publicview.css', PLANNER), 'utf8');
  const vars = Object.entries(tokenVars(LIGHT)).map(([k, v]) => `${k}:${v};`).join('');
  const font = withFont
    ? `@font-face{font-family:'Pretendard';src:url(data:font/woff2;base64,${readFileSync(new URL('node_modules/pretendard/dist/web/variable/woff2/PretendardVariable.woff2', PLANNER)).toString('base64')}) format('woff2-variations');}`
    : '';
  const body = cards.map((c) => renderToStaticMarkup(React.createElement(Card, { card: c, lang, example: false }))).join('');
  return `<!doctype html><html lang="${lang}"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${font}:root{${vars}}body{margin:0}${css}</style></head><body><div class="pv-root">${body}</div></body></html>`;
}

describe('320 px layout in Chromium (Iris)', () => {
  for (const withFont of [true, false]) {
    for (const lang of ['ko', 'en'] as const) {
      it(`${withFont ? 'Pretendard' : 'fallback fonts'}, ${lang}: no horizontal scroll; every stamp, time and data age fully inside the viewport and inside its card`, async () => {
        if (!browser) {
          console.warn(`skipped: ${skip}`);
          return;
        }
        const page = await browser.newPage({ viewport: { width: 320, height: 2400 } });
        await page.setContent(html(worst.map((w) => w.card), lang, withFont), { waitUntil: 'load' });
        await page.evaluate('document.fonts.ready');
        const r = await page.evaluate<{ scrollW: number; bad: string[]; n: number }>(`(() => {
          const bad = [];
          const vw = document.documentElement.clientWidth;
          const cards = [...document.querySelectorAll('article[data-pv="card"]')];
          for (const [i, c] of cards.entries()) {
            const cb = c.getBoundingClientRect();
            for (const sel of ['[data-pv="stamp"]', '[data-pv="time"]', '[data-pv="time-stamp"]', '[data-pv="age"]']) {
              const e = c.querySelector(sel);
              if (!e) continue;
              const b = e.getBoundingClientRect();
              if (b.width === 0 || b.height === 0) bad.push(i + ' ' + sel + ' invisible');
              if (b.left < -0.5 || b.right > vw + 0.5) bad.push(i + ' ' + sel + ' outside viewport ' + b.left.toFixed(1) + '..' + b.right.toFixed(1));
              if (b.left < cb.left - 0.5 || b.right > cb.right + 0.5 || b.top < cb.top - 0.5 || b.bottom > cb.bottom + 0.5) bad.push(i + ' ' + sel + ' outside its card');
            }
          }
          for (const e of document.querySelectorAll('*')) { const b = e.getBoundingClientRect(); if (b.right > vw + 0.5) bad.push('WIDE ' + e.tagName + '.' + e.className + ' ' + b.right.toFixed(0) + ' ' + (e.textContent || '').slice(0, 40)); }
          return { scrollW: document.documentElement.scrollWidth, bad, n: cards.length };
        })()`);
        await page.close();
        expect(r.n).toBe(worst.length);
        expect(r.bad, worst.map((w, i) => `${i}: ${w.label} = ${pick(w.card.place, lang)}`).join(' | ')).toEqual([]);
        expect(r.scrollW).toBeLessThanOrEqual(320);
      }, 120_000);
    }
  }
});
