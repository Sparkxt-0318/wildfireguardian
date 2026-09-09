"""The region-literal gate must read a place name, not a syllable (WFG-194).

`scripts/check_region_literals.py` exists because a per-region value typed into a
screen string is correct for the region the author is looking at and wrong for the
other two. Its region-name branch was a bare substring test, and 의성 (Uiseong) is
also the last two syllables of 창의성 (creativity) -- a 20-point row on both KCF
scoring tables which this project has to be able to name on the finals screen. The
gate read the card title 「창의성 · 이 작품이 직접 만든 것」 as a claim about Uiseong.

The narrowing is one rule: a region name counts only where it STARTS a word, i.e.
is not preceded by a Hangul syllable. These tests grade both directions, because a
narrowing that is not graded is a hole. The last test states, in a passing
assertion, the case the rule deliberately cannot see, so the limit is a fact of the
suite rather than a sentence in a comment.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gate():
    path = REPO / "scripts" / "check_region_literals.py"
    spec = importlib.util.spec_from_file_location("check_region_literals", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # The module defines a @dataclass under `from __future__ import
    # annotations`, and dataclasses resolves the annotation module by name, so
    # the module has to be in sys.modules before its body runs.
    sys.modules["check_region_literals"] = mod
    spec.loader.exec_module(mod)
    return mod


def _hits(gate, line: str) -> list[str]:
    found = gate.check_text(line, "scripts/finals.template.html", suffix=".html")
    return [f.what for f in found if "region name" in f.what]


def test_the_creativity_row_is_not_a_region_claim(gate):
    """창의성 must be sayable on a screen. This is the defect that was found."""
    assert _hits(gate, "      ? '창의성 · 이 작품이 직접 만든 것'") == []


def test_a_real_region_name_still_fires(gate):
    """The gate's own reason for existing is untouched by the narrowing."""
    assert _hits(gate, "    note.textContent = '의성·안동에서 368곳입니다';")
    assert _hits(gate, "    note.textContent = '경북 의성 지역입니다';")
    assert _hits(gate, "    note.textContent = '영덕 보행망입니다';")


def test_a_particle_attached_to_the_name_still_fires(gate):
    """The trailing half of a word boundary must NEVER be added here.

    Korean particles attach directly to the noun -- 영덕에서는, 의성군, 울진의 --
    and Hangul syllables are word characters, so a symmetric rule
    `(?<![가-힣])<name>(?![가-힣])` looks tidier and blinds the gate to the way
    these names are ordinarily written on a screen. WFG-194's independent
    reviewer made exactly that edit while probing the narrowing; measured, it
    suppresses 영덕에서는, 의성군 and 울진의 while still passing every other test
    in this file, which is why this one exists. It is the same trap
    `tests/test_creativity_card.py` records for a trailing `\b` after Hangul.
    """
    assert _hits(gate, "    note.textContent = '영덕에서는 458곳입니다';")
    assert _hits(gate, "    note.textContent = '의성군 자료입니다';")
    assert _hits(gate, "    note.textContent = '울진의 결과입니다';")


def test_a_compound_of_two_region_names_is_still_caught(gate):
    """울진삼척 has no separator, but 울진 still starts the word."""
    assert _hits(gate, "    note.textContent = '울진삼척 결과';")


@pytest.mark.xfail(strict=False, reason=(
    "the narrowing cannot see a place name glued to a non-region noun; recorded "
    "as an xfail so a later lap that closes the hole makes this XPASS instead of "
    "breaking a green assertion"))
def test_the_limit_the_narrowing_accepts_is_stated_as_a_test(gate):
    """A place name glued to a non-region noun escapes, and that is recorded.

    `경북의성군` is not a spelling this repository writes -- every Korean region
    label on a screen is read from `region_label_kr`, which returns 「영덕 2025」,
    「의성·안동 2025」 and 「울진·삼척 2022」, all word-initial -- but the rule
    cannot see it, and a limit written only in a comment is a limit nobody
    re-checks.

    ⚠ **Written as an xfail rather than as `assert _hits(...) == []`**, which is
    how it was first written and what WFG-194's independent reviewer objected to:
    a green assertion that pins a LIMITATION is a ratchet pointing the wrong way,
    because the lap that closes the hole then has to delete a passing test to
    ship the fix. The assertion below is the one that SHOULD hold; today it does
    not, and that is the fact being recorded.
    """
    assert _hits(gate, "    note.textContent = '경북의성군 지역입니다';")
