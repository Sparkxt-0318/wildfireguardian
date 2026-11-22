// Verify the displayed data in the checkout without requiring the external study archive.
const test = require('node:test');
const assert = require('node:assert/strict');
require('../data.js');
const { replay, watch } = globalThis.WFG_DATA;

function distanceSquared(point, a, b) {
  const dx = b[0] - a[0],
    dy = b[1] - a[1],
    squared = dx * dx + dy * dy;
  const along = squared ? ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / squared : 0;
  const t = Math.min(1, Math.max(0, along));
  return (point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2;
}

test('every proximity flag matches the displayed historic road and pixel-centre geometry', () => {
  assert.equal(replay.frames.length, 21);
  assert.equal(replay.roads.length, 2453);
  assert.equal(replay.radiusM, 375);
  const roads = replay.roads;
  let positives = 0,
    detections = 0;
  for (const f of replay.frames) {
    assert.equal(f.receiptTime, null);
    detections += f.detections.length;
    const actual = new Set(
      roads
        .filter((r) => {
          assert.equal(r.points.length, 2);
          return f.detections.some((p) => distanceSquared(p, r.points[0], r.points[1]) <= 375 ** 2);
        })
        .map((r) => r.id),
    );
    assert.deepEqual(actual, new Set(f.affected), f.sourceTime);
    positives += actual.size;
  }
  assert.equal(detections, 476);
  assert.equal(positives, 3451);
});

test('the featured corridor follows the displayed road chords in travel order', () => {
  const roads = new Map(replay.roads.map((r) => [r.id, r]));
  const close = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < 0.001;
  assert.equal(watch.ids.length, 123);
  assert.equal(watch.points.length, watch.ids.length + 1);
  watch.ids.forEach((id, i) => {
    const [a, b] = roads.get(id).points,
      p = watch.points[i],
      q = watch.points[i + 1];
    assert.ok((close(a, p) && close(b, q)) || (close(b, p) && close(a, q)), id);
  });
});
