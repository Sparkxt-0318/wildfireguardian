/**
 * COMPREHENSION session kit (research/harness-2026-11/COMPREHENSION/kit): selects the five fixed replay cases by the
 * protocol's rule and writes each channel's output EXACTLY as the kit produces it. Without KIT_WRITE=1 the test
 * regenerates every item and checks it is byte-identical to the committed file (Mira's check); with KIT_WRITE=1 it
 * (re)writes them. No wording is produced here: every string comes from the production modules.
 */
import { describe, expect, it } from 'vitest';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { deadlineHeadline } from '../../planner/src/domain/plan';
import { messagePlan, type MessagePlan } from '../../planner/src/features/lastmile/plan';
import { buildChannels } from '../../planner/src/features/lastmile/channels/build';
import { cardFor } from '../../planner/src/features/publicview/model';
import { coordsOf } from '../../planner/src/features/publicview/load';
import { loadBoothCaches } from './lastmile.cachedata';

// React is loaded with Node's resolver from planner/ (the tests live outside the Vite root; pattern of pproto.test.ts)
const req = createRequire(new URL('../../planner/package.json', import.meta.url));
const { createElement } = req('react') as { createElement: (t: unknown, p: unknown) => unknown };
const { renderToStaticMarkup } = req('react-dom/server') as { renderToStaticMarkup: (e: unknown) => string };

const KIT = new URL('../../research/harness-2026-11/COMPREHENSION/kit/', import.meta.url);
const WRITE = process.env.KIT_WRITE === '1';
/** when the outputs are produced; replay inputs show the replay data time, not an age, so this does not reach any text */
const NOW = '2026-11-12T10:00:00Z';

type CaseId = 'C1' | 'C2' | 'C3' | 'C4' | 'C5';
const RULE: Record<CaseId, string> = {
  C1: 'leave_by, after = horizon ("later departures not checked")',
  C2: 'leave_by, after = gap, and the staff headline carries a later window',
  C3: 'partial',
  C4: 'no_route',
  C5: 'unresolved',
};

function state(p: MessagePlan, laterWindow: boolean): CaseId | null {
  if (p.kind === 'leave_by' && p.after === 'horizon') return 'C1';
  if (p.kind === 'leave_by' && p.after === 'gap' && laterWindow) return 'C2';
  if (p.kind === 'partial') return 'C3';
  if (p.kind === 'no_route') return 'C4';
  if (p.kind === 'unresolved') return 'C5';
  return null;
}

const sha = (s: string | Buffer) => createHash('sha256').update(s).digest('hex');

describe('comprehension kit items', () => {
  it('selects the five cases and every item is the production output', async () => {
    const pvPath = '../../planner/src/features/publicview/PublicView';
    const { Card } = (await import(/* @vite-ignore */ pvPath)) as { Card: unknown };
    const caches = loadBoothCaches();
    const picked = new Map<CaseId, { cache: (typeof caches)[number]; inputIdx: number }>();
    // fixed rule: caches in planner/cache/INDEX.json order; within a cache, origins by ascending origin id
    for (const c of caches) {
      const order = c.inputs.map((i, k) => [i.origin.id, k] as const).sort((a, b) => a[0].localeCompare(b[0]));
      for (const [, k] of order) {
        const i = c.inputs[k]!;
        const p = messagePlan(i, null);
        const s = state(p, deadlineHeadline(c.plans[i.origin.id]).laterWindowS !== null);
        if (s && !picked.has(s)) picked.set(s, { cache: c, inputIdx: k });
      }
    }
    // how many origins of the replay are in each state (all six caches); recorded so a missing case is visible
    const tally: Record<string, number> = {};
    for (const c of caches) {
      for (const i of c.inputs) {
        const p = messagePlan(i, null);
        const h = deadlineHeadline(c.plans[i.origin.id]);
        const k = `kit ${p.kind}${p.after ? `/${p.after}` : ''} · staff ${h.kind}${h.laterWindowS !== null ? '+later_window' : ''}`;
        tally[k] = (tally[k] ?? 0) + 1;
      }
    }
    const files: Record<string, string> = {};
    const cases: unknown[] = [];
    for (const id of ['C1', 'C2', 'C3', 'C4', 'C5'] as CaseId[]) {
      const hit = picked.get(id);
      if (!hit) {
        cases.push({ case: id, rule: RULE[id], found: false, note: 'no origin of the six booth caches is in this state' });
        continue;
      }
      const { cache, inputIdx } = hit;
      const input = cache.inputs[inputIdx]!;
      const p = messagePlan(input, null);
      const set = buildChannels(p, { nowIso: NOW });
      const card = cardFor(input, coordsOf(cache.places));
      const h = deadlineHeadline(cache.plans[input.origin.id]);
      files[`items/${id}/head.ko.txt`] = set.text.ko.head.script;
      files[`items/${id}/sms.ko.txt`] = set.text.ko.familyText;
      // the card's GPX link is an object URL (random per render): a fixed placeholder keeps the item byte-stable
      const realObjectUrl = URL.createObjectURL;
      URL.createObjectURL = () => 'blob:replay-gpx';
      try {
        files[`items/${id}/card.ko.html`] = renderToStaticMarkup(createElement(Card, { card, lang: 'ko', example: false }));
      } finally {
        URL.createObjectURL = realObjectUrl;
      }
      cases.push({
        case: id,
        rule: RULE[id],
        found: true,
        cache: cache.entry.path,
        region: cache.entry.regionId,
        scenario_set_id: cache.entry.scenarioSetId,
        input_time: cache.entry.inputTime,
        origin_id: input.origin.id,
        kit_kind: p.kind,
        kit_after: p.after,
        staff_headline_kind: h.kind,
        staff_later_window: h.laterWindowS !== null,
        head_seconds: { core: set.text.ko.head.coreS, full: set.text.ko.head.fullS, core_slow: set.text.ko.head.coreSlowS, full_slow: set.text.ko.head.fullSlowS },
        violations: set.violations,
      });
    }
    files['CASES.json'] = JSON.stringify({ schema: 'wfg.comprehension.cases/1', rule: 'first origin id (ascending) of each state, caches in planner/cache/INDEX.json order', now_iso: NOW, options: 'buildChannels(plan, { nowIso }) — no order status, issuer or issue-order-by supplied', origins_by_state: Object.fromEntries(Object.entries(tally).sort()), cases }, null, 2) + '\n';
    const manifest: Record<string, string> = {};
    for (const [rel, body] of Object.entries(files)) {
      const url = new URL(rel, KIT);
      manifest[rel] = sha(body);
      if (WRITE) {
        mkdirSync(new URL('.', url), { recursive: true });
        writeFileSync(url, body);
      } else {
        expect(existsSync(url), `${rel} missing — run with KIT_WRITE=1`).toBe(true);
        expect(readFileSync(url, 'utf8'), `${rel} differs from the production output`).toBe(body);
      }
    }
    const m = JSON.stringify(manifest, null, 2) + '\n';
    if (WRITE) writeFileSync(new URL('MANIFEST.generated.json', KIT), m);
    else expect(readFileSync(new URL('MANIFEST.generated.json', KIT), 'utf8')).toBe(m);
  }, 600_000);
});
