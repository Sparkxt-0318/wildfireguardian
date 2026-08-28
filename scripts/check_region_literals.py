#!/usr/bin/env python
"""One region's values, typed into a string every region will read.

Round-3 PHASE 22 STEP 4.

WHY THIS EXISTS
---------------
The same defect was found three times in three days, in three different files,
and every instance had the same shape:

1. ``build_operator_screen.py`` — the legend read
   ``보행망 범위 (커버리지 32.6%)`` from static markup while the footer read the
   per-region value. The 의성·안동 DEMONSTRATION screen showed **32.6 % and
   99.2 % at the same time**.
2. ``build_console.py`` — ``"coverage_pct": 32.6`` in the payload builder,
   correct for Yeongdeok and about to be wrong for two more regions the moment
   the console could switch.
3. ``live/scope.py`` — ``COVERAGE_CAVEAT_KO`` named 영덕 and 32.6 % and went out
   on **273** A4 dispatch sheets belonging to the other two regions, neither of
   which carried its own coverage figure anywhere.
4. (Round-4, 2026-08-10) ``live/pipeline.py write_viz`` — TWO more, in
   ARTIFACTS rather than on screens: ``origins_note`` carried Yeongdeok's
   44/458 into every region's viz.json in an ENGLISH sentence the
   Korean-gated numeric branch could not see (the gate is dropped for the
   numeric branch because of it), and ``phrasing_rule`` wrote
   Uiseong-Andong's measured depot facts into every region's record, beside
   a status_ko saying the opposite (guarded by a write_viz test, since it
   carries no digit this scanner could hold on to).

⚠ **Every one of them was correct on Yeongdeok.** That is what made all three
survive review: the author checks the screen they are looking at, and the screen
they are looking at is the one the literal happens to match. A defect that is
invisible from the default region needs a check that does not start there.

WHAT IT LOOKS FOR
-----------------
A **user-visible string** that hard-codes something which differs per region:

* a Korean region label — 영덕 / 의성 / 안동 / 울진 / 삼척;
* a per-region measurement — the coverage figures, the walk-bbox areas, the
  origin and shelter counts, the weather basis timestamps.

⚠ **IT IS NOT COMPLETE AND DOES NOT TRY TO BE.** It catches the shape those
three had: a literal beside a Korean label, or inside a string that is written
to a screen. A value assembled at a distance from its label will slip past it.
The bar it was built to clear is "would this have caught the three", and it is
demonstrated to fail on each of them by
``tests/test_screen_checks.py::test_the_region_literal_check_catches_all_three``.

WHAT IT DELIBERATELY PERMITS
----------------------------
* **Documentation and comments.** A docstring saying "Coverage 32.6 %, and the
  dashed walk bbox" is describing Yeongdeok on purpose.
* **Per-region tables.** ``COVERAGE_PCT = {"yeongdeok_2025": 32.6, …}`` is the
  fix, not the defect, so a literal on a line that also carries a region *key*
  is allowed.
* **Anything outside the builders and the operator-facing layer.** Analysis
  scripts quote Yeongdeok figures constantly and correctly.

Run:
    python scripts/check_region_literals.py
    python scripts/check_region_literals.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: The files that BUILD or EMIT operator-facing text. The check is scoped to
#: these because a literal only becomes this defect when a second region reads
#: it; analysis scripts that quote Yeongdeok are doing so deliberately.
SCOPE: tuple[str, ...] = (
    # ⚠ The finals screen is in scope for the same reason the console is: it is
    # a builder that emits operator-facing text and reads all three regions from
    # one payload, which is exactly the shape this check exists to catch. Added
    # with the file, not after the first defect.
    "scripts/build_finals.py",
    "scripts/finals.template.html",
    "scripts/build_console.py",
    "scripts/build_operator_screen.py",
    "scripts/console.template.html",
    "src/wildfireguardian/live/scope.py",
    "src/wildfireguardian/live/pipeline.py",
    "src/wildfireguardian/delivery/printable.py",
    "src/wildfireguardian/delivery/email.py",
    "src/wildfireguardian/delivery/sms.py",
    "src/wildfireguardian/delivery/broadcast.py",
)

#: Korean region labels. A screen string naming one of these is claiming to be
#: about that region, so it must not be built for another.
REGION_WORDS: tuple[str, ...] = ("영덕", "의성", "안동", "울진", "삼척")

#: Values that differ per region and have a committed per-region source.
#: `docs/console_regions.md` §5 is the table; the sources are
#: `multi_region_comparison.json` and `osm_completeness.json`.
PER_REGION_NUMBERS: dict[str, str] = {
    r"\b32\.6\b": "Yeongdeok's walk-bbox coverage (99.2 / 81.5 elsewhere)",
    r"\b99\.2\b": "Uiseong-Andong's walk-bbox coverage",
    r"\b81\.5\b": "Uljin-Samcheok's walk-bbox coverage",
    r"\b919\b": "Uiseong-Andong's walk bbox area (931 / 924 elsewhere)",
    r"\b3,?926\b": "Uiseong-Andong's manifest bbox area",
    r"\b458\b": "Yeongdeok's origin count (368 / 393 elsewhere)",
    r"2025-03-25 12:25": "Yeongdeok's weather basis",
    r"2025-03-22 05:39": "Uiseong-Andong's weather basis",
    r"2022-03-04 05:26": "Uljin-Samcheok's weather basis",
}

#: A line that also names a region KEY is a per-region table entry, which is the
#: correct pattern rather than the defect.
_REGION_KEY = re.compile(r"(yeongdeok_2025|uiseong_andong_2025|uljin_samcheok_2022)")

#: A line that reads the value instead of stating it.

#: Is this line user-visible text at all? Either a Korean string literal, or a
#: line that writes to the DOM / builds operator wording.
_KOREAN = re.compile(r"[가-힣]")
_STRING = re.compile(r"""['"]""")

_PY_COMMENT = re.compile(r"^\s*(#|\"\"\"|'''|\*|:)")
_JS_COMMENT = re.compile(r"^\s*(//|/\*|\*)")


@dataclass
class Finding:
    path: str
    line: int
    what: str
    excerpt: str

    def as_dict(self) -> dict:
        return {"path": self.path, "line": self.line, "what": self.what,
                "excerpt": self.excerpt}


#: ⚠ THE RATCHET, AND EVERY ENTRY NEEDS A REASON.
#: Same idea as ``KNOWN_DASHES`` in the screen gate: the floor is where the tree
#: is today, and it may only go down. An entry here is a literal that has been
#: LOOKED AT and found harmless on its current reach — not one that was noisy.
KNOWN_REGION_LITERALS: dict[str, int] = {
    # The <svg> element's initial aria-label. `renderFacts()` overwrites it with
    # `${D.label_kr}` on every mount, including the first, so what a screen
    # reader announces is always the mounted region. The literal is only ever
    # the value between parse and first paint. Recorded in
    # docs/console_regions.md §10 rather than fixed, on the same call as
    # build_console.py's `차고지 0곳` stdout literal.
    "scripts/console.template.html": 1,
    # `weather_basis: str  # e.g. "2025-03-25 12:25 UTC"` — a dataclass field
    # whose TRAILING COMMENT gives Yeongdeok's timestamp as an example. The
    # value itself is always derived (pipeline.weather_basis re-clusters the
    # detections CSV; a test asserts the literal date is absent from that
    # function). The widened numeric branch (no Korean gate, Round-4 A3-2)
    # sees the quotes inside the comment; the comment-skip only covers lines
    # that START with #. Looked at, harmless: an example label on a field
    # that cannot drift, not a value any region reads.
    "src/wildfireguardian/live/scope.py": 1,
}


def _is_comment(line: str, suffix: str) -> bool:
    return bool(_JS_COMMENT.match(line) if suffix in (".html", ".js")
                else _PY_COMMENT.match(line))


def check_text(text: str, path: str, *, suffix: str) -> list[Finding]:
    """Region literals in user-visible strings, one file."""
    out: list[Finding] = []
    in_docstring = False
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        # ⚠ Docstring CONTINUATION lines are prose, and the first version of
        # this checker flagged its own explanation of the defect. Track the
        # fences rather than only matching an opening line.
        if suffix == ".py":
            fences = line.count('"""') + line.count("'''")
            if in_docstring:
                if fences:
                    in_docstring = False
                continue
            if fences == 1:
                in_docstring = True
                continue
        if not line.strip() or _is_comment(line, suffix):
            continue
        # Only strings a person could read. A bare number in arithmetic is not
        # this defect; a number inside a sentence is.
        # ⚠ The Korean gate applies to the REGION-NAME branch only. The first
        # version required Korean for the numeric branch too, and that is how
        # Yeongdeok's 44/458 sat inside an ENGLISH note string in
        # live/pipeline.py's write_viz — shipped in every region's viz.json —
        # while this checker looked straight past it (Round-4 A3-2). A
        # per-region number inside ANY string literal in these files is the
        # defect, whatever language the sentence around it speaks.
        if not _STRING.search(line):
            continue
        if _REGION_KEY.search(line):
            continue                      # a per-region table entry: the fix

        # ⚠ `_READS_A_VALUE` is NOT applied to the numeric branch, and the first
        # version of this checker got that wrong: it exempted any line
        # mentioning `coverage_pct`, which is exactly the name the defect wore
        # — `"coverage_pct": 32.6` both names the field and states the value.
        # A line that READS a value has no literal in it, so the literal test is
        # sufficient on its own and the exemption only created a blind spot.
        if _KOREAN.search(line):
            for word in REGION_WORDS:
                if word in line:
                    out.append(Finding(path, i, f"region name {word!r} in a "
                                                "user-visible string",
                                       line.strip()[:110]))
                    break
        for pat, why in PER_REGION_NUMBERS.items():
            if re.search(pat, line):
                out.append(Finding(path, i, f"per-region value: {why}",
                                   line.strip()[:110]))
                break
    return out


def check_repo(repo: Path = REPO, scope: tuple[str, ...] = SCOPE) -> list[Finding]:
    out: list[Finding] = []
    for rel in scope:
        p = repo / rel
        if not p.exists():
            continue
        out += check_text(p.read_text(encoding="utf-8"), rel, suffix=p.suffix)
    return out


def over_the_ratchet(found: list[Finding]) -> list[Finding]:
    """Findings beyond the recorded floor, per file.

    ⚠ The floor may only go DOWN. If a file improves below its entry the check
    still passes, but :mod:`tests.test_screen_checks` says so loudly, the same
    way the dash ratchet does — a stale allowance is how a floor becomes a
    ceiling.
    """
    by_file: dict[str, list[Finding]] = {}
    for f in found:
        by_file.setdefault(f.path, []).append(f)
    out: list[Finding] = []
    for path, items in by_file.items():
        allowed = KNOWN_REGION_LITERALS.get(path, 0)
        if len(items) > allowed:
            out += items[allowed:]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("paths", nargs="*", default=None)
    args = ap.parse_args()

    scope = tuple(args.paths) if args.paths else SCOPE
    found = check_repo(scope=scope)
    over = over_the_ratchet(found)
    if args.json:
        print(json.dumps({"findings": [f.as_dict() for f in found],
                          "over_ratchet": [f.as_dict() for f in over]},
                         indent=2, ensure_ascii=False))
        return 1 if over else 0

    if not over:
        allowed = sum(KNOWN_REGION_LITERALS.values())
        print(f"OK — no NEW region literal in user-visible text across "
              f"{len(scope)} operator-facing files "
              f"({allowed} known and recorded).")
        return 0
    print(f"{len(over)} region literal(s) above the recorded floor:\n")
    for f in over:
        print(f"  {f.path}:{f.line}")
        print(f"      {f.what}")
        print(f"      {f.excerpt}")
    print("\n⚠ A value that differs per region must be READ from its committed "
          "source, not typed.\n  coverage / label -> multi_region_comparison.json "
          "(live.scope.region_coverage_pct, region_label_kr)"
          "\n  bbox areas + station counts -> osm_completeness.json "
          "(live.scope.responder_status_ko)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
