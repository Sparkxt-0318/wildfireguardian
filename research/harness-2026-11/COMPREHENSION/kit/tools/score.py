#!/usr/bin/env python3.12
"""Scores a filled results sheet (results_template.csv) against the PRE-STATED targets of PROTOCOL.md v2.2.

Every count is fixed by the protocol before any session; this script only applies it. Groups A and B are scored
separately and never pooled. Every miss is listed verbatim with its case, channel, group and exposure order. No
percentage is printed without its n/N.

Conservative coding rule of this kit (stated before any session): an open answer counts as a miss when EITHER coder
gives it a miss code; the coders' agreement is reported beside it, never resolved silently.

    python3.12 score.py results.csv [--cases ../CASES.json] [--out RESULTS.md]

Exit code: 0 = every target met, 1 = a target missed or a critical miss, 2 = the sheet is malformed.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CODES = {"USABLE-LATER", "STAY", "TIME-INVENTED", "OFFICIAL", "NEUTRAL"}
GROUPS = ("A", "B")
CHANNELS = {"A": ("broadcast", "sms", "card"), "B": ("headline", "a4")}
YES_NO = {"", "yes", "no", "unsure"}
COLUMNS = [
    "participant", "group", "age_band", "reads_phone_unaided", "seq", "case", "channel", "exposure", "repeat_used",
    "open_verbatim", "open_code_1", "open_code_2", "q1_time", "q1_seconds", "q2_answer", "q3_answer",
    "q4_verbatim", "q4_code_1", "q4_code_2", "notes",
]
CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")


class SheetError(Exception):
    pass


@dataclass
class Row:
    n: int
    d: dict[str, str]

    def __getitem__(self, k: str) -> str:
        return self.d[k].strip()

    def codes(self, prefix: str) -> tuple[set[str], set[str]]:
        out = []
        for k in (f"{prefix}_code_1", f"{prefix}_code_2"):
            v = {c.strip().upper() for c in self[k].split(";") if c.strip()}
            bad = v - CODES
            if bad:
                raise SheetError(f"row {self.n}: unknown code(s) {sorted(bad)} in {k}")
            out.append(v)
        return out[0], out[1]

    def where(self) -> str:
        return f"participant {self['participant']} · group {self['group']} · case {self['case']} · channel {self['channel']} · exposure {self['exposure']} (item {self['seq']})"


def allowed_q1(n: int) -> int:
    return (2 * n) // 10  # floor(0.2 N)


def allowed_q4(n: int) -> int:
    return n // 10  # floor(0.1 N)


def norm_clock(s: str) -> str | None:
    m = CLOCK.match(s.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def load(path: Path) -> list[Row]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (r.fieldnames or [])]
        if missing:
            raise SheetError(f"missing columns: {missing}")
        rows = [Row(i + 2, d) for i, d in enumerate(r)]
    return [x for x in rows if any(v.strip() for v in x.d.values())]


def score(rows: list[Row], cases: dict[str, dict]) -> tuple[bool, str]:
    leave = {c for c, v in cases.items() if v.get("leave_by_kst")}
    gap = {c for c, v in cases.items() if v.get("q2_case")}
    no_time = {c for c, v in cases.items() if not v.get("leave_by_kst")}
    out: list[str] = []
    ok = True
    for r in rows:
        if r["group"] not in GROUPS:
            raise SheetError(f"row {r.n}: group must be A or B")
        if r["case"] not in cases:
            raise SheetError(f"row {r.n}: case {r['case']!r} is not a kit case ({sorted(cases)})")
        if r["channel"] not in CHANNELS[r["group"]]:
            raise SheetError(f"row {r.n}: channel {r['channel']!r} is not a group {r['group']} channel")
        if r["exposure"] not in ("first", "later", "end"):
            raise SheetError(f"row {r.n}: exposure must be first, later or end")
        for k in ("q2_answer", "q3_answer"):
            if r[k].lower() not in YES_NO:
                raise SheetError(f"row {r.n}: {k} must be yes, no, unsure or empty")
        r.codes("open")
        r.codes("q4")
    out.append("# Comprehension pilot — scored results\n")
    out.append("Scored by tools/score.py against the targets fixed in PROTOCOL.md v2.2 before any session. Groups are never pooled. "
               "A pass allows paused wording work to resume; it supports no statement about comprehension in public material.\n")
    for g in GROUPS:
        gr = [r for r in rows if r["group"] == g]
        people = sorted({r["participant"] for r in gr})
        n = len(people)
        out.append(f"\n## Group {g} (N = {n})\n")
        if n == 0:
            out.append("No participants.\n")
            continue
        items = [r for r in gr if r["exposure"] != "end"]
        # ---- Q1: first exposure per leave-by case, pooled over channels
        for c in sorted(leave):
            want = cases[c]["leave_by_kst"]
            first = [r for r in items if r["case"] == c and r["exposure"] == "first"]
            if len({r["participant"] for r in first}) != len(first):
                raise SheetError(f"group {g}: a participant has more than one first exposure of {c}")
            misses = []
            secs = []
            for r in first:
                t = norm_clock(r["q1_time"])
                s = r["q1_seconds"]
                sec = float(s) if s else None
                if sec is not None:
                    secs.append((r["channel"], sec))
                if t is None:
                    misses.append((r, "no time given" if not r["q1_time"] else f"not a clock time: {r['q1_time']!r}"))
                elif t != want:
                    misses.append((r, f"wrong time {t} (shown {want})"))
                elif sec is None or sec > 30:
                    misses.append((r, "correct time but no recorded seconds" if sec is None else f"correct time after {sec:g} s (> 30 s)"))
            allow = allowed_q1(len(first))
            met = len(misses) <= allow and len(first) == n
            ok &= met
            out.append(f"- **Q1 {c}** (first exposure, pooled over channels): {len(misses)} misses of {len(first)} (allowed ≤ {allow}) → **{'met' if met else 'NOT MET'}**"
                       + ("" if len(first) == n else f" — only {len(first)} of {n} participants have a first exposure of {c}"))
            for r, why in misses:
                out.append(f"  - MISS: {why} — {r.where()} — open answer: “{r['open_verbatim']}”")
            for ch in CHANNELS[g]:
                v = sorted(x for k, x in secs if k == ch)
                if v:
                    med = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
                    out.append(f"  - {ch}: first-exposure seconds median {med:g}, longest {v[-1]:g} (n = {len(v)}; descriptive, no target)")
            allx = [r for r in items if r["case"] == c]
            allmiss = sum(1 for r in allx if norm_clock(r["q1_time"]) != want or not r["q1_seconds"] or float(r["q1_seconds"]) > 30)
            out.append(f"  - all exposures (descriptive, no target): {allmiss} misses of {len(allx)}")
        # ---- open-answer codes over every exposure
        crit, q2m, q3m = [], [], []
        agree = disagree = 0
        for r in items:
            c1, c2 = r.codes("open")
            agree += c1 == c2
            disagree += c1 != c2
            both = c1 | c2
            if r["case"] in no_time and "TIME-INVENTED" in both:
                crit.append((r, f"TIME-INVENTED (coder 1: {sorted(c1)}, coder 2: {sorted(c2)})"))
            if "USABLE-LATER" in both:
                q2m.append((r, f"USABLE-LATER (coder 1: {sorted(c1)}, coder 2: {sorted(c2)})"))
            if r["case"] in gap and r["q2_answer"].lower() == "yes":
                q2m.append((r, "closed Q2 answered yes"))
            if r["case"] in no_time and "STAY" in both:
                q3m.append((r, f"STAY (coder 1: {sorted(c1)}, coder 2: {sorted(c2)})"))
            if r["case"] in no_time and r["q3_answer"].lower() == "yes":
                q3m.append((r, "closed Q3 answered yes (safe to stay)"))
        for name, lst, rule in (("Q1 critical (time invented where none is shown)", crit, "0 allowed"),
                                ("Q2 (a later or next time read as usable)", q2m, "0 allowed, any exposure"),
                                ("Q3 (read as safe or as stay)", q3m, "0 allowed, any exposure")):
            met = not lst
            ok &= met
            out.append(f"- **{name}**: {len(lst)} of {len(items)} exposures ({rule}) → **{'met' if met else 'NOT MET'}**")
            for r, why in lst:
                out.append(f"  - MISS: {why} — {r.where()} — “{r['open_verbatim']}”")
        unsure = sum(1 for r in items if r["q2_answer"].lower() == "unsure" or r["q3_answer"].lower() == "unsure")
        out.append(f"- closed Q2/Q3 answered “unsure” (not a miss; reported): {unsure}")
        # ---- Q4: each participant's first item
        q4 = []
        firsts = []
        for p in people:
            pr = sorted((r for r in items if r["participant"] == p), key=lambda r: int(r["seq"]))
            if not pr:
                continue
            r = pr[0]
            firsts.append(r)
            c1, c2 = r.codes("q4")
            if "OFFICIAL" not in c1 or "OFFICIAL" not in c2:
                q4.append((r, f"not coded OFFICIAL by both coders (coder 1: {sorted(c1)}, coder 2: {sorted(c2)})"))
        allow = allowed_q4(n)
        met = len(q4) <= allow and len(firsts) == n
        ok &= met
        out.append(f"- **Q4 (official first; first item only)**: {len(q4)} misses of {len(firsts)} (allowed ≤ {allow}) → **{'met' if met else 'NOT MET'}**")
        for r, why in q4:
            out.append(f"  - MISS: {why} — {r.where()} — “{r['q4_verbatim']}”")
        end = [r for r in gr if r["exposure"] == "end"]
        endok = sum(1 for r in end if {"OFFICIAL"} <= (r.codes("q4")[0] & r.codes("q4")[1]))
        out.append(f"- Q4 asked again at the end (secondary, no target): {endok} of {len(end)} coded OFFICIAL by both coders")
        out.append(f"- coder agreement on open answers: {agree} of {agree + disagree} identical code sets; {disagree} disagreements (listed in the sheet, not resolved here)")
    out.append(f"\n## Decision\n\n{'All targets met: the paused wording work may resume, scoped by these results. No public statement about comprehension is made.' if ok else 'A target was missed or a critical miss occurred: the failing wording is revised first, with Iris and Sofia, and re-tested on new participants before any new wording is added.'}\n")
    return ok, "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--cases", default=str(Path(__file__).resolve().parent.parent / "CASES.json"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    doc = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    cases = {c["case"]: c for c in doc["cases"] if c.get("found")}
    try:
        ok, text = score(load(Path(a.results)), cases)
    except SheetError as e:
        print(f"malformed results sheet: {e}", file=sys.stderr)
        return 2
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
