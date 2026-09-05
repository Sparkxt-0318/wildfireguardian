"""`docs/auto/finals/BOOTH_SETUP.md` — the claims in it that a machine can check.

WFG-037, KCF_READINESS R3 (booth half). A booth procedure is a document of assertions
about a laptop nobody in this repository has touched, and the half that a test can
reach is the mechanical half: does every file it sends the student to exist, does every
`make` target it names exist, and is every key its table tells the student to press
actually bound in the screen that will be on the laptop?

The half a test cannot reach is the rehearsal, which is NH-014 / R12, and the document
says so at the top and again in §8. This file does not pretend otherwise.

Nothing here reads the clock, the network, or anything outside the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "auto" / "finals" / "BOOTH_SETUP.md"
SCREEN = REPO / "web" / "finals.html"
MAKEFILE = REPO / "Makefile"

TEXT = DOC.read_text(encoding="utf-8")


def test_the_document_exists_and_names_its_row_and_readiness_lines():
    assert DOC.is_file()
    head = TEXT.split("---", 1)[0]
    assert "WFG-037" in head
    assert "R3" in head and "R9" in head


def test_every_repository_path_the_document_sends_the_student_to_exists():
    # Backticked paths that look like repository paths. `web/demo-media/*.mp4` and the
    # release payload are deliberately absent from a clean clone and are excluded by
    # name, with the document saying why in 2.1 and in the finals-bundle doc.
    absent_by_design = {
        "web/demo-media/intro-forest-loop.mp4",
        "web/demo-media/ambient-documentary.mp3",
        "release/kcf-finals-2026/",
        "release/.../web/finals.html",
        "data/raw/firms_data/",
        "docs/auto/finals/BOOTH_SETUP.md",  # this file, referred to as the target
    }
    candidates = set(re.findall(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+)`", TEXT))
    for rel in sorted(candidates):
        if rel in absent_by_design or rel.endswith("/"):
            continue
        assert (REPO / rel).exists(), f"BOOTH_SETUP.md sends the student to {rel!r}, which is not in the tree"


def test_every_make_target_the_document_names_exists():
    targets = set(re.findall(r"`make ([a-z][a-z0-9-]*)", TEXT))
    assert targets, "the document names no make target, which cannot be right"
    declared = set(re.findall(r"^([a-z][a-z0-9_-]*):", MAKEFILE.read_text(encoding="utf-8"), re.M))
    missing = targets - declared
    assert not missing, f"BOOTH_SETUP.md names make targets that do not exist: {sorted(missing)}"


#: Every key the document tells the student to press, and the fragment of
#: `web/finals.html` that binds it. The point of the pairing is that a key
#: rebound in the screen turns this red instead of turning the booth silent.
KEY_BINDINGS = {
    "Enter": "ev.key === 'Enter'",
    "G": "case 'g': case 'G':",
    "Esc": "case 'Escape':",
    "Space": "case ' ':",
    "R": "case 'r': case 'R':",
    "F": "case 'f': case 'F':",
    "M": "case 'm': case 'M':",
    "ArrowRight": "case 'ArrowRight':",
    "ArrowLeft": "case 'ArrowLeft':",
    "1234": "case '1': case '2': case '3': case '4':",
}


def test_every_key_the_document_teaches_is_bound_in_the_screen():
    screen = SCREEN.read_text(encoding="utf-8")
    for name, fragment in KEY_BINDINGS.items():
        assert fragment in screen, f"BOOTH_SETUP.md teaches {name}, which web/finals.html does not bind"


def test_the_document_actually_mentions_each_of_those_keys():
    """The other direction: a binding this file lists must be one the document teaches."""
    tokens = {
        "Enter": "**Enter**",
        "G": "**G**",
        "Esc": "**Esc**",
        "Space": "**Space**",
        "R": "**R**",
        "F": "**F**",
        "M": "**M**",
        "ArrowRight": "→",
        "ArrowLeft": "←",
        "1234": "**1 2 3 4**",
    }
    for name, token in tokens.items():
        assert token in TEXT, f"{name} is graded against the screen but the document does not teach it"


def test_the_document_does_not_tell_the_student_that_the_builder_checks_the_usb():
    """The defect this row found. `make finals-bundle` overwrites before it hashes."""
    assert "check_bundle_copy.py" in TEXT
    assert "make finals-bundle` 은 USB 검사가 아닙니다" in TEXT


def test_the_checker_the_document_relies_on_travels_inside_the_bundle():
    builder = (REPO / "scripts" / "build_finals_bundle.py").read_text(encoding="utf-8")
    assert '("scripts/check_bundle_copy.py", "check_bundle_copy.py")' in builder, (
        "BOOTH_SETUP.md §7.2 tells the student to run the checker on a borrowed machine "
        "from the USB copy, so it has to be in the bundle payload"
    )


def test_the_document_says_all_checks_is_not_the_booth_morning_command():
    """R3 names `make all-checks`; it aborts at baseline-verify on the laptop too."""
    assert "make all-checks" in TEXT
    assert "NH-029" in TEXT
    assert "gates.py --mode full" in TEXT


def test_the_unmeasured_half_is_named_where_it_is_read():
    assert TEXT.count("NH-014") >= 2
    assert "R12" in TEXT
    assert "WFG-007" in TEXT, "the missing printables hold the third fallback step"
