"""마을방송 낭독 문구 — plain text a person reads aloud over the village PA.

Round-3 PHASE 3.

The 2025 Yeongnam survey (n=300) found the village PA (마을방송) and neighbours
carried more evacuation information than SMS did. The PA is not a fallback
channel here; for this population it is a primary one.

CONSTRAINTS, all enforced by :func:`check`
------------------------------------------
* **15 characters or fewer per sentence.** A reader under stress loses long
  sentences, and so does a listener.
* **Repetition.** The key instruction is stated, then restated after the detail,
  because a listener who missed the opening needs a second chance.
* **Place names only.** Never coordinates, never node identifiers.
* No English, no numerals-as-identifiers, no jargon.

TTS is out of scope. The output is text for a human announcer.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Maximum code points per sentence.
MAX_SENTENCE_CHARS: int = 15


@dataclass(frozen=True)
class Broadcast:
    village: str
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def check(self) -> dict:
        over = [(i + 1, ln, len(ln)) for i, ln in enumerate(self.lines)
                if len(ln) > MAX_SENTENCE_CHARS]
        return {"n_lines": len(self.lines),
                "max_sentence_chars": MAX_SENTENCE_CHARS,
                "longest": max((len(ln) for ln in self.lines), default=0),
                "violations": over, "ok": not over}

    def as_dict(self) -> dict:
        return {"village": self.village, "lines": self.lines, **self.check()}


#: Address suffixes, with their true code-point lengths.
_INLINE_SUFFIX = " 주민 여러분."      # 8 chars including the leading space
_OWN_LINE_SUFFIX = "주민 여러분."     # 7 chars


def _split_name(name: str) -> list[str]:
    """Break a long place name across lines so NO line exceeds the limit.

    Measured against the real suffix length rather than an estimate: an earlier
    version compared ``len(name) + 6`` when the suffix is 8 code points, and
    emitted 17-character lines for names like "거무역리공원 일대".
    """
    if len(name) + len(_INLINE_SUFFIX) <= MAX_SENTENCE_CHARS:
        return [f"{name}{_INLINE_SUFFIX}"]
    lines, rem = [], name
    while len(rem) > MAX_SENTENCE_CHARS:
        lines.append(rem[:MAX_SENTENCE_CHARS])
        rem = rem[MAX_SENTENCE_CHARS:]
    if rem:
        lines.append(rem)
    lines.append(_OWN_LINE_SUFFIX)
    return lines


def compose(village: str, *, refuge: str | None = None,
            blocked: str | None = None, n_unreachable: int = 0) -> Broadcast:
    """Build the announcement.

    Structure: address → instruction → detail → repeat instruction. Every line
    is <= 15 characters; long place names are wrapped rather than truncated.
    """
    lines: list[str] = []
    lines += _split_name(village)
    lines.append("산불이 접근합니다.")

    if refuge:
        target = refuge if len(refuge) <= 7 else refuge[:7]
        lines.append(f"{target} 쪽으로")
        lines.append("대피하십시오.")
    else:
        lines.append("낮은 곳으로")
        lines.append("대피하십시오.")

    if blocked:
        b = blocked if len(blocked) <= 8 else blocked[:8]
        lines.append(f"{b} 길은")
        lines.append("통행할 수 없습니다.")

    if n_unreachable:
        lines.append("차량 진입이")
        lines.append("어려운 곳이 있습니다.")
        lines.append("무리하지 마십시오.")

    lines.append("거동이 불편한 분은")
    lines.append("집에서 기다리십시오.")
    lines.append("반복합니다.")
    lines += _split_name(village)
    if refuge:
        target = refuge if len(refuge) <= 7 else refuge[:7]
        lines.append(f"{target} 쪽으로")
    lines.append("대피하십시오.")

    return Broadcast(village=village, lines=lines)


__all__ = ["Broadcast", "MAX_SENTENCE_CHARS", "compose"]
