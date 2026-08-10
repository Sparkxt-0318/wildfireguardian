// 한국어 — 기본 언어. 존댓말, 쉬운 말. (spec §1.6)
// This object defines the single typed key map; en.ts must provide every key.
export const ko = {
  app_name: "산불지킴이",

  // tabs
  tab_home: "홈",
  tab_map: "지도",
  tab_guide: "안내",
  tab_family: "가족",
  tab_settings: "설정",

  // shared / states
  loading_title: "잠시만 기다려 주세요",
  loading_sub: "정보를 불러오고 있습니다",
  error_title: "정보를 불러오지 못했습니다",
  error_sub: "인터넷 연결을 확인해 주세요",
  error_retry: "다시 시도",
  updated_label: "업데이트",
  close: "닫기",
  save: "저장",
  saved: "저장되었습니다",

  // read aloud
  read_aloud: "소리로 듣기",
  read_aloud_stop: "읽기 멈추기",
  read_screen: "화면 전체 소리로 듣기",
  read_not_supported: "이 기기에서는 소리 읽기가 되지 않습니다",

  // home
  home_btn_safe: "지도 보기",
  home_btn_go: "대피 경로 보기",

  // honesty labels
  demo_banner_fallback: "연습 모드 — 실제 상황이 아닙니다",
  prediction_unavailable: "지금은 확산 예측 정보가 없습니다",
  mode_label: "데이터",
  mode_demo: "연습용 자료",
  mode_live: "실시간 자료",

  // map
  map_my_location: "내 위치",
  map_location_denied:
    "위치 권한이 없어서 기본 위치(영덕 부근)를 보여 드립니다",
  map_zoom_in: "확대",
  map_zoom_out: "축소",
  legend_title: "지도 표시",
  legend_fire: "산불 감지 지점",
  legend_spread_1h: "1시간 안 확산 예상",
  legend_spread_3h: "3시간 안 확산 예상",
  legend_spread_6h: "6시간 안 확산 예상",
  legend_pathway: "불길이 가는 방향",
  legend_shelter: "대피소",
  legend_me: "내 위치",
  legend_route: "대피 경로",
  map_route_btn: "대피 경로 보기",
  map_route_hide: "경로 지우기",
  map_route_loading: "경로를 찾고 있습니다",
  route_no_safe_walk:
    "안전한 도보 길을 찾지 못했습니다. 지금 바로 119에 전화해 주세요.",
  route_outside_region: "지금 계신 곳은 아직 서비스 지역이 아닙니다",
  dist_label: "거리",
  walk_label: "도보",

  // guide
  guide_title: "안내",
  guide_empty: "지금 보여 드릴 안내가 없습니다",
  call_119: "119에 전화하기",
  open_map_action: "지도 보기",
  open_route_action: "대피 경로 보기",

  // weather / fire labels (numbers always come from the server)
  wx_wind: "바람",
  wx_humidity: "습도",
  wx_temp: "기온",
  wx_days_since_rain: "비가 안 온 지",
  wx_wind_toward: "바람이 집 쪽으로 불고 있습니다",
  wx_wind_not_toward: "바람이 집 반대쪽으로 불고 있습니다",
  fire_distance: "불까지 거리",
  fire_direction: "불이 있는 방향",
  fire_detections: "감지된 지점",

  // charts
  wind_compass_title: "바람",
  wind_toward_label: "바람이 가는 쪽",
  timeline_title: "감지 지점 수",
  timeline_sub: "시간에 따른 변화",
  eta_bar_title: "불이 닿기까지",
  eta_bar_sub: "예상 시간입니다. 실제와 다를 수 있습니다.",
  dir_n: "북",
  dir_e: "동",
  dir_s: "남",
  dir_w: "서",
  unit_min: "분",
  unit_hour: "시간",
  unit_km: "km",
  unit_ms: "m/s",
  unit_c: "°C",
  unit_pct: "%",
  unit_day: "일",

  // family / Guardian Plus
  family_title: "가족",
  plus_name: "가디언 플러스",
  free_title: "안전 기능은 언제나 무료입니다",
  free_note:
    "위험 알림, 지도, 확산 예측, 대피 경로는 계정 없이 누구나 영원히 무료로 쓰실 수 있습니다.",
  free_1: "위험 단계 알림",
  free_2: "산불 지도와 확산 예측",
  free_3: "대피 경로와 대피소 안내",
  free_4: "실시간 새 소식",
  plus_title: "가디언 플러스는 편의 기능입니다",
  plus_note: "구독하지 않아도 안전에 필요한 것은 모두 보실 수 있습니다.",
  plus_1: "가족에게 자동으로 소식 보내기",
  plus_2: "문자와 전화로도 알림 받기",
  plus_3: "인터넷 없이 쓰는 지도 저장",
  plus_4: "여러 집 주소 함께 지켜보기",
  fam_list_title: "우리 가족 연락처",
  fam_note: "연락처는 이 휴대폰에만 저장됩니다. 어디에도 보내지 않습니다.",
  fam_name_ph: "이름",
  fam_phone_ph: "전화번호",
  fam_add: "추가",
  fam_remove: "삭제",
  fam_call: "전화",
  fam_empty: "아직 저장된 연락처가 없습니다",
  subscribe_monthly: "월간 구독하기",
  subscribe_yearly: "연간 구독하기",
  billing_not_configured:
    "지금은 구독 결제를 준비하고 있습니다. 조금만 기다려 주세요. 안전 기능은 모두 무료로 계속 쓰실 수 있습니다.",
  billing_success: "구독해 주셔서 감사합니다",
  billing_cancelled: "결제가 취소되었습니다. 안전 기능은 계속 무료입니다.",
  billing_redirecting: "결제 화면으로 이동합니다",

  // settings
  settings_title: "설정",
  set_text_size: "글자 크기",
  text_size_normal: "보통",
  text_size_large: "크게",
  set_language: "언어",
  set_home: "우리 집 위치",
  home_current: "저장된 위치",
  home_not_set: "아직 저장된 위치가 없습니다",
  use_my_location: "내 위치 사용",
  pick_on_map: "지도에서 고르기",
  pick_on_map_hint: "지도를 눌러서 집 위치를 정해 주세요",
  about_title: "이 앱은",
  about_body:
    "산불지킴이는 우리 집 근처 산불 소식을 쉬운 말로 알려 드리는 앱입니다. 위험 단계, 지도, 대피 경로를 한눈에 보실 수 있습니다.",
  disclaimer_title: "꼭 읽어 주세요",
  disclaimer_body:
    "이 앱은 참고용입니다. 정부의 재난문자와 119, 마을 방송의 안내를 항상 먼저 따라 주세요. 이 앱은 공식 경보를 대신하지 않습니다. 확산 예측은 연구용 계산 결과이며 실제와 다를 수 있습니다.",
  version_label: "버전",
} as const;

export type MessageKey = keyof typeof ko;
export type Messages = { readonly [K in MessageKey]: string };
