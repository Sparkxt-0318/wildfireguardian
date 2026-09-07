"""The screen -> key mapping table is bound to the template that draws it (WFG-110).

Readiness line R1 asks that every on-screen number map to a `docs/NUMBERS.json`
key with the mapping table committed. `docs/finals_screen_numbers.md` is that
table and this is the gate that keeps it true, so that a card added tomorrow
cannot ship with a number no committed document explains.

⚠ What these tests can and cannot do, said here because the document says it too.
They compare two artifacts written by different means - a table a lap filled in
by reading `scripts/finals.template.html`'s eight card blocks by hand, and a
derivation of the same relation from the template's syntax
(`scripts/finals_screen_keys.py`). Agreement is evidence that the table is not
stale. It is NOT evidence that the attribution is right: both could be wrong the
same way, and no test here opens a browser. `mandela` names that limit and the
document records it in §4 rather than hiding it.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "finals_screen_numbers.md"
SCRIPT = REPO / "docs" / "auto" / "DEMO_SCRIPT_5MIN.md"
REGISTRY = REPO / "docs" / "NUMBERS.json"

sys.path.insert(0, str(REPO / "scripts"))
import finals_screen_keys as fsk  # noqa: E402

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HEADER = "| # | 뷰 | 카드 (kicker) | 레지스트리 키 | 그 카드에서 하는 일 | §3 |"


@pytest.fixture(scope="module")
def doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def derived() -> dict:
    return fsk.derive()


def _rows(text: str) -> list[dict]:
    """Rows of §2's table: (#, 뷰, 카드, 키, 하는 일, §3)."""
    rows: list[dict] = []
    in_table = False
    for line in text.splitlines():
        if line.strip() == HEADER:
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 6 or set(cells[0]) <= {"-", ":"}:
                continue
            key = cells[3].strip("`")
            rows.append(
                {"n": cells[0], "view": cells[1], "card": cells[2], "key": key,
                 "does": cells[4], "in_demo_script": cells[5]}
            )
    return rows


def test_the_table_is_parseable_and_not_vacuous(doc_text, derived):
    """Without this, a changed header makes every other test read nothing."""
    rows = _rows(doc_text)
    assert len(rows) == len(derived) and rows, (
        "§2's table did not parse into one row per referenced key, so the "
        f"checks below are looking at nothing: parsed {len(rows)} rows against "
        f"{len(derived)} keys derived from {fsk.TEMPLATE.name}. If the header "
        f"changed, HEADER in this file must change with it."
    )
    assert len({r["key"] for r in rows}) == len(rows), "a key is listed twice in §2"

    # The two counts the document states in prose (§1's 「여덟 개」 and §2's 「카드 8개,
    # 키 28개」) are bound here rather than left to go stale silently: CHARTER §3.3 asks
    # that a number in prose trace to a committed artifact, and the artifact for these
    # two is the template. Found by the independent reviewer of the lap that wrote them.
    n_cards = len({r["card"] for r in rows})
    text = DOC.read_text(encoding="utf-8")
    assert f"카드 {n_cards}개, 키 {len(rows)}개" in text, (
        f"§2's prose count is stale: the table now covers {len(rows)} keys across "
        f"{n_cards} cards."
    )
    korean_numerals = {6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열"}
    expected = korean_numerals.get(n_cards, str(n_cards))
    said = re.findall(r"카드 블록 (\S+?) ?개", text)
    assert said and set(said) == {expected}, (
        f"§1 and the header say how many card blocks were read by hand and they must "
        f"all say the same thing: the template has {n_cards} ({expected}), the document "
        f"says {sorted(set(said))}. Changing one occurrence and not the other is the "
        "failure this checks for."
    )


def test_the_table_covers_exactly_the_keys_the_template_references(doc_text, derived):
    """The failure this row exists for: a new card ships a number nothing explains."""
    in_doc = {r["key"] for r in _rows(doc_text)}
    in_template = set(derived)
    assert in_doc == in_template, (
        "the finals screen and its mapping table have drifted. On the screen "
        f"but unmapped: {sorted(in_template - in_doc)}; mapped but no longer "
        f"drawn: {sorted(in_doc - in_template)}. A judge pointing at the first "
        "group gets no answer from any committed document."
    )


def test_every_key_in_the_table_resolves_in_the_registry(doc_text):
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["numbers"]
    rows = _rows(doc_text)
    unresolved = [r["key"] for r in rows if r["key"] not in registry]
    assert not unresolved, (
        "the mapping table names registry keys that do not exist, so the answer "
        f"it gives a judge traces to nothing: {unresolved}"
    )
    malformed = [r["key"] for r in rows if not KEY_RE.match(r["key"])]
    assert not malformed, f"not registry keys: {malformed}"


def test_every_row_names_the_card_the_template_puts_the_key_on(doc_text, derived):
    wrong = []
    for row in _rows(doc_text):
        expected = derived.get(row["key"], {}).get("card")
        if expected is not None and row["card"] != expected:
            wrong.append((row["key"], row["card"], expected))
    assert not wrong, (
        "a key moved between cards and the table still names the old one, so "
        "the student would point at the wrong card: "
        + "; ".join(f"{k}: table says {got!r}, template says {exp!r}" for k, got, exp in wrong)
    )


def test_every_row_names_the_view_that_builds_that_card(doc_text, derived):
    wrong = [
        (r["key"], r["view"], derived[r["key"]]["view"])
        for r in _rows(doc_text)
        if r["key"] in derived and r["view"] != derived[r["key"]]["view"]
    ]
    assert not wrong, (
        "a card moved between the 근거 and 신뢰성 views (evCard vs rel) and the "
        f"table did not follow: {wrong}"
    )


def test_no_key_is_attributed_to_more_than_one_card(derived):
    """The derivation reports ambiguity rather than picking; that must stay empty."""
    ambiguous = {k: v["card"] for k, v in derived.items()
                 if v["card"] is None or str(v["card"]).startswith("AMBIGUOUS")}
    assert not ambiguous, (
        "scripts/finals_screen_keys.py could not attribute these keys to exactly "
        f"one card, so §2's table cannot be trusted for them: {ambiguous}"
    )


def test_the_six_keys_absent_from_the_demo_script_are_named_here(doc_text, derived):
    """§3's list is a claim about a set difference; re-derive it rather than trust it."""
    script_text = SCRIPT.read_text(encoding="utf-8")
    cited: set[str] = set()
    in_table = False
    for line in script_text.splitlines():
        if line.startswith("| 구간 | 값 |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            for token in re.findall(r"`([^`]+)`", line):
                if KEY_RE.match(token):
                    cited.add(token)
    missing = set(derived) - cited
    section = doc_text.split("## 3.", 1)[-1].split("## 4.", 1)[0]
    named = {t for t in re.findall(r"`([^`]+)`", section) if KEY_RE.match(t)}
    assert named == missing, (
        "§3 lists the keys the screen draws but the 5-minute script never "
        f"speaks. Re-derived now: {sorted(missing)}; §3 names: {sorted(named)}"
    )
    # And the table's own ✅/❌ column must agree with the same set difference.
    rows = _rows(doc_text)
    disagree = [r["key"] for r in rows
                if (r["in_demo_script"] == "❌") != (r["key"] in missing)]
    assert not disagree, f"§2's §3 column disagrees with the script's own table: {disagree}"
