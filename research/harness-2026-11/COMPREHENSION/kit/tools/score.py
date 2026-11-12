#!/usr/bin/env python3.12
"""Scores a filled results sheet (results_template.csv) against the PRE-STATED targets of PROTOCOL.md v2.3.

Every count was fixed by the protocol before any session; this script only applies it.
- Groups A and B are scored separately and never pooled.
- Every miss is listed verbatim with its case, channel, group and exposure order.
- No percentage is printed without its n/N.
- Either-coder rule: an answer is a miss when EITHER coder gives it a miss code. For group A's Q4, both coders must
  code OFFICIAL. Coder agreement is reported, never resolved silently.

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

OPEN_CODES = {"USABLE-LATER", "STAY", "SHELTER-MENTION", "TIME-INVENTED", "AMBIGUOUS-TIME", "OFFICIAL", "OFFICIAL-FOLLOW", "EMERGENCY-SERVICE", "NEUTRAL"}
Q4_CODES = {"OFFICIAL", "EMERGENCY-SERVICE", "NOT-STATED", "MODEL-AUTHORITY", "NEUTRAL"}
GROUPS = ("A", "B")
CHANNELS = {"A": ("broadcast", "sms", "card"), "B": ("headline", "a4")}
NO_CUT = {"a4"}  # v2.3: a full-page planning sheet is not a glance channel; seconds are reported with no cut
LATER = {"", "yes", "no", "not_stated"}
STAY_ANS = {"", "yes", "no", "unsure"}
COLUMNS = [
    "participant", "group", "age_band", "reads_phone_unaided", "seq", "case", "channel", "exposure", "repeat_used",
    "open_verbatim", "open_code_1", "open_code_2", "q1_time", "q1_seconds",
    "later_verbatim", "later_code_1", "later_code_2", "later_answer", "stay_answer",
    "q4_verbatim", "q4_code_1", "q4_code_2", "notes",
]
CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")
CUT_S = 30.0


class SheetError(Exception):
    pass


@dataclass
class Row:
    n: int
    d: dict[str, str]

    def __getitem__(self, k: str) -> str:
        return self.d[k].strip()

    def codes(self, prefix: str, allowed: set[str]) -> tuple[set[str], set[str]]:
        out = []
        for k in (f"{prefix}_code_1", f"{prefix}_code_2"):
            v = {c.strip().upper() for c in self[k].split(";") if c.strip()}
            bad = v - allowed
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


def validate(rows: list[Row], cases: dict[str, dict]) -> None:
    for r in rows:
        if r["group"] not in GROUPS:
            raise SheetError(f"row {r.n}: group must be A or B")
        if r["case"] not in cases:
            raise SheetError(f"row {r.n}: case {r['case']!r} is not a kit case ({sorted(cases)})")
        if r["channel"] not in CHANNELS[r["group"]]:
            raise SheetError(f"row {r.n}: channel {r['channel']!r} is not a group {r['group']} channel")
        if r["exposure"] not in ("first", "later", "end"):
            raise SheetError(f"row {r.n}: exposure must be first, later or end")
        if r["later_answer"].lower() not in LATER:
            raise SheetError(f"row {r.n}: later_answer must be yes, no, not_stated or empty")
        if r["stay_answer"].lower() not in STAY_ANS:
            raise SheetError(f"row {r.n}: stay_answer must be yes, no, unsure or empty")
        t = r["q1_time"].lower()
        if t and t not in ("none", "unsure") and norm_clock(t) is None:
            raise SheetError(f"row {r.n}: q1_time must be HH:MM, none, unsure or empty")
        if r["q1_seconds"]:
            try:
                float(r["q1_seconds"])
            except ValueError as e:
                raise SheetError(f"row {r.n}: q1_seconds is not a number") from e
        r.codes("open", OPEN_CODES)
        r.codes("later", OPEN_CODES)
        r.codes("q4", Q4_CODES)


def score(rows: list[Row], cases: dict[str, dict]) -> tuple[bool, str]:
    validate(rows, cases)
    leave = sorted(c for c, v in cases.items() if v.get("leave_by_kst"))
    no_time = {c for c, v in cases.items() if not v.get("leave_by_kst")}
    out: list[str] = ["# Comprehension pilot: scored results\n",
                      "Scored by tools/score.py against the targets fixed in PROTOCOL.md v2.3 before any session. Groups are never pooled. "
                      "A pass allows paused wording work to resume; it supports no statement about comprehension in public material.\n"]
    ok = True
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
        for c in leave:
            want = cases[c]["leave_by_kst"]
            first = [r for r in items if r["case"] == c and r["exposure"] == "first"]
            if len({r["participant"] for r in first}) != len(first):
                raise SheetError(f"group {g}: a participant has more than one first exposure of {c}")

            def miss(r: Row) -> str | None:
                t = norm_clock(r["q1_time"])
                sec = float(r["q1_seconds"]) if r["q1_seconds"] else None
                if t is None:
                    return {"none": "said no time is given", "unsure": "unsure of the time", "": "no time given"}.get(r["q1_time"].lower(), "no time given")
                if t != want:
                    return f"wrong time {t} (shown {want})"
                if r["channel"] in NO_CUT:
                    return None
                if sec is None:
                    return "correct time but no recorded seconds"
                return f"correct time after {sec:g} s (> {CUT_S:g} s)" if sec > CUT_S else None

            misses = [(r, m) for r in first if (m := miss(r))]
            allow = allowed_q1(len(first))
            met = len(misses) <= allow and len(first) == n
            ok &= met
            out.append(f"- **Q1 {c}** (first exposure, pooled over channels): {len(misses)} misses of {len(first)} (allowed ≤ {allow}) → **{'met' if met else 'NOT MET'}**"
                       + ("" if len(first) == n else f" — only {len(first)} of {n} participants have a first exposure of {c}"))
            for r, why in misses:
                out.append(f"  - MISS: {why} — {r.where()} — open answer: “{r['open_verbatim']}”")
            for ch in CHANNELS[g]:
                v = sorted(float(r["q1_seconds"]) for r in first if r["channel"] == ch and r["q1_seconds"])
                if v:
                    med = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
                    out.append(f"  - {ch}: first-exposure seconds median {med:g}, longest {v[-1]:g} (n = {len(v)}{'; no cut on this channel' if ch in NO_CUT else ''}; descriptive)")
            allx = [r for r in items if r["case"] == c]
            out.append(f"  - all exposures (descriptive, no target): {sum(1 for r in allx if miss(r))} misses of {len(allx)}")
        # ---- every exposure
        crit, q2m, q3m, ambiguous, findings = [], [], [], [], []
        agree = disagree = 0
        for r in items:
            o1, o2 = r.codes("open", OPEN_CODES)
            l1, l2 = r.codes("later", OPEN_CODES)
            for a, b in ((o1, o2), (l1, l2)):
                if a or b:
                    agree += a == b
                    disagree += a != b
            both = o1 | o2 | l1 | l2
            if r["case"] in no_time:
                if "TIME-INVENTED" in both:
                    crit.append((r, f"TIME-INVENTED (coder 1: {sorted(o1)}, coder 2: {sorted(o2)})"))
                if norm_clock(r["q1_time"]) is not None:
                    crit.append((r, f"gave {norm_clock(r['q1_time'])} as the time to leave where none is shown (closed time question)"))
                elif "AMBIGUOUS-TIME" in both:
                    ambiguous.append(r)
                if "STAY" in both:
                    q3m.append((r, f"STAY (coder 1: {sorted(o1)}, coder 2: {sorted(o2)})"))
                if r["stay_answer"].lower() == "yes":
                    q3m.append((r, "closed stay question answered yes"))
            if "USABLE-LATER" in both:
                q2m.append((r, f"USABLE-LATER (open: {sorted(o1)} / {sorted(o2)}; later: {sorted(l1)} / {sorted(l2)}) — later answer: “{r['later_verbatim']}”"))
            if r["case"] not in no_time and r["later_answer"].lower() == "yes":
                q2m.append((r, f"closed later-departure question answered yes — “{r['later_verbatim']}”"))
            for code in ("SHELTER-MENTION", "EMERGENCY-SERVICE", "OFFICIAL-FOLLOW"):
                if code in both:
                    findings.append((r, code))
        for name, lst, rule in (("Q1 critical (a time to leave given where none is shown)", crit, "0 allowed, any exposure"),
                                ("Q2 (a later time read as usable; C1 and C2)", q2m, "0 allowed, any exposure"),
                                ("Q3 (read as stay; C4 and C5)", q3m, "0 allowed, any exposure")):
            met = not lst
            ok &= met
            out.append(f"- **{name}**: {len(lst)} of {len(items)} exposures ({rule}) → **{'met' if met else 'NOT MET'}**")
            for r, why in lst:
                out.append(f"  - MISS: {why} — {r.where()} — “{r['open_verbatim']}”")
        out.append(f"- AMBIGUOUS-TIME open answers cleared by the closed time question (no time given there): {len(ambiguous)}")
        ns = sum(1 for r in items if r["later_answer"].lower() == "not_stated")
        un = sum(1 for r in items if r["stay_answer"].lower() == "unsure")
        out.append(f"- later-departure answered “not stated” (correct, reported): {ns}; stay answered “unsure” (not a miss, reported): {un}")
        if findings:
            out.append("- descriptive codes (no target; wording findings if they recur):")
            for r, code in findings:
                out.append(f"  - {code} — {r.where()} — “{r['open_verbatim']}”")
        # ---- Q4: each participant's first item
        firsts = []
        for p in people:
            pr = sorted((r for r in items if r["participant"] == p), key=lambda r: int(r["seq"]))
            if pr:
                firsts.append(pr[0])
        if g == "A":
            q4 = []
            for r in firsts:
                c1, c2 = r.codes("q4", Q4_CODES)
                if "OFFICIAL" not in c1 or "OFFICIAL" not in c2:
                    q4.append((r, f"not coded OFFICIAL by both coders (coder 1: {sorted(c1)}, coder 2: {sorted(c2)})"))
            allow = allowed_q4(n)
            met = len(q4) <= allow and len(firsts) == n
            ok &= met
            out.append(f"- **Q4 (official first; first item only)**: {len(q4)} misses of {len(firsts)} (allowed ≤ {allow}) → **{'met' if met else 'NOT MET'}**")
            for r, why in q4:
                out.append(f"  - MISS: {why} — {r.where()} — “{r['q4_verbatim']}”")
        else:
            out.append(f"- Q4 (first item; DESCRIPTIVE for group B, no target — the staff surfaces state no precedence): {len(firsts)} answers")
            for r in firsts:
                c1, c2 = r.codes("q4", Q4_CODES)
                flag = " ⚑ MODEL-AUTHORITY" if "MODEL-AUTHORITY" in c1 | c2 else ""
                out.append(f"  - coder 1 {sorted(c1)}, coder 2 {sorted(c2)}{flag} — {r.where()} — “{r['q4_verbatim']}”")
        end = [r for r in gr if r["exposure"] == "end"]
        endok = sum(1 for r in end if "OFFICIAL" in r.codes("q4", Q4_CODES)[0] and "OFFICIAL" in r.codes("q4", Q4_CODES)[1])
        out.append(f"- Q4 asked again at the end (secondary, no target): {endok} of {len(end)} coded OFFICIAL by both coders")
        out.append(f"- coder agreement on open and later answers: {agree} of {agree + disagree} identical code sets; {disagree} disagreements (in the sheet, not resolved here)")
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
