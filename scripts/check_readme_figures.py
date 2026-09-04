#!/usr/bin/env python
"""Gate — the README's opening figures must be the registry's, final only (WFG-049).

The first paragraph a judge reads states the scale of the March 2025 fire. It was
rewritten wrongly twice while every gate stayed green: once to 116,000 ha (larger than
the nationwide total) and once to 45,157 ha (a provincial tally from the day before
containment, presented as final). Neither rewrite touched a registered number, so no
gate could object. This one can:

* every FINAL figure the paragraph must state is read from ``docs/NUMBERS.json``
  (``fire2025_*`` keys, themselves re-derived from
  ``data/processed/external/fire_2025_scale.json`` by ``verify_numbers.py``) and must
  appear, formatted the way prose writes it, in BOTH the Korean and the English
  paragraph;
* no INTERIM or SECONDARY figure may appear in either paragraph unless the line also
  says it is interim (잠정 / interim / 재인용);
* the retired values (116,000 ha, 27 deaths, 영덕 8명) may not appear at all;
* every registered figure carries agency, as-of date, scope and a URL.

    python scripts/check_readme_figures.py             # gate, exit 1 on a defect
    python scripts/check_readme_figures.py --readme X  # test hook: check another file
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
NUMBERS = REPO / "docs" / "NUMBERS.json"

#: (registry key, how the prose writes it in each language). Two spellings are
#: accepted where Korean and English differ in separators.
REQUIRED = [
    ("fire2025_chain_area_ha", ["99,289 ha"]),
    ("fire2025_chain_hours_to_containment", ["149시간", "149 hours"]),
    ("fire2025_chain_deaths", ["26명", "26**", "killed **26"]),
    ("fire2025_chain_deaths_yeongdeok", ["영덕 10명", "10 of them in 영덕"]),
    ("fire2025_chain_homes_damaged", ["3,819동", "3,819 homes"]),
    ("fire2025_chain_displaced_households", ["2,246세대", "2,246 households"]),
    ("fire2025_chain_displaced_people", ["3,587명", "3,587\npeople", "3,587 people"]),
    ("fire2025_nationwide_area_ha", ["104,788 ha"]),
    ("fire2025_nationwide_fires", ["347건", "347 fires"]),
]
RETIRED = ["116,000", "27명", "27 deaths", "영덕 8명", "8 of them in 영덕", "4,000여 채", "다른 사건", "different event"]
INTERIM_MARKERS = ("잠정", "interim", "재인용", "provisional", "초기", "추정", "initial", "estimate", "중간 집계", "interim tally")

# the two paragraphs, located by their labels so the gate does not depend on line numbers
KO = (r"\*\*보호 대상\*\*", r"\*\*대회\*\*")
EN = (r"\*\*Motivating event\*\*", r"\*\*Target venue\*\*")


def paragraph(text: str, start: str, end: str) -> str | None:
    m = re.search(start + r"(.*?)" + end, text, flags=re.S)
    return m.group(1) if m else None


def fmt(v) -> str:
    return f"{int(v):,}" if float(v).is_integer() else str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme", default=str(README))
    args = ap.parse_args()
    text = Path(args.readme).read_text(encoding="utf-8")
    nums = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    fire = {k: e for k, e in nums.items() if k.startswith("fire2025_")}
    problems: list[str] = []

    ko, en = paragraph(text, *KO), paragraph(text, *EN)
    if ko is None:
        problems.append("the Korean opening paragraph (보호 대상 … 대회) was not found")
    if en is None:
        problems.append("the English opening paragraph (Motivating event … Target venue) was not found")

    # 1. provenance fields on every registered figure
    for k, e in fire.items():
        for field in ("agency", "as_of", "scope", "source_url", "figure_status"):
            if not e.get(field):
                problems.append(f"{k}: registry entry lacks {field}")

    for name, para in (("Korean", ko), ("English", en)):
        if para is None:
            continue
        flat = para.replace("\n", " ")
        # 2. every FINAL figure is present with the registry's value
        for key, spellings in REQUIRED:
            e = fire.get(key)
            if e is None:
                problems.append(f"{key} is not registered")
                continue
            if e.get("figure_status") != "final":
                problems.append(f"{key} is required in the README but its status is {e.get('figure_status')!r}, not final")
            literal = fmt(e["value"])
            ok = any(sp.replace("\n", " ") in flat for sp in spellings) and literal in flat
            if not ok:
                problems.append(f"{name} paragraph does not state {key} = {literal} ({' / '.join(spellings)})")
        # 3. interim / secondary figures may not pose as final
        for key, e in fire.items():
            if e.get("figure_status") in ("interim", "secondary"):
                lit = fmt(e["value"])
                # the qualifier may sit on the neighbouring line, so the window is the
                # flattened paragraph around each occurrence, not the line
                for m in re.finditer(rf"(?<![\d,]){re.escape(lit)}(?![\d,])", flat):
                    window = flat[max(0, m.start() - 160): m.end() + 220]
                    if not any(mk in window for mk in INTERIM_MARKERS):
                        problems.append(f"{name} paragraph states the {e['figure_status']} figure {lit} ({key}) without marking it {e['figure_status']}")
        # 4. retired values are gone
        for tok in RETIRED:
            if tok in flat:
                problems.append(f"{name} paragraph still carries the retired value/phrase {tok!r}")

    if problems:
        print("README OPENING FIGURES — defects:")
        for p in problems:
            print(f"  - {p}")
        print("The paragraph is bound to docs/NUMBERS.json fire2025_* keys; fix the registry "
              "(scripts/register_fire2025_figures.py from the artifact) or the prose, never by "
              "typing a number that has no key.")
        return 1
    print(f"OK — both opening paragraphs state the {len(REQUIRED)} registered final figures, "
          f"no interim tally poses as final, {len(fire)} fire2025 keys carry agency/date/scope/URL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
