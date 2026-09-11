"""WFG-247: where a refuge-siting count is SAID, the population it counts is said too.

**The defect this closes is three populations in one breath.** The five-minute demo's
closing 56 seconds — the last thing each of the five judges hears — said, at
``docs/auto/DEMO_SCRIPT_5MIN.md:266-268`` as it stood at ``c579c81``:

    보행망 노드 **2,218곳을 전수 탐색**해서, 대피 지점 한 곳을 추가하면 **20가구**,
    두 곳이면 **24가구** 가 도달 가능해지고, **세 번째는 0가구** 를 더합니다.

Three different populations, and the repository knows all three are different:

* **2,218** is ``l0i_candidates_enumerated``, candidate SITES surviving the constraint
  filter — of 8,443 walk-network nodes, which is what the sentence called them;
* **20 / 24 / 0** are ``l0i_best_single_refuge_saved``, ``l0i_best_pair_saved`` and
  ``l0i_third_refuge_gain``, whose registry ``sample`` reads ``OSM 건물 124동(잠정)``;
* **지점**, which the demo's own 도입 claims as this project's output unit, is one node
  of the OSM **walking graph** (``docs/auto/JUDGE_QA.md`` Q20a).

The reconciliation already existed and nothing pointed at it: ``JUDGE_QA.md`` Q19 says
「두 질문은 모집단도 다릅니다」 one hundred and ninety lines away, in a different card, in
a different segment of the demo. ``WC-013``'s ``say_instead`` states the rule that breaks
in one line — **the bound goes in the SAME block as the claim, never one screen away** —
and this file is that rule, held mechanically, for this family of numbers.

⚠ **This is NOT a ``WC-013`` violation and must not be read as one.** ``WC-013`` withdrew
the household register for this project's walk-or-be-rescued **verdict**. The refuge-siting
result genuinely is measured on buildings and ``docs/NUMBERS.json`` says so, so the fix is
never to swap 가구 for 지점 here — that would make a true sentence false. What is required
is that the population be named where the number is said.

Two properties, and they fail in opposite directions on purpose:

1. **per-block** — a declared surface that speaks a saved-household count must name the
   population in the same block. It cannot be satisfied by deleting the count:
   ``test_every_surface_still_speaks_the_result`` fails if a surface goes quiet, because a
   silent 마무리 is not a fixed one.
2. **tree-wide** — no tracked ``.md`` or ``.html`` may call 2,218 「보행망 노드」 again.
   That half is a spelling ratchet over the whole tree and catches the copy, not the
   reword; the per-block half is structural and covers only the surfaces named here.

⚠ **What this cannot catch, stated rather than implied.** The declared list below is five
entries and the defect travelled to four of them before anyone counted. A sixth surface
built tomorrow from one of these is invisible to property 1 until it is added here, and a
reworded population claim ("건물 스냅숏 기준" with no number, say) satisfies neither the
letter nor the intent. This is a ratchet over a declared list plus a spelling sweep, not a
population detector — the same limit ``docs/withdrawn_claims.md`` §4 records for the
withdrawn-claim registry, written down here for the same reason.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: A saved-household count as the surfaces actually speak it. Two spellings, because the
#: two kinds of surface speak it two ways: prose writes the literal 20가구 / 24가구, and the
#: finals screen never writes a number at all — it names the registry key and the value is
#: read from docs/NUMBERS.json at build time (that is the rule `docs/finals_screen_v2.md`
#: exists to enforce). A test that demanded the literal would declare the screen silent.
_SAVED_COUNT = re.compile(r"\b(?:20|24)\s*가구|l0i_best_(?:single_refuge|pair)_saved")

#: The population, as any of the spellings a surface may honestly use for it. 124 is
#: `l0i_household_population`, read from the same artifact the numerators come from.
_POPULATION = re.compile(r"124\s*(?:동|가구|채|개)|OSM\s*건물\s*(?:스냅숏|124)")

#: The mislabel itself: 2,218 called a count of walk-network nodes. `l0i_walk_nodes_total`
#: is 8,443; 2,218 is what survives the filter. Tolerant of markdown emphasis and of a
#: line break between the label and the number, because that is how it hid once already.
_MISLABEL = re.compile(r"보행망\s*노드\s*(?:\*\*)?\s*2,?218")

#: Surfaces that speak this result, by path and by the marker that opens the block. Each
#: entry is (path, marker) where the marker is a literal that occurs exactly once.
SURFACES = [
    # the spoken 마무리, and the 금지 list item that licenses the phrasing
    ("docs/auto/DEMO_SCRIPT_5MIN.md", "대피 지점 배치도 마찬가지입니다"),
    ("docs/auto/DEMO_SCRIPT_5MIN.md", "두 군데가 틀릴 수 있으므로"),
    # the screen's spec, then the screen's source and the built screen
    ("docs/finals_screen_v2.md", "240분 지평에서 도달 실패인"),
    ("scripts/finals.template.html", "도달 가능해지는 가구 수"),
    ("web/finals.html", "도달 가능해지는 가구 수"),
]

#: CHARTER §3.5c's record class, which exists to QUOTE a defect in order to record it.
#: A sweep that fired here would teach the next lap to stop writing the record down.
_RECORD_CLASS = {
    "docs/auto/BACKLOG.md", "docs/auto/CRITIC_LATEST.md", "docs/auto/MEMO.md",
    "docs/auto/DIRECTION.md", "docs/auto/SCORECARD.md", "docs/auto/KCF_READINESS.md",
    "docs/auto/CHARTER.md", "docs/auto/NEEDS_HUMAN.md", "docs/withdrawn_claims.md",
}


def _blocks(text: str) -> list[str]:
    """Maximal runs of consecutive non-blank lines.

    The demo script's whole 마무리 segment is one unbroken run of ``> `` lines, and the
    screen's card is one JavaScript statement, so a run is the unit a judge hears or reads
    at once. A bound in the next paragraph is a bound one screen away, which is the case
    ``WC-013``'s rule refuses.
    """
    out, cur = [], []
    for line in text.split("\n"):
        if line.strip():
            cur.append(line)
        elif cur:
            out.append("\n".join(cur))
            cur = []
    if cur:
        out.append("\n".join(cur))
    return out


def _tracked(suffixes: tuple[str, ...]) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    return [REPO / p for p in out.split("\0")
            if p and p.endswith(suffixes) and (REPO / p).exists()]


@pytest.mark.parametrize("rel,marker", SURFACES)
def test_the_population_is_named_in_the_same_block_as_the_count(rel, marker):
    text = (REPO / rel).read_text(encoding="utf-8")
    assert text.count(marker) == 1, (
        f"{rel}: the marker {marker!r} occurs {text.count(marker)} times, so this test no "
        "longer names one block; re-point SURFACES at the block that speaks the result"
    )
    block = next(b for b in _blocks(text) if marker in b)
    assert _SAVED_COUNT.search(block), (
        f"{rel}: the block at {marker!r} no longer speaks a saved-household count. If the "
        "result was deliberately dropped, remove its entry from SURFACES in the same "
        "commit and say why; a silent surface is not a corrected one"
    )
    assert _POPULATION.search(block), (
        f"{rel}: the block at {marker!r} says 20가구/24가구 without naming the population "
        "those are counted over. It is OSM 건물 124동 (l0i_household_population), which is "
        "neither the 2,218 candidate sites nor the 지점 this project calls its output "
        "unit. Name it HERE — WC-013's say_instead: the bound goes in the same block as "
        "the claim, never one screen away. Do NOT fix this by writing 지점 instead of "
        "가구; these really are buildings"
    )


@pytest.mark.parametrize("rel,marker", SURFACES)
def test_every_surface_still_speaks_the_result(rel, marker):
    """Deleting the count is not a fix, and this is the half that says so."""
    assert marker in (REPO / rel).read_text(encoding="utf-8"), (
        f"{rel}: the block that spoke the refuge-siting result is gone. That is a change "
        "to what five judges hear, not a repair of how it is worded"
    )


def test_no_surface_calls_the_candidate_sites_walk_network_nodes():
    """2,218 survived the filter; 8,443 went into it. Tree-wide, not per-block."""
    hits = []
    for path in _tracked((".md", ".html")):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(("docs/auto/reports/", "docs/auto/archive/")):
            continue  # reports are the record of what was said, including this defect
        if rel in _RECORD_CLASS:
            continue  # record class: these pages exist to quote the defect
        text = path.read_text(encoding="utf-8", errors="replace")
        flat = re.sub(r"\s+", " ", text)
        if _MISLABEL.search(flat):
            hits.append(rel)
    assert not hits, (
        "2,218 is l0i_candidates_enumerated — candidate SITES surviving the constraint "
        "filter, of the 8,443 walk-network nodes registered as l0i_walk_nodes_total. "
        "Calling it 「보행망 노드」 names the filter's input with the filter's output. "
        "Say 「후보 지점」. Files: " + ", ".join(hits)
    )


def test_the_population_is_registered_from_the_artifact_that_produced_the_counts():
    """Not from building_origin_routing.json, whose 124 agrees by coincidence (WFG-244)."""
    numbers = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))
    entry = numbers["numbers"]["l0i_household_population"]
    assert entry["source_file"] == "data/processed/vulnerability/refuge_placement.json", (
        "the denominator must come from the artifact the numerators come from; a second "
        "file that happens to hold 124 is a coincidence, not a derivation"
    )
    assert entry["value"] == 124.0
    nodes = numbers["numbers"]["l0i_walk_nodes_total"]
    assert nodes["value"] == 8443.0
    assert nodes["value"] > numbers["numbers"]["l0i_candidates_enumerated"]["value"], (
        "the filter's input must exceed its output, or the two keys have been swapped"
    )


def test_the_registrar_agrees_with_the_artifact():
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "register_refuge_population.py"), "--check"],
        cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
