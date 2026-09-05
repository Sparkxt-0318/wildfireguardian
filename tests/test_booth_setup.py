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


#: Every key the document tells the student to press, and the WHOLE binding in
#: `web/finals.html` — the `case` label together with what it does.
#:
#: ⚠ The first version of this table held the `case` labels alone, and the lap's own
#: independent reviewer showed what that is worth: it rebound `g` from
#: `setView('live'); GUIDED.start(0)` to `GUIDED.exit()` and reversed `ArrowRight` to
#: `GUIDED.prev()`, making two rows of §6 false, and this file stayed green. A booth
#: does not suffer a deleted `case` label; it suffers a key that now does something
#: else. So the action travels with the label.
KEY_BINDINGS = {
    "Enter": "if (ev.key === 'Escape' || ev.key === 'Enter') hideIntro(ev.key === 'Enter');",
    "G": "case 'g': case 'G': setView('live'); GUIDED.start(0); break;",
    "Esc": "    case 'Escape':\n      if (GUIDED.active()) GUIDED.exit();",
    "Space": "case ' ': setPlaying(!state.playing); ev.preventDefault(); break;",
    "R": "case 'r': case 'R': resetScenario(); break;",
    "F": "case 'f': case 'F': toggleFullscreen(); break;",
    "M": "case 'm': case 'M': setSound(!state.sound); break;",
    "ArrowRight": "case 'ArrowRight': if (GUIDED.active()) GUIDED.next(); break;",
    "ArrowLeft": "case 'ArrowLeft': if (GUIDED.active()) GUIDED.prev(); break;",
    "1234": (
        "case '1': case '2': case '3': case '4':\n"
        "      if (state.view === 'live') GUIDED.jump(Number(ev.key) - 1);"
    ),
}


def test_every_key_the_document_teaches_does_in_the_screen_what_the_document_says():
    screen = SCREEN.read_text(encoding="utf-8")
    for name, fragment in KEY_BINDINGS.items():
        assert fragment in screen, (
            f"BOOTH_SETUP.md §6 teaches {name}, and web/finals.html no longer binds it "
            f"to what the document says it does"
        )


def test_the_document_does_not_tell_the_student_the_language_button_should_read_ko():
    """The one sentence the reviewer blocked this row for, pinned so it cannot come back.

    `web/finals.html` labels the language button with the language a press would switch
    TO, so a Korean screen shows `EN`. Three documents told the student to check for
    `KO`, which is the instruction that switches the judged demo into English ten
    minutes after registration.
    """
    screen = SCREEN.read_text(encoding="utf-8")
    assert "$('btnLang').textContent = lang === 'ko' ? 'EN' : 'KO';" in screen, (
        "the language button's label mapping changed; §5.6 of BOOTH_SETUP.md, "
        "release/kcf-finals-2026/README_KO.md and docs/auto/DEMO_SCRIPT_5MIN.md all "
        "explain it and have to be re-read"
    )
    for doc in (
        DOC,
        REPO / "release" / "kcf-finals-2026" / "README_KO.md",
        REPO / "docs" / "auto" / "DEMO_SCRIPT_5MIN.md",
    ):
        text = doc.read_text(encoding="utf-8")
        assert "언어가 **KO**" not in text, (
            f"{doc.name} tells the student to check that the language button reads KO; "
            f"on a Korean screen it reads EN, and pressing it switches the demo to English"
        )
    assert "누르지 마십시오" in TEXT, "the recipe has to say not to press it"


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
