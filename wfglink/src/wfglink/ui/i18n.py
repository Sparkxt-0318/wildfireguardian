"""Korean and English strings for the booth screen. L toggles; every key exists in both.

The limits card shows limit_1, limit_2, ... in order (limit_keys); the printed placards read
the same keys, so the screen and the paper always agree.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "ko": {
        "app": "wfglink",
        "subtitle": "영상으로 재는 불티",
        "count_rate": "초당 통과 수",
        "cpc": "누적 입자 수 (게이트)",
        "pnf": "입자 수 플럭스 (투영)",
        "speed": "불티 속도",
        "per_s": "개/초",
        "count": "개",
        "pnf_unit_px": "개/100 px/초",
        "pnf_unit_m": "개/m/초",
        "speed_unit_px": "px/초",
        "speed_unit_m": "m/초",
        "estimate": "추정치",
        "uncalibrated": "보정 안 됨 (px)",
        "projected": "투영값",
        "at_distance": "거리 {z} m 기준",
        "field_legend": "불티 기반 바람 추정",
        "gate": "게이트",
        "sparkline": "최근 60초 통과 수",
        "synthetic": "합성 영상 · 실측 아님",
        "playing": "녹화 영상을 실시간 분석 중",
        "paused": "일시정지",
        "quit_confirm": "Esc를 한 번 더 누르면 종료합니다",
        "warming": "측정 준비 중",
        "source_file": "녹화 파일 분석",
        "fps": "fps",
        "limits_title": "이 측정의 한계",
        "limits_hint": "I 키로 닫기",
        "limit_1": "카메라 하나로는 깊이를 알 수 없습니다. 속도와 플럭스는 화면에 투영된 값이며, m/초는 표시된 거리에서만 맞습니다.",
        "limit_2": "불티는 공기가 아닙니다. 바람 변화에 약 0.25~0.8초 늦게 반응하고 초속 2.5~8 m로 떨어지므로, 화살표는 바람의 추정치입니다.",
        "limit_3": "보정에는 불확실성이 있습니다. 도로 표시는 도로 면에서만 크기를 알려 주므로, 공중의 불티는 가정한 거리 범위로 계산합니다.",
        "limit_4": "빛나고 보이는 불티만 셉니다. 개수는 최솟값이며, 플럭스는 NIST의 제곱미터당 값이 아니라 화면 속 선의 길이당 값입니다.",
        "limit_5": "검증은 합성 영상, 속도를 아는 LED, 타당성 점검으로 했습니다. 실제 화재에서 NIST 장비와 나란히 비교하지는 않았습니다.",
    },
    "en": {
        "app": "wfglink",
        "subtitle": "Embers measured from video",
        "count_rate": "Count rate",
        "cpc": "Cumulative Particle Count (gate)",
        "pnf": "Particle Number Flux (projected)",
        "speed": "Ember speed",
        "per_s": "per s",
        "count": "embers",
        "pnf_unit_px": "per 100 px per s",
        "pnf_unit_m": "per m per s",
        "speed_unit_px": "px/s",
        "speed_unit_m": "m/s",
        "estimate": "Estimate",
        "uncalibrated": "Uncalibrated (px)",
        "projected": "Projected",
        "at_distance": "at {z} m",
        "field_legend": "Ember-derived wind (estimate)",
        "gate": "Gate",
        "sparkline": "Crossings, last 60 s",
        "synthetic": "Synthetic video · not measured",
        "playing": "Recorded clip, analysed live",
        "paused": "Paused",
        "quit_confirm": "Press Esc again to quit",
        "warming": "Starting measurement",
        "source_file": "Recorded file",
        "fps": "fps",
        "limits_title": "What this measurement cannot do",
        "limits_hint": "Press I to close",
        "limit_1": "One camera cannot see depth. Speeds and flux are projections onto the picture; m/s holds only at the stated distance.",
        "limit_2": "Embers are not air. They follow gusts 0.25 to 0.8 s late and fall at 2.5 to 8 m/s, so the arrows estimate the wind.",
        "limit_3": "Calibration is uncertain. Road markings only scale the road surface, so airborne embers use an assumed distance range.",
        "limit_4": "Only glowing, visible embers are counted, so counts are lower bounds. Flux is per length of a line in the picture, not NIST's per square metre.",
        "limit_5": "Validated on synthetic video, a known-speed LED and plausibility checks; not side by side with a NIST Emberometer in a real fire.",
    },
}


def limit_keys(lang: str = "en") -> list[str]:
    """limit_1, limit_2, ... in order, as many as exist."""
    keys, k = [], 1
    while f"limit_{k}" in STRINGS.get(lang, STRINGS["en"]):
        keys.append(f"limit_{k}")
        k += 1
    return keys


def t(lang: str, key: str, **fmt) -> str:
    s = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return s.format(**fmt) if fmt else s
