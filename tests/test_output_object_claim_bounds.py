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
    SAME block, say what was synthetic in the run that produced them, that the origins
    were sampled, and that no dispatch document has yet been made on a real spread
    surface — and it may not assert the reverse of any of those.

Three consequences of writing it that way:

* it cannot be satisfied by **deleting** the claim - ``test_every_surface_still_makes_the
  _existence_claim`` fails if a surface goes quiet, because a silent surface is how the
  screen carried this for a day;
* it is **per-surface and per-block**, so a bound two screens away does not pay for a claim
  here, which is the ``12b8ac7`` failure and the reason CHARTER §3 rule 3 exists;
* it is **graded against text this file's author did not write** - the six blocks the
  repository shipped at ``3eec471`` - after this lap's independent reviewer blocked a first
  version whose mutation was derived from its own patterns and therefore could not fail;
* it reads **polarity**, because the same reviewer beat the token checks with a block that
  carried every required word and asserted the opposite of all of them;
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

⚠ **What this file cannot catch, measured rather than guessed.** It reads seven blocks
named by path and marker, and the count is itself the evidence: the row named five, the
lap's own sweep found a sixth, registering ``WC-013`` found three more surfaces outside
this file's remit, and the independent reviewer found two the registry's first pattern
missed. An eighth surface that acquires the claim tomorrow is invisible to it until
someone adds it here, exactly as ``docs/withdrawn_claims.md`` §4 records for the
withdrawn-claim registry: this is a structural ratchet over a **declared** list, not a claim
detector over the tree. ``docs/auto/withdrawn_claims.json`` ``WC-013`` is the half that does
scan every gated file, and it catches a copied spelling rather than a reworded one. Neither
closes the class; together they cover the two ways this defect has actually travelled -
copy-paste, and a new surface built from an old one.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""

from __future__ import annotations

import re
import subprocess
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

#: ⚠ THE POLARITY ANCHOR, AND THIS FILE'S FIRST VERSION DID NOT HAVE ONE. The independent
#: reviewer blocked it with a block that carried every token above and asserted their
#: OPPOSITE — 「이 실행에는 합성 위험면도 표본 좌표도 쓰이지 않았습니다, 모두 실제입니다」 —
#: which passed four token-presence assertions while telling a judge exactly the thing
#: WC-013 withdrew. Token presence is not polarity. So the bound must also carry the
#: consequence: the dispatch document made on a real spread surface DOES NOT EXIST YET,
#: with the object and the absence in one clause rather than two screens apart.
#: ⚠ The gap class is ``[^.。]`` and NOT ``[^.。\n]``, deliberately and after a red run.
#: These blocks are hard-wrapped prose, and the first draft of this pattern excluded the
#: newline — so 「출동 지시서는\n아직 없습니다」 in the printed related-work panel escaped it.
#: That is the same line-break hole this lap measured in ``check_withdrawn_claims.py`` and
#: published as ``docs/withdrawn_claims.md`` §4 item 7; a gate written in the same lap that
#: named it is the last place it should reappear. The sentence terminator still bounds the
#: gap, so the object and the absence must be in one sentence.
_NOT_YET = re.compile(
    r"(?:출동\s*지시서|출동\s*문서|dispatch\s+(?:sheet|document))[^.。]{0,40}?"
    r"(?:아직\s*없|아직\s*아니|yet\s+been\s+made|not\s+yet\s+been)"
)

#: And the reverse assertion is refused outright rather than merely unrewarded, because the
#: reviewer's exploit is a sentence somebody will one day write in good faith while
#: 「tidying」 a caveat. This is the reviewer's mutation turned into a property.
_DENIES = re.compile(
    r"합성[^.。\n]{0,30}(?:아니|않)|(?:모두|전부|다)\s*실제입니다"
    r"|(?:hazard|terrain|origins)[^.\n]{0,40}(?:are|were)\s+(?:all\s+)?real"
)


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
    # ⚠ Added by this lap's independent reviewer, which blocked the first version of this
    # file for leaving it out. The lap's own commit message and MEMO make this panel the
    # PROOF that 「a lap that fixes the surfaces on the list has fixed the list, not the
    # claim」 — and then did not put it on the list. It is printed in the booth kit.
    (
        "docs/auto/finals/RELATED_WORK_PANEL.md, the front-panel claim",
        "docs/auto/finals/RELATED_WORK_PANEL.md",
        "산림청 국립산림과학원의 산불확산예측시스템은",
        "## 뒷면 1",
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


def test_every_existence_claim_says_the_real_fire_sheet_does_not_exist_yet(surface) -> None:
    """The polarity anchor. Four token checks are not four claims — see ``_NOT_YET``."""
    label, block = surface
    assert _NOT_YET.search(block), (
        f"{label} names the synthetic hazard and the sampled origins and never says the "
        "thing they add up to: that no dispatch document has yet been produced on a real "
        "spread surface. A block can carry both nouns and assert their opposite, which is "
        "what this lap's independent reviewer demonstrated; the consequence is what makes "
        "the bound a bound rather than a vocabulary list."
    )


def test_no_surface_asserts_the_committed_run_was_real(surface) -> None:
    """The reviewer's inversion, refused rather than merely unrewarded."""
    label, block = surface
    hit = _DENIES.search(block)
    assert not hit, (
        f"{label} asserts that the run which produced the committed dispatch documents was "
        f"real ({hit.group(0)!r}). data/processed/rescue_routing.json → provenance.sources "
        "says hazard: synthetic, terrain: synthetic, origins: sampled candidates. If that "
        "artifact ever changes, this assertion is the one to re-derive first — and it is "
        "changed by re-running the pipeline, not by editing this string."
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
    if not _NOT_YET.search(block):
        out.append("not-yet")
    if _HOUSEHOLD.search(block):
        out.append("household-register")
    if _DENIES.search(block):
        out.append("denies-the-synthetic-run")
    return out


#: ⚠⚠ THE GRADING CORPUS, AND THE FIRST VERSION OF THIS FILE DID NOT HAVE ONE.
#: It graded itself: it built a mutation by deleting every substring matching ``_SYNTHETIC``
#: and ``_SAMPLED``, then asserted that ``_missing()`` — which is those same two regexes —
#: reported them missing. That cannot fail by construction. It is ``mandela`` pattern #4,
#: tautology, and pattern #3, one definition serving as both the scorer and the thing
#: scored; the independent reviewer blocked the lap on it and this corpus is the repair.
#:
#: These six blocks are what the repository ACTUALLY SHIPPED at ``3eec471``, before this
#: lap touched anything. They were written by five earlier laps over six days, none of
#: which had seen these patterns, so nothing here was drawn to fit the check.
#: ``test_the_corpus_is_the_text_that_actually_shipped`` re-derives them from git and
#: refuses a corpus that has drifted into something hand-tuned.
#: ⚠ ``web/finals.html`` has no entry: it is GENERATED from
#: ``scripts/finals.template.html`` by ``make finals``, so its pre-fix text is that
#: template's pre-fix text and a second copy would grade the same prose twice. It stays in
#: ``SURFACES`` because it is the file five judges actually look at.
_PRE_FIX_COMMIT = "3eec471"

_PRE_FIX_BLOCKS: tuple[tuple[str, str], ...] = (
    (
        'README.md §5 item ①',
        '- **① 산출물 자체가 기여입니다.** 확산 예측 격자는 최종 결과물이 아니라 중간 입력이고,\n  이 시스템이 내놓는 것은 **가구 단위의 「걸어서 나갈 수 있는가 / 구조를 보내야 하는가」\n  판정과 그 도보 경로**입니다. 예측 정확도로 겨루지 않고 산출물의 모양으로 겨루는 쪽을\n  택했다는 뜻입니다. **그 산출물의 실물이 저장소에 커밋돼 있습니다** — 마을별 A4 출동\n  지시서, 마을방송 낭독 문안, 문자 초안이고, 어느 것도 발송되지 않았습니다.\n  → 실물과 그 한계: [`outputs/dispatch/README.md`](outputs/dispatch/README.md)\n  → 정확도로 겨루지 않기로 한 판단의 근거:\n  [`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`](docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md)\n',
    ),
    (
        'the finals screen template, CREATIVE item ①',
        "ko_h: '내놓는 것은 지도가 아니라 판정입니다',\n    ko_b: '확산 예보 격자는 중간 입력이고, 산출물은 가구 단위의 대피 판정과 걸어 나갈 경로, 그리고 마을 단위 출동 목록입니다. 그 실물이 저장소에 커밋돼 있습니다 - 마을별 A4 출동 지시서, 방송 문안, 문자 초안이며 어느 것도 발송되지 않았습니다.',\n    en_h: 'The output is a decision, not a map',\n    en_b: 'The spread forecast grid is an intermediate input. What comes out is a per-household evacuation verdict, the walking route that goes with it, and a village-level dispatch list. Committed instances of that object are in the repository - the A4 dispatch sheet, the broadcast script and the SMS drafts for each village cluster, none of them ever sent.',\n    doc: 'outputs/dispatch/20260801T163042Z/01-거무역리공원-북쪽/dispatch_a4.html · outputs/dispatch/README.md · docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md §3',\n  },\n  {\n    ",
    ),
    (
        'docs/auto/JUDGE_QA.md Q29a, spoken item 1 (tier T0)',
        '**첫째, 만든 물건이 다릅니다.** 저희가 내놓는 것은 위험도 지도가 아니라 **어느 집을 먼저\n가고 어느 길로 걸어 나오는가**입니다. 예보 격자가 최종 산출물이 아니라 중간 입력이고, 그\n뒤에 가구 단위 구조 순서와 보행 경로가 붙습니다. 그래서 저희가 답하는 질문은 「불이 어디로\n가는가」가 아니라 **「불이 어디로 갈지를 알면 어느 집을 먼저 구해야 하는가가 달라지는가」**\n입니다. 이건 더 정확한 예보라는 주장이 아니라 **다른 질문**이라는 뜻입니다. **말씀만\n드리는 게 아니라 실물을 열어 드릴 수 있습니다** — `outputs/dispatch/` 에 마을별 A4 출동\n지시서와 방송 문안, 문자 초안이 커밋돼 있고, 어느 것도 발송된 적이 없습니다. 「마을」이\n행정리가 아니라 공간 군집이라는 것도 그 지시서마다 박스로 적혀 있습니다.\n\n',
    ),
    (
        'docs/auto/DEMO_SCRIPT_5MIN.md, the 도입 segment',
        '### 도입 (0:00 → 0:37) · 37초 · 숫자 없음\n\n> 「2025년 3월 경북 산불 때, 이 문제를 풀려고 만들었습니다.\n> 산불 대응에서 지도가 답하는 질문은 보통 **「불이 지금 어디 있는가」** 입니다.\n> 저는 다른 질문을 풀었습니다. **「불이 다음에 어디로 갈 것이며, 그래서 지금 어느\n> 길로 걸어 나가야 하는가」.**\n> 심사기준이 첫 줄에 두는 **창의성**에 대한 제 답이 그것입니다. 내놓는 것이 확산\n> 지도가 아니라 **가구 단위 판정과 걸어 나갈 길**입니다.\n> 이 화면은 인터넷 없이 이 노트북에서 도는 완제품이고, 지금 보시는 모든 숫자는\n> 커밋된 산출물에서 빌드 때 읽어 온 값입니다. 화면 안에서 계산하는 값은 없습니다.」\n\n⚠ **창의성 문장은 여기서 끝냅니다 — 나머지 둘은 화면에 있습니다** (WFG-194).\n창의성은 두 채점표 **모두에서 20점**이고, 심사개요의 심사기준 한 줄이 그것을 **맨 먼저**\n부릅니다 — 「단순 암기 발표 지양; 창의성, 과학적 원리, 과학적 사고 중점」\n(`docs/auto/RUBRIC.md`). 채점표 **안에서는** 다섯 행 중 넷째 줄이니, 심사위원이 채점표를\n들고 있을 때 「맨 앞 항목」이라고 말하지 마십시오. 위에서 말한 것은 세 가지 중 첫 번째이고, 나머지 둘 —\n「실제 보행망과 전방 시뮬레이션 확산면이 **한 실행 안에서 동시에 실제**인 실행」과\n「**철회한 주장을 기계가 읽도록 등록**한다」 — 은 **시스템 구조 탭 아래쪽의\n「창의성 · 이 작품이 직접 만든 것」** 블록에 근거 파일 경로와 함께 떠 있습니다.\n심사위원이 「무엇이 새롭습니까」라고 물으면 그 탭을 열고 세 칸을 짚으십시오.\n**「그 산출물을 하나 보여 주십시오」라고 하면 탭이 아니라 파일을 여십시오** —\n`outputs/dispatch/` 에 마을별 A4 출동 지시서와 방송 문안, 문자 초안이 커밋돼 있고,\n발송된 것은 없습니다. 깊은 답은 `docs/auto/JUDGE_QA.md` **Q29a**, 설계 이유와 한계는\n[`docs/creativity_card.md`](../creativity_card.md) 입니다.\n**이 문단은 대본이 아니라 질의응답용이며, 300초 배분에 들어가지 않습니다.**\n\n⚠ **스스로 「독창적입니다」라고 말하지 마십시오.** 이 프로젝트의 창의성 카드는\n**만든 것을 적을 뿐 점수를 매기지 않는다**는 것이 설계 전부이고, 화면 블록도 같은\n등록(register)으로 쓰여 있습니다. 창의적인지 아닌지는 심사위원이 쓰는 문장입니다.\n`tests/test_creativity_card.py` 가 카드·화면·이 대본 세 곳에서 그 규칙을 검사합니다.\n\n화면: 인트로. **Enter** 또는 「시연 시작」.\n\n',
    ),
    (
        "docs/creativity_card.md, the method table's item 1",
        '| 1 | the **output object** is the contribution — a rescue order and a walking route per household, with the forecast grid as an intermediate input rather than the deliverable | `outputs/dispatch/README.md` and the committed sheets beside it, e.g. `outputs/dispatch/20260801T163042Z/01-거무역리공원-북쪽/dispatch_a4.html` (an instance of the object); `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3 (why the choice is not to compete on accuracy) |',
    ),
    (
        'docs/auto/finals/RELATED_WORK_PANEL.md, the front-panel claim',
        '산림청 국립산림과학원의 산불확산예측시스템은 **진화 지휘관**을 위한 콘솔이고,\n경기도 G-DAPS 는 **민방위 경보 담당자**를 위한 예측 모델입니다. 둘 다 확산을\n예측합니다. 이 프로젝트가 만드는 것은 예측 그 자체가 아니라 **가구 단위의 대피\n경로와 구조 출동 순서**이고, 그 판단이 예측 때문에 바뀐다는 것을 커밋된 공개\n자료 위에서 보인 것입니다.\n\n---\n\n',
    ),
)


def test_the_shipped_blocks_all_pass(surface) -> None:
    """The whole check, as one call, on what is in the tree now."""
    label, block = surface
    assert not _missing(block), f"{label} fails the shipped check: {_missing(block)}"


@pytest.mark.parametrize("label,block", _PRE_FIX_BLOCKS, ids=[b[0] for b in _PRE_FIX_BLOCKS])
def test_every_pre_fix_block_is_refused(label: str, block: str) -> None:
    """The grading direction: the text this lap replaced must fail, and fail on the claim.

    ⚠ This is the assertion the first version of this file was pretending to make. The
    input is not derived from the patterns; it is six blocks of prose that shipped on
    judge-facing surfaces and were carried, uncorrected, past every gate this repository
    had. If a later rewrite of the families lets any of them through, the families no
    longer describe the defect.
    """
    missing = _missing(block)
    assert missing, (
        f"the PRE-FIX text of {label} passes this gate. That text is the defect WFG-222 "
        "exists for — it names the committed instances without saying the run that made "
        "them had a synthetic hazard surface — so a gate that accepts it is not the gate "
        "this file claims to be."
    )
    assert "household-register" in missing or "synthetic" in missing, (
        f"the PRE-FIX text of {label} is refused, but for none of the reasons the row is "
        f"about: {missing}. That is a gate failing for the wrong reason, which passes a "
        "test and protects nothing."
    )


def test_the_corpus_is_the_text_that_actually_shipped() -> None:
    """The corpus cannot be quietly tuned into something the patterns happen to fail on.

    ⚠ Skipped rather than failed when the clone cannot resolve the commit. CHARTER §4
    records that this routine's checkout is SHALLOW and that its depth is **not a
    constant** — 50 commits measured on 2026-09-07, 294 earlier, 531 unshallowed — so a
    test whose predicate is 「can this clone resolve X」 fires at the clone depth rather
    than on any defect. GitHub Actions runs at ``fetch-depth: 0`` and therefore always
    grades it; the skip reason says which of the two happened.
    """
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{_PRE_FIX_COMMIT}^{{commit}}"],
        cwd=REPO, capture_output=True, text=True,
    )
    if probe.returncode != 0:
        pytest.skip(
            f"this clone cannot resolve {_PRE_FIX_COMMIT}, so the corpus below cannot be "
            "re-derived here (CHARTER §4: the routine's checkout is shallow and its depth "
            "is not a constant). The corpus is still graded by the test above; only its "
            "provenance is unverified in this clone."
        )
    by_label = {label: (rel, start, end) for label, rel, start, end in SURFACES}
    for label, embedded in _PRE_FIX_BLOCKS:
        rel, start, end = by_label[label]
        shown = subprocess.run(
            ["git", "show", f"{_PRE_FIX_COMMIT}:{rel}"],
            cwd=REPO, capture_output=True, text=True,
        ).stdout
        i = shown.find(start)
        assert i >= 0, (
            f"{label}: {rel} at {_PRE_FIX_COMMIT} does not contain the marker {start!r}, "
            "so the corpus entry cannot be the block this gate reads today"
        )
        if end is None:
            j = shown.find("\n", i)
            derived = shown[i:] if j < 0 else shown[i:j]
        else:
            j = shown.find(end, i)
            derived = shown[i:j]
        assert derived == embedded, (
            f"{label}: the embedded pre-fix block is not byte-identical to "
            f"{_PRE_FIX_COMMIT}:{rel}. A corpus a lap can edit is a corpus a lap can tune "
            "until the patterns fail on it, which is the leakage this whole section exists "
            "to remove. Re-derive it from git rather than editing it here."
        )


#: The independent reviewer's own inversion, verbatim from its block of this lap. It carries
#: 합성, 표본 좌표, 지점 단위 and the existence claim, and asserts the opposite of all of it.
_REVIEWER_INVERSION = (
    "- **① …** 산출물은 지점 단위 판정이고, 그 실물이 저장소에 커밋돼 있습니다. "
    "이 실행에는 합성 위험면도 표본 좌표도 쓰이지 않았습니다 — 화재 위험면·지형·"
    "출발지 모두 실제입니다."
)


def test_the_reviewers_inversion_is_refused() -> None:
    """The exploit that blocked the first version of this file, kept as a regression.

    The first version returned ``[]`` on this sentence: every family was a token-presence
    check, and the sentence contains every token while denying every one of them. Two
    assertions were added for it — the polarity anchor and the refusal of the reverse
    claim — and this test is what keeps them honest if either is ever rewritten.
    """
    missing = _missing(_REVIEWER_INVERSION)
    assert "not-yet" in missing, (
        "the reviewer's inversion no longer fails the polarity anchor; _NOT_YET has been "
        "widened until a sentence that denies the bound satisfies it"
    )
    assert "denies-the-synthetic-run" in missing, (
        "the reviewer's inversion is no longer caught by _DENIES, which is the assertion "
        "written for this exact sentence"
    )


def test_the_household_register_ban_would_have_caught_the_pre_fix_text() -> None:
    """The five wordings critic #54 measured at ``3eec471``, kept as regression data.

    These are the sentences that stood on the judge-facing surfaces while ``README.md``'s
    lead block, in the same repository, denied them. They are data rather than prose so
    that a later rewrite of ``_HOUSEHOLD`` has to face them.
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
