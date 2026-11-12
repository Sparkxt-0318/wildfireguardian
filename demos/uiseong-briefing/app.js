(() => {
  'use strict';
  const data = globalThis.WFG_DATA;
  const { replay, watch, forecast } = data;
  const frames = replay.frames;
  const roads = new Map(replay.roads.map((road) => [road.id, road]));
  const times = frames.map((frame) => Date.parse(frame.sourceTime));
  const example = times.indexOf(Date.parse('2025-03-24T03:44Z'));
  const $ = (id) => document.getElementById(id);
  const text = (id, value) => {
    $(id).textContent = value;
  };
  const kst = (ms) => new Date(ms + 9 * 3600000).toISOString().slice(0, 16);
  const hour = (ms) => kst(ms).slice(11);
  const dateTime = (ms) => kst(ms).slice(5).replace('-', '.').replace('T', ' ');
  const roadName = (id) => {
    const road = roads.get(id);
    return road.osmName || road.ref || '도로명 미등록';
  };
  const state = { index: 0, time: times[0], reviewed: null, area: null };
  const drafts = new Map();
  let result;
  const map = WfgReplayMap.create($('map'), data, selectRoad);

  function evaluate() {
    const usablePin = state.reviewed && state.reviewed.time <= state.time;
    result = WfgBriefing.evaluate(data, {
      index: state.index,
      reviewMs: state.time,
      baselineIndex: usablePin ? state.reviewed.index : null,
    });
  }

  function stretchName(stretch, i) {
    const same = result.stretches.filter((s) => s.label === stretch.label);
    if (same.length === 2) {
      const other = same.find((s) => s !== stretch);
      const dx = (stretch.start[0] + stretch.end[0] - other.start[0] - other.end[0]) / 2;
      const dy = (stretch.start[1] + stretch.end[1] - other.start[1] - other.end[1]) / 2;
      const side = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? '동쪽' : '서쪽') : dy > 0 ? '북쪽' : '남쪽';
      return stretch.label + ' · 두 구간 중 ' + side;
    }
    return stretch.label + (same.length > 1 ? ' · 복귀 방향 ' + (i + 1) + '번째 구간' : '');
  }
  function chooseStretch(i, focus = false) {
    const stretch = result.stretches[i];
    state.area = { ids: stretch.ids, label: stretchName(stretch, i), index: i };
    if (focus) map.focus(stretch.ids);
  }
  function selectRoad(id) {
    if (!roads.has(id)) return;
    state.area = { ids: [id], label: roadName(id) + ' · ' + roads.get(id).mapId, index: null };
    map.focus([id]);
    render(false);
  }
  function mapOptions() {
    return {
      showWatch: $('show-watch').checked,
      showForecast: $('show-forecast').checked,
      showGone: $('show-gone').checked,
      selectedIds: state.area?.ids || [],
    };
  }

  function generateDraft() {
    const opening =
      '훈련. ' + dateTime(times[state.index]) + ' 위성 관측, ' + result.ageMinutes + '분 경과. ';
    const area = state.area;
    if (area) {
      const added = area.ids.filter((id) => result.newIds.includes(id)).length;
      const nearby = area.ids.some((id) => result.current.includes(id));
      const where = area.label.replace(' · ', ' ');
      if (!nearby) {
        const dropped = area.ids.some((id) => result.gone.includes(id));
        return (
          opening +
          where +
          (dropped
            ? '은 이번 열점 인접 표시에서 빠졌습니다. '
            : '에는 이번 관측의 열점 인접 표시가 없습니다. ') +
          '통행 여부 확인 바랍니다.'
        );
      }
      return (
        opening +
        where +
        (added ? '에 열점 인접 구간이 새로 표시됐습니다. ' : ' 인근에 열점이 관측됐습니다. ') +
        '해당 구간의 통행 상황 확인 바랍니다.'
      );
    }
    if (!$('show-watch').checked)
      return (
        opening +
        '지도 전체에서 열점 인접 도로 구간 ' +
        result.current.length +
        '개가 표시됐습니다. 확인할 위치를 지정 바랍니다.'
      );
    return (
      opening +
      '가상 복귀 동선 주변에 이번 관측에서 표시된 도로 구간은 없습니다. 현장 통행 여부는 미확인입니다.'
    );
  }
  function draftKey() {
    return [
      state.index,
      state.time,
      result.baselineIndex,
      $('show-watch').checked,
      state.area?.ids.join(',') || 'overview',
    ].join('|');
  }

  function makeButton(label, action, pressed) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    if (pressed !== undefined) b.setAttribute('aria-pressed', String(pressed));
    b.addEventListener('click', action);
    return b;
  }

  function drawLists() {
    $('stretch-list').replaceChildren();
    if ($('show-watch').checked)
      result.stretches.forEach((s, i) => {
        const label = stretchName(s, i) + '　' + s.ids.length + '개 구간';
        $('stretch-list').append(
          makeButton(
            label,
            () => {
              chooseStretch(i, true);
              render(false);
            },
            state.area?.index === i,
          ),
        );
      });
    const list = $('road-list');
    list.replaceChildren();
    const sortedIds = [...result.newIds].sort(
      (a, b) =>
        Number(!roads.get(a).osmName) - Number(!roads.get(b).osmName) ||
        roadName(a).localeCompare(roadName(b), 'ko') ||
        a.localeCompare(b),
    );
    for (const id of sortedIds) {
      list.append(
        makeButton(roadName(id) + ' · ' + roads.get(id).mapId, () => {
          selectRoad(id);
          $('map-title').scrollIntoView({ block: 'start' });
        }),
      );
    }
    if (!sortedIds.length) list.textContent = '새로 표시된 구간이 없습니다.';
  }

  function render(autoSelect = true) {
    evaluate();
    if (autoSelect) {
      if ($('show-watch').checked && result.stretches.length) chooseStretch(0);
      else state.area = null;
    }
    const src = times[state.index],
      pin = state.reviewed,
      b = result.baselineIndex;
    $('scrub').value = String(state.index);
    text('frame-number', state.index + 1 + ' / ' + frames.length);
    text('observation-time', dateTime(src));
    text('review-time', dateTime(state.time));
    text('sensor', result.frame.sourceLabel);
    text('map-date', dateTime(state.time) + ' 기준');
    text('age', result.ageMinutes + '분');
    $('review-at').value = kst(state.time);
    $('prev').disabled = state.index === 0;
    $('next').disabled = state.index === frames.length - 1;
    $('age-15').disabled = times[state.index + 1] <= src + 900000;
    text('new-count', result.newIds.length);
    text('kept-count', result.kept.length);
    text('gone-count', result.gone.length);
    text('watch-count', result.watchHits.length);
    text(
      'reviewed-label',
      result.comparisonSource === 'reviewed'
        ? '검토 완료한 브리핑과 비교 · ' + dateTime(times[b]) + ' 관측'
        : b === null
          ? '첫 관측 · 비교 시작점'
          : '직전 관측과 비교 · ' + dateTime(times[b]),
    );
    text(
      'change-context',
      '현재 열점 ' +
        result.frame.detections.length +
        '개 · 인접 도로 구간 ' +
        result.current.length +
        '개',
    );
    text(
      'watch-delta',
      !$('show-watch').checked
        ? '지도에 복귀 동선을 표시하면 연속 구간을 선택할 수 있습니다.'
        : result.stretches.length
          ? '연속된 ' +
            result.stretches.length +
            '곳 · 새로 표시된 도로 구간 ' +
            result.watchNew.length +
            '개'
          : '표시가 없어도 실제 통행 가능 여부는 확인되지 않았습니다.',
    );
    $('reset-baseline').disabled = !pin;
    $('review-log').hidden = !pin;
    if (pin)
      text(
        'review-log',
        pin.time > state.time
          ? '더 나중에 검토한 브리핑은 현재 비교에서 제외했습니다.'
          : '검토 기록 · ' + dateTime(pin.time) + ' | ' + pin.note,
      );
    const fc = result.forecast;
    text(
      'forecast-status',
      fc
        ? dateTime(Date.parse(fc.origin)) +
            ' ~ ' +
            hour(Date.parse(fc.validEnd)) +
            ' 유효 · 연구 예측' +
            ($('show-forecast').checked ? '' : ' (지도에서 숨김)')
        : '이 시각에 유효한 예측 없음',
    );
    $('forecast-key').hidden = !fc || !$('show-forecast').checked;
    $('radio-locate').disabled = !state.area;
    text(
      'radio-context',
      state.area
        ? '지도 A–B · ' + state.area.label + ' · 도로 구간 ' + state.area.ids.length + '개'
        : '선택한 도로 구간 없음',
    );
    $('radio-text').value = drafts.get(draftKey()) ?? generateDraft();
    map.render(result, mapOptions());
    drawLists();
    updatePaper();
  }

  let timer = null;
  function stopPlayback() {
    clearInterval(timer);
    timer = null;
    text('play', '자동 재생');
    $('play').setAttribute('aria-pressed', 'false');
  }
  function move(index, time = times[index]) {
    state.index = index;
    state.time = time;
    text('time-error', '');
    map.reset();
    render();
  }
  function seek(ms) {
    // Bound the exercise to its case dates, including the remainder of the last day.
    const i = times.findLastIndex((t) => t <= ms);
    if (!Number.isFinite(ms) || i < 0 || ms >= endExclusive) {
      text('time-error', '수록 기간 안의 한국시간을 입력해 주세요.');
      return;
    }
    if (i === state.index) {
      state.time = ms;
      text('time-error', '');
      render(false);
    } else move(i, ms);
  }
  function updatePaper() {
    const pin = state.reviewed;
    const reviewed =
      pin && pin.time <= state.time
        ? '\n비교 기준으로 검토한 문안 (' + dateTime(pin.time) + ') | ' + pin.note
        : '';
    text(
      'paper',
      '지휘부 훈련용 · ' +
        dateTime(state.time) +
        ' KST\n' +
        $('radio-context').textContent +
        '\n무전 검토 문안 | ' +
        $('radio-text').value +
        reviewed +
        '\n위성 관측은 불규칙합니다. 훈련용 동선의 실제 통행 여부와 현장 수신 시각은 확인되지 않았습니다.',
    );
  }

  const endExclusive = Date.parse(kst(times.at(-1)).slice(0, 10) + 'T00:00:00+09:00') + 86400000;
  $('scrub').max = String(frames.length - 1);
  $('review-at').min = kst(times[0]);
  $('review-at').max = kst(endExclusive - 60000);
  // Pause as soon as the operator takes control of the map, clock, or draft.
  for (const event of ['pointerdown', 'keydown', 'focusin']) {
    document.addEventListener(
      event,
      (e) => {
        if (e.target !== $('play') && timer !== null) stopPlayback();
      },
      true,
    );
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopPlayback();
  });
  $('play').onclick = () => {
    if (timer !== null) {
      stopPlayback();
      return;
    }
    if (state.index === frames.length - 1) move(0);
    text('play', '일시정지');
    $('play').setAttribute('aria-pressed', 'true');
    timer = setInterval(() => {
      move(state.index + 1);
      if (state.index === frames.length - 1) stopPlayback();
    }, 3300);
  };
  $('prev').onclick = () => move(state.index - 1);
  $('next').onclick = () => move(state.index + 1);
  $('scrub').oninput = (e) => move(Number(e.target.value));
  $('age-15').onclick = () => seek(times[state.index] + 900000);
  $('apply-time').onclick = () => seek(Date.parse($('review-at').value + ':00+09:00'));
  $('forecast-jump').onclick = () => {
    $('show-forecast').checked = true;
    const nextFc = forecast.frames.find((f) => Date.parse(f.origin) > state.time) || forecast.frames[0];
    seek(Date.parse(nextFc.origin));
  };
  $('start-example').onclick = () => {
    state.reviewed = null;
    $('show-watch').checked = true;
    move(example);
  };
  $('mark-reviewed').onclick = () => {
    state.reviewed = { index: state.index, time: state.time, note: $('radio-text').value };
    render(false);
  };
  $('reset-baseline').onclick = () => {
    state.reviewed = null;
    render(false);
  };
  $('show-watch').onchange = () => render();
  for (const id of ['show-forecast', 'show-gone']) $(id).onchange = () => render(false);
  $('radio-text').oninput = () => {
    drafts.set(draftKey(), $('radio-text').value);
    updatePaper();
  };
  $('radio-reset').onclick = () => {
    drafts.delete(draftKey());
    render(false);
  };
  $('radio-locate').onclick = () => {
    if (!state.area) return;
    map.focus(state.area.ids);
    map.render(result, mapOptions());
    $('map-title').scrollIntoView({ block: 'start' });
  };
  $('zoom-in').onclick = () => map.zoom(1.5);
  $('zoom-out').onclick = () => map.zoom(1 / 1.5);
  $('zoom-reset').onclick = () => map.reset();
  $('print').onclick = () => {
    updatePaper();
    window.print();
  };
  window.addEventListener('beforeprint', () => {
    stopPlayback();
    updatePaper();
  });
  for (const [i, label] of forecast.legend.entries()) {
    const chip = document.createElement('span'),
      square = document.createElement('i');
    square.className = 'keybox';
    square.style.background = forecast.colors[i];
    chip.append(square, label);
    $('forecast-key').append(chip);
  }
  move(example);
})();
