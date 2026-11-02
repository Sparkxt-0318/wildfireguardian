/**
 * Print fit of the A4 plan sheets with the "왜 이 시각인가요? / Why this time?" section (planner/src/features/explain).
 * The section takes height from the map section above it: nothing inside the map section (map and legend) may stick
 * out of it, the map keeps its minimum height and the footer stays inside the sheet — for every sheet of the six
 * recorded scenarios, in both languages, in print media.
 *
 * Needs a browser: it runs when Playwright (WFG_PLAYWRIGHT_MODULE, a local install, or the global npm root) and its
 * Chromium are available, and is skipped otherwise (set WFG_PRINT_FIT=0 to skip it on purpose).
 */
import { execSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const plannerDir = fileURLToPath(new URL('../../planner/', import.meta.url));
const req = createRequire(join(plannerDir, 'package.json'));

interface Browser {
  newPage(o: { viewport: { width: number; height: number } }): Promise<Page>;
  close(): Promise<void>;
}
interface Page {
  goto(url: string, o?: { waitUntil?: string; timeout?: number }): Promise<unknown>;
  waitForSelector(sel: string, o?: { timeout?: number }): Promise<unknown>;
  waitForFunction(fn: () => boolean, arg?: unknown, o?: { timeout?: number }): Promise<unknown>;
  getByRole(role: string, o: { name: RegExp }): { first(): { click(o?: { timeout?: number }): Promise<void> } };
  emulateMedia(o: { media: string }): Promise<void>;
  waitForTimeout(ms: number): Promise<void>;
  evaluate<T>(fn: () => T): Promise<T>;
  close(): Promise<void>;
}
interface Chromium {
  executablePath(): string;
  launch(): Promise<Browser>;
}

function findPlaywright(): string | null {
  const tries: string[] = [];
  if (process.env.WFG_PLAYWRIGHT_MODULE) tries.push(process.env.WFG_PLAYWRIGHT_MODULE);
  try {
    tries.push(dirname(req.resolve('playwright/package.json')));
  } catch {
    /* not installed locally */
  }
  try {
    tries.push(join(execSync('npm root -g', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(), 'playwright'));
  } catch {
    /* no npm */
  }
  for (const p of tries) {
    try {
      const chromium = (createRequire(join(p, 'package.json'))(p) as { chromium?: Chromium }).chromium;
      if (chromium && existsSync(chromium.executablePath())) return p;
    } catch {
      /* not usable */
    }
  }
  return null;
}

const PW = process.env.WFG_PRINT_FIT === '0' ? null : findPlaywright();
const RUNS = (JSON.parse(readFileSync(join(plannerDir, 'cache', 'INDEX.json'), 'utf8')) as { region_id: string; input_time: string }[]).map((e) => [
  e.region_id,
  e.input_time.replace(/[-:]/g, '').replace(/\.\d+/, ''),
]);

interface SheetFit {
  origin: string;
  sectionOverflowMm: number;
  mapMm: number | null;
  minMapMm: number;
  footClipMm: number;
  sheetOverflowMm: number;
}

describe.skipIf(!PW)('A4 plan sheets fit in print with the explanation section', () => {
  let server: { listen(): Promise<unknown>; close(): Promise<void>; resolvedUrls: { local: string[] } | null } | null = null;
  let browser: Browser | null = null;
  let base = '';

  beforeAll(async () => {
    const vite = (await import(pathToFileURL(req.resolve('vite')).href)) as {
      createServer(o: Record<string, unknown>): Promise<NonNullable<typeof server>>;
      createLogger(level: string): { error(msg: string, o?: unknown): void };
    };
    // no routing API runs here: drop the dev proxy's connection errors, keep every other error
    const logger = vite.createLogger('error');
    const error = logger.error.bind(logger);
    logger.error = (msg: string, o?: unknown) => {
      if (!/ECONNREFUSED|proxy error/i.test(String(msg))) error(msg, o);
    };
    server = await vite.createServer({ root: plannerDir, configFile: join(plannerDir, 'vite.config.ts'), customLogger: logger, server: { host: '127.0.0.1', port: 5470, strictPort: false } });
    await server.listen();
    base = server.resolvedUrls!.local[0]!;
    const pw = createRequire(join(PW!, 'package.json'))(PW!) as { chromium: Chromium };
    browser = await pw.chromium.launch();
  }, 120_000);

  afterAll(async () => {
    await browser?.close();
    await server?.close();
  });

  it.each(RUNS.flatMap(([region, input]) => (['en', 'ko'] as const).map((lang) => [region!, input!, lang] as const)))(
    '%s %s %s',
    async (region, input, lang) => {
      const page = await browser!.newPage({ viewport: { width: 1440, height: 1100 } });
      try {
        await page.goto(`${base}?region=${region}&scenario=${input}&lang=${lang}`, { waitUntil: 'domcontentloaded', timeout: 120_000 });
        await page.waitForSelector('html[data-wfg-data-ready="true"]', { timeout: 180_000 });
        await page.getByRole('button', { name: lang === 'ko' ? /계획서/ : /plan sheet/i }).first().click({ timeout: 60_000 });
        await page.waitForSelector('.wfgf-sheet[data-sheet-origin] [data-explain-sheet]', { timeout: 120_000 });
        await page.waitForFunction(() => document.querySelectorAll('.wfgx-sheet__row[data-explain-state="loading"]').length === 0, null, { timeout: 120_000 });
        await page.emulateMedia({ media: 'print' });
        await page.waitForTimeout(300);
        const sheets = await page.evaluate((): SheetFit[] => {
          const mm = 96 / 25.4;
          const out: SheetFit[] = [];
          for (const s of document.querySelectorAll<HTMLElement>('.wfgf-sheet[data-sheet-origin]')) {
            const sec = s.querySelector<HTMLElement>('.wfgf-sheet__mapsec');
            const bottom = sec ? sec.getBoundingClientRect().bottom : 0;
            let over = -Infinity;
            for (const el of sec ? sec.querySelectorAll('*') : []) {
              const r = el.getBoundingClientRect();
              if (r.height > 0) over = Math.max(over, (r.bottom - bottom) / mm);
            }
            const map = sec?.querySelector('.wfgf-sheetmap');
            const foot = s.querySelector('.wfgf-sheet__foot');
            const padB = parseFloat(getComputedStyle(s).paddingBottom);
            out.push({
              origin: s.getAttribute('data-sheet-origin') ?? '?',
              sectionOverflowMm: sec ? over : Infinity,
              mapMm: map ? map.getBoundingClientRect().height / mm : null,
              minMapMm: s.classList.contains('wfgf-sheet--dense') ? 26 : 34,
              footClipMm: foot ? (foot.getBoundingClientRect().bottom - (s.getBoundingClientRect().bottom - padB)) / mm : Infinity,
              sheetOverflowMm: (s.scrollHeight - s.clientHeight) / mm,
            });
          }
          return out;
        });
        expect(sheets.length).toBeGreaterThan(80);
        const bad = sheets
          .filter((x) => x.sectionOverflowMm > 0.05 || x.mapMm === null || x.mapMm < x.minMapMm - 0.05 || x.footClipMm > 0.05 || x.sheetOverflowMm > 0.05)
          .map((x) => `${x.origin}: map section overflow ${x.sectionOverflowMm.toFixed(2)} mm, map ${x.mapMm?.toFixed(1)} mm, footer ${x.footClipMm.toFixed(2)} mm`);
        expect(bad).toEqual([]);
      } finally {
        await page.close();
      }
    },
    400_000,
  );
});
