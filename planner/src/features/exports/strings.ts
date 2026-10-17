/** Export dialog copy (Korean first, English variant for every string). */
export const EXP = {
  title: { ko: '내보내기', en: 'Export' },
  close: { ko: '닫기', en: 'Close' },
  routeTitle: { ko: '선택한 경로', en: 'Selected route' },
  routeDesc: {
    ko: 'GIS·내비게이션 도구에서 열 수 있는 경로 파일입니다. 꼭짓점마다 통과 시각(times_s)이 들어 있습니다.',
    en: 'Route file for GIS and navigation tools, with a passing time (times_s) for every vertex.',
  },
  routeNone: { ko: '선택한 출발지가 없습니다.', en: 'No origin selected.' },
  routeRefused: {
    ko: '확인된 경로가 없어 내보낼 수 없습니다. 모델상 경로 없음·미확인 결과는 경로로 내보내지 않습니다.',
    en: 'There is no checked route to export. No-route and unresolved results are never exported as routes.',
  },
  routeFrom: { ko: '출발', en: 'Depart' },
  routeArrive: { ko: '도착', en: 'Arrive' },
  includeComparison: { ko: '비교용 이동시간 최단 경로 함께 넣기 (화재 미고려 · 대피 경로 아님)', en: 'Include the travel-time-only comparison (fire ignored · not an evacuation route)' },
  geojson: { ko: 'GeoJSON', en: 'GeoJSON' },
  kml: { ko: 'KML', en: 'KML' },
  csvTitle: { ko: '출발지별 대피 목록', en: 'Dispatch list by origin' },
  csvDesc: {
    ko: '출발지마다 한 줄: 우선순위, 판정, 출발 마감(KST), 연속 확인 기준, 대피소, 도착 시각, 비고. Excel에서 바로 열립니다 (UTF-8 BOM).',
    en: 'One row per origin: priority, verdict, deadline (KST), contiguous basis, shelter, arrival, notes. Opens directly in Excel (UTF-8 BOM).',
  },
  csvCount: { ko: '출발지 {n}곳', en: '{n} origins' },
  csv: { ko: 'CSV', en: 'CSV' },
  note: {
    ko: '내보낸 파일에는 산불 입력 표시와 출처 정보(예측 체크포인트·패키지·키트·API 모드·버전)가 함께 기록됩니다.',
    en: 'Every exported file carries the fire-input label and provenance (forecast checkpoint, package, kit, API mode and version).',
  },
  apiNote: {
    ko: '파일은 화면에 불러온 결과로 브라우저에서 바로 만듭니다 (사전 계산·오프라인 자료에서도 사용 가능).',
    en: 'Files are built in the browser from the results on screen (also works with precomputed or offline data).',
  },
  zonesTitle: { ko: '사용자 입력 확산 구역 (가정)', en: 'User-drawn spread zones (assumption)' },
  zonesDesc: {
    ko: '그린 5시간·8시간 구역을 GeoJSON 다각형으로 저장합니다 (properties.arrival_h_max, 발표 시각, 여유). 선택한 경로 GeoJSON에도 같은 구역이 별도 레이어로 들어갑니다.',
    en: 'Saves the drawn 5 h / 8 h zones as GeoJSON polygons (properties.arrival_h_max, issue time, margin). The selected-route GeoJSON carries the same zones as an extra layer.',
  },
  zonesCount: { ko: '구역 {n}개', en: '{n} zones' },
  zonesGeojson: { ko: '구역 GeoJSON', en: 'Zones GeoJSON' },
  saved: { ko: '저장됨: {name}', en: 'Saved: {name}' },
  error: { ko: '내보내지 못했습니다: {msg}', en: 'Export failed: {msg}' },
} as const;
