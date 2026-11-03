/**
 * "왜 이 시각인가요? / Why this time?" — Korean first, English mirror. Every sentence is a template filled only from
 * the structured fields of wfg.explanation/1 (no free text from the file is shown). Honesty wording: no route is called
 * safe; scenario members are "fire scenarios from the forecast", never simulations of the actual fire; unresolved is
 * never turned into a reason; a conclusion about what sets the leave-by time is shown only when the file establishes
 * it (deadline_cause), and it names the next checked departure — the only later time that was evaluated.
 *
 * Recorded vs computed: a sentence that rests on a value tools/explain_deadlines computed for the explanation (road
 * times from the road graph, flame-avoiding arrivals, replay contact and pass times, the exits and everything said
 * about them) ends with COMPUTED_MARK ('*') after its full stop, and so does each item of the exit list (a computed
 * exit with its place distance and member count; no full stop). `computedNote` / `sheetNote*` say what the mark means,
 * `host*` where the file was computed. Sentences that restate recorded results only (the last checked time, a "시간창
 * 밖" skip, an unresolved next time or origin) carry no mark. The member dots repeat the k of n of the marked sentence
 * they illustrate.
 */
import type { L10n } from '../shared/strings';

/** Ends every sentence (and exit-list item) that rests on a value computed for the explanation rather than a recorded check. */
export const COMPUTED_MARK = '*';

export const EXPLAIN = {
  titleTime: { ko: '왜 이 시각인가요?', en: 'Why this time?' },
  titleNoRoute: { ko: '왜 확인된 경로가 없나요?', en: 'Why is there no checked route?' },
  basis: {
    ko: '예측에서 나온 화재 시나리오 {total}개를 기준으로 한 결과이며, 관측이 아닙니다.',
    en: 'Based on {total} fire scenarios from the forecast; not an observation.',
  },
  status: {
    explained: { ko: '설명됨(기록된 점검 재현)', en: 'Explained (replay of recorded checks)' },
    explained_partial: { ko: '부분 설명(기록된 점검 재현)', en: 'Partly explained (replay of recorded checks)' },
    not_explainable: { ko: '설명 없음', en: 'No explanation' },
  } as Record<'explained' | 'explained_partial' | 'not_explainable', L10n>,
  members: { ko: '화재 시나리오 {total}개 중 {k}개', en: '{k} of {total} fire scenarios' },
  membersAtLeast: { ko: '화재 시나리오 {total}개 중 {k}개 이상', en: 'at least {k} of {total} fire scenarios' },

  // ---- where (a road location; the place is the nearest named OSM place, its distance straight-line) ----
  wherePlace: { ko: '{name}에서 약 {dist} 떨어진 도로', en: 'a road about {dist} from {name}' },
  wherePlaceOrigin: { ko: '이 마을({name})에서 약 {dist} 떨어진 도로', en: 'a road about {dist} from {name} (this village)' },
  wherePlaceOriginOther: { ko: '이곳({name})에서 약 {dist} 떨어진 도로', en: 'a road about {dist} from {name} (this place)' },
  whereNamed: { ko: '{name}', en: '{name}' },
  whereUnnamed: { ko: '이름 없는 도로(도로 노드 {node})', en: 'an unnamed road (road node {node})' },

  // ---- shared pieces ----
  byTime: { ko: '{time}까지', en: 'by {time}' },
  inTime: { ko: '제때', en: 'in time' },

  // ---- last checked time (recorded only) ----
  noLater: {
    ko: '점검한 마지막 출발 시각이 {deadline}입니다. 기록된 화재 시나리오는 입력 시각부터 {hours}시간({end}까지)만 다루므로 그 뒤의 출발은 점검하지 않았습니다. 이 시각은 예측 화염으로 정해진 것이 아닙니다.',
    en: '{deadline} is the last departure time that was checked. The recorded fire scenarios cover only {hours} h after the input time (until {end}), so later departures were not checked. This time is not set by predicted flames.',
  },

  // ---- time window (no shelter considered can be reached in time even without fire) ----
  windowFireFree: {
    ko: '{next}에 출발하면 화재가 없더라도 가장 빠른 도로로 대피소에 도착해 {dwell}분 머무는 일이 {fastestEnd}에야 끝나, 기록된 화재 시나리오가 끝나는 {end}를 넘습니다.*',
    en: 'Leaving at {next}, even the fastest road route, ignoring the fire, would finish the {dwell}-minute stay at the shelter only at {fastestEnd}, after the recorded fire scenarios end at {end}.*',
  },
  windowFireFreeUnreachable: {
    ko: '{next}에 출발하면 화재가 없더라도 어떤 도로로도 기록된 화재 시나리오가 끝나는 {end} 전에 대피소에 도착해 {dwell}분 머물 수 없습니다.*',
    en: 'Leaving at {next}, no road route, even ignoring the fire, reaches the shelter and completes the {dwell}-minute stay before the recorded fire scenarios end at {end}.*',
  },
  windowArrivalFireFree: {
    ko: '{next}에 출발하면 화재가 없더라도 가장 빠른 도로로 도착해 {dwell}분 머무는 일이 {fastestEnd}에야 끝나, 이 기록 임무의 도착 허용 시간({close}까지)을 넘습니다.*',
    en: "Leaving at {next}, even the fastest road route, ignoring the fire, would finish the {dwell}-minute stay only at {fastestEnd}, after this recorded mission's arrival window closes at {close}.*",
  },
  othersFireFreeOne: {
    ko: '화재가 없더라도 나머지 후보 대피소 {k}곳에도 {by} 도착해 {dwell}분 체류를 마칠 수 없습니다.*',
    en: 'Even ignoring the fire, the other candidate shelter cannot be reached {by} (including the {dwell}-minute stay) either.*',
  },
  othersFireFree: {
    ko: '화재가 없더라도 나머지 후보 대피소 {k}곳에도 {by} 도착해 {dwell}분 체류를 마칠 수 없습니다.*',
    en: 'Even ignoring the fire, none of the other {k} candidate shelters can be reached {by} (including the {dwell}-minute stay) either.*',
  },
  // only the next checked departure was evaluated: the conclusions name it and claim nothing about other times
  rangeOne: {
    ko: '다음 점검 출발 시각인 {next}에 출발하면 이 대피소는 1시간 시나리오 범위를 벗어나므로, 이 출발 마감은 예측 화염이 아니라 시나리오 범위로 정해진 것입니다.*',
    en: 'At the next checked departure, {next}, the trip to this shelter falls outside the one-hour scenario range, so this leave-by time is set by that range, not by predicted flames.*',
  },
  rangeMany: {
    ko: '다음 점검 출발 시각인 {next}에 출발하면 이 대피소들은 모두 1시간 시나리오 범위를 벗어나므로, 이 출발 마감은 예측 화염이 아니라 시나리오 범위로 정해진 것입니다.*',
    en: 'At the next checked departure, {next}, the trip to every one of these shelters falls outside the one-hour scenario range, so this leave-by time is set by that range, not by predicted flames.*',
  },
  arrivalOne: {
    ko: '다음 점검 출발 시각인 {next}에 출발하면 이 기록 임무의 도착 허용 시간을 벗어나므로, 이 출발 마감은 예측 화염이 아니라 그 시간으로 정해진 것입니다.*',
    en: "At the next checked departure, {next}, the trip to this shelter falls outside this recorded mission's arrival window, so this leave-by time is set by that window, not by predicted flames.*",
  },
  limitsMany: {
    ko: '다음 점검 출발 시각인 {next}에 출발하면 이 대피소들은 모두 점검 시간 범위를 벗어나므로, 이 출발 마감은 예측 화염이 아니라 그 시간 범위로 정해진 것입니다.*',
    en: 'At the next checked departure, {next}, the trip to every one of these shelters falls outside the time limits of the checks, so this leave-by time is set by those limits, not by predicted flames.*',
  },
  windowSkip: {
    ko: '{next}에 출발하면 이 기록 임무의 도착 허용 시간({open}–{close}) 안에 {dwell}분 체류를 마칠 수 없어 그 시각은 점검하지 않았습니다(시간창 밖).',
    en: "Leaving at {next}, the {dwell}-minute stay cannot fit this recorded mission's arrival window ({open}–{close}), so that time was not checked (outside the window).",
  },
  noRouteFireFree: {
    ko: '점검한 어느 출발 시각에도 화재가 없더라도 후보 대피소에 {by} 도착해 {dwell}분 체류를 마칠 수 있는 도로가 없으므로, 이는 예측 화염이 아니라 시간 범위 때문입니다.*',
    en: 'From every checked departure time, even ignoring the fire, no road route reaches a candidate shelter {by} (including the {dwell}-minute stay), so this is set by the time window, not by predicted flames.*',
  },

  // ---- no flame-avoiding route (a fire-free road would fit; every flame-avoiding one is too late or absent) ----
  windowDetour: {
    ko: '{next}에 출발하면 시나리오상 화염을 피하는 도로로는 {close}까지 대피소에 도착해 {dwell}분 체류를 마칠 수 없습니다({fa}).* 화재가 없다면 가장 빠른 도로로 {fastestEnd}에 체류를 마칠 수 있습니다.*',
    en: 'Leaving at {next}, no road route that avoids the flames in the fire scenarios reaches the shelter in time to finish the {dwell}-minute stay by {close} ({fa}).* Without fire the fastest road would finish the stay at {fastestEnd}.*',
  },
  faArrival: { ko: '화염을 피하면 {time} 전에는 도착할 수 없음', en: 'avoiding the flames, no arrival before {time}' },
  faNone: { ko: '시나리오가 끝나는 {end}까지 화염을 피해 도착하는 경로 없음', en: 'no flame-avoiding arrival at all by {end}, when the scenarios end' },
  // the shown route's shelter is out of the window even without fire; other shelters only because of the flames
  mixedShownRange: {
    ko: '{next}에 출발하면 표시된 경로의 대피소는 화재가 없어도 1시간 시나리오 범위 안에 체류를 마칠 수 없고({shownEnd}),',
    en: "Leaving at {next}, the shown route's shelter is beyond the one-hour scenario range even without fire ({shownEnd});",
  },
  mixedShownArrival: {
    ko: '{next}에 출발하면 표시된 경로의 대피소는 화재가 없어도 이 기록 임무의 도착 허용 시간 안에 체류를 마칠 수 없고({shownEnd}),',
    en: "Leaving at {next}, the shown route's shelter is beyond this recorded mission's arrival window even without fire ({shownEnd});",
  },
  mixedShownEnd: { ko: '{time}', en: 'the stay would end at {time}' },
  mixedShownNoRoad: { ko: '1시간 안에 닿는 도로 없음', en: 'no road reaches it within the hour' },
  mixedFlameAllOne: {
    ko: '화재가 없다면 제때 갈 수 있는 나머지 대피소 {k}곳은 시나리오상 화염을 피하는 도로로 갈 수 없습니다.*',
    en: 'the other shelter, which a fire-free road would still reach in time, cannot be reached on any road that avoids the flames in the fire scenarios.*',
  },
  mixedFlameAll: {
    ko: '화재가 없다면 제때 갈 수 있는 나머지 대피소 {k}곳은 시나리오상 화염을 피하는 도로로 갈 수 없습니다.*',
    en: 'the other {k} shelters, which a fire-free road would still reach in time, cannot be reached on any road that avoids the flames in the fire scenarios.*',
  },
  mixedFlameSomeOne: {
    ko: '화재가 없다면 제때 갈 수 있는 다른 대피소 {k}곳은 시나리오상 화염을 피하는 도로로 갈 수 없습니다.*',
    en: 'another shelter, which a fire-free road would still reach in time, cannot be reached on any road that avoids the flames in the fire scenarios.*',
  },
  mixedFlameSome: {
    ko: '화재가 없다면 제때 갈 수 있는 다른 대피소 {k}곳은 시나리오상 화염을 피하는 도로로 갈 수 없습니다.*',
    en: '{k} other shelters, which a fire-free road would still reach in time, cannot be reached on any road that avoids the flames in the fire scenarios.*',
  },
  mixedAlsoOutOne: {
    ko: '나머지 대피소 {k}곳은 화재가 없어도 제때 갈 수 없습니다.*',
    en: 'The remaining shelter cannot be reached in time even without fire.*',
  },
  mixedAlsoOut: {
    ko: '나머지 대피소 {k}곳은 화재가 없어도 제때 갈 수 없습니다.*',
    en: 'The remaining {k} shelters cannot be reached in time even without fire.*',
  },
  /** only with deadline_cause "flames": without the fire the next checked departure would reach a shelter in time */
  flamesConclusion: { ko: '따라서 이 출발 마감은 시나리오상 화염 때문입니다.*', en: 'So this leave-by time comes from the flames in the fire scenarios.*' },
  noRouteFlames: {
    ko: '점검한 어느 출발 시각에도 시나리오상 화염을 피하는 도로로는 후보 대피소에 {by} 도착해 {dwell}분 체류를 마칠 수 없습니다.* 화재가 없다면 적어도 한 곳에는 제때 갈 수 있으므로, 이는 시나리오상 화염 때문입니다.*',
    en: 'From every checked departure time, no road route that avoids the flames in the fire scenarios reaches a candidate shelter {by} (including the {dwell}-minute stay).* A fire-free road would reach at least one of them in time, so this comes from the flames in the fire scenarios.*',
  },

  // ---- shelters with a checked route at the leave-by time ----
  cdUnreachable: {
    ko: '{next}에 출발하면 {deadline}에 확인된 경로가 있던 대피소 {n}곳 어디에도 시나리오상 화염을 피하는 도로로 {by} 도착해 {dwell}분 체류를 마칠 수 없습니다.*',
    en: 'Leaving at {next}, no road route that avoids the flames in the fire scenarios reaches any of the {n} shelters with a checked route at {deadline} {by} (including the {dwell}-minute stay).*',
  },
  oneUnreachable: {
    ko: '{next}에 출발하면 시나리오상 화염을 피하는 도로로는 그 대피소에 {by} 도착해 {dwell}분 체류를 마칠 수 없습니다.*',
    en: 'Leaving at {next}, no road route that avoids the flames in the fire scenarios reaches that shelter {by} (including the {dwell}-minute stay).*',
  },

  // ---- flame on the route shown (replay of the recorded route, shifted to the next checked time) ----
  flame: {
    ko: '{next}에 출발해 {deadline}에 확인된 같은 경로로 가면 {where}에서 {contact}에 시나리오상 화염과 만납니다({members}).*',
    en: 'Leaving at {next} on the same route that was checked for {deadline}, the vehicle would meet flames on {where} at {contact} ({members}).*',
  },
  thatCell: { ko: '그 375 m 격자 칸', en: 'that 375 m grid cell' },
  aCellOnRoad: { ko: '그 도로의 한 375 m 격자 칸', en: 'a 375 m grid cell on that road' },
  flameSlackOne: {
    ko: '출발 마감 {deadline}에 출발하면 차량은 {pass}에 {cell}을 벗어납니다.* 그 시나리오에서 이 칸이 타기 시작하는 {flame}보다 {slack} 이릅니다.*',
    en: 'Leaving at the leave-by time {deadline}, the vehicle clears {cell} at {pass}, {slack} before that cell starts burning in that scenario ({flame}).*',
  },
  flameSlackMany: {
    ko: '출발 마감 {deadline}에 출발하면 차량은 {pass}에 {cell}을 벗어납니다.* 그 시나리오들 중 하나에서 이 칸이 타기 시작하는 {flame}보다 {slack} 이릅니다.*',
    en: 'Leaving at the leave-by time {deadline}, the vehicle clears {cell} at {pass}, {slack} before that cell starts burning in one of those scenarios ({flame}).*',
  },
  dwell: {
    ko: '{next}에 출발하면 대피소에 도착한 뒤 {dwell}분 머무는 동안 {contact}에 대피소 주변(375 m 격자 칸)이 시나리오상 화염과 만납니다({members}).*',
    en: "Leaving at {next}, the shelter's surroundings (375 m grid cell) meet flames in the fire scenarios at {contact}, during the {dwell}-minute stay ({members}).*",
  },

  // ---- cut off ----
  exitsOne: {
    ko: '진입 지점에서 화염과 만나지 않고 갈 수 있는 구역을 벗어나는 도로는 1개뿐이며, 이 도로가 시나리오상 화염과 만납니다({members}).*',
    en: 'The only road leading out of the area that can be reached from the entry point without meeting flames runs into flames in the fire scenarios ({members}).*',
  },
  exitsTwo: {
    ko: '진입 지점에서 화염과 만나지 않고 갈 수 있는 구역의 도로 출구 2곳이 모두 시나리오상 화염과 만납니다({members}).*',
    en: 'Both road exits from the area that can be reached from the entry point without meeting flames run into flames in the fire scenarios ({members}).*',
  },
  exits: {
    ko: '진입 지점에서 화염과 만나지 않고 갈 수 있는 구역의 도로 출구 {n}곳이 모두 시나리오상 화염과 만납니다({members}).*',
    en: 'All {n} road exits from the area that can be reached from the entry point without meeting flames run into flames in the fire scenarios ({members}).*',
  },
  // the follow-up sentences describe the computed exits of the sentence before them: marked as well
  exitsSameWayBothDirections: {
    ko: '두 출구는 같은 도로(OSM way {way})의 양쪽 방향입니다.*',
    en: 'Both are on the same road (OSM way {way}), one in each direction.*',
  },
  exitsSameWay: { ko: '두 출구는 같은 도로(OSM way {way})에 있습니다.*', en: 'Both are on the same road (OSM way {way}).*' },
  exitsPresentOne: {
    ko: '이 도로는 입력 시각({input})에 이미 타고 있는 것으로 표시된 칸을 지납니다.*',
    en: 'It crosses cells already marked as burning at the input time ({input}).*',
  },
  exitsPresent: {
    ko: '이 도로들은 입력 시각({input})에 이미 타고 있는 것으로 표시된 칸을 지납니다.*',
    en: 'They cross cells already marked as burning at the input time ({input}).*',
  },
  exitsLatestOne: {
    ko: '차량이 가장 일찍 닿을 수 있는 시각에 이미 막혀 있으며, {latest}에는 화염과 만납니다.*',
    en: 'It is already blocked when the vehicle could first reach it and meets flames by {latest}.*',
  },
  exitsLatest: {
    ko: '차량이 가장 일찍 닿을 수 있는 시각에 이미 막혀 있으며, 마지막 도로도 {latest}에는 화염과 만납니다.*',
    en: 'Each is already blocked when the vehicle could first reach it; the last one meets flames by {latest}.*',
  },
  // exit list items (not sentences): a computed exit, its place distance and member count; the mark ends each item
  exitItem: { ko: '{where}: 시나리오 {k}/{total}*', en: '{where}: {k}/{total} scenarios*' },
  exitsMore: { ko: '외 {n}개*', en: 'and {n} more*' },
  entryInFlame: {
    ko: '점검한 첫 출발 시각인 {first}에 진입 지점이 이미 화재 시나리오 중 적어도 하나에서 화염 안에 있습니다.*',
    en: 'At the first checked departure, {first}, the entry point itself is already in flames in at least one of the fire scenarios.*',
  },

  // ---- unresolved (recorded only) ----
  unresolvedNext: {
    ko: '다음 출발 시각({next})의 점검 결과는 미확인입니다. 출발 마감은 확인된 마지막 시각일 뿐이며, 더 늦은 출발이 가능한지는 알 수 없습니다. 미확인을 안전으로 해석하지 마십시오.',
    en: 'The next departure time ({next}) could not be verified (unresolved). The leave-by time is only the last checked time; whether a later departure would work is unknown. Unresolved never means safe.',
  },
  originUnresolved: {
    ko: '이 출발지는 미확인이어서 설명할 출발 마감이 없습니다.',
    en: 'This origin is unresolved, so there is no leave-by time to explain.',
  },
  other: { ko: '이 결과에 대해서는 설명을 확립하지 못했습니다.', en: 'No explanation could be established for this result.' },

  // ---- fallbacks ----
  loading: { ko: '설명을 불러오는 중…', en: 'Loading the explanation…' },
  absent: { ko: '이 시나리오에 대한 설명 파일이 없습니다.', en: 'No explanation file for this scenario.' },
  missingOrigin: { ko: '이 출발지에 대한 설명이 없습니다.', en: 'No explanation for this origin.' },
  noPlan: { ko: '이 출발지에는 설명할 출발 마감 결과가 없습니다.', en: 'There is no leave-by result for this origin to explain.' },
  mismatch: {
    ko: '표시된 결과가 설명을 만든 사전 계산 결과와 달라 설명을 표시하지 않습니다.',
    en: 'The results shown differ from the precomputed results the explanation was made from, so it is not shown.',
  },

  // ---- recorded vs computed, where it was computed (panel; the plan sheet says it once in its section footer) ----
  computedNote: {
    ko: '* 기록된 점검이 아니라 이 설명을 위해 도로망과 화재 시나리오로 계산한 값입니다.',
    en: '* Computed for this explanation from the road graph and the fire scenarios, not a recorded check.',
  },
  hostOff: {
    ko: '이 설명은 평가 호스트가 아닌 {platform}에서 계산했습니다. 기록된 경로 점검을 같은 위험 패킷으로 재현했으며, 새 경로 점검은 하지 않았습니다.',
    en: 'Computed for this explanation on {platform}, not on the evaluated host: the recorded route checks are replayed against the same hazard packet; no new route checks were run.',
  },
  hostOffUnknown: {
    ko: '이 설명은 평가 호스트에서 계산한 것이 아닙니다. 기록된 경로 점검을 같은 위험 패킷으로 재현했으며, 새 경로 점검은 하지 않았습니다.',
    en: 'Not computed on the evaluated host: the recorded route checks are replayed against the same hazard packet; no new route checks were run.',
  },
  hostOn: {
    ko: '이 설명은 평가 호스트({platform})에서 계산했습니다. 기록된 경로 점검을 같은 위험 패킷으로 재현했으며, 새 경로 점검은 하지 않았습니다.',
    en: 'Computed for this explanation on the evaluated host ({platform}): the recorded route checks are replayed against the same hazard packet; no new route checks were run.',
  },
  // A4 footer: the mark's meaning, the computing host, and that it is no new route check either (fits one line)
  sheetNoteOff: {
    ko: '* 평가 호스트가 아닌 {platform}에서 계산한 값이며, 기록된 점검도 새 경로 점검도 아닙니다.',
    en: '* Computed on {platform} (not the evaluated host); not a recorded or new route check.',
  },
  sheetNoteOffUnknown: {
    ko: '* 평가 호스트가 아닌 곳에서 계산한 값이며, 기록된 점검도 새 경로 점검도 아닙니다.',
    en: '* Computed off the evaluated host; not a recorded or new route check.',
  },
  sheetNoteOn: {
    ko: '* 평가 호스트({platform})에서 계산한 값이며, 기록된 점검도 새 경로 점검도 아닙니다.',
    en: '* Computed on the evaluated host ({platform}); not a recorded or new route check.',
  },

  // ---- provenance ----
  provenance: {
    ko: '근거: 기록 캐시 {cache} · 위험 패킷 {hazard} · 생성 코드 {commit} · 통과한 검증 {checks}',
    en: 'Basis: recorded cache {cache} · hazard packet {hazard} · code {commit} · validations passed {checks}',
  },
  sheetTitle: { ko: '왜 이 시각인가요? (출발 마감 설명)', en: 'Why this time? (leave-by time explanations)' },

  // ---- units ----
  /** margins are rounded down to whole minutes, so they are stated as a lower bound */
  atLeastMinutes: { ko: '{m}분 이상', en: 'at least {m} min' },
  underMinute: { ko: '1분 미만', en: 'under 1 min' },
} as const;
