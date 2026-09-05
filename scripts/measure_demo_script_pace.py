#!/usr/bin/env python
"""Measure the spoken length of the booth script, in syllables, per segment (WFG-100).

``docs/auto/DEMO_SCRIPT_5MIN.md`` §1 divides five minutes into six segments. Until this
script existed the six numbers came from 「문장 수와 한국어 발화 속도」 with nobody having
done the arithmetic, and critic #16 showed the six cannot all be right: measured over the
spoken lines they implied 4.24 to 7.07 syllables per second, a 1.67x spread inside one
document from one stated method, with the *fastest* segment being the limitations close.
This module's own convention (below) reads Latin and symbols aloud where the critic's did
not, so it puts the same six at 4.51 to 7.29, a 1.62x spread: the two conventions find the
same defect and differ only in its third decimal. Do not mix the two sets of figures.

What this measures: the number of Korean syllables a student actually pronounces in each
segment, and the seconds those syllables get. What it does NOT measure is whether the
resulting rate is comfortable to say - that is a stopwatch and a human (R12 / NH-014), and
``docs/demo_script_pace.md`` says so. The re-budget this feeds is an *internal consistency*
fix: one rate across six segments instead of six different ones.

Counting rules, so the count is a definition anyone can re-run rather than a judgement:

* Only ``> `` blockquote lines inside §1 count. The ⚠ blocks are prose *about* the script,
  the §3 mapping table is a reference, the DRAFT header is not spoken.
* The ``[버림]`` marker itself is not spoken; the sentence carrying it is, so it counts.
* Each Hangul syllable block (U+AC00..U+D7A3) is one syllable.
* Digits are read sino-Korean and counted as the syllables of that reading: ``2,008`` is
  이천팔 (3), ``0.1939`` is 영점일구삼구 (6).
* Every other non-space token must be in ``LEXICON`` with its spoken Korean. An unknown
  token is a hard error, never a silent zero - a tokenizer that scores what it does not
  recognise as nothing under-counts exactly the segments densest in symbols.

``--variant hangul-only`` re-runs with the ``LEXICON`` readings scored as zero. It exists
to size the judgement in the count: if the second budget barely moves between the two
variants, the re-budget does not rest on how ``%`` is pronounced. See the doc.

    python scripts/measure_demo_script_pace.py --stamp 20260905T0625Z   # write the artifact
    python scripts/measure_demo_script_pace.py --print                  # table on stdout
    python scripts/measure_demo_script_pace.py --check                  # artifact still current?
    python scripts/measure_demo_script_pace.py --register               # upsert registry keys

No clock, no timezone, no network, no file outside the repository (CHARTER §4b): the stamp
is passed in, never read from the machine.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "docs" / "auto" / "DEMO_SCRIPT_5MIN.md"
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT_DIR = REPO / "data" / "processed" / "demo_script_pace"
TOTAL_SECONDS = 300

DIGITS = "영일이삼사오육칠팔구"
UNITS = ["", "십", "백", "천"]

# Every non-Hangul, non-digit token the spoken lines contain, with what the student says.
# Longest first: the matcher is greedy so "TIME-AWARE VIEW" wins over "VIEW".
LEXICON: list[tuple[str, str]] = [
    ("TIME-AWARE VIEW", "타임어웨어뷰"),
    ("STATIC VIEW", "스태틱뷰"),
    ("pooled", "풀드"),
    ("OSM", "오에스엠"),
    ("km", "킬로미터"),
    ("ha", "헥타르"),
    ("%", "퍼센트"),
    ("≥", "이상"),
    ("K", "켈빈"),
    ("W", "더블유"),
]

# Markup and punctuation nobody pronounces. Stripped before the unknown-token check.
SILENT = "**「」*·—–-,.…?!:;()[]/'\"`~“”‘’ \t"
HANGUL = re.compile(r"[가-힣]")
HEADER = re.compile(r"^### (.+?) \((\d):(\d\d) → (\d):(\d\d)\) · (\d+)초")


class UnknownToken(ValueError):
    """A spoken character with no reading. Never scored as zero (see the docstring)."""


def sino_korean(token: str) -> str:
    """Read a numeral the way a Korean speaker says it, for counting only."""
    token = token.replace(",", "")
    whole, _, frac = token.partition(".")
    out = _read_integer(int(whole))
    if frac:
        out += "점" + "".join(DIGITS[int(d)] for d in frac)
    return out


def _read_integer(n: int) -> str:
    if n == 0:
        return DIGITS[0]
    if n >= 10_000:
        return _read_integer(n // 10_000) + "만" + (_read_integer(n % 10_000) if n % 10_000 else "")
    out = ""
    for power, digit in enumerate(reversed(str(n))):
        d = int(digit)
        if d == 0:
            continue
        # 일십 / 일백 / 일천 are said 십 / 백 / 천
        out = (("" if d == 1 and power else DIGITS[d]) + UNITS[power]) + out
    return out


def spoken_segments(text: str) -> list[dict]:
    """§1's six segments, each with its declared seconds and its spoken lines."""
    body = text.split("## 1. 대본", 1)[1].split("## 2. 끼어들 때", 1)[0]
    segments: list[dict] = []
    for line in body.splitlines():
        m = HEADER.match(line)
        if m:
            name, m0, s0, m1, s1, secs = m.groups()
            segments.append({
                "name": name.split(" · ")[0].strip(),
                "heading": name.strip(),
                "start_s": int(m0) * 60 + int(s0),
                "end_s": int(m1) * 60 + int(s1),
                "seconds": int(secs),
                "lines": [],
            })
        elif line.startswith("> ") and segments:
            segments[-1]["lines"].append(line[2:])
    return segments


def count_syllables(lines: list[str], *, lexicon: bool = True) -> int:
    """Syllables a student pronounces, by the rules in this module's docstring."""
    total = 0
    for line in lines:
        text = line.replace("[버림]", " ")
        for word in ["**", "「", "」"]:
            text = text.replace(word, " ")
        # numerals first: they may sit against Hangul (240분) or a unit (0.1939 ha)
        text = re.sub(r"\d[\d,]*(?:\.\d+)?", lambda m: sino_korean(m.group()), text)
        for token, reading in LEXICON:
            text = text.replace(token, reading if lexicon else " ")
        total += len(HANGUL.findall(text))
        leftover = "".join(ch for ch in HANGUL.sub(" ", text) if ch not in SILENT)
        if leftover:
            raise UnknownToken(
                f"no reading for {leftover!r} in {line!r}. Add it to LEXICON with what the "
                "student says, or this segment is being under-counted."
            )
    return total


def measure(text: str, *, lexicon: bool = True) -> dict:
    segments = spoken_segments(text)
    if len(segments) != 6:
        raise ValueError(f"§1 no longer holds six timed segments; parsed {len(segments)}")
    rows = []
    for seg in segments:
        syl = count_syllables(seg["lines"], lexicon=lexicon)
        rows.append({
            "name": seg["name"],
            "declared_seconds": seg["seconds"],
            "spoken_syllables": syl,
            "implied_syllables_per_second": round(syl / seg["seconds"], 2),
        })
    total_syl = sum(r["spoken_syllables"] for r in rows)
    declared = sum(r["declared_seconds"] for r in rows)
    for row in rows:
        row["proportional_seconds"] = row["spoken_syllables"] / total_syl * TOTAL_SECONDS
    return {
        "segments": rows,
        "total_spoken_syllables": total_syl,
        "declared_total_seconds": declared,
        "syllables_per_second": round(total_syl / TOTAL_SECONDS, 2),
        "implied_rate_spread": round(
            max(r["implied_syllables_per_second"] for r in rows)
            / min(r["implied_syllables_per_second"] for r in rows), 2),
    }


def allocate(syllables: list[int], total_seconds: int = TOTAL_SECONDS) -> list[int]:
    """Whole seconds proportional to syllables, summing to exactly total_seconds.

    Largest-remainder, so no segment is silently rounded out of its share and the six
    numbers still add to five minutes without a fudge on the last one.
    """
    total = sum(syllables)
    exact = [s / total * total_seconds for s in syllables]
    floors = [int(x) for x in exact]
    remaining = total_seconds - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: (exact[i] - floors[i], syllables[i]), reverse=True)
    for i in order[:remaining]:
        floors[i] += 1
    return floors


def registry_entries(art: dict, artifact_path: str, head: str, config_hash: str) -> dict:
    common = {
        "source_file": artifact_path,
        "config_hash": config_hash,
        "config_hash_at_production": None,
        "git_commit": head,
        "sample": "docs/auto/DEMO_SCRIPT_5MIN.md §1, the six segments' > blockquote lines",
        "reproducible": True,
        "reproducibility": {
            "status": "reproducible",
            "evidence": "python scripts/measure_demo_script_pace.py --stamp <UTC> re-derives "
                        "the artifact from the committed document",
            "blocked_by": None,
        },
        "provenance": "derived",
        "arm": "booth_pace",
        "forbidden_phrasings": [
            "comfortable speaking rate",
            "편안한 발화 속도",
            "리허설을 대신",
        ],
        "notes": "WFG-100. Bound to the document by tests/test_demo_script_pace.py; editing a "
                 "spoken line changes these values and the gate goes red until the artifact is "
                 "re-measured under a new filename (CHARTER §3.2).",
    }
    caveat = (
        "A COUNT OF SYLLABLES, NOT A MEASUREMENT OF SPEECH. This is how many syllables the "
        "script asks the student to pronounce divided by the seconds it gives them; it does "
        "not say that rate is sayable, and no rehearsal has been run (R12 / NH-014). The "
        "count's rules are in scripts/measure_demo_script_pace.py: Hangul syllable blocks, "
        "numerals read sino-Korean, symbols and Latin read from an explicit lexicon."
    )
    return {
        "demo_pace_total_spoken_syllables": {
            **common, "value": art["total_spoken_syllables"], "unit": "syllables",
            "json_path": "total_spoken_syllables",
            "derivation": "sum of the six segments' spoken_syllables",
            "caveat": caveat,
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": artifact_path, "json_path": "total_spoken_syllables"}}},
        },
        "demo_pace_syllables_per_second": {
            **common, "value": art["syllables_per_second"], "unit": "syllables/s",
            "json_path": "syllables_per_second",
            "derivation": f"round({art['total_spoken_syllables']} / {TOTAL_SECONDS}, 2)",
            "caveat": caveat,
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": artifact_path, "json_path": "syllables_per_second"}}},
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", help="UTC stamp for the new artifact filename, e.g. 20260905T0625Z")
    ap.add_argument("--print", action="store_true", dest="show")
    ap.add_argument("--check", action="store_true", help="exit 1 if no artifact matches the document")
    ap.add_argument("--register", action="store_true", help="upsert the demo_pace_ registry keys")
    ap.add_argument("--variant", choices=["full", "hangul-only"], default="full")
    args = ap.parse_args()

    text = SCRIPT.read_text(encoding="utf-8")
    art = measure(text, lexicon=args.variant == "full")

    if args.show:
        print(f"{'segment':<34}{'syl':>6}{'declared':>10}{'syl/s':>8}{'proportional':>14}")
        for r in art["segments"]:
            print(f"{r['name']:<30}{r['spoken_syllables']:>6}{r['declared_seconds']:>10}"
                  f"{r['implied_syllables_per_second']:>8}{r['proportional_seconds']:>14.1f}")
        alloc = allocate([r["spoken_syllables"] for r in art["segments"]])
        print(f"total {art['total_spoken_syllables']} syllables / {TOTAL_SECONDS} s = "
              f"{art['syllables_per_second']} syl/s; spread {art['implied_rate_spread']}x; "
              f"allocation {alloc} (sum {sum(alloc)})")

    current = sorted(ARTIFACT_DIR.glob("pace_*.json"))
    if args.check:
        if not current:
            print("no pace artifact committed")
            return 1
        live = json.loads(current[-1].read_text(encoding="utf-8"))
        stale = {k: (live.get(k), art[k]) for k in ("total_spoken_syllables", "syllables_per_second")
                 if live.get(k) != art[k]}
        if stale:
            print(f"STALE {current[-1].name}: the document moved since it was measured: {stale}")
            return 1
        print(f"OK - {current[-1].name} matches the document ({art['total_spoken_syllables']} syllables)")
        return 0

    if args.stamp:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        out = ARTIFACT_DIR / f"pace_{args.stamp}.json"
        if out.exists():
            print(f"refusing to overwrite {out.name} (CHARTER §3.2); pass a new --stamp")
            return 1
        payload = dict(art)
        payload["measured_from"] = "docs/auto/DEMO_SCRIPT_5MIN.md"
        payload["variant"] = args.variant
        payload["method"] = ("Hangul syllable blocks in §1's > lines; numerals read sino-Korean; "
                             "symbols and Latin read from scripts/measure_demo_script_pace.py "
                             "LEXICON; [버림] markers, ⚠ blocks and the §3 table excluded.")
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {out.relative_to(REPO)}")
        current = sorted(ARTIFACT_DIR.glob("pace_*.json"))

    if args.register:
        if not current:
            print("nothing to register: no pace artifact")
            return 1
        artifact_path = str(current[-1].relative_to(REPO))
        doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
        live = json.loads(current[-1].read_text(encoding="utf-8"))
        new = registry_entries(live, artifact_path, head, doc["config_hash"])
        cur = doc["numbers"]
        for k, e in new.items():
            if k in cur:
                e["git_commit"] = cur[k].get("git_commit", head)
            cur[k] = e
        NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"upserted {len(new)} demo_pace entries from {artifact_path}; "
              f"registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
