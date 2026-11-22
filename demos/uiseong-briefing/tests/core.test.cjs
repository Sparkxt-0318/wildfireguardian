'use strict';
const { test } = require('node:test');
const { strict: assert } = require('node:assert');
const { evaluate } = require('../core.js');
require('../data.js');
const data = globalThis.WFG_DATA;
const at = (index, baselineIndex, reviewMs) => evaluate(data, { index, baselineIndex, reviewMs });
const ms = Date.parse;

test('March 24 at 13:22 uses the 13:07 pass and the 12:44 reviewed briefing', () => {
  const before = at(5);
  const v = at(6, 5, ms('2025-03-24T13:22:00+09:00'));
  assert.equal(before.watchHits.length, 0);
  assert.equal(v.baselineIndex, 5);
  assert.equal(v.comparisonSource, 'reviewed');
  assert.equal(v.frame.sourceTime, '2025-03-24T04:07:00Z');
  assert.equal(v.ageMinutes, 15);
  assert.equal(v.gapMinutes, 23);
  assert.equal(v.current.length, 245);
  assert.equal(v.newIds.length, 187);
  assert.equal(v.kept.length, 58);
  assert.equal(v.gone.length, 4);
  assert.equal(v.watchHits.length, 17);
  assert.deepEqual(v.watchNew, v.watchHits);
  assert.equal(v.forecast, null);
  assert.deepEqual(
    v.stretches.map((s) => [s.label, s.ids.length]),
    [
      ['신감옥산로', 6],
      ['신감옥산로', 11],
    ],
  );
  for (const [i, j] of [
    [0, 26],
    [1, 36],
  ]) {
    const s = v.stretches[i];
    assert.deepEqual(s.start, data.watch.points[j]);
    assert.deepEqual(s.end, data.watch.points[j + s.ids.length]);
    assert.deepEqual(s.newIds, s.ids);
  }
});

test('first, same-frame, older and future-reviewed comparisons each have a defined baseline', () => {
  const first = at(0);
  assert.equal(first.baselineIndex, null);
  assert.equal(first.gapMinutes, null);
  assert.equal(first.comparisonSource, 'initial');
  assert.deepEqual([first.newIds, first.kept, first.gone], [[], [], []]);
  const self = at(5, 5);
  assert.deepEqual(self.kept, self.current);
  assert.equal(self.newIds.length + self.gone.length, 0);
  assert.equal(self.gapMinutes, 0);
  const pinned = at(7, 5);
  assert.equal(pinned.baselineIndex, 5);
  assert.deepEqual(
    pinned.newIds,
    data.replay.frames[7].affected.filter((x) => !data.replay.frames[5].affected.includes(x)),
  );
  assert.notDeepEqual(pinned.newIds, at(7).newIds);
  const rewind = at(4, 5);
  assert.equal(rewind.baselineIndex, 3);
  assert.equal(rewind.comparisonSource, 'future-review-ignored');
  assert.deepEqual(rewind.newIds, at(4).newIds);
  assert.deepEqual(at(0, 5).newIds, []);
});

test('forecast becomes valid exactly at its origin and expires exactly at the one-hour boundary', () => {
  for (const fc of data.forecast.frames) {
    const start = ms(fc.origin),
      end = ms(fc.validEnd);
    for (const [when, expected] of [
      [start - 1, null],
      [start, fc],
      [end - 1, fc],
      [end, null],
    ]) {
      const idx = data.replay.frames.findLastIndex((frame) => ms(frame.sourceTime) <= when);
      assert.equal(at(idx, null, when).forecast, expected);
    }
  }
});

test('all 20 transitions between the 21 observations reproduce the archived changes', () => {
  for (let i = 1; i < data.replay.frames.length; i++) {
    const v = at(i),
      frame = data.replay.frames[i];
    assert.deepEqual(new Set(v.newIds), new Set(frame.added));
    assert.deepEqual(new Set(v.gone), new Set(frame.removed));
    assert.equal(v.current.length, v.kept.length + v.newIds.length);
    assert.equal(v.ageMinutes, 0);
  }
});

test('reject malformed indices, acquisition lookahead and skipping a newer archived observation', () => {
  for (const bad of [-1, 0.5, data.replay.frames.length]) {
    assert.throws(() => at(bad), RangeError);
    assert.throws(() => at(1, bad), RangeError);
  }
  assert.throws(() => at(6, null, ms(data.replay.frames[6].sourceTime) - 1), RangeError);
  assert.throws(() => at(6, null, ms(data.replay.frames[7].sourceTime)), RangeError);
  assert.throws(() => at(6, null, NaN), RangeError);
});
