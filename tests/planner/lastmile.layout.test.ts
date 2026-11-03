/**
 * The "현장 전달 문구 / Field messages" dialog at phone width, in Chromium. The real component is
 * rendered in a local jsdom (as in lastmile.render.test.ts) for every booth cache, with the scenario's
 * explanation file: the first origin of each message kind, Korean and English UI. Every dialog is then
 * laid out with the app's style sheets and the bundled Pretendard font at 375 px and 320 px wide.
 * Nothing may make the dialog, its head, body or foot scroll sideways or reach past the screen edge.
 * The card preview is the exception: it scrolls inside its own box. The origin picker (a <select> as
 * wide as its longest option) used to widen the dialog's one-column grid, so text was cut at the
 * right edge on a phone.
 *
 * Runs when Playwright with Chromium is installed, as lastmile.print.test.ts does (PLAYWRIGHT_MODULE,
 * the planner's node_modules or the global npm root; not a planner dependency); skipped otherwise.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { buildFieldMessages } from '../../planner/src/features/lastmile/messages';
import { loadBoothCaches, realExplanationFor } from './lastmile.cachedata';

const PLANNER = new URL('../../planner/', import.meta.url);
const req = createRequire(new URL('package.json', PLANNER));
const { JSDOM } = req('jsdom') as { JSDOM: new (html?: string, opts?: Record<string, unknown>) => { window: Window & typeof globalThis } };

const WIDTHS = [375, 320] as const;
const STYLES = ['src/styles/app.css', 'src/styles/mobile.css', 'src/features/shared/features.css', 'src/features/lastmile/lastmile.css'];

type Page = {
  setContent: (html: string, o?: Record<string, unknown>) => Promise<void>;
  evaluate: <T>(fn: string) => Promise<T>;
  close: () => Promise<void>;
};
type Browser = { newPage: (o?: Record<string, unknown>) => Promise<Page>; close: () => Promise<void> };
type Pw = { chromium: { launch: (o?: Record<string, unknown>) => Promise<Browser> } };

function loadPlaywright(): Pw | null {
  const tries: string[] = [];
  if (process.env.PLAYWRIGHT_MODULE) tries.push(process.env.PLAYWRIGHT_MODULE);
  tries.push('playwright');
  try {
    const root = execFileSync('npm', ['root', '-g'], { encoding: 'utf8', timeout: 10_000 }).trim();
    if (root) tries.push(`${root}/playwright`);
  } catch {
    /* no npm on PATH */
  }
  for (const t of tries) {
    try {
      return req(t) as Pw;
    } catch {
      /* next */
    }
  }
  return null;
}

/** One rendered dialog: which cache, message kind and UI language, and its markup (the portal). */
interface Rendered {
  key: string;
  html: string;
}

let dialogs: Rendered[] = [];
let browser: Browser | null = null;
let skipReason = '';

async function renderDialogs(): Promise<Rendered[]> {
  const dom = new JSDOM('<!doctype html><html lang="ko"><head></head><body></body></html>', { url: 'http://127.0.0.1/', pretendToBeVisual: true });
  const w = dom.window as unknown as Record<string, unknown>;
  const g = globalThis as unknown as Record<string, unknown>;
  for (const k of ['window', 'document', 'navigator', 'HTMLElement', 'HTMLDivElement', 'Element', 'Node', 'Text', 'SVGElement', 'Event', 'KeyboardEvent', 'MouseEvent', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame', 'DOMParser']) {
    Object.defineProperty(g, k, { value: k === 'window' ? dom.window : w[k], configurable: true, writable: true });
  }
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const React = req('react') as { createElement: (t: unknown, p: Record<string, unknown>) => unknown; act: (f: () => unknown) => Promise<void> };
  const { createRoot } = req('react-dom/client') as { createRoot: (el: Element) => { render: (e: unknown) => void; unmount: () => void } };
  const dialogPath = '../../planner/src/features/lastmile/FieldMessagesDialog';
  const Dialog = ((await import(/* @vite-ignore */ dialogPath)) as { FieldMessagesDialog: unknown }).FieldMessagesDialog;
  const out: Rendered[] = [];
  for (const cache of loadBoothCaches()) {
    const { file } = realExplanationFor(cache);
    const items = cache.inputs.map((input) => buildFieldMessages(input, file));
    for (const kind of ['leave_by', 'no_route', 'unresolved'] as const) {
      const first = items.find((x) => x.kind === kind);
      if (!first) continue;
      for (const lang of ['ko', 'en'] as const) {
        const host = document.createElement('div');
        document.body.appendChild(host);
        const root = createRoot(host);
        await React.act(() =>
          root.render(React.createElement(Dialog, { open: true, onClose: () => undefined, lang, items, initialOriginId: first.originId, explanation: { state: 'ready', url: 'x', file } })),
        );
        out.push({ key: `${cache.entry.path} ${kind} ${lang}`, html: document.body.innerHTML });
        await React.act(() => root.unmount());
        document.body.innerHTML = '';
      }
    }
  }
  return out;
}

beforeAll(async () => {
  dialogs = await renderDialogs();
  const pw = loadPlaywright();
  if (!pw) {
    skipReason = 'Playwright is not installed';
    return;
  }
  try {
    browser = await pw.chromium.launch({ headless: true });
  } catch (e) {
    skipReason = `Chromium could not start: ${e instanceof Error ? e.message.split('\n')[0] : String(e)}`;
  }
}, 180_000);

afterAll(async () => {
  await browser?.close();
});

/** Every dialog in one page: each is fixed to the viewport, so their layouts do not affect each other. */
function pageHtml(): string {
  const font = readFileSync(new URL('node_modules/pretendard/dist/web/variable/woff2/PretendardVariable.woff2', PLANNER)).toString('base64');
  const css = STYLES.map((p) => readFileSync(new URL(p, PLANNER), 'utf8')).join('\n');
  return [
    '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>',
    `@font-face{font-family:'Pretendard Variable';font-weight:45 920;font-style:normal;src:url(data:font/woff2;base64,${font}) format('woff2-variations');}`,
    css,
    '</style></head><body>',
    ...dialogs.map((d, i) => `<div data-dialog="${i}">${d.html}</div>`),
    '</body></html>',
  ].join('');
}

const MEASURE = `document.fonts.ready.then(() => [...document.querySelectorAll('[data-dialog]')].map((box) => {
  const vw = window.innerWidth;
  const q = (s) => box.querySelector(s);
  const parts = ['.wfgl-dialog', '.wfgl-dialog__head', '.wfgl-dialog__body', '.wfgl-dialog__foot'].map((s) => [s, q(s)]);
  return {
    i: Number(box.getAttribute('data-dialog')),
    found: parts.every(([, e]) => e !== null) && q('.wfgl-dialog__pick select') !== null,
    sideways: parts.filter(([, e]) => e && e.scrollWidth - e.clientWidth > 0.5).map(([s, e]) => s + ' ' + (e.scrollWidth - e.clientWidth)),
    outside: [...q('.wfgl-dialog').querySelectorAll('*')]
      .filter((e) => !e.closest('.wfgl-preview') && e.getBoundingClientRect().right > vw + 0.5)
      .slice(0, 5)
      .map((e) => e.tagName + '.' + e.className + ' ' + e.getBoundingClientRect().right.toFixed(1)),
    select: q('.wfgl-dialog__pick select').getBoundingClientRect().width,
  };
}))`;

describe('field-messages dialog at phone width (Chromium, the app\'s style sheets, bundled Pretendard)', () => {
  it('at 375 px and 320 px nothing scrolls sideways or reaches past the screen edge (every booth cache, each message kind, Korean and English UI)', async (ctx) => {
    if (!browser) {
      console.warn(`dialog layout check skipped: ${skipReason}`);
      ctx.skip();
      return;
    }
    // the six caches hold leave-by and unresolved origins, and no-route ones in three of them
    expect(dialogs.length).toBe(2 * (6 * 2 + 3));
    for (const width of WIDTHS) {
      const page = await browser.newPage({ viewport: { width, height: 812 } });
      try {
        await page.setContent(pageHtml(), { waitUntil: 'load' });
        const res = await page.evaluate<{ i: number; found: boolean; sideways: string[]; outside: string[]; select: number }[]>(MEASURE);
        expect(res.length).toBe(dialogs.length);
        const bad = res.filter((r) => !r.found || r.sideways.length || r.outside.length).map((r) => `${width} px ${dialogs[r.i]!.key}: ${JSON.stringify(r)}`);
        expect(bad).toEqual([]);
        console.info(`dialog ${width} px: ${res.length} dialogs fit; origin picker ${Math.min(...res.map((r) => r.select)).toFixed(0)}–${Math.max(...res.map((r) => r.select)).toFixed(0)} px wide`);
      } finally {
        await page.close();
      }
    }
  }, 300_000);
});
