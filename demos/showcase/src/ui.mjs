const icons = {
  mark: '<path d="M4 25 13 8l5 9 4-7 10 15H4Z"/><path d="m9 25 7-12 7 12M18 25l5-8 5 8"/>',
  play: '<path d="m9 5 11 7-11 7V5Z"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  restart: '<path d="M5 8a8 8 0 1 1-1 7M5 3v5h5"/>',
  view: '<path d="m12 3 10 6-10 6L2 9l10-6ZM2 14l10 6 10-6"/>',
  compare: '<path d="M12 3v18M8 6H4v12h4M16 6h4v12h-4"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8l10-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/>',
  reset: '<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/><circle cx="12" cy="12" r="3"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
  arrow: '<path d="M4 12h16m-5-5 5 5-5 5"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
  check: '<path d="m5 12 4 4 10-10"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5 5-3Z"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>'
};
const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="${name === 'mark' ? '0 0 36 32' : '0 0 24 24'}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || ''}</svg>`;

const copy = {
  ko: {
    demo: '일러스트 데모', local: '사용자 자료', recorded: '기록 트랙 · 일러스트 지형', fallback: '2D 보기', language: 'English', info: '이 체험에 관하여', eyebrow: 'WILDFIRE INTELLIGENCE',
    headings: [['불길을 읽고,', '돌아갈 길을 잇다.'], ['갈림길마다,', '다음을 생각하다.'], ['현장의 움직임을,', '하나의 흐름으로.']],
    descriptions: ['변하는 불길부터 이동의 순간까지.\n산불을 이해하는 새로운 시선을 만나보세요.', '지형과 불길, 그리고 이동을 함께 살펴봅니다.\n경로가 만들어지는 맥락을 따라가 보세요.', '기기와 이동 기록, 지형을 한 장면에.\n현장과 연결되는 인터페이스를 상상합니다.'],
    chapters: ['불길을 이해하다', '돌아갈 길을 찾다', '현장과 연결하다'],
    recordedHeadings: [['남겨진 움직임,', '하나의 기록으로.'], ['이동의 흔적을,', '천천히 따라가다.'], ['기록과 지형을,', '하나의 장면으로.']],
    recordedDescriptions: ['불러온 이동 기록을 장면 위에서 탐색합니다.\n지형과 재생 시간은 일러스트입니다.', '기록의 좌표를 따라 이동의 흐름을 살펴봅니다.\n새로운 경로나 대피 안내를 계산하지 않습니다.', '이동 기록과 CAD 하우징 연구를 함께 봅니다.\n실시간으로 연결된 기기를 보여주지는 않습니다.'],
    recordedChapters: ['기록을 살펴보다', '이동을 따라가다', '장면을 탐색하다'], recordedRouteLegend: '이동 기록', recordedDestinationLegend: '기록 종점', recordedFollow: '기록 따라가기',
    recordedHint: '기록 트랙 · 고도와 시간은 일러스트 · 드래그하여 회전', recordedMobileHint: '기록 트랙 · 고도와 시간은 일러스트',
    compareUnavailable: '경로 비교: 기록 트랙에는 비교 경로가 없습니다', fallbackHint: '2D 개요 · 타임라인으로 이동 살펴보기', fallbackViewReason: '시점: 2D 모드에서는 개요만 표시합니다',
    chapterLabels: ['UNDERSTAND THE FIRE', 'FIND A WAY THROUGH', 'CONNECT THE FIELD'],
    start: '108초로 둘러보기', resume: '체험 이어보기', playing: '잠시 멈추기', replay: '처음부터 보기',
    play: '체험 재생', pause: '체험 일시 정지', restart: '처음부터 다시 재생', time: '체험 시간', timeline: '체험 타임라인',
    view: '시점', compare: '경로 비교', layers: '레이어', reset: '시점 초기화', cinematic: '시네마틱', follow: '경로 따라가기', overview: '전체 지형',
    viewCaption: '장면을 보는 방식', layerCaption: '장면 표시', forest: '숲', fire: '불길과 연기', lowEffects: '효과 줄이기',
    hint: '드래그하여 회전 · 스크롤하여 확대', mobileHint: '한 손가락 회전 · 두 손가락 확대',
    fireLegend: '불길', routeLegend: '선택 경로', destinationLegend: '도착 지점', compareLegend: '비교 경로',
    demonstration: 'SCRIPTED SCENARIO', duration: '01:48 JOURNEY', chapter: '장',
    drawerTitle: '이 장면을 이해하는 법', drawerEyebrow: 'ABOUT THIS EXPERIENCE', close: '닫기',
    drawerIntro: 'WildfireGuardian의 생각을 공간으로 풀어낸 인터랙티브 전시입니다. 지형과 불길, 이동 경로를 하나의 장면에서 탐색할 수 있습니다.',
    evidenceTitle: '지금 보고 있는 것은',
    evidenceText: '기본 장면의 지형과 숲은 절차적으로 생성되며, 불길과 이동은 정해진 시나리오로 재생됩니다. 108초는 전시의 재생 시간입니다.',
    recordedEvidence: '불러온 기록의 이동 경로를 재생합니다. 불길은 표시하지 않으며 좌표는 장면에 맞춰 정규화됩니다. 지형의 고도와 재생 시간은 일러스트이며, 원본 기록의 진위와 정확성은 검증되지 않았습니다.',
    artifactEvidence: '사용자가 제공한 자료의 지점과 경로를 표시합니다. 지형과 불길은 일러스트이며 실제 지형 측량이나 화재 예측이 아닙니다. 자료의 출처와 정확성은 검증되지 않았습니다. 108초는 전시의 재생 시간입니다.',
    sourceLabel: '불러온 자료의 출처', sourceMissing: '이 자료에는 출처 설명이 없습니다.',
    boundaryTitle: '데모의 범위',
    boundaryText: '실시간 산불 관측, 실제 화재 예측, 검증된 대피 안내가 아닙니다. 경로 비교는 두 경로의 형태를 보여주며, 어느 쪽이 더 안전하거나 우수하다는 의미가 아닙니다. 기기는 소유자 CAD를 바탕으로 한 하우징 연구입니다. 실제 제작 적합성은 검증되지 않았으며 내부 구조를 표현하지 않습니다.',
    exploreTitle: '직접 탐색하기',
    exploreText: '재생을 멈추고 타임라인을 움직여 장면을 살펴보세요. 지형을 드래그하면 자동 카메라가 멈춥니다. 레이어와 시점을 바꾸어 각 요소의 관계를 확인할 수 있습니다.',
    importTitle: '내 자료로 살펴보기',
    importText: '정해진 형식의 JSON 자료를 이 브라우저에서 불러올 수 있습니다. 자료는 서버로 전송되지 않습니다. 불러온 자료의 출처나 정확성을 자동으로 검증하지는 않습니다.',
    importButton: 'JSON 자료 불러오기', fileHint: '지원 형식과 예제: 함께 제공된 ARTIFACT_SCHEMA.md',
    technicalTitle: 'DISPLAY & ACCESSIBILITY', technicalText: '동작 줄이기 설정을 존중합니다. 성능이 느리면 ‘효과 줄이기’를 켜세요. 모든 탐색 도구는 키보드로 사용할 수 있습니다.',
    statusReady: '탐색할 준비가 되었습니다', sceneLabel: 'WildfireGuardian 공간형 산불 일러스트 데모', compareNote: '경로의 형태를 비교하는 일러스트입니다.', footerLabel: '탐색 컨트롤',
    loading: '장면을 준비하고 있습니다', reduced: '동작 줄이기 설정이 적용되었습니다', localNote: '사용자가 불러온 자료 · 출처 검증 안 됨'
  },
  en: {
    demo: 'Illustrative demo', local: 'User artifact', recorded: 'Recorded track · illustrated terrain', fallback: '2D view', language: '한국어', info: 'About this experience', eyebrow: 'WILDFIRE INTELLIGENCE',
    headings: [['Read the fire.', 'Find a way through.'], ['At every turn,', 'consider what’s next.'], ['From the field,', 'into the picture.']],
    descriptions: ['From a changing fire to a moving journey.\nA new perspective on wildfire intelligence.', 'Explore terrain, fire, and movement together.\nFollow the context behind a route.', 'Devices, movement, and terrain in one scene.\nImagine a closer connection to the field.'],
    chapters: ['Understand the fire', 'Find a way through', 'Connect the field'],
    recordedHeadings: [['A journey made.', 'A record to explore.'], ['Follow the traces.', 'One moment at a time.'], ['A recorded path.', 'A spatial perspective.']],
    recordedDescriptions: ['Explore an imported movement record.\nTerrain and playback timing are illustrative.', 'Follow the coordinates of an existing track.\nNo new route or evacuation guidance is computed.', 'View a recorded track with the CAD housing study.\nThis does not show a live connection to a device.'],
    recordedChapters: ['Explore the record', 'Follow the track', 'Explore the scene'], recordedRouteLegend: 'Recorded track', recordedDestinationLegend: 'Track endpoint', recordedFollow: 'Follow the track',
    recordedHint: 'Recorded track · Illustrative elevation & timing · Drag to orbit', recordedMobileHint: 'Recorded track · Illustrative elevation & timing',
    compareUnavailable: 'Compare routes: no comparator exists for this recorded track', fallbackHint: '2D overview · Scrub to explore', fallbackViewReason: 'View: 2D mode supports overview only', chapterLabels: ['UNDERSTAND THE FIRE', 'FIND A WAY THROUGH', 'CONNECT THE FIELD'],
    start: 'Explore in 108 seconds', resume: 'Continue the journey', playing: 'Pause the journey', replay: 'Start again',
    play: 'Play experience', pause: 'Pause experience', restart: 'Restart experience', time: 'Experience time', timeline: 'Experience timeline',
    view: 'View', compare: 'Compare routes', layers: 'Layers', reset: 'Reset view', cinematic: 'Cinematic', follow: 'Follow the route', overview: 'Terrain overview',
    viewCaption: 'A different perspective', layerCaption: 'Scene visibility', forest: 'Forest', fire: 'Fire & smoke', lowEffects: 'Reduce effects',
    hint: 'Drag to orbit · Scroll to zoom', mobileHint: 'One finger to orbit · Pinch to zoom',
    fireLegend: 'Fire', routeLegend: 'Selected route', destinationLegend: 'Destination', compareLegend: 'Comparator',
    demonstration: 'SCRIPTED SCENARIO', duration: '01:48 JOURNEY', chapter: 'Chapter',
    drawerTitle: 'A closer look', drawerEyebrow: 'ABOUT THIS EXPERIENCE', close: 'Close',
    drawerIntro: 'An interactive exhibition of the ideas behind WildfireGuardian. Explore terrain, fire, and movement together in one spatial scene.',
    evidenceTitle: 'What you are seeing', evidenceText: 'The default terrain and forest are generated procedurally. Fire and movement follow a scripted scenario. The 108 seconds represent exhibition playback time.',
    recordedEvidence: 'This view plays back an imported track. Fire is hidden and coordinates are normalized to fit the scene. Terrain elevation and playback timing are illustrative. The authenticity and accuracy of the original record have not been verified.',
    artifactEvidence: 'This view displays the points and routes supplied in an imported artifact. Terrain and fire are illustrative, not surveyed terrain or a fire forecast. The source and accuracy of the artifact have not been verified. The 108 seconds represent exhibition playback time.',
    sourceLabel: 'Imported artifact source', sourceMissing: 'No source description was supplied with this artifact.',
    boundaryTitle: 'The scope of this demo', boundaryText: 'This is not live wildfire observation, an actual fire forecast, or validated evacuation guidance. Route comparison shows two path shapes; it does not establish that either is safer or better. The device is a housing study based on owner CAD. Physical fit is unverified and internal components are not represented.',
    exploreTitle: 'Make it your own', exploreText: 'Pause and scrub the timeline to examine a moment. Dragging the terrain pauses the guided camera. Change views and layers to explore how the elements relate.',
    importTitle: 'Explore your own artifact', importText: 'Load a JSON artifact that follows the included schema. The file is read in this browser and is not uploaded. Its provenance and accuracy are not automatically verified.',
    importButton: 'Load JSON artifact', fileHint: 'Format and example: included ARTIFACT_SCHEMA.md',
    technicalTitle: 'DISPLAY & ACCESSIBILITY', technicalText: 'Your reduced motion preference is respected. Turn on “Reduce effects” if performance is slow. All exploration controls are keyboard accessible.',
    statusReady: 'Ready to explore', sceneLabel: 'WildfireGuardian spatial wildfire illustration', compareNote: 'An illustrative comparison of route shapes.', footerLabel: 'Exploration controls',
    loading: 'Preparing the scene', reduced: 'Reduced motion preference applied', localNote: 'User-provided artifact · provenance unverified'
  }
};
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const formatTime = value => { const n = Math.max(0, Math.floor(Number(value) || 0)); return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`; };

export function mountUI(root, initialState, onAction) {
  let state = initialState;
  let language = '';
  let previousChapter = -1;
  let lastStatus = '';
  let returnFocus = null;
  let openPanel = null;
  let drawerOpen = false;
  let previousBodyOverflow = '';
  const events = new AbortController();
  root.innerHTML = `
    <main class="showcase" aria-label="WildfireGuardian">
      <div class="ambient-wash" aria-hidden="true"></div>
      <div id="scene-host" class="scene-host" role="region" tabindex="0"></div>
      <div class="scene-loading" role="status"><span class="loading-orbit"></span><span data-copy="loading"></span></div>
      <header class="masthead">
        <a class="wordmark" href="#" aria-label="WildfireGuardian" data-action="brand">${icon('mark')}<span>Wildfire<span class="wordmark-light">Guardian</span><span class="brand-dot"></span></span></a>
        <div class="exhibition-label">KOREA CODE FAIR <span>2026</span></div>
        <div class="masthead-actions"><span class="demo-badge"><i></i><span data-copy="demo"></span></span><button class="language-button" type="button" data-action="language"></button><button class="icon-button info-button" type="button" data-action="info">${icon('info')}</button></div>
      </header>
      <section class="story" aria-labelledby="hero-title">
        <div class="eyebrow"><span class="eyebrow-line"></span><span data-copy="eyebrow"></span></div>
        <div class="narrative"><h1 id="hero-title"></h1><p class="hero-description"></p></div>
        <button class="journey-cta" type="button" data-action="play"><span class="cta-circle">${icon('play')}</span><span class="cta-text"></span>${icon('arrow', 'cta-arrow')}</button>
        <nav class="chapter-navigation" aria-label="Chapters">${[0,1,2].map(i => `<button type="button" class="chapter-button" data-action="chapter" data-index="${i}"><span class="chapter-number">0${i+1}</span><span class="chapter-title"></span><span class="chapter-active-line"></span>${icon('chevron')}</button>`).join('')}</nav>
      </section>
      <div class="scene-coordinate" aria-hidden="true"><span class="crosshair">+</span><span>WFG / SPATIAL EXPLORER</span><span class="coordinate-rule"></span><span>01 — 03</span></div>
      <div class="scene-tools" role="toolbar">
        <button type="button" class="tool-button" data-action="view-menu" aria-expanded="false" aria-controls="view-panel">${icon('view')}<span class="tool-tip" data-copy="view"></span></button>
        <button type="button" class="tool-button" data-action="compare" aria-pressed="false">${icon('compare')}<span class="tool-tip" data-copy="compare"></span></button>
        <button type="button" class="tool-button" data-action="layers-menu" aria-expanded="false" aria-controls="layers-panel">${icon('layers')}<span class="tool-tip" data-copy="layers"></span></button>
        <span class="tool-divider"></span><button type="button" class="tool-button" data-action="reset">${icon('reset')}<span class="tool-tip" data-copy="reset"></span></button>
        <div class="tool-panel" id="view-panel" hidden><p data-copy="viewCaption"></p>${['cinematic','follow','overview'].map(view => `<button class="view-option" type="button" data-action="view" data-value="${view}" aria-pressed="false"><span data-copy="${view}"></span>${icon('check')}</button>`).join('')}</div>
        <div class="tool-panel" id="layers-panel" hidden><p data-copy="layerCaption"></p>${['forest','fire'].map(key => `<button class="toggle-option" role="switch" aria-checked="true" type="button" data-action="layer" data-key="${key}"><span data-copy="${key}"></span><i class="switch-track"><i></i></i></button>`).join('')}<div class="panel-rule"></div><button class="toggle-option" role="switch" aria-checked="false" type="button" data-action="lowEffects"><span data-copy="lowEffects"></span><i class="switch-track"><i></i></i></button></div>
      </div>
      <div class="scene-bottom"><div class="scene-legend"><span class="fire-legend"><i class="legend-fire"></i><span data-copy="fireLegend"></span></span><span><i class="legend-route"></i><span data-copy="routeLegend"></span></span><span><i class="legend-destination"></i><span data-copy="destinationLegend"></span></span><span class="compare-legend" hidden><i class="legend-compare"></i><span data-copy="compareLegend"></span></span></div><div class="scene-hint"><span class="fallback-indicator" hidden data-copy="fallback"></span><span class="desktop-hint" data-copy="hint"></span><span class="mobile-hint" data-copy="mobileHint"></span></div></div>
      <div class="compare-note" hidden data-copy="compareNote"></div>
      <footer class="transport">
        <div class="transport-intro"><span class="transport-kicker" data-copy="demonstration"></span><span class="current-chapter-name"></span></div>
        <div class="transport-controls"><button class="transport-play" type="button" data-action="play">${icon('play')}</button><button class="transport-restart icon-button" type="button" data-action="restart">${icon('restart')}</button><div class="time-display"><span class="current-time">00:00</span><span class="time-divider">/</span><span>01:48</span></div></div>
        <div class="timeline-wrap"><div class="timeline-track"><div class="timeline-fill"></div><span class="timeline-tick tick-one"></span><span class="timeline-tick tick-two"></span><span class="timeline-thumb"></span></div><input class="timeline-input" type="range" min="0" max="108" value="0" step="0.1" data-action="scrub"/><div class="timeline-labels" aria-hidden="true"><span>01 <b data-timeline-chapter="0"></b></span><span>02 <b data-timeline-chapter="1"></b></span><span>03 <b data-timeline-chapter="2"></b></span></div></div>
        <div class="transport-end">${icon('compass')}<span>WFG<span class="small-dot">/</span>2026</span></div>
      </footer>
      <div class="status-toast" role="status" aria-live="polite" hidden></div>
      <div class="drawer-backdrop" hidden></div>
      <aside class="info-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" hidden>
        <div class="drawer-header"><div class="eyebrow" data-copy="drawerEyebrow"></div><button class="icon-button" type="button" data-action="close-info">${icon('close')}</button></div>
        <h2 id="drawer-title" data-copy="drawerTitle"></h2><p class="drawer-intro" data-copy="drawerIntro"></p>
        <section><h3><span>01</span><span data-copy="evidenceTitle"></span></h3><p data-copy="evidenceText"></p><div class="current-source" hidden><span data-copy="sourceLabel"></span><strong class="current-source-title"></strong><p class="current-source-text"></p></div></section>
        <section><h3><span>02</span><span data-copy="boundaryTitle"></span></h3><p data-copy="boundaryText"></p></section>
        <section><h3><span>03</span><span data-copy="exploreTitle"></span></h3><p data-copy="exploreText"></p></section>
        <section class="import-section"><h3><span>04</span><span data-copy="importTitle"></span></h3><p data-copy="importText"></p><button class="import-button" type="button" data-action="import">${icon('upload')}<span data-copy="importButton"></span></button><p class="file-hint" data-copy="fileHint"></p><p class="import-status" role="status"></p><input type="file" accept=".json,application/json" id="artifact-file" hidden /></section>
        <div class="drawer-foot"><span data-copy="technicalTitle"></span><p data-copy="technicalText"></p><span class="drawer-signature">WildfireGuardian <span>·</span> 2026</span></div>
      </aside>
    </main>`;
  const $ = selector => root.querySelector(selector);
  const $$ = selector => [...root.querySelectorAll(selector)];
  const c = () => copy[state.lang === 'en' ? 'en' : 'ko'];
  const dispatch = action => onAction(action);
  const closePanels = () => {
    $$('.tool-panel').forEach(panel => { panel.hidden = true; });
    $$('[aria-controls="view-panel"], [aria-controls="layers-panel"]').forEach(button => button.setAttribute('aria-expanded', 'false'));
    openPanel = null;
  };
  const setDrawer = open => {
    if (open === drawerOpen) return;
    drawerOpen = open;
    const drawer = $('.info-drawer');
    drawer.hidden = !open;
    $('.drawer-backdrop').hidden = !open;
    $('.showcase').classList.toggle('drawer-open', open);
    if (open) {
      previousBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      returnFocus = document.activeElement;
      closePanels();
      [...$('.showcase').children].filter(el => el !== drawer && !el.classList.contains('drawer-backdrop')).forEach(el => { el.inert = true; });
      $('[data-action="close-info"]').focus();
    } else {
      document.body.style.overflow = previousBodyOverflow;
      [...$('.showcase').children].forEach(el => { el.inert = false; });
      returnFocus?.focus?.();
    }
  };
  root.addEventListener('click', event => {
    if (event.target.classList.contains('drawer-backdrop')) { setDrawer(false); return; }
    const button = event.target.closest('button[data-action], a[data-action]');
    if (!button) { if (!event.target.closest('.scene-tools')) closePanels(); return; }
    const action = button.dataset.action;
    if (action === 'brand') { event.preventDefault(); dispatch({type:'chapter', index:0}); return; }
    if (action === 'view-menu' || action === 'layers-menu') {
      const panelId = action === 'view-menu' ? 'view-panel' : 'layers-panel';
      const wasOpen = openPanel === panelId;
      closePanels();
      if (!wasOpen) { $(`#${panelId}`).hidden = false; button.setAttribute('aria-expanded','true'); openPanel = panelId; }
      return;
    }
    if (action === 'info') { setDrawer(true); dispatch({type:'info'}); return; }
    if (action === 'close-info') { setDrawer(false); return; }
    if (action === 'import') { $('#artifact-file').click(); return; }
    if (action === 'play') { dispatch({type: state.playing ? 'pause' : (state.time >= 108 ? 'restart' : 'play')}); return; }
    if (action === 'chapter') { dispatch({type:'chapter', index:Number(button.dataset.index)}); return; }
    if (action === 'language') { dispatch({type:'language', value:state.lang === 'en' ? 'ko' : 'en'}); return; }
    if (action === 'compare') { if ((state.mode || state.data?.mode) !== 'recorded') dispatch({type:'compare', value:!state.compare}); return; }
    if (action === 'layer') { dispatch({type:'layer', key:button.dataset.key, value:!state.layers?.[button.dataset.key]}); return; }
    if (action === 'lowEffects') { dispatch({type:'lowEffects', value:!state.lowEffects}); return; }
    if (action === 'view') { dispatch({type:'view', value:button.dataset.value}); closePanels(); return; }
    if (action === 'reset' || action === 'restart') dispatch({type:action});
  }, {signal:events.signal});
  $('.timeline-input').addEventListener('input', event => dispatch({type:'scrub', time:Number(event.target.value)}), {signal:events.signal});
  $('#artifact-file').addEventListener('change', event => {
    const file = event.target.files?.[0];
    if (file) dispatch({type:'import', file});
    event.target.value = '';
  }, {signal:events.signal});
  root.addEventListener('keydown', event => {
    if (event.key === 'Escape') { if (!$('.info-drawer').hidden) setDrawer(false); closePanels(); }
    if (event.key === 'Tab' && !$('.info-drawer').hidden) {
      const focusable = [...$('.info-drawer').querySelectorAll('button, a, input:not([hidden]), [tabindex="0"]')];
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    if ((event.key === ' ' || event.code === 'Space') && event.target.id === 'scene-host') { event.preventDefault(); dispatch({type:state.playing ? 'pause':'play'}); }
  }, {signal:events.signal});

  function update(next) {
    state = next;
    const mode = state.mode || state.data?.mode || 'fixture';
    const recorded = mode === 'recorded';
    const baseText = c();
    const sceneText = recorded ? {...baseText, headings:baseText.recordedHeadings, descriptions:baseText.recordedDescriptions, chapters:baseText.recordedChapters, routeLegend:baseText.recordedRouteLegend, destinationLegend:baseText.recordedDestinationLegend, follow:baseText.recordedFollow, hint:baseText.recordedHint, mobileHint:baseText.recordedMobileHint} : baseText;
    const text = state.fallback ? {...sceneText, hint:sceneText.fallbackHint, mobileHint:sceneText.fallbackHint} : sceneText;
    const copyContext = `${state.lang}:${mode}:${Boolean(state.fallback)}`;
    const chapter = Math.max(0, Math.min(2, Number(state.chapter) || 0));
    const time = Math.max(0, Math.min(108, Number(state.time) || 0));
    if (language !== copyContext) {
      language = copyContext;
      document.documentElement.lang = state.lang === 'en' ? 'en' : 'ko';
      document.title = state.lang === 'en' ? 'WildfireGuardian — A way through the fire' : 'WildfireGuardian — 불길을 읽고, 돌아갈 길을 잇다';
      $$('.showcase [data-copy]').forEach(el => { el.textContent = text[el.dataset.copy] || ''; });
      $('.language-button').textContent = text.language;
      $('.language-button').setAttribute('aria-label', state.lang === 'en' ? '한국어로 변경' : 'Switch to English');
      [['info','info'], ['close-info','close'], ['view-menu','view'], ['layers-menu','layers'], ['compare','compare'], ['reset','reset'], ['restart','restart']].forEach(([action,key]) => $$(`[data-action="${action}"]`).forEach(el => { el.setAttribute('aria-label',text[key]); el.title = text[key]; }));
      $('#scene-host').setAttribute('aria-label', text.sceneLabel);
      $('.timeline-input').setAttribute('aria-label', text.timeline);
      $('.transport').setAttribute('aria-label', text.footerLabel);
      $('.scene-tools').setAttribute('aria-label', text.footerLabel);
      $('.chapter-navigation').setAttribute('aria-label', state.lang === 'en' ? 'Experience chapters' : '체험 챕터');
      $$('.chapter-button').forEach((button,i) => { button.querySelector('.chapter-title').textContent = text.chapters[i]; });
      $$('[data-timeline-chapter]').forEach(el => { el.textContent = text.chapters[Number(el.dataset.timelineChapter)]; });
      previousChapter = -1;
    }
    if (previousChapter !== chapter) {
      $('#hero-title').innerHTML = text.headings[chapter].map((line,i) => `<span class="hero-line ${i === 1 ? 'hero-line-accent':''}">${escape(line)}</span>`).join('');
      $('.hero-description').innerHTML = text.descriptions[chapter].split('\n').map(escape).join('<br />');
      $('.story').dataset.chapter = chapter;
      $('.current-chapter-name').textContent = `0${chapter+1} ${text.chapters[chapter]}`;
      $$('.chapter-button').forEach((button,i) => { button.classList.toggle('is-current',i === chapter); button.setAttribute('aria-current', i === chapter ? 'step':'false'); });
      previousChapter = chapter;
    }
    const playingLabel = state.playing ? text.pause : text.play;
    const playIcon = state.playing ? 'pause' : 'play';
    if ($('.transport-play').dataset.icon !== playIcon) {
      $('.transport-play').innerHTML = icon(playIcon);
      $('.cta-circle').innerHTML = icon(playIcon);
      $('.transport-play').dataset.icon = playIcon;
    }
    $('.transport-play').setAttribute('aria-label', playingLabel);
    $('.transport-play').title = playingLabel;
    $('.journey-cta .cta-text').textContent = state.playing ? text.playing : (time >= 108 ? text.replay : time > 0 ? text.resume:text.start);
    $('.current-time').textContent = formatTime(time);
    $('.time-display').setAttribute('aria-label',`${text.time}: ${formatTime(time)} / 01:48`);
    $('.timeline-input').value = time;
    $('.timeline-input').setAttribute('aria-valuetext',`${formatTime(time)} — ${text.chapters[chapter]}`);
    $('.timeline-wrap').style.setProperty('--progress',`${time / 108 * 100}%`);
    const showCompare = !recorded && Boolean(state.compare);
    $('[data-action="compare"]').disabled = recorded;
    $('[data-action="compare"]').setAttribute('aria-pressed',String(showCompare));
    $('[data-action="compare"]').setAttribute('aria-label',recorded ? text.compareUnavailable : text.compare);
    $('[data-action="compare"]').title = recorded ? text.compareUnavailable : text.compare;
    $('.compare-legend').hidden = !showCompare;
    $('.compare-note').hidden = !showCompare;
    $('.fire-legend').hidden = recorded || !state.layers?.fire || Number(state.data?.fire?.radius) <= 0;
    $('[data-action="layer"][data-key="fire"]').disabled = recorded || Number(state.data?.fire?.radius) <= 0;
    $$('[data-action="view"]').forEach(el => el.setAttribute('aria-pressed',String(el.dataset.value === (state.fallback ? 'overview' : state.view))));
    $('[data-action="view-menu"]').disabled = Boolean(state.fallback);
    $('[data-action="view-menu"]').title = state.fallback ? text.fallbackViewReason : text.view;
    $('[data-action="view-menu"]').setAttribute('aria-label',state.fallback ? text.fallbackViewReason : text.view);
    if (state.fallback && openPanel === 'view-panel') closePanels();
    $$('[data-action="layer"]').forEach(el => el.setAttribute('aria-checked',String(!el.disabled && Boolean(state.layers?.[el.dataset.key]))));
    $('[data-action="lowEffects"]').setAttribute('aria-checked',String(Boolean(state.lowEffects)));
    const local = mode !== 'fixture';
    $('.demo-badge span').textContent = mode === 'recorded' ? text.recorded : local ? text.local : text.demo;
    $('.fallback-indicator').hidden = !state.fallback;
    if (state.ready) $('.scene-loading').hidden = true;
    $('.demo-badge').title = local ? text.localNote : text.evidenceText;
    $('[data-copy="evidenceText"]').textContent = mode === 'recorded' ? text.recordedEvidence : local ? text.artifactEvidence : text.evidenceText;
    $('.current-source').hidden = !local;
    const artifactTitle = state.data?.title;
    $('.current-source-title').textContent = typeof artifactTitle === 'string' ? artifactTitle.slice(0, 240) : String(artifactTitle?.[state.lang] || artifactTitle?.ko || artifactTitle?.en || '').slice(0, 240);
    const source = state.data?.provenance?.source;
    const sourceText = typeof source === 'string' ? source : source && typeof source === 'object' ? Object.entries(source).filter(([, value]) => typeof value === 'string').map(([key, value]) => `${key}: ${value}`).join(' · ') : '';
    $('.current-source-text').textContent = sourceText ? sourceText.slice(0, 1600) : text.sourceMissing;
    $('.transport-kicker').textContent = mode === 'recorded' ? 'RECORDED TRACK' : local ? 'LOCAL ARTIFACT' : text.demonstration;
    $('.import-status').textContent = state.importStatus || '';
    $('.import-status').classList.toggle('is-error',Boolean(state.error));
    $('.showcase').classList.toggle('is-playing',Boolean(state.playing));
    $('.showcase').classList.toggle('reduced-motion',Boolean(state.reducedMotion || state.lowEffects));
  }
  function setStatus(message) {
    const text = String(message || '');
    $('.scene-loading').hidden = true;
    if (text === lastStatus) return;
    lastStatus = text;
    $('.status-toast').textContent = text;
    $('.status-toast').hidden = !text;
  }
  update(initialState);
  return {update,setStatus,destroy() { if (drawerOpen) document.body.style.overflow = previousBodyOverflow; events.abort(); root.innerHTML = ''; }};
}
