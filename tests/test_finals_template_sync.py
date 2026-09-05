"""The judged screens are generated; this file refuses a hand-edit that outlives its source.

WFG-109, KCF_READINESS R4 (and R1's surface). `scripts/build_finals.py` builds the finals
screen by reading `scripts/finals.template.html` and replacing ONE placeholder,
`/*__DATA__*/`, with the JSON payload; `scripts/build_console.py` does the same for the
operator console. Every other byte of each output is its template's, so each pair is
identical line for line except that one line.

Why this test exists. WFG-103 corrected the STATIC VIEW caption in the OUTPUT by hand and
left the template carrying the sentence it had just established was false: the arm is
`naive`, which is fire-blind (`src/wildfireguardian/routing/evacuation.py:270`,
`docs/real_roads_real_hazard.md:50`), not a map that sees the fire now. Nothing was wrong
on the judged screen; the next `make finals` would have put the withdrawn claim back in
front of five judges, and no gate read the template.

The narrow version of this test compares the two STATIC VIEW captions. That is the shape
of the bug, not the class: the next hand-fix to a different generated line survives it the
same way. So the invariant here is the whole file, which is what the builders actually
promise, and the caption check below is kept only as the named regression it came from.
The console is included because it is the same mechanism on a second judged screen and was
clean when this file was written; the cost of holding it there is one table row.

Nothing here reads the clock, the network, or anything outside the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The builders' own placeholder, spelled the way they spell it so a rename there turns
#: this red rather than silently widening the exemption.
PLACEHOLDER = "/*__" + "DATA" + "__*/"

#: (template, built output, the command that regenerates it). The console has no `make`
#: target — checked against the Makefile rather than assumed, because a failure message
#: naming a command that does not exist is the BOOTH_SETUP failure all over again.
GENERATED_SCREENS = [
    ("scripts/finals.template.html", "web/finals.html", "make finals"),
    (
        "scripts/console.template.html",
        "web/console.html",
        "python scripts/build_console.py",
    ),
]

#: The sentence WFG-103 withdrew, in both languages, as it stood before the fix. It
#: describes an opponent that looks at the fire; the arm does not.
WITHDRAWN = (
    "지도가 지금 이 순간만 본다면",
    "A map that only sees the present would recommend it",
)

#: What the corrected caption says instead, in both languages.
CORRECTED = (
    "화재를 전혀 보지 않는 지도가 그리는 경로입니다",
    "This is the route a fire-blind map draws",
)


def _lines(rel: str) -> list[str]:
    path = REPO / rel
    assert path.is_file(), f"{rel} does not exist"
    return path.read_text(encoding="utf-8").split("\n")


def _payload_line_index(template_lines: list[str], rel: str) -> int:
    """The one line the builder is allowed to change, found in the template."""
    hits = [i for i, ln in enumerate(template_lines) if PLACEHOLDER in ln]
    assert len(hits) == 1, (
        f"expected exactly one {PLACEHOLDER} line in {rel}, found {len(hits)}: "
        f"{[i + 1 for i in hits]}"
    )
    return hits[0]


@pytest.mark.parametrize("tpl_rel,out_rel,target", GENERATED_SCREENS)
def test_the_template_carries_exactly_one_payload_placeholder(tpl_rel, out_rel, target):
    assert _payload_line_index(_lines(tpl_rel), tpl_rel) >= 0


@pytest.mark.parametrize("tpl_rel,out_rel,target", GENERATED_SCREENS)
def test_the_built_screen_is_the_template_with_only_the_payload_substituted(
    tpl_rel, out_rel, target
):
    """Any line of the output that differs from its template is a hand-edit.

    A hand-edit is not wrong because it is wrong; it is wrong because the builder
    reverts it, so it lies to whoever reads the file and not to whoever rebuilds it.
    """
    tpl, out = _lines(tpl_rel), _lines(out_rel)
    payload = _payload_line_index(tpl, tpl_rel)
    assert len(tpl) == len(out), (
        f"{out_rel} has {len(out)} lines, {tpl_rel} has {len(tpl)}; the builder "
        f"substitutes one line and adds none. Run `{target}`."
    )
    drift = [
        i + 1 for i, (t, s) in enumerate(zip(tpl, out)) if t != s and i != payload
    ]
    assert not drift, (
        f"{out_rel} differs from {tpl_rel} at line(s) {drift}, outside the payload "
        f"line {payload + 1}. The screen is generated: fix {tpl_rel} and run "
        f"`{target}`, never the output by hand (WFG-109)."
    )


@pytest.mark.parametrize("tpl_rel,out_rel,target", GENERATED_SCREENS)
def test_the_payload_line_really_does_differ(tpl_rel, out_rel, target):
    """Guard against the test passing because the template was committed as the screen.

    If someone does that, every line matches and the test above goes green on a screen
    with no data in it.
    """
    tpl, out = _lines(tpl_rel), _lines(out_rel)
    payload = _payload_line_index(tpl, tpl_rel)
    assert PLACEHOLDER in tpl[payload]
    assert PLACEHOLDER not in out[payload], (
        f"{out_rel} still carries the unsubstituted placeholder; it was not built."
    )


@pytest.mark.parametrize("tpl_rel,out_rel,target", GENERATED_SCREENS)
def test_the_command_each_failure_message_names_actually_exists(tpl_rel, out_rel, target):
    """A failure message that names a command nobody can run wastes the catch.

    MEMO 2026-09-05: every sentence of a procedure is a prediction about a machine.
    These two are the only procedure this file states, so they are checked here.
    """
    if target.startswith("make "):
        makefile = (REPO / "Makefile").read_text(encoding="utf-8")
        goal = target.split(None, 1)[1]
        assert any(
            ln.startswith(f"{goal}:") for ln in makefile.split("\n")
        ), f"{target!r} is named as the fix for {out_rel} but is not a Makefile target"
    else:
        script = target.split()[-1]
        assert (REPO / script).is_file(), (
            f"{target!r} is named as the fix for {out_rel} but {script} does not exist"
        )


def test_the_withdrawn_static_view_claim_is_in_neither_finals_face():
    """WFG-103's withdrawal, pinned by name in both the source and the output."""
    for rel in ("scripts/finals.template.html", "web/finals.html"):
        text = "\n".join(_lines(rel))
        for phrase in WITHDRAWN:
            assert phrase not in text, (
                f"{rel} carries the STATIC VIEW claim WFG-103 withdrew ({phrase!r}). "
                "The routing baseline is fire-blind, not a map that sees the present."
            )
        for phrase in CORRECTED:
            assert phrase in text, (
                f"{rel} lost the corrected STATIC VIEW caption ({phrase!r})."
            )
