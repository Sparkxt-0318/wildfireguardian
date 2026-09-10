"""WFG-222: wherever a surface says the output object is committed, its bounds are beside it.

**The defect this closes was not a word.** On 2026-09-09 the lap that wrote ``README.md``'s
Round-4 lead block was blocked by its independent reviewer on a **conjunction**: two
artifacts named side by side assert their conjunction, and the committed dispatch documents
came from a run whose hazard surface and terrain are **synthetic**
(``data/processed/rescue_routing.json`` → ``provenance.sources`` reads ``hazard: synthetic``,
``terrain: synthetic``, ``origins: sampled candidates``), while the run where the walking
graph and the spread surface are **both** real produces four-way verdicts and no dispatch
documents at all. The lap accepted the block and fixed the lead. It fixed **one** surface.

Critic #54 measured the rest: the identical claim, in the identical words, stood on the
finals screen, on a **T0** Q&A card the student speaks from memory, on the booth script and
in the printed creativity card. The gate that lap wrote to prevent exactly this
(``tests/test_readme_round4_lead.py``) scoped its bound assertion to its ``lead`` fixture,
so the same file could contradict its own headline claim one hundred and eighty lines lower
with the whole suite green.

**So this file is deliberately NOT a wording gate.** The property it holds is structural and
it is the one the reviewer actually objected to:

    a block that asserts committed instances of the output object EXIST must, in the
    SAME block, say what was synthetic in the run that produced them and that the
    origins were sampled.

Three consequences of writing it that way:

* it cannot be satisfied by **deleting** the claim - ``test_every_surface_still_makes_the
  _existence_claim`` fails if a surface goes quiet, because a silent surface is how the
  screen carried this for a day;
* it is **per-surface and per-block**, so a bound two screens away does not pay for a claim
  here, which is the ``12b8ac7`` failure and the reason CHARTER §3 rule 3 exists;
* the families are **not substrings this lap invented**. ``합성`` / ``synthetic`` and
  ``표본`` / ``sampled`` are the words the artifact's own ``provenance.sources`` uses about
  itself, so a later lap that rewrites the prose has to keep saying what the artifact says.

⚠ **The household register is banned in these blocks, and that is the narrow half.**
``docs/auto/JUDGE_QA.md`` Q20a *defines* 「가구」 in this repository as one node of the OSM
walking graph, and that definition is honest. It is also two hundred lines from the claim,
and a judge who has not read it hears an address register that the sampled origins do not
support. The blocks below therefore say 지점, and this file refuses 가구 단위 **inside them
only** - Q20a's definition, Q16's quantity and Q16a's sentence about other systems are
untouched, which is why the ban is scoped to a block and not to a file.

⚠ **What this file cannot catch, measured rather than guessed.** It reads five blocks named
by path and marker. A sixth surface that acquires the claim tomorrow is invisible to it
until someone adds it here, exactly as ``docs/withdrawn_claims.md`` §4 records for the
withdrawn-claim registry: this is a structural ratchet over a **declared** list, not a claim
detector over the tree. ``docs/auto/withdrawn_claims.json`` ``WC-013`` is the half that does
scan every gated file, and it catches a copied spelling rather than a reworded one. Neither
closes the class; together they cover the two ways this defect has actually travelled -
copy-paste, and a new surface built from an old one.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


#: The claim itself: this repository holds instances of the output object. A surface that
#: stops saying this has not been fixed, it has gone silent.
_EXISTENCE = re.compile(r"커밋(?:돼|되어|된)|Committed instances|committed sheets")

#: What was NOT real in the run that made those instances. The words are the artifact's:
#: ``provenance.sources`` says ``hazard: synthetic`` and ``terrain: synthetic`` about itself.
_SYNTHETIC = re.compile(r"합성|synthetic", re.I)

#: And where the origins came from: ``origins: sampled candidates``.
_SAMPLED = re.compile(r"표본\s*좌표|sampled\s+(?:coordinates|origins|candidates)", re.I)

#: The register that outran the evidence. Scoped to these blocks; see the module docstring.
_HOUSEHOLD = re.compile(r"가구\s*단위|per[-\s]household", re.I)


#: ``(label, path, start marker, end marker)``. The markers are structural - a heading, a
#: list item's own bold lead, the next object in a literal array - so that editing the prose
#: inside a block does not move its boundary. ``None`` as the end marker means "to the end
#: of the line the start marker is on".
SURFACES: tuple[tuple[str, str, str, str | None], ...] = (
    (
        "README.md §5 item ①",
        "README.md",
        "- **① 산출물 자체가 기여입니다.**",
        "- **② 두 축이 동시에 실제인 실행.**",
    ),
    (
        "the finals screen template, CREATIVE item ①",
        "scripts/finals.template.html",
        "ko_h: '내놓는 것은 지도가 아니라 판정입니다'",
        "ko_h: '두 축이 동시에 실제인 실행'",
    ),
    (
        "the built finals screen, CREATIVE item ①",
        "web/finals.html",
        "ko_h: '내놓는 것은 지도가 아니라 판정입니다'",
        "ko_h: '두 축이 동시에 실제인 실행'",
    ),
    (
        "docs/auto/JUDGE_QA.md Q29a, spoken item 1 (tier T0)",
        "docs/auto/JUDGE_QA.md",
        "**첫째, 만든 물건이 다릅니다.**",
        "**둘째, 그 질문을 재려고",
    ),
    (
        "docs/auto/DEMO_SCRIPT_5MIN.md, the 도입 segment",
        "docs/auto/DEMO_SCRIPT_5MIN.md",
        "### 도입",
        "### 1막",
    ),
    (
        "docs/creativity_card.md, the method table's item 1",
        "docs/creativity_card.md",
        "| 1 | the **output object** is the contribution",
        None,
    ),
)


def _block(label: str, rel: str, start: str, end: str | None) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    i = text.find(start)
    assert i >= 0, (
        f"{label}: {rel} no longer contains the marker {start!r}, so this gate can no "
        "longer find the block it is meant to hold. If the surface was restructured, move "
        "the marker in the same commit; if the claim was retired from this surface, delete "
        "the row here and say why in the backlog."
    )
    if end is None:
        j = text.find("\n", i)
        return text[i:] if j < 0 else text[i:j]
    j = text.find(end, i)
    assert j > i, (
        f"{label}: {rel} contains {start!r} but no following {end!r}; the block has no "
        "end and this gate would read the rest of the file."
    )
    return text[i:j]


@pytest.fixture(scope="module", params=SURFACES, ids=lambda s: s[0])
def surface(request) -> tuple[str, str]:
    label, rel, start, end = request.param
    return label, _block(label, rel, start, end)


def test_every_surface_still_makes_the_existence_claim(surface) -> None:
    """The fix is bounds ADDED, never the claim removed.

    ⚠ This assertion is the reason the rest of the file cannot be satisfied cheaply. The
    lazy way to make a block carry its bounds is to stop making the claim, and a surface
    that says nothing about the output object is the state ``web/finals.html`` was in for
    the six days WFG-194 measured. 창의성 is 20 points on both KCF tables whether or not a
    judge asks.
    """
    label, block = surface
    assert _EXISTENCE.search(block), (
        f"{label} no longer says that committed instances of the output object exist. "
        "WFG-222 asks for the bound beside the claim, not for the claim to go quiet: an "
        "existence claim a judge can settle by opening a file is this project's strongest "
        "card (README TL;DR)."
    )


def test_every_existence_claim_carries_the_synthetic_hazard_bound(surface) -> None:
    """The conjunction the independent reviewer broke, held per block.

    ``rescue_routing.json`` → ``provenance.sources`` is the whole argument: the committed
    dispatch documents are real documents from a run with a **synthetic** fire. A surface
    that states the claim and leaves this out reads as 「real roads + real fire → these
    sheets」, and that execution does not exist in this repository.
    """
    label, block = surface
    assert _SYNTHETIC.search(block), (
        f"{label} states that committed instances exist and does not say, in the same "
        "block, that the hazard surface and the terrain of the run that produced them are "
        "SYNTHETIC. data/processed/rescue_routing.json → provenance.sources says so about "
        "itself; a claim whose bound sits on another screen is the 12b8ac7 failure "
        "(CHARTER §3 rule 3, WFG-049)."
    )


def test_every_existence_claim_says_the_origins_were_sampled(surface) -> None:
    """A point is not an address, and the artifact says so about itself."""
    label, block = surface
    assert _SAMPLED.search(block), (
        f"{label} does not say, in the same block, that the origins are SAMPLED "
        "coordinates. Real elderly household locations are not public data "
        "(scripts/build_numbers.py registers that caveat on the routing entries), so the "
        "origins are walk-network samples; without this line the block claims a household "
        "register the run cannot support."
    )


def test_no_surface_puts_the_committed_instances_in_the_household_register(surface) -> None:
    """The narrow half, scoped to the block (see the module docstring).

    ⚠ Q20a's definition of 「가구」 as one OSM walk-graph node is honest and is deliberately
    NOT touched by this assertion. What is refused is the household register **in the block
    that makes the existence claim**, where a judge meets it without the definition.
    """
    label, block = surface
    hits = _HOUSEHOLD.findall(block)
    assert not hits, (
        f"{label} describes the committed instances in the household register "
        f"({', '.join(hits)}). The word for the committed instances is 지점 단위 / "
        "point-level, with the bound in the same block: WFG-222, and README.md's Round-4 "
        "lead is the model. Q20a's definition of the term is a separate surface and is not "
        "what this refuses."
    )


# --------------------------------------------------------------------------- graded

def _missing(block: str) -> list[str]:
    """The families a block fails to carry. The assertions above, as data."""
    out = []
    if not _EXISTENCE.search(block):
        out.append("existence")
    if not _SYNTHETIC.search(block):
        out.append("synthetic")
    if not _SAMPLED.search(block):
        out.append("sampled")
    if _HOUSEHOLD.search(block):
        out.append("household-register")
    return out


def test_the_shipped_blocks_all_pass_and_the_pre_fix_wording_all_fails() -> None:
    """The gate is graded rather than asserted, because MEMO 2026-09-09 says to.

    That lesson: *a gate whose assertions are substrings the same lap just wrote is a gate
    the next writer edits around* - the lap's own reviewer walked through the first version
    of ``test_readme_round4_lead.py`` three times with the suite green. So this test does
    not trust the four assertions above; it re-runs them over each shipped block **and**
    over that block with the bound sentence removed, and requires the second to fail. The
    mutation is mechanical (drop every sentence carrying the bound), so it is the same
    mutation on all six surfaces and no wording is hand-picked to fail.
    """
    for label, rel, start, end in SURFACES:
        block = _block(label, rel, start, end)
        assert not _missing(block), f"{label} fails the shipped check: {_missing(block)}"

        # Mutation: strike every sentence that carries a bound family, which is what a
        # later lap "tidying" the block would do, and what every one of the five surfaces
        # actually looked like at 3eec471.
        pieces = re.split(r"(?<=[.。])\s|(?<=다\.)|\n", block)
        stripped = "".join(
            p for p in pieces
            if p and not (_SYNTHETIC.search(p) or _SAMPLED.search(p))
        )
        assert _missing(stripped), (
            f"{label}: removing every sentence that carries a bound left a block this "
            "gate still accepts. Then the gate is not what keeps the bound there and the "
            "families above need re-deriving before this file is trusted."
        )


def test_the_household_register_ban_would_have_caught_the_pre_fix_text() -> None:
    """The five wordings critic #54 measured at ``3eec471``, kept as regression data.

    These are the sentences that stood on the five judge-facing surfaces while
    ``README.md``'s lead block, in the same repository, denied them. They are data rather
    than prose so that a later rewrite of ``_HOUSEHOLD`` has to face them.
    """
    pre_fix = (
        "이 시스템이 내놓는 것은 **가구 단위의 「걸어서 나갈 수 있는가 / 구조를 보내야 "
        "하는가」 판정과 그 도보 경로**입니다.",
        "산출물은 가구 단위의 대피 판정과 걸어 나갈 경로, 그리고 마을 단위 출동 목록입니다.",
        "What comes out is a per-household evacuation verdict, the walking route that goes "
        "with it, and a village-level dispatch list.",
        "그 뒤에 가구 단위 구조 순서와 보행 경로가 붙습니다.",
        "지도가 아니라 **가구 단위 판정과 걸어 나갈 길**입니다.",
        "a rescue order and a walking route per household",
    )
    for sentence in pre_fix:
        assert _HOUSEHOLD.search(sentence), (
            "a wording that shipped on a judge-facing surface at 3eec471 is no longer "
            f"caught by _HOUSEHOLD: {sentence!r}"
        )
        assert not _SYNTHETIC.search(sentence) and not _SAMPLED.search(sentence), (
            "the pre-fix wording is supposed to carry NO bound - that was the finding. If "
            f"it now does, this regression datum is wrong: {sentence!r}"
        )
