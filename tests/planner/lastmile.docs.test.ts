/**
 * planner/docs/LASTMILE.md stays true to the code: every example block marked
 * `<!-- example <cache path> <origin id> <lang>.<output> -->` equals the kit's output for that origin
 * of that booth cache with the scenario's deadline explanation file (as the panel shows it), §2's
 * statement of what each output of a leave-by origin gives holds for every leave-by origin of the six
 * booth caches (with the counts it states), and the forbidden-word list in §3 is exactly strings.ts
 * FORBIDDEN.
 */
import { readFileSync } from 'node:fs';
import { beforeAll, describe, expect, it } from 'vitest';
import { LASTMILE_CSV_COLUMNS } from '../../planner/src/features/lastmile/csv';
import { allTexts, buildFieldMessages } from '../../planner/src/features/lastmile/messages';
import { FORBIDDEN } from '../../planner/src/features/lastmile/strings';
import { loadBoothCaches, realExplanationFor, type BoothCache } from './lastmile.cachedata';
import { leaveByOutputFacts } from './lastmile.oracle';

const DOC = readFileSync(new URL('../../planner/docs/LASTMILE.md', import.meta.url), 'utf8');
const EXAMPLE = /<!-- example (\S+) (\S+) (ko|en)\.(sms|lms|broadcast|call|card) -->\n```text\n([\s\S]*?)\n```/g;

let caches: BoothCache[] = [];

beforeAll(() => {
  caches = loadBoothCaches();
}, 180_000);

describe('planner/docs/LASTMILE.md', () => {
  it('every example in §11 is the kit\'s output for that real origin (with the scenario\'s explanation file)', () => {
    const examples = [...DOC.matchAll(EXAMPLE)];
    expect(examples.length).toBeGreaterThanOrEqual(20);
    // the four outputs (and the card) all appear, in both languages
    const outs = new Set(examples.map((m) => `${m[3]}.${m[4]}`));
    for (const o of ['ko.sms', 'ko.lms', 'ko.broadcast', 'ko.call', 'ko.card', 'en.sms', 'en.lms', 'en.broadcast', 'en.call', 'en.card']) expect(outs.has(o), o).toBe(true);
    // an origin the cache holds no result for shows that on its data line (§2), as a real example
    expect(examples.some((m) => m[4] === 'lms' && m[5]!.split('\n')[2]!.endsWith(' · 이 출발지 결과 없음'))).toBe(true);
    const covered = new Set<string>();
    for (const [, path, id, lang, kind, text] of examples) {
      const cache = caches.find((c) => c.entry.path === path);
      expect(cache, path).toBeDefined();
      const input = cache!.inputs.find((i) => i.origin.id === id);
      expect(input, `${path} ${id}`).toBeDefined();
      const { file, error } = realExplanationFor(cache!);
      expect(error ?? null).toBeNull();
      expect(file, `the explanation file of ${path} (it ships in planner/public/data/explanations/)`).not.toBeNull();
      const fm = buildFieldMessages(input!, file);
      expect(fm.violations).toEqual([]);
      expect(text, `${path} ${id} ${lang}.${kind}`).toBe(allTexts(fm, lang as 'ko' | 'en')[kind as 'sms']);
      covered.add(`${fm.kind} ${lang}.${kind}`);
    }
    // every Korean output of every message kind the booth caches hold has a real example
    for (const k of ['leave_by', 'no_route', 'unresolved']) {
      for (const o of ['sms', 'lms', 'broadcast', 'call', 'card']) expect(covered.has(`${k} ko.${o}`), `${k} ko.${o}`).toBe(true);
    }
  }, 60_000);

  it('§2 says per output what a leave-by origin\'s messages give — true for every leave-by origin of the six caches, with the counts it states', () => {
    // the old sentence claimed that every output carried every item (destination, arrival, "do not wait", …)
    expect(DOC).not.toContain('Each output gives');
    const flat = DOC.replace(/\s+/g, ' ');
    for (const head of [
      '**long text and card**: leave by T with "do not wait until this time"',
      '**SMS**: T, the data time and the short forms of the mandatory lines (§3) — no destination, arrival time, "do not wait" or what limits T',
      '**broadcast and call script**: T and the destination',
      'What limits T: the call script always, the broadcast only when the 60 s budget leaves room for that optional block (§5)',
    ]) {
      expect(flat, head).toContain(head);
    }
    const said = /Over the (\d+) leave-by origins of the six booth caches with their explanation files \(what the panel shows\), what limits T is in (\d+) Korean and (\d+) English broadcasts, the Korean broadcast leaves the destination out for (\d+) \(60 s\), and the English broadcast and call script cannot name it for (\d+) \(no Latin-script name\)/.exec(flat);
    expect(said, 'the counts sentence of §2').not.toBeNull();
    let n = 0;
    let noLatin = 0;
    const reason = { ko: 0, en: 0 };
    const leftOut = { ko: 0, en: 0 };
    const bad: string[] = [];
    for (const cache of caches) {
      const { file, error } = realExplanationFor(cache);
      expect(error ?? null).toBeNull();
      expect(file, cache.entry.path).not.toBeNull();
      for (const input of cache.inputs) {
        const fm = buildFieldMessages(input, file);
        if (fm.kind !== 'leave_by') continue;
        n += 1;
        const f = leaveByOutputFacts(fm);
        bad.push(...f.violations.map((v) => `${cache.entry.path} ${input.origin.id} ${v}`));
        for (const l of ['ko', 'en'] as const) {
          if (f.broadcastReason[l]) reason[l] += 1;
          if (f.destinationLeftOut60s[l]) leftOut[l] += 1;
        }
        if (f.noLatinName) noLatin += 1;
      }
    }
    expect(bad).toEqual([]);
    // §2 names the Korean broadcast only: no English broadcast leaves its destination out for time
    expect(leftOut.en).toBe(0);
    expect(said!.slice(1).map(Number)).toEqual([n, reason.ko, reason.en, leftOut.ko, noLatin]);
  }, 60_000);

  it('§8 names the CSV\'s counter columns as csv.ts writes them', () => {
    const flat = DOC.replace(/\s+/g, ' ');
    expect(flat).toContain("the counters of the SMS and the broadcast in both languages and of the Korean long text (the English long text's bytes and the call scripts' estimated seconds are in the dialog only)");
    expect(LASTMILE_CSV_COLUMNS.en.filter((c) => /bytes|characters|seconds/.test(c))).toEqual([
      'SMS KO bytes (EUC-KR; max 90)',
      'Long text KO bytes (max 2000)',
      'Broadcast KO est. seconds (max 60)',
      'SMS EN GSM-7 characters (max 160)',
      'Broadcast EN est. seconds (max 60)',
    ]);
  });

  it('§3 lists every forbidden word of strings.ts FORBIDDEN, and nothing else', () => {
    const block = DOC.slice(DOC.indexOf('<!-- forbidden-list -->'), DOC.indexOf('<!-- /forbidden-list -->'));
    const ko = /- Korean \((\d+)\): (.*)/.exec(block)!;
    const en = /- English \((\d+)\): (.*)/.exec(block)!;
    const words = (line: string) => [...line.matchAll(/`([^`]+)`/g)].map((m) => m[1]);
    expect(words(ko[2]!)).toEqual(FORBIDDEN.ko);
    expect(words(en[2]!)).toEqual(FORBIDDEN.en);
    expect(Number(ko[1])).toBe(FORBIDDEN.ko.length);
    expect(Number(en[1])).toBe(FORBIDDEN.en.length);
  });

  it('states the limitation that the kit is not an official alerting channel', () => {
    expect(DOC).toContain('Not an official alerting channel — 재난문자·공식 경보가 아닙니다.');
    expect(DOC).not.toMatch(/150–160 wpm|not in this branch|nobody lives there/);
  });
});
