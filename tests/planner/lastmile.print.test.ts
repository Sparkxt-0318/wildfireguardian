/**
 * Print fit of the origin cards (FieldCard + lastmile.css): every origin of the six booth caches,
 * Korean and English, A5 and A4.
 *
 * 1. Box-model estimate (always runs, no browser — lastmile.printfit.ts): the card's boxes filled
 *    with its text, wrapped greedily at spaces with the bundled font's measured advance widths
 *    (rounded up, kerning ignored), must fit each page box at its body size (A5 14 pt, A4 18 pt).
 * 2. Real layout (runs when Playwright and its Chromium are installed — they are not planner
 *    dependencies; PLAYWRIGHT_MODULE, the planner's node_modules or the global npm root are tried):
 *    Chromium with print media and the bundled Pretendard font renders every card; no card may
 *    overflow its page box, every body element is ≥ 14 pt and the estimate of (1) is never below the
 *    real height. Then all cards of one cache are printed to PDF per language and size and the PDF
 *    must have exactly one page per card.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { buildFieldMessages, TEMPLATES, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import type { CardContent } from '../../planner/src/features/lastmile/compose';
import { loadBoothCaches, realExplanationFor, syntheticExplanationFor } from './lastmile.cachedata';
import { estimate, type CardSize } from './lastmile.printfit';

const PLANNER = new URL('../../planner/', import.meta.url);
const PT_PX = 96 / 72;
const MM_PX = 96 / 25.4;

// The test tsconfig resolves neither React's types nor TSX: React is loaded with Node's resolver from
// planner/ and the card component through a runtime path (same convention as features.plansheet.test.ts).
const reqPlanner = createRequire(new URL('package.json', PLANNER));
const React = reqPlanner('react') as { createElement: (type: unknown, props: Record<string, unknown>) => unknown };
const { renderToStaticMarkup } = reqPlanner('react-dom/server') as { renderToStaticMarkup: (el: unknown) => string };
let FieldCard: unknown = null;
let FONT_B64 = '';
let CARD_CSS = '';

let items: { path: string; fm: FieldMessages }[] = [];

beforeAll(async () => {
  // every origin as it is now (no explanation file), plus — the longest cards — every origin whose
  // messages gain a reason line from a synthetic contract-shaped explanation with a long road name
  // (and, when the real explanation files are present, every origin they give a reason line)
  items = loadBoothCaches().flatMap((c) => {
    const file = syntheticExplanationFor(c);
    const real = realExplanationFor(c).file;
    const plain = c.inputs.map((input) => ({ path: c.entry.path, fm: buildFieldMessages(input, null) }));
    const reasoned = c.inputs.map((input) => ({ path: `${c.entry.path} +reason`, fm: buildFieldMessages(input, file) })).filter((x) => x.fm.reason);
    const withReal = real ? c.inputs.map((input) => ({ path: `${c.entry.path} +real`, fm: buildFieldMessages(input, real) })).filter((x) => x.fm.reason) : [];
    return [...plain, ...reasoned, ...withReal];
  });
  const cardPath = '../../planner/src/features/lastmile/FieldCard';
  FieldCard = ((await import(/* @vite-ignore */ cardPath)) as { FieldCard: unknown }).FieldCard;
  FONT_B64 = readFileSync(new URL('node_modules/pretendard/dist/web/variable/woff2/PretendardVariable.woff2', PLANNER)).toString('base64');
  CARD_CSS = readFileSync(new URL('src/features/lastmile/lastmile.css', PLANNER), 'utf8');
}, 180_000);

// ---------------------------------------------------------------- 1. box-model estimate (no browser)

describe('origin cards: box-model estimate (no browser needed)', () => {
  it('every card of every origin fits one A5 page at 14 pt and one A4 page at 18 pt, Korean and English', () => {
    const over: string[] = [];
    for (const lang of ['ko', 'en'] as const) {
      for (const size of ['a5', 'a4'] as const) {
        let minSpare = Infinity;
        for (const { path, fm } of items) {
          const e = estimate(fm.text[lang].card, size);
          minSpare = Math.min(minSpare, e.availablePx - e.usedPx);
          if (e.usedPx > e.availablePx) over.push(`${path} ${fm.originId} ${lang} ${size}: ${e.usedPx.toFixed(0)} > ${e.availablePx.toFixed(0)} px ${JSON.stringify(e.parts)}`);
        }
        console.info(`estimate ${lang} ${size}: ${items.length} cards, smallest estimated free space ${(minSpare / MM_PX).toFixed(1)} mm`);
      }
    }
    expect(over).toEqual([]);
  });

  it('with the longest provenance lines and badges the app can produce, every card still fits', () => {
    const over: string[] = [];
    for (const lang of ['ko', 'en'] as const) {
      for (const size of ['a5', 'a4'] as const) {
        for (const v of variantCards(lang)) {
          const e = estimate(v.card, size);
          if (e.usedPx > e.availablePx) over.push(`${v.id} ${lang} ${size}: ${e.usedPx.toFixed(0)} > ${e.availablePx.toFixed(0)} px`);
        }
      }
    }
    expect(over).toEqual([]);
  });
});

/**
 * Every card again with the longest provenance lines and badges the app can produce — reachable
 * combinations only (input.ts originProvenance: a live result is never test data under MOCK): a
 * non-evaluated cache viewed with the MOCK server on (three badges), a live result on a
 * non-evaluated host, and a live result from the MOCK server.
 */
function variantCards(lang: 'ko' | 'en'): { id: string; card: CardContent }[] {
  const host = { ko: 'Linux x86_64 · 4 vCPU', en: 'Linux x86_64 · 4 vCPU' };
  const live = { source: 'live' as const, cachePath: null, cacheCreatedAtIso: null, host };
  const variants = [
    { name: 'cache+mock+test', over: { mock: true, testData: true } },
    { name: 'live+test', over: { testData: true, provenance: live } },
    { name: 'live+mock', over: { mock: true, provenance: live } },
  ];
  return variants.flatMap((v) => items.map(({ path, fm }) => ({ id: `${v.name} ${path} ${fm.originId}`, card: TEMPLATES[lang].card({ ...fm.plan, input: { ...fm.plan.input, ...v.over } }) })));
}

// ---------------------------------------------------------------- 2. real layout in Chromium

type Pw = { chromium: { launch: (o?: Record<string, unknown>) => Promise<Browser> } };
type Browser = { newPage: (o?: Record<string, unknown>) => Promise<Page>; close: () => Promise<void> };
type Page = {
  setContent: (html: string, o?: Record<string, unknown>) => Promise<void>;
  emulateMedia: (o: Record<string, unknown>) => Promise<void>;
  evaluate: <T>(fn: string | (() => T | Promise<T>)) => Promise<T>;
  pdf: (o?: Record<string, unknown>) => Promise<Buffer>;
  close: () => Promise<void>;
};

function loadPlaywright(): Pw | null {
  const req = createRequire(new URL('package.json', PLANNER));
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

let browser: Browser | null = null;
let skipReason = '';

beforeAll(async () => {
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
}, 120_000);

afterAll(async () => {
  await browser?.close();
});

function pageHtml(cards: { card: CardContent; size: CardSize; id: string }[], printRoot: boolean, pageSize?: CardSize): string {
  const body = cards.map((c) => renderToStaticMarkup(React.createElement(FieldCard, { card: c.card, size: c.size, originId: c.id }))).join('');
  return [
    '<!doctype html><html lang="ko"' + (printRoot ? ' class="wfgl-printing-cards"' : '') + '><head><meta charset="utf-8"><style>',
    `@font-face{font-family:'Pretendard Variable';font-weight:45 920;font-style:normal;src:url(data:font/woff2;base64,${FONT_B64}) format('woff2-variations');}`,
    CARD_CSS,
    'body{margin:0}',
    pageSize ? `@page{size:${pageSize === 'a4' ? 'A4' : 'A5'} portrait;margin:0}` : '',
    '</style></head><body>',
    printRoot ? `<div class="wfgf wfgl-print-root">${body}</div>` : `<div style="display:flex;flex-wrap:wrap;gap:4mm">${body}</div>`,
    '</body></html>',
  ].join('');
}

const MEASURE = `(() => {
  const body = '.wfgl-card__lines li, .wfgl-card__official, .wfgl-card__data, .wfgl-card__model, .wfgl-card__limits, .wfgl-card__status, .wfgl-card__bigsub';
  return [...document.querySelectorAll('.wfgl-card')].map((c) => ({
    id: c.getAttribute('data-card-origin'),
    overflowY: c.scrollHeight - c.clientHeight,
    overflowX: c.scrollWidth - c.clientWidth,
    minBodyPx: Math.min(...[...c.querySelectorAll(body)].map((e) => parseFloat(getComputedStyle(e).fontSize))),
    minHeadFootPx: Math.min(...[...c.querySelectorAll('.wfgl-card__head, .wfgl-card__head *, .wfgl-card__footrule, .wfgl-card__cat')].map((e) => parseFloat(getComputedStyle(e).fontSize))),
    spareMm: (() => {
      const lines = c.querySelector('.wfgl-card__lines').getBoundingClientRect();
      const bottom = c.querySelector('.wfgl-card__bottom').getBoundingClientRect();
      return (bottom.top - lines.bottom) / (96 / 25.4);
    })(),
    usedPx: (() => {
      const cs = getComputedStyle(c);
      const lines = c.querySelector('.wfgl-card__lines').getBoundingClientRect();
      const bottom = c.querySelector('.wfgl-card__bottom').getBoundingClientRect();
      return c.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - Math.max(0, bottom.top - lines.bottom);
    })(),
  }));
})()`;

describe('origin cards in Chromium (print media, bundled Pretendard)', () => {
  it('no card overflows its A5 / A4 page, body text is ≥ 14 pt and header / footer ≥ 12 pt (Korean and English, every origin)', async (ctx) => {
    if (!browser) {
      console.warn(`print layout check skipped: ${skipReason}`);
      ctx.skip();
      return;
    }
    const page = await browser.newPage();
    try {
      await page.emulateMedia({ media: 'print' });
      for (const lang of ['ko', 'en'] as const) {
        for (const size of ['a5', 'a4'] as const) {
          await page.setContent(pageHtml(items.map(({ fm }) => ({ card: fm.text[lang].card, size, id: fm.originId })), false), { waitUntil: 'load' });
          const fontOk = await page.evaluate<boolean>(`document.fonts.ready.then(() => document.fonts.check('14pt "Pretendard Variable"', '가'))`);
          expect(fontOk).toBe(true);
          const res = await page.evaluate<{ id: string; overflowY: number; overflowX: number; minBodyPx: number; minHeadFootPx: number; spareMm: number; usedPx: number }[]>(MEASURE);
          expect(res.length).toBe(items.length);
          // the browser-free estimate above must never be below the real height (it stands in for this test in CI)
          const under = res
            .map((r, i) => ({ r, e: estimate(items[i]!.fm.text[lang].card, size) }))
            .filter(({ r, e }) => e.usedPx < r.usedPx - 0.5)
            .map(({ r, e }) => `${lang} ${size} ${r.id}: estimate ${e.usedPx.toFixed(1)} < real ${r.usedPx.toFixed(1)} px`);
          expect(under).toEqual([]);
          // body ≥ 14 pt; header, category and the planner footer line ≥ 12 pt
          const bad = res
            .filter((r) => r.overflowY > 0.5 || r.overflowX > 0.5 || r.minBodyPx < 14 * PT_PX - 0.05 || r.minHeadFootPx < 12 * PT_PX - 0.05)
            .map((r) => `${lang} ${size} ${r.id}: ${JSON.stringify(r)}`);
          expect(bad).toEqual([]);
          const minSpare = Math.min(...res.map((r) => r.spareMm));
          console.info(
            `cards ${lang} ${size}: ${res.length} rendered, smallest free space ${minSpare.toFixed(1)} mm, smallest body ${(Math.min(...res.map((r) => r.minBodyPx)) / PT_PX).toFixed(1)} pt, smallest header/footer ${(Math.min(...res.map((r) => r.minHeadFootPx)) / PT_PX).toFixed(1)} pt`,
          );
          expect(minSpare).toBeGreaterThanOrEqual(0);
        }
      }
    } finally {
      await page.close();
    }
  }, 300_000);

  it('the tightest cards with MOCK / test-data badges and live staff lines also fit in Chromium (and the estimate holds for them)', async (ctx) => {
    if (!browser) {
      ctx.skip();
      return;
    }
    const page = await browser.newPage();
    try {
      await page.emulateMedia({ media: 'print' });
      for (const lang of ['ko', 'en'] as const) {
        for (const size of ['a5', 'a4'] as const) {
          // the 60 cards with the least estimated free space (the estimate never undershoots: tested above)
          const tight = variantCards(lang)
            .map((v) => ({ ...v, e: estimate(v.card, size) }))
            .sort((a, b) => a.e.availablePx - a.e.usedPx - (b.e.availablePx - b.e.usedPx))
            .slice(0, 60);
          await page.setContent(pageHtml(tight.map((v) => ({ card: v.card, size, id: v.id })), false), { waitUntil: 'load' });
          await page.evaluate(`document.fonts.ready.then(() => true)`);
          const res = await page.evaluate<{ id: string; overflowY: number; overflowX: number; minBodyPx: number; minHeadFootPx: number; spareMm: number; usedPx: number }[]>(MEASURE);
          expect(res.length).toBe(tight.length);
          const bad = res
            .map((r, i) => ({ r, e: tight[i]!.e }))
            .filter(({ r, e }) => r.overflowY > 0.5 || r.overflowX > 0.5 || r.minBodyPx < 14 * PT_PX - 0.05 || r.minHeadFootPx < 12 * PT_PX - 0.05 || r.spareMm < 0 || e.usedPx < r.usedPx - 0.5)
            .map(({ r, e }) => `${lang} ${size} ${r.id}: estimate ${e.usedPx.toFixed(1)} ${JSON.stringify(r)}`);
          expect(bad).toEqual([]);
          console.info(`badge/live variants ${lang} ${size}: ${res.length} tightest rendered, smallest free space ${Math.min(...res.map((r) => r.spareMm)).toFixed(1)} mm`);
        }
      }
    } finally {
      await page.close();
    }
  }, 300_000);

  it('printing all cards of a scenario gives exactly one page per card (A5 and A4, Korean and English)', async (ctx) => {
    if (!browser) {
      ctx.skip();
      return;
    }
    const scenario = items.filter((x) => x.path.startsWith('uiseong_andong_2025/20250325T170000Z.json'));
    expect(new Set(scenario.map((x) => x.fm.kind)).size).toBe(3);
    const page = await browser.newPage();
    try {
      for (const lang of ['ko', 'en'] as const) {
        for (const size of ['a5', 'a4'] as const) {
          await page.setContent(pageHtml(scenario.map(({ fm }) => ({ card: fm.text[lang].card, size, id: fm.originId })), true, size), { waitUntil: 'load' });
          await page.evaluate(`document.fonts.ready.then(() => true)`);
          const pdf = (await page.pdf({ preferCSSPageSize: true, printBackground: true })).toString('latin1');
          const pages = (pdf.match(/\/Type\s*\/Page(?!s)/g) ?? []).length;
          expect(pages, `${lang} ${size}`).toBe(scenario.length);
        }
      }
    } finally {
      await page.close();
    }
  }, 300_000);
});
