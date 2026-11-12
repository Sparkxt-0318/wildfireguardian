#!/usr/bin/env python3.12
"""Builds the print-ready session kit from the committed item files (items/<case>/...). It adds no wording to any
item: each participant handout shows one item's bytes exactly, inside a neutral frame that carries only its handout
code. Writes:

    print/handouts/<code>.html   one participant-facing item per page (SMS, public card, staff headline)
    print/RECORDING_SCRIPT.html  the broadcast scripts, for the one person who records them (not shown to participants)
    SCHEDULE.csv                 item order per participant slot (Latin square over case x channel)
    results_template.csv         one pre-filled row per exposure, for the facilitator and the two coders

The A4 plan sheet is printed straight from items/<case>/a4.ko.pdf (one A4 page, as the planner prints it).

    python3.12 build_print.py [--check]       (--check: rebuild in memory, fail on any byte difference)
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

KIT = Path(__file__).resolve().parent.parent
REPO = KIT.parents[3]
CHANNELS = {"A": ("broadcast", "sms", "card"), "B": ("headline", "a4")}
SLOTS = {"A": 12, "B": 8}
CHANNEL_KO = {"broadcast": "마을 방송(녹음)", "sms": "가족 문자", "card": "공개 화면 카드", "headline": "계획 도구 상단 문구", "a4": "A4 계획서"}


def tokens_css() -> str:
    """The P-PROTO light theme as CSS variables, read from planner/src/features/publicview/tokens.ts (no restyling)."""
    import re

    ts = (REPO / "planner/src/features/publicview/tokens.ts").read_text(encoding="utf-8")
    light = ts[ts.index("export const LIGHT"): ts.index("export const DARK")]
    get = lambda k: re.search(rf"\b{k}: '([^']+)'", light).group(1)  # noqa: E731
    tone = lambda t: re.search(rf"{t}: \{{ accent: '([^']+)'", light).group(1)  # noqa: E731
    banner = re.search(r"banner: \{ bg: '([^']+)', text: '([^']+)'", light)
    official = re.search(r"official: \{ bg: '([^']+)', text: '([^']+)'", light)
    size = dict(re.findall(r"(\w+): (\d+)", ts[ts.index("export const SIZE"):].split("}")[0]))
    v = {
        "--pv-bg": get("bg"), "--pv-text": get("text"), "--pv-muted": get("muted"),
        "--pv-banner-bg": banner.group(1), "--pv-banner-text": banner.group(2),
        "--pv-official-bg": official.group(1), "--pv-official-text": official.group(2),
        "--pv-leave": tone("leave"), "--pv-stop": tone("stop"), "--pv-unknown": tone("unknown"),
        "--pv-base": f"{size['base']}px", "--pv-words": f"{size['words']}px", "--pv-time": f"{size['time']}px",
        "--pv-age": f"{size['dataAge']}px", "--pv-stamp": f"{size['stamp']}px", "--pv-question": f"{size['question']}px",
    }
    return ":root{" + ";".join(f"{k}:{x}" for k, x in v.items()) + "}"


def num_of(case: str, channel: str) -> int:
    """A neutral handout number that does not reveal the case (fixed: from a hash of case and channel)."""
    return int(hashlib.sha256(f"{case}/{channel}".encode()).hexdigest(), 16) % 900 + 100


def code_of(case: str, channel: str) -> str:
    return f"자료-{num_of(case, channel)}"


def file_of(case: str, channel: str) -> str:
    return f"print/handouts/item-{num_of(case, channel)}.html"


FRAME = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{code}</title><style>
@page {{ size: A4; margin: 14mm; }}
body {{ margin: 0; font-family: Pretendard, "Noto Sans KR", system-ui, sans-serif; background: #fff; color: #111; }}
.code {{ font: 12px/1.4 ui-monospace, monospace; color: #555; margin: 0 0 6mm; }}
.phone {{ width: 390px; margin: 0 auto; border: 1px solid #bbb; border-radius: 28px; padding: 18px 0; min-height: 560px; }}
.sms {{ margin: 24px 16px; background: #e9e9eb; border-radius: 18px; padding: 14px 16px; font-size: 22px; line-height: 1.45; white-space: pre-wrap; }}
.staff {{ max-width: 720px; margin: 0 auto; }} .staff img {{ width: 100%; height: auto; border: 1px solid #ccc; }}
{extra}
</style></head><body><p class="code">{code}</p>
{body}
</body></html>
"""


def build(check: bool) -> dict[str, bytes]:
    cases_doc = json.loads((KIT / "CASES.json").read_text(encoding="utf-8"))
    cases = [c for c in cases_doc["cases"] if c.get("found")]
    css = (REPO / "planner/src/features/publicview/publicview.css").read_text(encoding="utf-8")
    out: dict[str, bytes] = {}
    key_rows = []
    for c in cases:
        d = KIT / "items" / c["case"]
        sms = (d / "sms.ko.txt").read_text(encoding="utf-8")
        page = (d / "page.ko.html").read_text(encoding="utf-8")
        code = code_of(c["case"], "sms")
        out[file_of(c["case"], "sms")] = FRAME.format(code=code, extra="", body=f'<div class="phone"><div class="sms">{html.escape(sms)}</div></div>').encode()
        key_rows.append((c["case"], "sms", code, file_of(c["case"], "sms")))
        code = code_of(c["case"], "card")
        out[file_of(c["case"], "card")] = FRAME.format(code=code, extra=tokens_css() + "\n" + css, body=f'<div class="phone"><div class="pv-root" lang="ko">{page}</div></div>').encode()
        key_rows.append((c["case"], "card", code, file_of(c["case"], "card")))
        code = code_of(c["case"], "headline")
        out[file_of(c["case"], "headline")] = FRAME.format(code=code, extra="", body=f'<div class="staff"><img src="../../items/{c["case"]}/headline.ko.png" alt=""></div>').encode()
        key_rows.append((c["case"], "headline", code, file_of(c["case"], "headline")))
        key_rows.append((c["case"], "a4", code_of(c["case"], "a4"), f"items/{c['case']}/a4.ko.pdf (print as is; write the code {code_of(c['case'], 'a4')} on the back)"))
        key_rows.append((c["case"], "broadcast", code_of(c["case"], "broadcast"), "print/RECORDING_SCRIPT.html → one audio file per code"))
    # recording script: the exact bytes of head.ko.txt, one per code, for the person who records them once
    parts = []
    for c in cases:
        code = code_of(c["case"], "broadcast")
        head = (KIT / "items" / c["case"] / "head.ko.txt").read_text(encoding="utf-8")
        s = c["head_seconds"]
        parts.append(f'<section><h2>{code}</h2><pre>{html.escape(head)}</pre><p class="meta">kit estimate: {s["full"]:.0f} s at the kit\'s normal rate, {s["full_slow"]:.0f} s at the slow rate. Save the recording as <b>{code}.m4a</b> (or .wav). Read the lines in order, once, with no added words.</p></section>')
    out["print/RECORDING_SCRIPT.html"] = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Recording script</title><style>
@page {{ size: A4; margin: 16mm; }} body {{ font-family: Pretendard, "Noto Sans KR", system-ui, sans-serif; }}
section {{ break-inside: avoid; border-top: 2px solid #111; padding-top: 6mm; margin-top: 8mm; }}
pre {{ font: 22px/1.6 Pretendard, "Noto Sans KR", system-ui, sans-serif; white-space: pre-wrap; }} .meta {{ font-size: 12px; color: #444; }}
</style></head><body><h1>마을 방송 녹음 원고 — 녹음하는 한 사람만 사용 (참가자에게 보여 주지 않음)</h1>
<p>Recording script for the one person who records the broadcasts. Each block is the kit's output, byte for byte. Record each once; every participant hears the same file. Not shown to participants.</p>
{''.join(parts)}</body></html>
""".encode()
    # Latin square over case x channel: participant p, round r, case at position i of the round
    sched = io.StringIO()
    w = csv.writer(sched, lineterminator="\n")
    w.writerow(["slot", "group", "seq", "case", "channel", "handout_code", "exposure"])
    res = io.StringIO()
    rw = csv.writer(res, lineterminator="\n")
    from score import COLUMNS  # one source for the column list (tools/score.py)

    rw.writerow(COLUMNS)
    blank = lambda **kw: [kw.get(c, "") for c in COLUMNS]  # noqa: E731
    ids = [c["case"] for c in cases]
    k = len(ids)
    for g, chs in CHANNELS.items():
        m = len(chs)
        for p in range(SLOTS[g]):
            slot = f"{g}{p + 1:02d}"
            seq = 0
            seen: set[str] = set()
            for r in range(m):
                order = [ids[(i + p + r) % k] for i in range(k)]
                for case in order:
                    ch = chs[(ids.index(case) + p + r) % m]
                    seq += 1
                    exp = "first" if case not in seen else "later"
                    seen.add(case)
                    w.writerow([slot, g, seq, case, ch, code_of(case, ch), exp])
                    rw.writerow(blank(participant=slot, group=g, seq=seq, case=case, channel=ch, exposure=exp))
            rw.writerow(blank(participant=slot, group=g, seq=seq + 1, case=ids[0], channel=chs[0], exposure="end", notes="Q4 asked again at the end"))
    out["SCHEDULE.csv"] = sched.getvalue().encode()
    out["results_template.csv"] = res.getvalue().encode()
    keys = io.StringIO()
    kw = csv.writer(keys, lineterminator="\n")
    kw.writerow(["case", "channel", "handout_code", "file"])
    for row in key_rows:
        kw.writerow(row)
    out["FACILITATOR_KEY.csv"] = keys.getvalue().encode()
    return out


def main() -> int:
    check = "--check" in sys.argv
    files = build(check)
    bad = []
    for rel, body in sorted(files.items()):
        p = KIT / rel
        if check:
            if not p.exists() or p.read_bytes() != body:
                bad.append(rel)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
    if bad:
        print("differs from a fresh build:\n" + "\n".join(bad), file=sys.stderr)
        return 1
    print(f"{'checked' if check else 'wrote'} {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
