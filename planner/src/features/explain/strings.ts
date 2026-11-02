/**
 * "왜 이 시각인가요? / Why this time?" — Korean first, English mirror. Every sentence is a template filled only from
 * the structured fields of wfg.explanation/1 (no free text from the file is shown). Honesty wording: no route is called
 * safe; scenario members are "fire scenarios from the forecast", never simulations of the actual fire; unresolved is
 * never turned into a reason.
 */
import type { L10n } from '../shared/strings';

export const EXPLAIN = {
  titleTime: { ko: '왜 이 시각인가요?', en: 'Why this time?' },
  titleNoRoute: { ko: '왜 확인된 경로가 없나요?', en: 'Why is there no checked route?' },
  basis: {
    ko: '예측에서 나온 화재 시나리오 {total}개를 기준으로 한 결과이며, 관측이 아닙니다.',
    en: 'Based on {total} fire scenarios from the forecast; not an observation.',
  },
  status: {
    explained: { ko: '검증된 설명', en: 'Verified explanation' },
    explained_partial: { ko: '부분 설명', en: 'Partial explanation' },
    not_explainable: { ko: '설명 없음', en: 'No explanation' },
  } as Record<'explained' | 'explained_partial' | 'not_explainable', L10n>,
  members: { ko: '화재 시나리오 {total}개 중 {k}개', en: '{k} of {total} fire scenarios' },
  membersAtLeast: { ko: '화재 시나리오 {total}개 중 {k}개 이상', en: 'at least {k} of {total} fire scenarios' },

  // ---- where (a road location) ----
  wherePlace: { ko: '{name} 부근 도로({dist} 거리)', en: 'the road near {name} ({dist} away)' },
  whereNamed: { ko: '{name}', en: '{name}' },
  whereUnnamed: { ko: '이름 없는 도로(도로 노드 {node})', en: 'an unnamed road (road node {node})' },
  wayRef: { ko: 'OSM 도로 {way}', en: 'OSM way {way}' },

  // ---- reasons ----
  noLater: {
    ko: '점검한 마지막 출발 시각이 {deadline}입니다. 기록된 화재 시나리오는 입력 시각부터 {hours}시간({end}까지)만 다루므로 그 뒤의 출발은 점검하지 않았습니다. 이 시각은 예측 화염으로 정해진 것이 아닙니다.',
    en: '{deadline} is the last departure time that was checked. The recorded fire scenarios cover only {hours} h after the input time (until {end}), so later departures were not checked. This time is not set by predicted flames.',
  },
  windowFireFree: {
    ko: '{next}에 출발하면 화재가 없더라도 가장 빠른 도로로 대피소에 도착해 {dwell}분 머무는 일이 {fastestEnd}에야 끝나, 기록된 화재 시나리오가 끝나는 {end}를 넘습니다. 이 마감은 예측 화염이 아니라 1시간 시나리오 범위에서 정해졌습니다.',
    en: 'Leaving at {next}, even the fastest road route, ignoring the fire, would finish the {dwell}-minute stay at the shelter only at {fastestEnd}, after the recorded fire scenarios end at {end}. This leave-by time comes from the one-hour scenario range, not from predicted flames.',
  },
  windowFireFreeUnreachable: {
    ko: '{next}에 출발하면 화재가 없더라도 어떤 도로로도 기록된 화재 시나리오가 끝나는 {end} 전에 대피소에 도착해 {dwell}분 머물 수 없습니다. 이 마감은 예측 화염이 아니라 1시간 시나리오 범위에서 정해졌습니다.',
    en: 'Leaving at {next}, no road route, even ignoring the fire, reaches the shelter and completes the {dwell}-minute stay before the recorded fire scenarios end at {end}. This leave-by time comes from the one-hour scenario range, not from predicted flames.',
  },
  windowArrivalFireFree: {
    ko: '{next}에 출발하면 화재가 없더라도 가장 빠른 도로로 도착해 {dwell}분 머무는 일이 {fastestEnd}에야 끝나, 이 기록 임무의 도착 허용 시간({close}까지)을 넘습니다.',
    en: "Leaving at {next}, even the fastest road route, ignoring the fire, would finish the {dwell}-minute stay only at {fastestEnd}, after this recorded mission's arrival window closes at {close}.",
  },
  windowDetour: {
    ko: '{next}에 출발하면 시나리오상 화염을 피하는 도로 경로로는 대피소에 도착해 {dwell}분 머무는 일을 {close}까지 마칠 수 없습니다({fa}). 화염이 없다면 가장 빠른 도로로 {fastestEnd}에 마칠 수 있으므로, 이 마감은 화염을 피하는 우회 때문입니다.',
    en: 'Leaving at {next}, no road route that avoids the flames in the fire scenarios reaches the shelter and completes the {dwell}-minute stay by {close} ({fa}). Without fire the fastest road would finish at {fastestEnd}, so this leave-by time comes from the detour around the flames.',
  },
  faArrival: { ko: '화염을 피하는 가장 이른 도착: {time}', en: 'earliest flame-avoiding arrival: {time}' },
  faNone: { ko: '그 시각까지 화염을 피해 도착하는 경로 없음', en: 'no flame-avoiding arrival before then' },
  windowSkip: {
    ko: '{next}에 출발하면 이 기록 임무의 도착 허용 시간({open}–{close}) 안에 {dwell}분 체류를 마칠 수 없어 그 시각은 점검하지 않았습니다(시간창 밖).',
    en: "Leaving at {next}, the {dwell}-minute stay cannot fit this recorded mission's arrival window ({open}–{close}), so that time was not checked (outside the window).",
  },
  windowNoRoute: {
    ko: '점검한 어느 출발 시각에도 시나리오상 화염을 피하는 도로 경로로 후보 대피소에 도착해 {dwell}분 머무는 일을 {close}까지 마칠 수 없습니다.',
    en: 'From every checked departure time, no road route that avoids the flames in the fire scenarios reaches a candidate shelter and completes the {dwell}-minute stay by {close}.',
  },
  othersUnreachable: {
    ko: '{deadline}에 확인된 다른 대피소 {k}곳도 {next}에 출발하면 화염을 피하는 도로로 제때(체류 포함) 도착할 수 없습니다.',
    en: 'The other {k} shelter(s) checked at {deadline} cannot be reached in time (stay included) from {next} either by a road route that avoids the flames.',
  },
  flame: {
    ko: '{next}에 출발하면 출발 마감 경로는 {where}에서 {contact}에 시나리오상 화염과 만납니다({members}).',
    en: 'Leaving at {next}, the route shown for the leave-by time meets flames in the fire scenarios on {where} at {contact} ({members}).',
  },
  flameSlack: {
    ko: '출발 마감 {deadline}에 출발하면 차량은 {pass}에 그 375 m 격자 칸을 벗어나며, 그곳에 화염이 닿는 예측 시각({flame})보다 {slack} 앞섭니다.',
    en: 'Leaving at the leave-by time {deadline}, the vehicle leaves that 375 m grid cell at {pass}, {slack} before the flame is predicted to reach it ({flame}).',
  },
  dwell: {
    ko: '{next}에 출발하면 대피소에 도착한 뒤 {dwell}분 머무는 동안 {contact}에 대피소 주변(375 m 격자 칸)이 시나리오상 화염과 만납니다({members}).',
    en: "Leaving at {next}, the shelter's surroundings (375 m grid cell) meet flames in the fire scenarios at {contact}, during the {dwell}-minute stay ({members}).",
  },
  exits: {
    ko: '진입 지점에서 화염과 만나지 않고 갈 수 있는 구역을 벗어나는 도로 {n}개가 모두 시나리오상 화염과 만납니다({members}).',
    en: 'All {n} roads leading out of the area that can be reached from the entry point without meeting flames run into flames in the fire scenarios ({members}).',
  },
  exitsPresent: {
    ko: '이 도로들은 입력 시각({input})에 이미 타고 있는 것으로 표시된 칸을 지납니다.',
    en: 'They cross cells already marked as burning at the input time ({input}).',
  },
  exitsLatest: {
    ko: '차량이 가장 일찍 닿을 수 있는 시각에 이미 막혀 있으며, 마지막 도로도 {latest}에는 화염과 만납니다.',
    en: 'Each is already blocked when the vehicle could first reach it; the last one meets flames by {latest}.',
  },
  exitItem: { ko: '{where}: 시나리오 {k}/{total}', en: '{where}: {k}/{total} scenarios' },
  exitsMore: { ko: '외 {n}개', en: 'and {n} more' },
  entryInFlame: {
    ko: '진입 지점이 출발 시각에 이미 시나리오상 화염 안에 있습니다.',
    en: 'The entry point itself is in flames at departure in the fire scenarios.',
  },
  unresolvedNext: {
    ko: '다음 출발 시각({next})의 점검 결과는 미확인입니다. 출발 마감은 확인된 마지막 시각일 뿐이며, 더 늦은 출발이 가능한지는 알 수 없습니다. 미확인을 안전으로 해석하지 마십시오.',
    en: 'The next departure time ({next}) could not be verified (unresolved). The leave-by time is only the last checked time; whether a later departure would work is unknown. Unresolved never means safe.',
  },
  originUnresolved: {
    ko: '이 출발지는 미확인이어서 설명할 출발 마감이 없습니다.',
    en: 'This origin is unresolved, so there is no leave-by time to explain.',
  },
  other: { ko: '이 결과에 대해 검증된 설명이 없습니다.', en: 'No verified explanation is available for this result.' },

  // ---- fallbacks ----
  loading: { ko: '설명을 불러오는 중…', en: 'Loading the explanation…' },
  absent: { ko: '이 시나리오에 대한 설명 파일이 없습니다.', en: 'No explanation file for this scenario.' },
  missingOrigin: { ko: '이 출발지에 대한 설명이 없습니다.', en: 'No explanation for this origin.' },
  mismatch: {
    ko: '표시된 결과가 설명을 만든 사전 계산 결과와 달라 설명을 표시하지 않습니다.',
    en: 'The results shown differ from the precomputed results the explanation was made from, so it is not shown.',
  },

  // ---- provenance ----
  provenance: {
    ko: '근거: 기록 캐시 {cache} · 위험 패킷 {hazard} · 생성 코드 {commit} · 통과한 검증 {checks}',
    en: 'Basis: recorded cache {cache} · hazard packet {hazard} · code {commit} · checks passed {checks}',
  },
  sheetTitle: { ko: '왜 이 시각인가요? (출발 마감 설명)', en: 'Why this time? (leave-by time explanations)' },

  // ---- units ----
  minutes: { ko: '{m}분', en: '{m} min' },
  underMinute: { ko: '1분 미만', en: 'under 1 min' },
} as const;
