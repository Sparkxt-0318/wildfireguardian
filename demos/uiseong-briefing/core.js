/* Deterministic comparison of archived observations, the return corridor, and the review clock. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WfgBriefing = factory();
})(globalThis, function () {
  'use strict';

  function checkIndex(value, count, name) {
    if (!Number.isInteger(value) || value < 0 || value >= count) {
      throw new RangeError(name + ' must identify an observation');
    }
  }

  // The replay clock models acquisition-time availability. Receipt at the incident is unknown.
  function validForecast(forecasts, reviewMs) {
    let best = null;
    let mostRecent = -Infinity;
    for (const forecast of forecasts) {
      const start = Date.parse(forecast.origin);
      const end = Date.parse(forecast.validEnd);
      if (start <= reviewMs && reviewMs < end && start > mostRecent) {
        best = forecast;
        mostRecent = start;
      }
    }
    return best;
  }

  function corridorStretches(watch, roads, flagged, newlyFlagged) {
    const stretches = [];
    if (!watch) return stretches;
    if (watch.points.length !== watch.ids.length + 1) {
      throw new RangeError('A watched path must include one more vertex than segment');
    }
    const roadById = new Map(roads.map((road) => [road.id, road]));
    let active = null;
    let lastGroup = null;
    for (let i = 0; i < watch.ids.length; i++) {
      const id = watch.ids[i];
      if (!flagged.has(id)) {
        active = null;
        continue;
      }
      const road = roadById.get(id);
      if (!road) throw new RangeError('Unknown return corridor segment: ' + id);
      // Combine consecutive segments on the same named road. On an unnamed road
      // retain the OSM way identity, so unrelated unnamed roads stay separate.
      const name = road.osmName || road.ref;
      const group = name || id.split(':')[0];
      if (!active || group !== lastGroup) {
        active = {
          ids: [],
          label: name || '도로명 미등록 · ' + (road.mapId || id),
          start: watch.points[i],
          end: watch.points[i + 1],
          newIds: [],
        };
        stretches.push(active);
        lastGroup = group;
      }
      active.ids.push(id);
      active.end = watch.points[i + 1];
      if (newlyFlagged.has(id)) active.newIds.push(id);
    }
    return stretches;
  }

  function evaluate(data, { index, baselineIndex = null, reviewMs }) {
    const frames = data.replay.frames;
    checkIndex(index, frames.length, 'index');
    if (baselineIndex !== null) checkIndex(baselineIndex, frames.length, 'baselineIndex');

    const frame = frames[index];
    const acquired = Date.parse(frame.sourceTime);
    const clock = reviewMs === undefined ? acquired : reviewMs;
    const next = index + 1 < frames.length ? Date.parse(frames[index + 1].sourceTime) : Infinity;
    if (!Number.isFinite(clock) || !Number.isFinite(acquired) || !(acquired <= clock && clock < next)) {
      throw new RangeError('Review time must fall in this observation interval');
    }

    const futurePin = baselineIndex !== null && baselineIndex > index;
    const hasPin = baselineIndex !== null && !futurePin;
    const baseIndex = hasPin ? baselineIndex : index > 0 ? index - 1 : null;
    const base = baseIndex === null ? null : frames[baseIndex];
    const current = [...new Set(frame.affected)];
    const flagged = new Set(current);
    const old = new Set(base ? base.affected : []);
    const newIds = base ? current.filter((id) => !old.has(id)) : [];
    const newlyFlagged = new Set(newIds);
    const stretches = corridorStretches(data.watch, data.replay.roads, flagged, newlyFlagged);
    const watchHits = [...new Set(stretches.flatMap((stretch) => stretch.ids))];

    return {
      index,
      frame,
      current,
      newIds,
      kept: current.filter((id) => old.has(id)),
      gone: [...old].filter((id) => !flagged.has(id)),
      baselineIndex: baseIndex,
      comparisonSource: futurePin
        ? 'future-review-ignored'
        : hasPin
          ? 'reviewed'
          : base
            ? 'previous'
            : 'initial',
      reviewMs: clock,
      ageMinutes: Math.floor((clock - acquired) / 60000),
      gapMinutes: base ? (acquired - Date.parse(base.sourceTime)) / 60000 : null,
      watchHits,
      watchNew: watchHits.filter((id) => newlyFlagged.has(id)),
      stretches,
      forecast: validForecast(data.forecast ? data.forecast.frames : [], clock),
    };
  }

  return { evaluate };
});
