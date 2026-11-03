/**
 * planner/docs/LASTMILE.md stays true to the code: every example block marked
 * `<!-- example <cache path> <origin id> <lang>.<output> -->` equals the kit's output for that origin
 * of that booth cache with the scenario's deadline explanation file (as the panel shows it), and the
 * forbidden-word list in §3 is exactly strings.ts FORBIDDEN.
 */
import { readFileSync } from 'node:fs';
import { beforeAll, describe, expect, it } from 'vitest';
import { allTexts, buildFieldMessages } from '../../planner/src/features/lastmile/messages';
import { FORBIDDEN } from '../../planner/src/features/lastmile/strings';
import { loadBoothCaches, realExplanationFor, type BoothCache } from './lastmile.cachedata';

const DOC = readFileSync(new URL('../../planner/docs/LASTMILE.md', import.meta.url), 'utf8');
const EXAMPLE = /<!-- example (\S+) (\S+) (ko|en)\.(sms|lms|broadcast|call|card) -->\n```text\n([\s\S]*?)\n```/g;

let caches: BoothCache[] = [];

beforeAll(() => {
  caches = loadBoothCaches();
}, 180_000);

describe('planner/docs/LASTMILE.md', () => {
  it('every example in §11 is the kit\'s output for that real origin (with the scenario\'s explanation file)', () => {
    const examples = [...DOC.matchAll(EXAMPLE)];
    expect(examples.length).toBeGreaterThanOrEqual(17);
    // the four outputs (and the card) all appear, in both languages
    const outs = new Set(examples.map((m) => `${m[3]}.${m[4]}`));
    for (const o of ['ko.sms', 'ko.lms', 'ko.broadcast', 'ko.call', 'ko.card', 'en.sms', 'en.lms', 'en.broadcast', 'en.call', 'en.card']) expect(outs.has(o), o).toBe(true);
    // an origin the cache holds no result for shows that on its data line (§2), as a real example
    expect(examples.some((m) => m[4] === 'lms' && m[5]!.split('\n')[2]!.endsWith(' · 이 출발지 결과 없음'))).toBe(true);
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
    }
  }, 60_000);

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
