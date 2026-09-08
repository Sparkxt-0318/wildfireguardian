"""Gates on the two cards a disaster-response judge asks for: 책임 and 개인정보.

Backlog rows WFG-167 (responsibility) and WFG-181 (privacy). Both cards are T0 —
the student recites them from memory in a 1:1 interview — and both answer with
claims about *this repository's own state*: what the printed sheet says, how many
sheets carry it, that nothing was ever transmitted, that a 「가구」 is a graph node
and not a person.

Why this file exists rather than a paragraph in the card
-------------------------------------------------------
Three of this project's four judge-facing regressions in the week to 2026-09-08
were a sentence that was true when it was typed and false a lap later, and each
was a claim the repository could have derived: 「여섯 개」 was written onto three
surfaces by the commit that made it seven (WFG-178), and the demo script still
said 「41문항」 when the bank held 42. DIRECTION's rule from critic #39 is the
generalisation — *do not hand-type a number about this repository's own state
onto a judge-facing surface* — and a gate is the only thing that enforces it.

So every quantity these two cards state is re-derived here from the tree and
compared to the card, and every sentence they quote from another surface is read
from that surface rather than retyped:

* the sheet's footer is read from ``delivery.printable.FOOTER_LINES``, the
  constant that puts it on every sheet, so deleting or rewording the footer
  breaks the card that promises it;
* the sheet count is counted;
* ``nothing_was_sent`` is read out of every committed manifest that carries it,
  and the absence of ``email_sent.json`` is checked as an absence;
* the screen's and the demo script's one-line versions of the same claim are
  located in their own files.

What this does NOT do. It does not check that the answers are *good*, and it
cannot see a reworded overclaim that carries none of the keyed phrases — the
same limit ``docs/withdrawn_claims.md`` §4 records for the withdrawn-claim
registry. It also does not assert anything about law: that is the one thing both
cards refuse to say, and the refusal itself is what is checked below.

Every assertion here fails loudly when its input set is empty (the
matches-nothing-fails clause WFG-178 added), because a derivation over zero
files agrees with any card at all.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from wildfireguardian.delivery.printable import FOOTER_LINES

REPO = Path(__file__).resolve().parents[1]
QA = REPO / "docs" / "auto" / "JUDGE_QA.md"
DISPATCH = REPO / "outputs" / "dispatch"
OUTPUTS = REPO / "outputs"
FINALS = REPO / "web" / "finals.html"
DEMO_SCRIPT = REPO / "docs" / "auto" / "DEMO_SCRIPT_5MIN.md"

#: The sentence the screen prints, and the one the demo script gives the student
#: as a one-line interruption answer. Kept as two spellings because they ARE two
#: spellings; the card cites both and the point of this gate is that all three
#: surfaces say the same thing.
SCREEN_SENTENCE = "최종 판단은 언제나 사람이 내립니다"
SCRIPT_FRAGMENT = "최종 판단은 언제나 사람"


def _qa() -> str:
    return QA.read_text(encoding="utf-8")


def _card(qid: str) -> str:
    """The body of one question card, from its header to the next `---` rule."""
    text = _qa()
    head = "**Q" + qid + " · T0"
    assert head in text, (
        "Q" + qid + " is gone from the bank. WFG-167 (책임) and WFG-181 "
        "(개인정보) are the two cards the 재난대응 실무자 judge asks for; if a "
        "card is being retired, retire this gate in the same commit and say why."
    )
    body = text[text.index(head):]
    return body.split("\n---\n", 1)[0]


def _draft(qid: str) -> str:
    """The quoted draft answer — the words the student actually speaks."""
    body = _card(qid)
    assert "답변(초안):" in body, "Q" + qid + " has no 답변(초안) block"
    return body.split("답변(초안):", 1)[1]


def _sheets() -> list[Path]:
    sheets = sorted(DISPATCH.glob("*/*/dispatch_a4.html"))
    assert sheets, (
        "no dispatch_a4.html found under outputs/dispatch/. Every claim below "
        "is derived from these files, and a derivation over zero files agrees "
        "with any card at all (WFG-178's matches-nothing-fails clause)."
    )
    return sheets


def _flat(text: str) -> str:
    """Collapse whitespace, so a markdown line wrap is not a difference.

    The card quotes the sheet footer verbatim and the file wraps it across two
    lines. Comparing raw would make this gate fail on reflow, which teaches the
    next lap to loosen the assertion rather than to fix a real drift.
    """
    return re.sub(r"\s+", " ", text)


def _manifests() -> list[Path]:
    """Every committed run record carrying the key — both spellings.

    The generator writes MANIFEST.json and the PHASE-6 replay writes RUN.json;
    16 and 12 of them at 2026-09-08. The first draft of this gate globbed only
    MANIFEST.json, derived 16, and reported the card's 28 as wrong -- the gate
    was the thing that was wrong, and the count is the whole set or it is a
    number about a subset nobody named.
    """
    found = [
        p for p in OUTPUTS.rglob("*.json")
        if p.name in ("MANIFEST.json", "RUN.json")
        and "nothing_was_sent" in p.read_text(encoding="utf-8")
    ]
    assert found, (
        "no committed manifest carries nothing_was_sent. Both cards tell a "
        "judge that nothing was ever transmitted and cite these files for it."
    )
    return found


# ---------------------------------------------------------------------------
# WFG-167 — 책임
# ---------------------------------------------------------------------------


def test_the_responsibility_card_quotes_the_footer_the_code_actually_prints() -> None:
    """The card's strongest sentence is read from the constant that ships it.

    Graded by mutation: reword FOOTER_LINES[0] in
    src/wildfireguardian/delivery/printable.py and this goes red, which is the
    point — the card promises a judge a sentence on a piece of paper, so the
    code that puts it there is what the card is bound to.
    """
    footer = FOOTER_LINES[0]
    assert "최종 판단은 현장에서" in footer, (
        "FOOTER_LINES[0] no longer carries the on-site-decision clause: "
        + repr(footer) + ". The 책임 card's whole answer is that the printed "
        "sheet says this; change the card in the same commit."
    )
    assert _flat(footer) in _flat(_draft("16b")), (
        "Q16b's draft no longer quotes the sheet footer verbatim. The footer is "
        + repr(footer) + " and the card must say the same words the judge will "
        "read off the paper the student hands them."
    )


def test_every_committed_sheet_carries_the_footer_and_the_card_counts_them() -> None:
    """「33장 전부에 있습니다」 is derived here, not typed there."""
    sheets = _sheets()
    footer = FOOTER_LINES[0]
    missing = [str(p.relative_to(REPO)) for p in sheets
               if footer not in p.read_text(encoding="utf-8")]
    assert not missing, (
        "these committed sheets do not carry the footer the 책임 card promises "
        "is on all of them: " + ", ".join(missing[:5])
    )
    stated = re.search(r"커밋된 (\d+)장 전부에", _draft("16b"))
    assert stated is not None, (
        "Q16b no longer states how many sheets carry the footer in the form "
        "「커밋된 N장 전부에」. Either say it and let this gate check it, or say "
        "nothing — do not write a count this gate cannot find (critic #39)."
    )
    assert int(stated.group(1)) == len(sheets), (
        "Q16b says 커밋된 " + stated.group(1) + "장 and the tree holds "
        + str(len(sheets)) + " dispatch sheets. This is the 「여섯 개」 failure "
        "(WFG-178): a hand-typed count about this repository's own state, made "
        "wrong by a later commit. Update the card."
    )


def test_nothing_was_ever_sent_and_the_cards_count_the_manifests() -> None:
    """Both cards rest on this; it is two independent checks, not one."""
    manifests = _manifests()
    sent = [
        str(p.relative_to(REPO)) for p in manifests
        if json.loads(p.read_text(encoding="utf-8")).get("nothing_was_sent")
        is not True
    ]
    assert not sent, (
        "these manifests do not record nothing_was_sent: true — "
        + ", ".join(sent[:5]) + ". Q16b and Q20a both tell a judge that nothing "
        "has ever been transmitted to a resident. If that stopped being true, "
        "the cards are the thing to change, not this gate."
    )
    for qid in ("16b", "20a"):
        stated = re.search(r"기록 (\d+)개가 전부", _draft(qid))
        assert stated is not None, (
            "Q" + qid + " no longer states the manifest count in the form "
            "「기록 N개가 전부」, so nothing checks it"
        )
        assert int(stated.group(1)) == len(manifests), (
            "Q" + qid + " says 기록 " + stated.group(1) + "개 and "
            + str(len(manifests)) + " committed manifests carry the key"
        )


def test_no_send_receipt_exists_anywhere_in_the_tree() -> None:
    """An absence, checked as an absence.

    ``scripts/send_dispatch_email.py`` writes ``email_sent.json`` into the run
    directory when it actually sends. The card tells a judge that no such file
    exists; that is only worth saying because it is falsifiable by one glob.
    """
    receipts = [
        str(p.relative_to(REPO)) for p in REPO.rglob("email_sent.json")
        if ".auto" not in p.parts and ".git" not in p.parts
    ]
    assert not receipts, (
        "Q16b tells a judge that no send receipt exists in this repository and "
        "these do: " + ", ".join(receipts)
    )
    assert "`email_sent.json`" in _draft("16b"), (
        "Q16b no longer names email_sent.json, so this check is guarding a "
        "sentence the student does not say"
    )


def test_the_screen_and_the_script_still_say_what_the_card_says_they_say() -> None:
    """Three surfaces, one claim. The card cites the other two by their words."""
    screen = FINALS.read_text(encoding="utf-8")
    script = DEMO_SCRIPT.read_text(encoding="utf-8")
    assert SCREEN_SENTENCE in screen, (
        "web/finals.html no longer prints 「" + SCREEN_SENTENCE + "」. That "
        "sentence is why WFG-167 exists: the screen invites the responsibility "
        "question. If the screen changed, Q16b's third paragraph is now false."
    )
    assert SCRIPT_FRAGMENT in script, (
        "the demo script's 재난대응 실무자 one-liner no longer carries 「"
        + SCRIPT_FRAGMENT + "」"
    )
    draft = _draft("16b")
    assert SCREEN_SENTENCE in draft, (
        "Q16b no longer quotes the screen's sentence, so the card and the "
        "screen can drift apart again — which is the defect WFG-167 names"
    )


# ---------------------------------------------------------------------------
# WFG-181 — 개인정보
# ---------------------------------------------------------------------------


def test_a_household_is_a_graph_node_and_the_card_names_the_field() -> None:
    """「가구는 사람이 아니라 노드입니다」, checked against the committed artifact."""
    routing = json.loads(
        (REPO / "data" / "processed" / "rescue_routing.json").read_text(
            encoding="utf-8")
    )
    points = routing["dispatch_top20"]
    assert points, "dispatch_top20 is empty; the privacy card describes its rows"
    person_shaped = {"name", "address", "phone", "resident", "이름", "주소",
                     "전화", "연락처"}
    for point in points:
        leaked = person_shaped & set(point)
        assert not leaked, (
            "a dispatch point carries person-shaped fields " + str(sorted(leaked))
            + ". Q20a tells a judge that a 「가구」 here is a road-network node "
            "and a coordinate with nowhere for a name to go."
        )
    assert "home_node" in points[0], (
        "dispatch points no longer carry home_node, the field Q20a names as "
        "the whole of what a 「가구」 is here"
    )
    assert "`home_node`" in _draft("20a"), (
        "Q20a no longer names home_node, so a judge cannot check the claim"
    )


def test_the_elderly_signal_is_an_assumed_fraction_and_a_placeholder() -> None:
    """Q20a's second paragraph, re-derived from the artifact and the module."""
    routing = json.loads(
        (REPO / "data" / "processed" / "rescue_routing.json").read_text(
            encoding="utf-8")
    )
    assumed = routing["provenance"]["assumed"]
    assert "immobile_fraction" in assumed, (
        "immobile_fraction is no longer declared an ASSUMED value in the "
        "committed artifact's provenance. Q20a's answer to 「고령자를 어떻게 "
        "특정합니까」 is that it is an assumption and not an observation."
    )
    draft = _draft("20a")
    assert "`immobile_fraction`" in draft, "Q20a no longer names immobile_fraction"
    stated = re.search(r"`immobile_fraction` (\d+\.\d+)", draft)
    assert stated is not None, (
        "Q20a no longer states immobile_fraction's value beside its name"
    )
    assert float(stated.group(1)) == pytest.approx(assumed["immobile_fraction"]), (
        "Q20a says immobile_fraction is " + stated.group(1) + " and the "
        "committed artifact says " + str(assumed["immobile_fraction"])
    )

    module = (REPO / "src" / "wildfireguardian" / "utils"
              / "vulnerability.py").read_text(encoding="utf-8")
    assert "placeholder values" in module, (
        "vulnerability.py no longer declares its county scores placeholders. "
        "Q20a tells a judge that the elderly signal is not even ingested yet; "
        "if that changed, the card is what to change."
    )
    assert "자리표" in draft, (
        "Q20a no longer says the county score is a 자리표(placeholder), which "
        "is the honest half of its answer"
    )


def test_the_clusters_are_not_administrative_villages_on_every_sheet() -> None:
    """The DBSCAN sentence, in the README the card cites and on every sheet."""
    readme = (DISPATCH / "README.md").read_text(encoding="utf-8")
    assert "행정리" in readme and "DBSCAN" in readme, (
        "outputs/dispatch/README.md no longer states that the clusters are "
        "DBSCAN groupings and not 행정리 — the sentence Q20a cites"
    )
    sheets = _sheets()
    missing = [str(p.relative_to(REPO)) for p in sheets
               if "행정리" not in p.read_text(encoding="utf-8")]
    assert not missing, (
        "these sheets do not carry the 행정리 disclaimer that Q20a says is "
        "printed on all of them: " + ", ".join(missing[:5])
    )
    assert "행정리" in _draft("20a"), "Q20a no longer makes the 행정리 distinction"


def test_the_sms_drafts_count_places_and_never_a_person() -> None:
    """「곳을 셉니다」 — checked against the committed drafts, including phones."""
    drafts = sorted(DISPATCH.glob("*/*/sms_drafts.txt"))
    assert drafts, "no committed SMS drafts; Q20a quotes them"
    phone = re.compile(r"01[016789][- ]?\d{3,4}[- ]?\d{4}")
    for path in drafts:
        text = path.read_text(encoding="utf-8")
        hit = phone.search(text)
        assert hit is None, (
            "a committed SMS draft contains a phone-shaped number ("
            + hit.group(0) + ") in " + str(path.relative_to(REPO))
            + ". Q20a tells a judge these drafts hold no person."
        )
    assert "곳" in _draft("20a"), (
        "Q20a no longer makes the 「사람이 아니라 곳을 센다」 point"
    )


# ---------------------------------------------------------------------------
# Both cards — the refusal
# ---------------------------------------------------------------------------

#: Sentences neither card may contain. This repository has not read a statute,
#: taken legal advice, or been deployed, so each of these is an assertion it
#: cannot support — and each is the *reassuring* direction, which is the one a
#: student under interview pressure drifts toward.
FORBIDDEN_ASSURANCES = (
    (r"법적으로\s*문제\s*없", "a legal opinion this repository cannot give"),
    (r"법적\s*책임(?:은|이)?\s*없", "a legal opinion this repository cannot give"),
    (r"면책(?:입니다|됩니다|이\s*됩니다)", "an indemnity claim with no source"),
    (r"개인정보(?:를)?\s*전혀\s*(?:쓰지|사용하지)\s*않습니다",
     "a flat universal; WC-009's register applies (say what arrived, and at "
     "what granularity)"),
    (r"개인정보\s*문제(?:는|가)?\s*없", "a legal opinion this repository cannot give"),
)


@pytest.mark.parametrize("qid", ["16b", "20a"])
def test_neither_card_asserts_a_legal_conclusion(qid: str) -> None:
    """The refusal is the load-bearing half of both answers.

    Note what is scanned: the *draft the student speaks*, not the whole card.
    Both 없는 것 blocks quote these sentences with a ❌ in front of them, which
    is the correct place for them and must not trip the gate.
    """
    draft = _draft(qid).split("근거:", 1)[0]
    for pattern, why in FORBIDDEN_ASSURANCES:
        hit = re.search(pattern, draft)
        assert hit is None, (
            "Q" + qid + "'s draft answer says " + repr(hit.group(0)) + ": "
            + why + ". This repository has read no statute and taken no legal "
            "advice; the card's job is to say so and then describe the object."
        )


@pytest.mark.parametrize("qid", ["16b", "20a"])
def test_both_cards_refuse_the_legal_question_in_writing(qid: str) -> None:
    body = _card(qid)
    assert "법령" in body, (
        "Q" + qid + " no longer says, in its own words, that this repository "
        "has not read the law. Without that sentence the card is a reassurance "
        "rather than an answer, and WFG-167's row forbids exactly that."
    )
    assert "없는 것:" in body, "Q" + qid + " has no 없는 것 block"
