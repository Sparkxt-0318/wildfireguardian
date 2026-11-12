/**
 * P-PROTO (planner/src/features/publicview): replay-only public prototype. Properties over every origin of the six
 * booth caches and the 600 synthetic cases, a full jsdom render of the page with fetch served from the repository's
 * own files, and the colour/size tokens. These tests show the page is consistent and never implies safety; they say
 * nothing about whether anyone understands it.
 */
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { BANNER, cardFor, exampleIds, handoffFor, leaveByWords, linkFor, nextRequestedMin, NOT_IN_MODEL, OFFICIAL_SLOT, ONE_TRIP, parseLink, REPLAY_MARK, sweepStepMin, validPlace, type AfterWords, type PublicCard } from '../../planner/src/features/publicview/model';
import { readSaved, writeSaved } from '../../planner/src/features/publicview/load';
import { DARK, LIGHT, SIZE } from '../../planner/src/features/publicview/tokens';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import type { LastMileInput } from '../../planner/src/features/lastmile/types';
import { loadBoothCaches } from './lastmile.cachedata';
import { generateCases } from './lastmile.generator';
import { NEVER } from './lastmile.oracle';

let real: LastMileInput[] = [];
let syn: LastMileInput[] = [];
beforeAll(() => {
  real = loadBoothCaches().flatMap((c) => c.inputs);
  syn = generateCases(20261102, 600).map((g) => g.input);
}, 300_000);

const strings = (c: PublicCard) =>
  [c.words, c.time, c.oneTrip, c.replayStamp, c.dataAge, c.guidance, c.handoff?.text].flatMap((t) => (t ? [t.ko, t.en] : []));

function masked(i: LastMileInput, s: string): string {
  const names = [i.origin.name, i.origin.display, ...Object.values(i.destinations).flatMap((d) => [d.name, d.display])]
    .flatMap((n) => (n ? [n.ko, n.en] : []))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  let out = s;
  for (const n of names) out = out.split(n).join('#');
  return out;
}

describe('cards over every real and synthetic origin', () => {
  it('a time only for leave_by, always with the replay date and mark in the same card; no time, destination or hand-off otherwise; no forbidden word; no green', () => {
    const counts: Record<string, number> = {};
    for (const i of [...real, ...syn]) {
      const c = cardFor(i, () => ({ lat: 36.5, lon: 129.4 }));
      const k = messagePlan(i, null).kind;
      counts[k] = (counts[k] ?? 0) + 1;
      expect(c.kind).toBe(k);
      expect(['leave', 'stop', 'unknown']).toContain(c.tone);
      if (k === 'leave_by') {
        expect(c.time).not.toBeNull();
        expect(c.oneTrip).toEqual(ONE_TRIP);
        expect(c.replayStamp.ko).toContain(REPLAY_MARK.ko);
        expect(c.replayStamp.en).toContain(REPLAY_MARK.en);
        expect(c.replayStamp.ko).toMatch(/^\d{4}-\d{2}-\d{2} /);
      } else {
        expect(c.time).toBeNull();
        expect(c.oneTrip).toBeNull();
        expect(c.handoff).toBeNull();
        for (const s of [c.words, c.guidance]) expect(`${s.ko} ${s.en}`).not.toMatch(/\d{1,2}:\d{2}/);
      }
      expect(c.dataAge.ko).toMatch(/재현/);
      expect(c.dataAge.en).not.toMatch(/min(ute)?s? old/);
      for (const s of strings(c)) expect(NEVER.test(masked(i, s)), s).toBe(false);
    }
    expect(counts.leave_by! > 0 && counts.no_route! > 0 && counts.unresolved! > 0).toBe(true);
  });

  it('the leave-by sentence is true of the sweep it describes, for every real and synthetic origin (verifier note: "none after" was shown where the model found a later road after a gap)', () => {
    const shown: Record<string, { real: number; syn: number }> = {};
    const laterVerdicts: Record<string, number> = {};
    const gapNext = { shown: 0, omitted: 0 };
    const check = (i: LastMileInput, set: 'real' | 'syn') => {
      const c = cardFor(i, () => null);
      const p = messagePlan(i, null);
      if (c.kind !== 'leave_by') return;
      const T = p.leaveByS!;
      // claims recomputed from the sweep itself, not from the plan's own classification
      const requested = [...i.plan!.sweep].sort((a, b) => a.offsetS - b.offsetS).filter((x) => x.verdict !== 'window_closed');
      const upTo = requested.filter((x) => x.offsetS <= T);
      const later = requested.filter((x) => x.offsetS > T);
      const step = sweepStepMin(i);
      const nextMin = nextRequestedMin(i, p.leaveByS!);
      // Iris: the three sentences are mutually exclusive and exhaustive — every timed card matches exactly one
      const matches = (['horizon', 'none_checked', 'gap'] as AfterWords[]).filter((k) => leaveByWords(k, step, nextMin).en === c.words.en);
      expect(matches.length, c.words.en).toBe(1);
      const which = matches[0]!;
      expect(c.words.ko).toBe(leaveByWords(which, step, nextMin).ko);
      // Iris note 1: the stated step is the sweep's own uniform step (recomputed here), or no step is stated
      const offs = [...new Set(i.plan!.sweep.map((x) => x.offsetS))].sort((a, b) => a - b);
      const diffs = new Set(offs.slice(1).map((v, k) => v - offs[k]!));
      if (step !== null) {
        expect(diffs.size).toBe(1);
        expect([...diffs][0]).toBe(step * 60);
        expect(c.words.en).toContain(`(every ${step} minutes)`);
        expect(c.words.ko).toContain(`${step}분 간격으로`);
      } else {
        expect(c.words.en).not.toMatch(/every \d+ minutes/);
        expect(c.words.ko).not.toMatch(/분 간격/);
      }
      if (set === 'real') expect(step).toBe(10);
      // Iris note 2: "no checked road" never drifts to "no road" / "closed"
      expect(c.words.en).not.toMatch(/\bno road\b|closed/i);
      expect(c.words.ko).not.toMatch(/길이 없습니다(?<!확인된 길이 없습니다)|막혔|통제/);
      // one-trip line on every timed card
      expect(c.oneTrip).toEqual(ONE_TRIP);
      shown[which!] = shown[which!] ?? { real: 0, syn: 0 };
      shown[which!]![set] += 1;
      // common claim: a checked road for every requested departure up to T
      expect(upTo.length).toBeGreaterThan(0);
      expect(upTo.every((x) => x.verdict === 'checked_route')).toBe(true);
      if (which === 'horizon') expect(later.length, i.origin.id).toBe(0); // "later departures were not checked"
      if (which === 'none_checked') {
        // "none after": at least one later requested departure, and none of them has a checked road
        expect(later.length, i.origin.id).toBeGreaterThan(0);
        expect(later.every((x) => x.verdict !== 'checked_route'), i.origin.id).toBe(true);
      }
      if (which === 'gap') {
        // "leaving at the next computed time (N minutes later) has no checked road": the first requested departure
        // after T has none, and when N is shown it is that departure's distance from T
        expect(later.length, i.origin.id).toBeGreaterThan(0);
        expect(later[0]!.verdict, i.origin.id).not.toBe('checked_route');
        const m = c.words.en.match(/\((\d+) minutes later\)/);
        if (m) expect(later[0]!.offsetS - T).toBe(Number(m[1]) * 60);
        gapNext[m ? 'shown' : 'omitted'] += 1;
      }
      // an unresolved later departure is "no checked road" (none_checked / gap), never "not checked" (horizon)
      for (const x of later) laterVerdicts[`${set}:${which}:${x.verdict}`] = (laterVerdicts[`${set}:${which}:${x.verdict}`] ?? 0) + 1;
      if (later.some((x) => x.verdict === 'unresolved')) expect(which).not.toBe('horizon');
    };
    for (const i of real) check(i, 'real');
    for (const i of syn) check(i, 'syn');
    // the generator must exercise all three sentences, or this property proves nothing about the gap case
    expect(shown.horizon?.syn ?? 0).toBeGreaterThan(0);
    expect(shown.none_checked?.syn ?? 0).toBeGreaterThan(0);
    expect(shown.gap?.syn ?? 0).toBeGreaterThan(0);
    // both meanings of "no checked road" after T are exercised: an unresolved later departure and a model no-route one
    expect(Object.keys(laterVerdicts).some((k) => k.startsWith('syn:') && k.endsWith(':unresolved') && !k.includes('horizon'))).toBe(true);
    expect(Object.keys(laterVerdicts).some((k) => k.endsWith(':model_no_route'))).toBe(true);
    console.log('[pproto] leave-by sentence shown (real / synthetic):', JSON.stringify(shown));
    console.log('[pproto] later requested departures by sentence and verdict:', JSON.stringify(laterVerdicts));
    console.log('[pproto] gap sentences with the next time shown / omitted:', JSON.stringify(gapNext));
  });

  it('examples: one of each state, by a fixed rule', () => {
    const byScenario = new Map<string, LastMileInput[]>();
    for (const i of real) byScenario.set(i.scenario.scenarioSetId, [...(byScenario.get(i.scenario.scenarioSetId) ?? []), i]);
    for (const inputs of byScenario.values()) {
      const ids = exampleIds(inputs);
      expect(ids).toEqual(exampleIds([...inputs].reverse()));
      const kinds = ids.map((id) => messagePlan(inputs.find((i) => i.origin.id === id)!, null).kind);
      expect(new Set(kinds).size).toBe(kinds.length);
      expect(kinds[0]).toBe('leave_by');
    }
  });

  it('hand-off: destination only, replay label inside the GPX file name, track name and description; never a geo: link', () => {
    let n = 0;
    for (const i of real) {
      const p = messagePlan(i, null);
      const h = handoffFor(p, () => ({ lat: 36.5, lon: 129.4 }));
      if (!h) continue;
      n++;
      expect(h.gpxFileName).toMatch(/^REPLAY-\d{4}-\d{2}-\d{2}-NOT-REAL-/);
      expect(h.gpx).toMatch(/<metadata><name>REPLAY \d{4}-\d{2}-\d{2} NOT REAL/);
      expect(h.gpx).toContain(BANNER.en.replace(/&/g, '&amp;'));
      expect(h.gpx.match(/<wpt /g)?.length).toBe(1);
      expect(`${h.gpx}${h.text.ko}${h.text.en}`).not.toMatch(/geo:/i);
    }
    expect(n).toBeGreaterThan(0);
  });

  it('saved places survive a storage that throws (the page works without it)', () => {
    const orig = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, get: () => { throw new Error('blocked'); } });
    expect(readSaved()).toEqual([]);
    expect(() => writeSaved(['x'])).not.toThrow();
    if (orig) Object.defineProperty(globalThis, 'localStorage', orig);
  });
});

// ------------------------------------------------------------------------------------------------ tokens

function lum(hex: string): number {
  const v = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * v[0]! + 0.7152 * v[1]! + 0.0722 * v[2]!;
}
const contrast = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x! + 0.05) / (y! + 0.05); };
function rgb(hex: string): number[] { return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255); }
// Machado et al. (2009) severity-1.0 simulation matrices, applied in linear RGB
const CVD: Record<string, number[][]> = {
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
  tritan: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.3039]],
  none: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
};
function lab(lin: number[]): number[] {
  const [r, g, b] = lin.map((x) => Math.min(1, Math.max(0, x))) as [number, number, number];
  const X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, Y = 0.2126 * r + 0.7152 * g + 0.0722 * b, Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
  const f = (t: number) => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
  return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
}
const linear = (hex: string) => rgb(hex).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
const sim = (hex: string, m: number[][]) => { const v = linear(hex); return m.map((row) => row[0]! * v[0]! + row[1]! * v[1]! + row[2]! * v[2]!); };
const dE = (a: number[], b: number[]) => Math.hypot(a[0]! - b[0]!, a[1]! - b[1]!, a[2]! - b[2]!);

describe('tokens: contrast, colour vision, sizes', () => {
  it('every text/background pair ≥ 7:1 (WCAG AAA), light and dark; accents ≥ 3:1 against the page', () => {
    for (const t of [LIGHT, DARK]) {
      expect(contrast(t.text, t.bg)).toBeGreaterThanOrEqual(7);
      expect(contrast(t.muted, t.bg)).toBeGreaterThanOrEqual(7);
      expect(contrast(t.banner.text, t.banner.bg)).toBeGreaterThanOrEqual(7);
      expect(contrast(t.official.text, t.official.bg)).toBeGreaterThanOrEqual(7);
      for (const k of ['leave', 'stop', 'unknown'] as const) {
        expect(contrast(t.tone[k].onAccent, t.tone[k].accent)).toBeGreaterThanOrEqual(7);
        expect(contrast(t.tone[k].accent, t.bg)).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it('the three state colours stay distinguishable under simulated protan, deutan and tritan vision (ΔE*ab ≥ 15), and no state is green', () => {
    for (const t of [LIGHT, DARK]) {
      const acc = (['leave', 'stop', 'unknown'] as const).map((k) => t.tone[k].accent);
      for (const m of Object.values(CVD)) {
        const L = acc.map((h) => lab(sim(h, m)));
        for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) expect(dE(L[i]!, L[j]!)).toBeGreaterThanOrEqual(15);
      }
      for (const h of acc) { const [r, g, b] = rgb(h); expect(g! > r! + 0.1 && g! > b! + 0.1).toBe(false); }
    }
  });

  it('data age is shown at least as large as the time; base type ≥ 20 px', () => {
    expect(SIZE.dataAge).toBeGreaterThanOrEqual(SIZE.time);
    expect(SIZE.base).toBeGreaterThanOrEqual(20);
    expect(SIZE.stamp).toBeGreaterThanOrEqual(SIZE.base);
  });
});

// ------------------------------------------------------------------------------------------------ the page

// local jsdom, React loaded at runtime (the pattern of lastmile.render.test.ts; the vitest config runs in node)
const req = createRequire(new URL('../../planner/package.json', import.meta.url));
const { JSDOM } = req('jsdom') as { JSDOM: new (html?: string, opts?: Record<string, unknown>) => { window: Window & typeof globalThis } };

async function mount(url: string): Promise<{ container: HTMLDivElement; urls: string[] }> {
  const urls: string[] = [];
  const planner = new URL('../../planner/', import.meta.url);
  const dom = new JSDOM('<!doctype html><html lang="ko"><head></head><body></body></html>', { url, pretendToBeVisual: true });
  const w = dom.window as unknown as Record<string, unknown>;
  const g = globalThis as unknown as Record<string, unknown>;
  for (const k of ['window', 'document', 'navigator', 'location', 'localStorage', 'HTMLElement', 'HTMLDivElement', 'Element', 'Node', 'Text', 'SVGElement', 'Event', 'MouseEvent', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame']) {
    Object.defineProperty(g, k, { value: k === 'window' ? dom.window : w[k], configurable: true, writable: true });
  }
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const u = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, url);
    urls.push(u.href);
    const file = u.pathname.startsWith('/cache/') ? new URL(`cache/${u.pathname.slice(7)}`, planner) : new URL(`public${u.pathname}`, planner);
    try {
      return new Response(readFileSync(file), { status: 200, headers: { 'content-type': 'application/json' } });
    } catch {
      return new Response('not found', { status: 404 });
    }
  }) as typeof fetch;
  const React = req('react') as { createElement: (t: unknown) => unknown; act: (fn: () => unknown) => Promise<void> };
  const { createRoot } = req('react-dom/client') as { createRoot: (el: Element) => { render: (e: unknown) => void } };
  const path = '../../planner/src/features/publicview/PublicView';
  const { PublicView } = (await import(/* @vite-ignore */ path)) as { PublicView: unknown };
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  await React.act(async () => { root.render(React.createElement(PublicView)); });
  // a CI runner can take far longer than a workstation to parse the 25 MB cache in jsdom: wait up to 90 s, and stop
  // early (with the page's own error text) if the page reports an error instead of cards
  const until = Date.now() + 90_000;
  while (Date.now() < until && !container.querySelector('[data-pv="card"]') && !container.querySelector('.pv-error')) {
    await React.act(async () => { await new Promise((r) => setTimeout(r, 100)); });
  }
  const err = container.querySelector('.pv-error');
  if (err) throw new Error(`page reported an error while loading the replay cache: ${err.textContent}`);
  return { container, urls };
}

const ORIGIN = 'http://127.0.0.1';

describe('the page in jsdom, fetch served from the repository files', () => {
  let container: HTMLDivElement;
  let urls: string[] = [];
  beforeAll(async () => {
    ({ container, urls } = await mount(`${ORIGIN}/public-view.html`));
  }, 180_000);
  afterAll(() => container?.remove());

  it('order: replay banner first, official-orders slot second, every card after both', () => {
    const all = [...container.querySelectorAll('[data-pv]')].filter((e) => ['banner', 'official', 'card'].includes(e.getAttribute('data-pv')!));
    expect(all[0]!.getAttribute('data-pv')).toBe('banner');
    expect(all[1]!.getAttribute('data-pv')).toBe('official');
    expect(all.slice(2).every((e) => e.getAttribute('data-pv') === 'card')).toBe(true);
    expect(all.length).toBeGreaterThanOrEqual(3);
    expect(container.textContent).toContain(BANNER.ko);
    expect(container.textContent).toContain(OFFICIAL_SLOT.ko);
  });

  it('crop property: every card that renders a time renders the replay date and mark inside the same card, beside the time', () => {
    const cards = [...container.querySelectorAll('article[data-pv="card"]')];
    let timed = 0;
    for (const c of cards) {
      const time = c.querySelector('[data-pv="time"]');
      expect(c.querySelector('[data-pv="stamp"]')!.textContent).toContain(REPLAY_MARK.ko);
      if (!time) {
        expect(c.getAttribute('data-kind')).not.toBe('leave_by');
        expect(c.querySelector('[data-pv="handoff"]')).toBeNull();
        expect(c.querySelector('[data-pv="one-trip"]')).toBeNull();
        continue;
      }
      timed++;
      // the one-trip line is inside the same card, right after the time line (a crop keeps it)
      const trip = c.querySelector('[data-pv="one-trip"]')!;
      expect(trip.textContent).toBe(ONE_TRIP.ko);
      expect(time.parentElement!.nextElementSibling).toBe(trip);
      // time first: before the status words and any hand-off, in DOM order
      const order = (a: Element, b: Element) => a.compareDocumentPosition(b) & 4; // b follows a
      expect(order(time, c.querySelector('[data-pv="words"]')!)).toBeTruthy();
      const h = c.querySelector('[data-pv="handoff"]');
      if (h) expect(order(time, h)).toBeTruthy();
      const beside = time.parentElement!.querySelector('[data-pv="time-stamp"]')!;
      expect(beside.textContent).toMatch(/^\d{4}-\d{2}-\d{2} /);
      expect(beside.textContent).toContain(REPLAY_MARK.ko);
    }
    expect(timed).toBeGreaterThanOrEqual(1);
    expect(cards.length).toBe(3); // examples: one per state
    const notIn = container.querySelector('[data-pv="not-in-model"]')!;
    for (const x of NOT_IN_MODEL.items) expect(notIn.textContent).toContain(x.ko);
  });

  it('no request leaves the page origin; no geo: link anywhere', () => {
    expect(urls.length).toBeGreaterThan(0);
    for (const u of urls) expect(new URL(u).origin).toBe(ORIGIN);
    expect(container.innerHTML).not.toMatch(/geo:/i);
  });
});

describe('places by URL (Iris: both parameters untrusted)', () => {
  const index = JSON.parse(readFileSync(new URL('../../planner/cache/INDEX.json', import.meta.url), 'utf8')) as { entries?: { path: string }[] } | { path: string }[];
  const paths = (Array.isArray(index) ? index : index.entries ?? []).map((e) => e.path);

  it('parseLink accepts only an exact cache index path and a plausible id; path-like, unknown and markup values give nulls', () => {
    expect(paths.length).toBe(6);
    const ok = parseLink(`?scenario=${encodeURIComponent(paths[0]!)}&place=osm%3Anode%2F1`, paths);
    expect(ok).toEqual({ scenario: paths[0], place: 'osm:node/1' });
    for (const bad of ['../../etc/passwd', `/${paths[0]}`, `${paths[0]}?x=1`, 'https://example.org/x.json', '<script>alert(1)</script>', '', paths[0]!.toUpperCase()]) {
      expect(parseLink(`?scenario=${encodeURIComponent(bad)}&place=osm%3Anode%2F1`, paths).scenario).toBeNull();
    }
    for (const bad of ['<img src=x onerror=1>', '"quoted"', 'a'.repeat(200), 'x y']) {
      expect(parseLink(`?scenario=${encodeURIComponent(paths[0]!)}&place=${encodeURIComponent(bad)}`, paths).place).toBeNull();
    }
    expect(validPlace('osm:node/does-not-exist', real)).toBeNull();
    expect(validPlace(real[0]!.origin.id, real)).toBe(real[0]!.origin.id);
    expect(linkFor(paths[0]!, real[0]!.origin.id)).toMatch(/^\?scenario=.*&place=/);
  });

  it('a shared link opens that place with the banner and the in-card replay date and mark', async () => {
    const byPath = loadBoothCaches().find((c) => c.entry.path === paths[0]);
    const target = byPath!.inputs.find((i) => messagePlan(i, null).kind === 'leave_by')!;
    const { container, urls } = await mount(`${ORIGIN}/public-view.html${linkFor(paths[0]!, target.origin.id)}`);
    const cards = [...container.querySelectorAll('article[data-pv="card"]')];
    expect(cards.length).toBe(1);
    expect(container.querySelector('[data-pv="banner"]')!.textContent).toBe(BANNER.ko);
    expect(cards[0]!.querySelector('[data-pv="time-stamp"]')!.textContent).toContain(REPLAY_MARK.ko);
    expect(container.textContent).not.toMatch(/예시 세 곳/);
    for (const u of urls) expect(new URL(u).origin).toBe(ORIGIN);
    container.remove();
  }, 180_000);

  it('hostile links fall back to the empty state (three labelled examples), fetch nothing they name, and render no markup from the URL', async () => {
    for (const q of ['?scenario=..%2F..%2Fetc%2Fpasswd&place=x', `?scenario=${encodeURIComponent(paths[0]!)}&place=%3Cimg%20src%3Dx%20onerror%3D1%3E`, `?scenario=${encodeURIComponent(paths[0]!)}&place=osm%3Anode%2F0`]) {
      const { container, urls } = await mount(`${ORIGIN}/public-view.html${q}`);
      expect(container.querySelectorAll('article[data-pv="card"]').length).toBe(3);
      expect(container.textContent).toMatch(/예시 세 곳/);
      expect(container.innerHTML).not.toMatch(/onerror/);
      for (const u of urls) {
        expect(new URL(u).origin).toBe(ORIGIN);
        expect(u).not.toMatch(/passwd/);
      }
      container.remove();
    }
  }, 300_000);
});
