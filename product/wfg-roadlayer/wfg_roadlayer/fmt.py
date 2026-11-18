"""Time formatting (KST), Korean/English labels and Revised Romanization for the English copy."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")

NOTICE = {"ko": "모델 출력 · 참고용 · 명령 아님", "en": "Model output · advisory · not an order"}
NOTICE_LONG = {
    "ko": "이 자료는 모델 출력입니다. 참고용이며 대피 명령이 아닙니다. 대피 결정은 권한 있는 기관이 현장 정보로 내립니다.",
    "en": "This is model output. It is advisory and not an evacuation order. Decisions rest with the competent "
          "authority and field information.",
}
STAGE = {"즉시 실행": {"ko": "즉시 실행", "en": "Execute now"},
         "실행대기": {"ko": "실행대기", "en": "Standby"},
         "준비": {"ko": "준비", "en": "Prepare"}}


def kst(dt: datetime) -> datetime:
    return dt.astimezone(KST)


def t_floor(issue: datetime, s: int) -> datetime:
    """issue + s seconds, rounded DOWN to the minute (never later than the computed time)."""
    t = kst(issue) + timedelta(seconds=s)
    return t.replace(second=0, microsecond=0)


def t_ceil(issue: datetime, s: int) -> datetime:
    """issue + s seconds, rounded UP to the minute (never earlier than the computed time)."""
    t = kst(issue) + timedelta(seconds=s)
    if t.second or t.microsecond:
        t = t.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return t


def full(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def hm_markup(dt: datetime, ref: datetime, lang: str) -> str:
    """HH:MM for a sheet; another day than the issue day is a superscript (+1일 / +1d)."""
    d = (dt.date() - kst(ref).date()).days
    if d == 0:
        return dt.strftime("%H:%M")
    return dt.strftime("%H:%M") + "<super>%+d%s</super>" % (d, "일" if lang == "ko" else "d")


_PLACE_EN = [("초등학교", "Elementary School"), ("중학교", "Middle School"), ("고등학교", "High School"),
             ("마을회관", "village hall"), ("복지회관", "welfare hall"), ("경로당", "seniors' centre"), ("회관", "hall"),
             ("대피소", "shelter"), ("체육관", "gymnasium"), ("분교장", "branch school"), ("분교", "branch school"),
             ("학교", "school"), ("센터", "centre")]


def place_en(name: str) -> str:
    """English label for a shelter or facility: romanized stem + translated suffix (지품초등학교 -> Jipum Elementary School)."""
    if not name:
        return name
    for ko, en in _PLACE_EN:
        if name.endswith(ko) and len(name) > len(ko):
            return "%s %s" % (romanize(name[:-len(ko)]), en)
    return romanize(name)


def minutes_floor(s: int) -> int:
    return int(math.floor(s / 60))


# ------------------------------------------------------------------------------------------------ romanization
_I = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_V = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu",
      "ui", "i"]
_F = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t", "ng", "t",
      "t", "k", "t", "p", "t"]
_SUFFIX = {"리": "ri", "면": "myeon", "읍": "eup", "동": "dong", "군": "gun", "시": "si"}


def _syl(ch):
    o = ord(ch) - 0xAC00
    if not 0 <= o < 11172:
        return None
    return o // 588, (o % 588) // 28, o % 28


def romanize(s: str) -> str:
    """Revised Romanization, syllable by syllable with the basic liaison rules (no full assimilation). Admin
    suffixes 리/면/읍/동/군/시 at the end are hyphenated (지품면 -> Jipum-myeon)."""
    if not s:
        return s
    suffix = ""
    if len(s) >= 2 and s[-1] in _SUFFIX and _syl(s[-2]) is not None:
        suffix, s = "-" + _SUFFIX[s[-1]], s[:-1]
    out = []
    sy = [_syl(c) for c in s]
    for k, c in enumerate(s):
        p = sy[k]
        if p is None:
            out.append(c)
            continue
        i, v, f = p
        ini = _I[i]
        if k > 0 and sy[k - 1] is not None:
            pf = sy[k - 1][2]
            if i == 5 and pf in (0,):
                ini = "r"
            elif i == 5:
                ini = "l" if pf == 8 else "n"
        elif i == 5:
            ini = "r"
        fin = _F[f]
        nxt = sy[k + 1] if k + 1 < len(s) else None
        if nxt is not None and nxt[0] == 11 and f:  # liaison before a vowel-initial syllable
            fin = {1: "g", 4: "n", 7: "d", 8: "r", 16: "m", 17: "b", 19: "s", 21: "ng", 22: "j", 23: "ch"}.get(f, fin)
        if nxt is not None and nxt[0] == 5 and f == 8:
            fin = "l"
        out.append([ini, _V[v], fin])
    for k in range(1, len(out)):  # nasalization of a final k/t/p before n/m (옥류 -> Ongnyu)
        if isinstance(out[k], list) and isinstance(out[k - 1], list) and out[k][0] in ("n", "m"):
            out[k - 1][2] = {"k": "ng", "t": "n", "p": "m"}.get(out[k - 1][2], out[k - 1][2])
    r = "".join("".join(x) if isinstance(x, list) else x for x in out)
    return (r[:1].upper() + r[1:] if r else r) + suffix
