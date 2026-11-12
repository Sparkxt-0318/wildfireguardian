// The archived roads and thermal-pixel centres share a projected CRS in metres.
// Keep the map north-up and apply the same transformation to every layer.
(function (global) {
  'use strict';
  const ns = 'http://www.w3.org/2000/svg';
  const ink = '#253c43';
  const colors = {
    added: '#b74919',
    kept: '#15736e',
    gone: '#71798a',
    watch: '#504c9b',
    hotspot: '#7e325a',
    chosen: '#153743',
  };

  function el(tag, attrs = {}, content) {
    const element = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) element.setAttribute(k, v);
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function create(svg, data, onRoadSelect) {
    const { replay, watch, forecast } = data;
    const roads = new Map(replay.roads.map((r) => [r.id, r]));
    const watchIndex = new Map((watch?.ids || []).map((id, i) => [id, i]));
    const [west, south, east, north] = replay.bounds;
    const regionSize = Math.max(east - west, north - south);
    const rootId = (svg.id || 'replay-map') + '-extent';
    let cx,
      cy,
      extent,
      state = null,
      display = {},
      drag = null,
      suppressClick = false;

    function resetView() {
      cx = (west + east) / 2;
      cy = (south + north) / 2;
      extent = regionSize * 1.06;
    }
    resetView();

    function size() {
      const rect = svg.getBoundingClientRect();
      return {
        w: Math.max(240, Math.round(rect.width) || 720),
        h: Math.max(200, Math.round(rect.height) || 420),
      };
    }
    function camera() {
      const { w, h } = size();
      const scale = Math.min(w, h) / extent;
      const xy = ([x, y]) => [(x - cx) * scale + w / 2, (cy - y) * scale + h / 2];
      return { w, h, scale, xy };
    }

    function paint() {
      if (!state) return;
      const { w, h, scale, xy } = camera();
      const line = (p) =>
        p
          .map(
            (v, j) =>
              (j ? 'L' : 'M') +
              xy(v)
                .map((k) => k.toFixed(2))
                .join(','),
          )
          .join('');
      const paths = new Map();
      for (const [id, road] of roads) paths.set(id, line(road.points));
      const joined = (ids) => ids.map((id) => paths.get(id) || '').join('');
      const roadPath = (d, stroke, width, extra = {}) =>
        el('path', {
          d,
          stroke,
          fill: 'none',
          'stroke-width': width,
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round',
          ...extra,
        });
      const title = el('title', {}, '의성·안동 위성 열점과 도로 구간');
      const desc = el(
        'desc',
        {},
        '위성 관측 시각의 열점 중심과 인접 도로, 선택한 훈련용 복귀 동선 및 구간을 표시합니다.',
      );
      svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
      svg.setAttribute('role', 'img');
      svg.replaceChildren(title, desc);
      function group(id, parent = svg) {
        const g = el('g', { id });
        parent.append(g);
        return g;
      }

      const [left, top] = xy([west, north]);
      const aoi = { x: left, y: top, width: (east - west) * scale, height: (north - south) * scale };
      const defs = el('defs');
      const clip = el('clipPath', { id: rootId });
      clip.append(el('rect', aoi));
      defs.append(clip);
      svg.append(
        defs,
        el('rect', { width: w, height: h, fill: '#eef1eb', 'pointer-events': 'none' }),
        el('rect', {
          ...aoi,
          fill: '#f7f6ed',
          stroke: '#d6ddd0',
          'stroke-width': 1,
          'pointer-events': 'none',
        }),
      );
      const geo = el('g', { 'clip-path': 'url(#' + rootId + ')' });
      svg.append(geo);
      const predictive = group('layer-forecast', geo);
      if (display.showForecast && state.forecast) {
        const f = state.forecast;
        for (const [x, y, k] of f.tiles) {
          const [px, py] = xy([x, y + f.cellSize]);
          predictive.append(
            el('rect', {
              x: px,
              y: py,
              width: f.cellSize * scale,
              height: f.cellSize * scale,
              'data-category': k,
              fill: forecast.colors[k],
              'shape-rendering': 'crispEdges',
              opacity: 0.78,
            }),
          );
        }
      }
      const major = [],
        minor = [];
      for (const [id, r] of roads) {
        (/^(motorway|trunk|primary|secondary|tertiary)(?:_link)?$/.test(r.highway) ? major : minor).push(
          id,
        );
      }
      const base = group('layer-roads', geo);
      base.append(
        roadPath(joined(minor), '#bac4b9', 1.15),
        roadPath(joined(major), '#b9b5a4', 3.4),
        roadPath(joined(major), '#fffdf4', 1.7),
      );

      const frame = replay.frames[state.index];
      const circles = group('layer-proximity', geo);
      for (const [i, p] of frame.detections.entries()) {
        const [x, y] = xy(p);
        circles.append(
          el('circle', {
            cx: x,
            cy: y,
            r: replay.radiusM * scale,
            fill: '#bd704b',
            'fill-opacity': 0.042,
            stroke: '#aa7f64',
            'stroke-width': 0.65,
            'stroke-opacity': 0.4,
            'data-radius-index': i,
          }),
        );
      }
      const watched = group('layer-watch', geo);
      if (display.showWatch && watch) {
        const d = line(watch.points);
        watched.append(
          roadPath(d, '#fff', 6.3),
          roadPath(d, colors.watch, 3.8, { 'stroke-dasharray': '6 4' }),
        );
      }
      const changes = group('layer-road-changes', geo);
      const initial = state.baselineIndex === null || state.baselineIndex === undefined;
      const shown = [
        {
          ids: display.showGone ? state.gone : [],
          color: colors.gone,
          width: 2.5,
          dash: '4 4',
          kind: 'gone',
        },
        { ids: initial ? state.current : state.kept, color: colors.kept, width: 3, kind: 'current' },
        { ids: state.newIds, color: colors.added, width: 3.7, kind: 'new' },
      ];
      for (const s of shown) {
        if (!s.ids.length) continue;
        const d = joined(s.ids);
        changes.append(
          roadPath(d, '#fff', s.width + 1.5),
          roadPath(d, s.color, s.width, s.dash ? { 'stroke-dasharray': s.dash } : {}),
        );
      }
      const hit = group('layer-road-targets', geo);
      for (const s of shown)
        for (const id of s.ids) {
          const road = roads.get(id);
          if (!road) continue;
          const target = roadPath(paths.get(id), 'transparent', 9, {
            'pointer-events': 'stroke',
            'data-road-id': id,
            'data-kind': s.kind,
            style: 'cursor:pointer',
          });
          target.append(
            el('title', {}, (road.osmName || road.ref || '이름 미등록') + ' · ' + road.mapId),
          );
          hit.append(target);
        }
      const hotspots = group('layer-hotspots', geo);
      hotspots.setAttribute('pointer-events', 'none');
      for (const [i, p] of frame.detections.entries()) {
        const [x, y] = xy(p),
          r = 3.8;
        hotspots.append(
          el('path', {
            'data-detection': i,
            d: `M${x} ${y - r}l${r} ${r} -${r} ${r} -${r} -${r}Z`,
            fill: colors.hotspot,
            stroke: '#fff',
            'stroke-width': 1.1,
          }),
        );
      }

      const selection = group('layer-selection', geo);
      selection.setAttribute('pointer-events', 'none');
      const ids = (display.selectedIds || []).filter((id) => roads.has(id));
      const exclude = [];
      if (ids.length) {
        selection.append(roadPath(joined(ids), '#fff', 8));
        for (const id of ids)
          selection.append(roadPath(paths.get(id), colors.chosen, 4.8, { 'data-selected-id': id }));
        const first = ids[0],
          last = ids[ids.length - 1];
        const allOrderedWatch = ids.every(
          (id, i) => watchIndex.has(id) && (!i || watchIndex.get(id) === watchIndex.get(ids[i - 1]) + 1),
        );
        const start = allOrderedWatch ? watch.points[watchIndex.get(first)] : roads.get(first).points[0];
        const end = allOrderedWatch
          ? watch.points[watchIndex.get(last) + 1]
          : roads.get(last).points.at(-1);
        for (const [label, p, dx] of [
          ['A', start, -12],
          ['B', end, 12],
        ]) {
          const [x, y] = xy(p);
          const pin = el('g', {
            'data-marker': label,
            transform: `translate(${x.toFixed(2)} ${y.toFixed(2)})`,
          });
          pin.append(
            el('circle', { r: 3, fill: colors.chosen, stroke: 'white', 'stroke-width': 1 }),
            roadPath(`M0 0L${dx} -15`, colors.chosen, 1.5),
            el('circle', {
              cx: dx,
              cy: -17,
              r: 9,
              fill: colors.chosen,
              stroke: 'white',
              'stroke-width': 1.2,
            }),
            el(
              'text',
              {
                x: dx,
                y: -13.7,
                'text-anchor': 'middle',
                'font-size': 10,
                'font-weight': 750,
                fill: '#fff',
              },
              label,
            ),
          );
          selection.append(pin);
          exclude.push([x + dx, y - 17, 32]);
        }
      }

      // Label named roads on the current view, with the selected road given priority.
      const labelLayer = group('layer-road-labels', geo);
      labelLayer.setAttribute('pointer-events', 'none');
      const groups = new Map();
      for (const id of [...new Set([...ids, ...state.newIds, ...state.current, ...major])]) {
        const r = roads.get(id),
          name = r?.osmName || r?.ref;
        if (!name) continue;
        if (!groups.has(name)) groups.set(name, []);
        groups.get(name).push(r);
      }
      let placed = 0;
      for (const [name, entries] of groups) {
        if (placed >= 5) break;
        for (const r of [entries[Math.floor(entries.length / 2)], ...entries]) {
          const [x, y] = xy(r.points[0]);
          const lw = Math.min(150, 10 * name.length + 8);
          if (
            x < 18 ||
            x + lw > w - 22 ||
            y < 35 ||
            y > h - 33 ||
            exclude.some(([ox, oy, ow]) => x < ox + ow && x + lw > ox && Math.abs(y - oy) < 22)
          )
            continue;
          labelLayer.append(
            el(
              'text',
              {
                x: x + 5,
                y: y - 6,
                fill: ink,
                stroke: '#fffef7',
                'stroke-width': 3.2,
                'paint-order': 'stroke',
                'font-size': 12,
                'font-weight': 650,
              },
              name,
            ),
          );
          exclude.push([x, y, lw]);
          placed++;
          break;
        }
      }

      const chrome = group('layer-scale');
      chrome.setAttribute('pointer-events', 'none');
      chrome.append(
        el(
          'text',
          { x: 19, y: 18, fill: ink, 'font-size': 11, 'font-weight': 750, 'text-anchor': 'middle' },
          '북',
        ),
        el('path', { d: 'M19 22l-4.6 14 4.6-3.5 4.6 3.5Z', fill: ink }),
      );
      const desired = 72 / scale,
        power = 10 ** Math.floor(Math.log10(desired));
      const metres = ([5, 2, 1].find((k) => k * power <= desired) || 1) * power;
      const x = w - 13,
        y = h - 13;
      chrome.append(
        roadPath(`M${x - metres * scale} ${y - 3}v3H${x}v-3`, ink, 1.7),
        el(
          'text',
          {
            x,
            y: y - 6,
            'text-anchor': 'end',
            'font-size': 10,
            'font-weight': 650,
            fill: ink,
            stroke: '#f4f4eb',
            'stroke-width': 2.8,
            'paint-order': 'stroke',
          },
          metres >= 1000 ? metres / 1000 + ' km' : metres + ' m',
        ),
      );
    }

    function focus(ids) {
      const pts = Array.from(ids || []).flatMap((id) => roads.get(id)?.points || []);
      if (!pts.length) return;
      let minX = Infinity,
        minY = Infinity,
        maxX = -Infinity,
        maxY = -Infinity;
      for (const [x, y] of pts) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
      cx = (minX + maxX) / 2;
      cy = (minY + maxY) / 2;
      extent = Math.min(regionSize * 1.3, Math.max(450, 1.45 * Math.max(maxX - minX, maxY - minY)));
      paint();
    }

    svg.addEventListener('click', (ev) => {
      if (suppressClick) {
        suppressClick = false;
        return;
      }
      const id = ev.target.closest?.('[data-road-id]')?.getAttribute('data-road-id');
      if (id && onRoadSelect) onRoadSelect(id);
    });
    // Capture only after crossing the drag threshold so a normal tap still selects the road.
    svg.style.touchAction = 'none';
    svg.addEventListener('pointerdown', (ev) => {
      if (!ev.isPrimary || ev.button !== 0) return;
      drag = { id: ev.pointerId, x: ev.clientX, y: ev.clientY, cx, cy, moved: false };
      suppressClick = false;
    });
    svg.addEventListener('pointermove', (ev) => {
      if (!drag || ev.pointerId !== drag.id) return;
      const dx = ev.clientX - drag.x,
        dy = ev.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 5) return;
      if (!drag.moved) svg.setPointerCapture(ev.pointerId);
      drag.moved = true;
      const { scale } = camera();
      cx = Math.max(west, Math.min(east, drag.cx - dx / scale));
      cy = Math.max(south, Math.min(north, drag.cy + dy / scale));
      paint();
    });
    const release = (ev) => {
      if (drag && ev.pointerId === drag.id) {
        suppressClick = drag.moved;
        drag = null;
      }
    };
    svg.addEventListener('pointerup', release);
    svg.addEventListener('pointercancel', release);
    svg.addEventListener('pointerleave', (ev) => {
      if (drag && !drag.moved) release(ev);
    });
    if (typeof ResizeObserver === 'function') new ResizeObserver(() => paint()).observe(svg);
    return {
      render(result, options = {}) {
        state = result;
        display = options;
        paint();
      },
      reset() {
        resetView();
        paint();
      },
      zoom(factor) {
        if (!(factor > 0) || !Number.isFinite(factor)) return;
        extent = Math.max(160, Math.min(regionSize * 1.8, extent / factor));
        paint();
      },
      focus,
    };
  }

  global.WfgReplayMap = { create };
})(globalThis);
