"""Refusals: the tool never outputs a number from a missing or stale input. Every refusal names the input."""
from __future__ import annotations


class Refusal(Exception):
    """Run-level refusal. ``reasons`` is a list of (code, korean, english)."""

    def __init__(self, reasons):
        if isinstance(reasons, tuple):
            reasons = [reasons]
        self.reasons = list(reasons)
        super().__init__("; ".join(r[2] for r in self.reasons))

    def text(self) -> str:
        out = ["계산 거부 — 아래 입력이 없거나 오래되어 숫자를 내지 않습니다.",
               "REFUSED — the inputs below are missing or stale, so no number is output.",
               "모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order", ""]
        for code, ko, en in self.reasons:
            out.append("[%s]" % code)
            out.append("  " + ko)
            out.append("  " + en)
        return "\n".join(out) + "\n"


def reason(code: str, ko: str, en: str):
    return (code, ko, en)
