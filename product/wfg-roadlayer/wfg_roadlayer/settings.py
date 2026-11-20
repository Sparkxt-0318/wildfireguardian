"""Settings: defaults in settings.toml next to this file; an operator file given with --settings overrides them."""
from __future__ import annotations

import tomllib
from pathlib import Path

from .errors import Refusal, reason

DEFAULT = Path(__file__).with_name("settings.toml")

_SCHEMA = {
    "stage": {"standby_hours": float, "immediate_hours": float},
    "routing": {"shelters_per_village": int, "dwell_s": int},
    "freshness": {"max_fire_input_age_min": float, "max_issue_ahead_min": float, "max_road_age_days": float,
                  "max_places_age_days": float},
    "run": {"workers": int},
    "heat": {"enabled": int, "threshold_kw_m2": float, "fuel_level": int, "wind10_m_s": float, "rh_pct": float,
             "air_temp_c": float},
}


def load(path: Path | None = None) -> dict:
    with open(DEFAULT, "rb") as f:
        s = tomllib.load(f)
    src = [str(DEFAULT.name)]
    if path is not None:
        p = Path(path)
        if not p.is_file():
            raise Refusal(reason("SETTINGS_MISSING", "설정 파일이 없습니다: %s" % p, "settings file not found: %s" % p))
        with open(p, "rb") as f:
            user = tomllib.load(f)
        for sec, vals in user.items():
            if sec not in _SCHEMA:
                raise Refusal(reason("SETTINGS_INVALID", "알 수 없는 설정 구역 [%s]" % sec, "unknown settings section [%s]" % sec))
            for k, v in vals.items():
                if k not in _SCHEMA[sec]:
                    raise Refusal(reason("SETTINGS_INVALID", "알 수 없는 설정 %s.%s" % (sec, k), "unknown setting %s.%s" % (sec, k)))
                s[sec][k] = v
        src.append(str(p))
    for sec, keys in _SCHEMA.items():
        for k, typ in keys.items():
            v = s[sec][k]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or (typ is int and not isinstance(v, int)):
                raise Refusal(reason("SETTINGS_INVALID", "설정 %s.%s 값이 잘못됨: %r" % (sec, k, v),
                                     "setting %s.%s has an invalid value: %r" % (sec, k, v)))
    st = s["stage"]
    if not (0 < st["immediate_hours"] < st["standby_hours"]):
        raise Refusal(reason("SETTINGS_INVALID", "단계 기준은 0 < 즉시 실행 < 실행대기 이어야 합니다",
                             "stage thresholds must satisfy 0 < immediate_hours < standby_hours"))
    if s["routing"]["shelters_per_village"] < 1 or s["routing"]["dwell_s"] < 0:
        raise Refusal(reason("SETTINGS_INVALID", "routing 설정 값이 잘못됨", "invalid routing settings"))
    h = s["heat"]
    if h["enabled"] not in (0, 1) or not (h["threshold_kw_m2"] > 0) or h["fuel_level"] not in (0, 1, 2) \
            or h["wind10_m_s"] < 0 or not (0 < h["rh_pct"] <= 100):
        raise Refusal(reason("SETTINGS_INVALID", "heat 설정 값이 잘못됨", "invalid heat settings"))
    s["_sources"] = src
    return s
