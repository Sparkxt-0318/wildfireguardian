"""Gate on Q16c, the card that answers 「저희 군에서 이걸 쓰려면 무엇이 필요합니까?」.

Backlog row WFG-188. One of the five finals judges is a public-sector
disaster-response official, and adoption is the question that judge asks before
책임 (Q16b) or 개인정보 (Q20a). The card is an *assembly* of what the repository
already commits -- two free keys, four data layers, one Python 3.11 machine, a
human -- and every one of those four is a claim about this repository's own
state, which DIRECTION's rule from critic #39 forbids hand-typing onto a
judge-facing surface. So each is re-derived here from the file that owns it.

The one assertion that matters more than the others
---------------------------------------------------
``test_the_card_leads_with_the_constraint_and_not_with_the_recipe``.

An adoption card is a list of what a county would need, and the honest first
item is not on the list at all: **the hazard surface cannot be built for today**,
because the weather field it is simulated from publishes on a lag while hotspot
detection is near-real-time (``docs/live_pipeline.md`` §0). A card that opens
with the recipe and mentions the lag later -- or not at all -- reads at a booth
as "this is ready to deploy", which is the exact shape critic #43 named as its
root objection one lap before this row was taken: *the strongest version of a
limitation lives in the file nobody opens, and the restatement for a wider
audience comes out softer.* The assertion below is paragraph-scoped for the same
reason ``test_readme_round4`` scopes the 42's caveats to the paragraph that
states the number: a caveat three paragraphs down is not attached to the claim,
and a judge reading the opening would never meet it.

What this gate does NOT catch, named rather than left implicit (WFG-186)
------------------------------------------------------------------------
**A cost figure written in words.** Every assertion about "no cost number" below
matches digits next to a currency unit. 「수백만 원대면 충분합니다」 carries no
digit, states a cost, and passes every check in this file -- run, not imagined.
The generalisation is the one ``docs/withdrawn_claims.md`` §4 already records for
the withdrawn-claim registry: these are copy-paste ratchets over spellings, not
claim detectors, and a rewording escapes.

⚠ **A second escape, found by this lap's independent reviewer and not by the lap,
and it is the more instructive of the two.** The first version of the credential
check parsed REPRODUCE §2 into a list, asserted the list was non-empty, and then
compared the card against ``{"FIRMS", "CDS"}`` typed one line below -- the
derivation was decorative, and the docstring claimed a property the code did not
have. Three mutations walked straight through it: a card naming one key instead
of two, a card naming three, and a *third row added to REPRODUCE §2 itself*. It
is fixed below (the count and the identities both come from the table now, and
the identity check is scoped to the card's own item 1), and it is recorded here
because the failure mode is the one this repository keeps paying for: **reading
the owning file is not deriving from it; the assertion has to consume what it
read.** What still escapes even so: nothing here can tell whether the four-item
list is *complete*, only that each item it states is true of the tree.

Every assertion fails loudly when its input set is empty (the
matches-nothing-fails clause WFG-178 added): a derivation over zero files agrees
with any card at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
QA = REPO / "docs" / "auto" / "JUDGE_QA.md"
REPRODUCE = REPO / "docs" / "REPRODUCE.md"
LIVE = REPO / "docs" / "live_pipeline.md"
REQUIREMENTS = REPO / "requirements.txt"
MULTI_REGION = REPO / "docs" / "multi_region.md"
SEND_EMAIL = REPO / "scripts" / "send_dispatch_email.py"

#: The card's id. A letter suffix, because the card is inserted beside the
#: question it sits with (Q16b, 책임) rather than renumbering 30 headings.
QID = "Q16c"

#: A currency amount: digits, optional separators, then a Korean money unit.
#: See the module docstring for what this cannot see.
_COST_FIGURE = re.compile(r"\d[\d,.]*\s*(?:원|만\s*원|억|천만|백만)")


def _card(qid: str = QID) -> str:
    """The one card's text, from its heading to the next card's heading."""
    text = QA.read_text(encoding="utf-8")
    start = text.find(f"**{qid} · ")
    assert start != -1, (
        f"{qid} is not in docs/auto/JUDGE_QA.md. WFG-188 put it there; if it was "
        "renamed, this whole file is pointing at nothing."
    )
    nxt = re.compile(r"^\*\*Q\d+[a-z]? · T[012]", re.MULTILINE)
    after = nxt.search(text, start + 4)
    return text[start : after.start()] if after else text[start:]


def _paragraphs(block: str) -> list[str]:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", block) if p.strip()]


# ---------------------------------------------------------------------------
# The card leads with what it cannot do.
# ---------------------------------------------------------------------------


def test_the_card_leads_with_the_constraint_and_not_with_the_recipe() -> None:
    """The lag is in the opening paragraph, with ERA5 named beside it.

    Not "somewhere in the card": see the module docstring.
    """
    paras = _paragraphs(_card())
    assert len(paras) >= 3, f"{QID} has {len(paras)} paragraphs; it is not the card"
    opening = paras[1] if paras[0].startswith(f"**{QID}") else paras[0]

    assert "오늘 만들 수 없습니다" in opening, (
        f"{QID}'s opening paragraph no longer says the hazard surface cannot be "
        "built for today. That sentence is the card's honest first item and the "
        "reason the row was taken; a recipe without it reads as deployment-ready."
    )
    assert "ERA5" in opening, (
        f"{QID}'s opening states the limitation without naming the input that "
        "causes it. A judge cannot check a limitation with no subject."
    )


def test_the_lag_the_card_states_is_the_one_its_source_document_states() -> None:
    """``docs/live_pipeline.md`` §0 is where the asymmetry is measured."""
    live = LIVE.read_text(encoding="utf-8")
    assert "ERA5" in live and "lag" in live.lower(), (
        "docs/live_pipeline.md no longer describes the ERA5 publication lag, so "
        f"{QID} is quoting a document that stopped saying it."
    )
    assert re.search(r"not\*{0,2}\s+real-time forecasting", live), (
        "docs/live_pipeline.md §0's own disclaimer is gone; the card leans on it."
    )


# ---------------------------------------------------------------------------
# The four things the card says a county would need.
# ---------------------------------------------------------------------------


#: Segments of a credential variable name that identify no service.
_GENERIC = {"API", "URL", "KEY", "MAP", "NASA", "ID", "TOKEN", "SECRET"}

#: len(rows) -> the Korean numeral the card must use for it. Deliberately short:
#: a project needing five separate credentials to stand up one county is a
#: different claim than this card makes, and should fail loudly here.
_COUNT_WORD = {1: "한", 2: "두", 3: "세", 4: "네"}


def _credential_rows() -> list[str]:
    """The variable names ``docs/REPRODUCE.md`` §2 requires, one per table row."""
    section = REPRODUCE.read_text(encoding="utf-8")
    start = section.find("## 2. Credentials")
    assert start != -1, "docs/REPRODUCE.md has no '## 2. Credentials' section"
    end = section.find("\n## ", start + 1)
    creds = section[start : end if end != -1 else len(section)]
    rows = re.findall(r"^\|\s*`([A-Z][A-Z0-9_]+)`", creds, re.MULTILINE)
    assert rows, "the credentials table lists no variables; nothing to compare"
    return rows


def _enumerated_item(n: int) -> str:
    """The card's ``**n)**`` item, up to the next one or the end of the answer.

    ⚠ **Item scope, not card scope, and this is the whole point of the helper.**
    The first version of this file asserted ``"FIRMS" in card``. An independent
    reviewer broke it in one move: rewrite the credential item to name a single
    key, and the assertion stays green because ``FIRMS`` is still standing three
    lines above, inside the *ERA5 lag* sentence of the opening paragraph -- a
    different claim entirely, and the very limitation the card was restructured
    to lead with. That is critic #41's defect (a scope assertion satisfied by a
    string in some other claim's neighbourhood) shipping for the fourth time, and
    the same shape WFG-185 fixed with a sentence-scoped assertion. The
    enumeration item is the exact scope of the claim being made, so it is the
    scope the assertion gets.
    """
    card = _card()
    start = card.find(f"**{n})**")
    assert start != -1, f"{QID} has no enumerated item {n})"
    nxt = card.find(f"**{n + 1})**", start + 1)
    end = nxt if nxt != -1 else card.find("근거:", start)
    return " ".join(card[start : end if end != -1 else len(card)].split())


def test_the_credential_count_the_card_states_is_the_one_the_table_requires() -> None:
    """「계정 키 두 개」 is derived from the table, not typed beside it."""
    rows = _credential_rows()
    word = _COUNT_WORD.get(len(rows))
    assert word, (
        f"docs/REPRODUCE.md §2 now lists {len(rows)} credentials, which this "
        "gate has no numeral for. Extend _COUNT_WORD and fix the card."
    )
    assert f"계정 키 {word} 개" in _card(), (
        f"{QID} does not state 「계정 키 {word} 개」, and docs/REPRODUCE.md §2 "
        f"requires {len(rows)} ({rows}). A county told the wrong number of "
        "credentials cannot even start."
    )


def test_every_credential_the_table_requires_is_named_in_the_card_s_own_item() -> None:
    """Each row of REPRODUCE §2 is identifiable inside item 1), not elsewhere.

    The expected set is derived from the table's variable names; nothing about
    which services those are is written in this file.
    """
    rows = _credential_rows()
    item = _enumerated_item(1)

    for var in rows:
        tokens = [s for s in var.split("_") if s not in _GENERIC and len(s) >= 3]
        assert tokens, f"{var} is all generic segments; this check cannot see it"
        # A prose card writes 「Copernicus CDS」 where the variable is CDSAPI_URL,
        # so an identifying *prefix* of a token counts. Three characters is the
        # floor: shorter than that stops identifying anything.
        candidates = {t for tok in tokens for t in
                      {tok, *(tok[:k] for k in range(3, len(tok) + 1))}}
        assert any(c in item for c in candidates), (
            f"{QID}'s item 1) does not name the credential docs/REPRODUCE.md §2 "
            f"requires as `{var}`. Item 1) reads: {item!r}"
        )


def test_the_dependencies_are_pinned_where_the_card_says_they_are() -> None:
    """「의존성은 판본이 고정돼 있습니다」, derived from requirements.txt itself."""
    lines = [
        ln.strip()
        for ln in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert lines, "requirements.txt declares nothing; the card's claim is vacuous"
    unpinned = [ln for ln in lines if "==" not in ln]
    assert not unpinned, (
        f"{QID} tells a county the dependency set is pinned, and these lines of "
        f"requirements.txt are not: {unpinned}"
    )


def test_the_python_version_the_card_names_is_the_one_the_repo_declares() -> None:
    """The card says 3.11; requirements.txt's own header is the declaration."""
    header = REQUIREMENTS.read_text(encoding="utf-8")[:600]
    m = re.search(r"Python (\d+\.\d+) required", header)
    assert m, "requirements.txt no longer declares a required Python version"
    declared = m.group(1)
    assert f"파이썬 {declared}" in _card(), (
        f"{QID} does not name Python {declared}, which is what requirements.txt "
        "declares. A county reading the card would install the wrong interpreter."
    )


def test_the_card_points_at_the_regional_defect_it_uses_as_its_warning() -> None:
    """「돌리면 나오는 것이 아니라」 rests on a specific, committed failure."""
    card = _card()
    assert "multi_region.md" in card, f"{QID} dropped its pointer to the record"
    assert re.search(r"^## 4\. The DEM defect", MULTI_REGION.read_text(encoding="utf-8"),
                     re.MULTILINE), (
        "docs/multi_region.md §4 is no longer the DEM-defect section the card sends "
        "a judge to."
    )


def test_the_delivery_layer_is_still_the_dry_run_the_card_promises() -> None:
    """④ 사람: the card says the delivery layer is a simulation *today*."""
    src = SEND_EMAIL.read_text(encoding="utf-8")
    assert "--confirm-send" in src and "DRY RUN" in src, (
        "scripts/send_dispatch_email.py no longer defaults to a dry run, so the "
        f"card {QID} states a safety property the code stopped having."
    )
    assert "모사" in _card(), f"{QID} no longer says the delivery layer is simulated"


# ---------------------------------------------------------------------------
# What the card refuses to say.
# ---------------------------------------------------------------------------


def test_the_card_states_no_cost_figure_anywhere() -> None:
    """No 도입비/운영비 number, in the answer or in the 없는 것 block.

    ⚠ Digits only. A cost written in words passes; see the module docstring.
    """
    hits = _COST_FIGURE.findall(_card())
    assert not hits, (
        f"{QID} carries what reads as a cost figure ({hits}). No cost of any kind "
        "is registered in this repository, so any such number is invented."
    )


def test_the_card_refuses_the_cost_question_in_writing() -> None:
    """The refusal is the card's last spoken sentence, not an omission."""
    card = _card()
    assert "비용은 말씀드릴 수 없습니다" in card, (
        f"{QID} no longer refuses the cost question out loud. Silence on cost "
        "reads at a booth as 'cheap'."
    )
    assert "운영해 본 적이 없" in card, (
        f"{QID} no longer says no institution has ever run this."
    )


def test_the_card_does_not_answer_the_adoption_decision_itself() -> None:
    """Q16b's register: 도입 여부 is not the student's question to answer."""
    card = _card()
    assert "제가 답할 질문이 아닙니다" in card or "답할 수 있는 범위가 아닙니다" in card, (
        f"{QID} has started answering whether a county should adopt this. That is "
        "the boundary Q16b sets and this card inherits."
    )
    for banned in ("법적 책임은 없습니다", "면책"):
        assert banned not in card, f"{QID} asserts a legal conclusion: {banned!r}"


# ---------------------------------------------------------------------------
# Shape: the same two blocks every card in the bank carries.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("block", ["근거:", "없는 것:"])
def test_the_card_carries_the_two_blocks_the_bank_requires(block: str) -> None:
    assert block in _card(), (
        f"{QID} has no {block!r} block; the bank's own rule 2 forbids that."
    )


def test_every_repository_path_the_card_cites_resolves() -> None:
    """The 근거 block's whole claim is 「열어 보시면 있습니다」."""
    card = _card()
    cited = re.findall(r"`([A-Za-z0-9_./-]+\.(?:md|py|txt|json|html))`", card)
    assert cited, f"{QID} cites no file at all"
    missing = sorted({c for c in cited if not (REPO / c).exists()})
    assert not missing, f"{QID} cites paths that do not exist: {missing}"
