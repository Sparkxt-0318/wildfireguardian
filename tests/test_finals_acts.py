"""WFG-009 — the four acts of `web/finals.html` advance, and the gate that says so.

Readiness line R1 asks that the screen 「opens from `file://` with Wi-Fi off, **all
four acts advance**」.  Until this file, nothing in the repository pressed a button
on that screen: the evidence for R1's first clause was one hand-run from
2026-09-05 on a build the screen has been rebuilt past.

The browser test is the deliverable, but it is not the interesting half.  The
interesting half is `test_the_advance_assertion_*`: a driver that clicks and
screenshots proves only that Chromium did not crash, so those tests break the
advance deliberately and require the checker to notice.  Without them this file
would be a gate that passes on four blank panels.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_finals_acts as acts  # noqa: E402

FINALS = REPO / "web" / "finals.html"

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ---------------------------------------------------------------------------
# The constant must not drift from the screen it asserts on.
# ---------------------------------------------------------------------------

def test_the_act_labels_are_the_ones_the_screen_actually_uses():
    """`ACT_LABELS` is a copy of the screen's own list, so it can go stale.

    If a lap renames an act in `web/finals.html`, the driver would assert on a
    label nobody displays and fail with a confusing message about a missing act.
    This reads the list out of the screen and compares.
    """
    src = FINALS.read_text(encoding="utf-8")
    m = re.search(r"acts:\s*\[([^\]]*?)\],", src)
    assert m, "could not find the guided demo's `acts:` list in web/finals.html"
    on_screen = re.findall(r"'([^']*)'", m.group(1))
    assert on_screen == acts.ACT_LABELS, (
        "scripts/check_finals_acts.py ACT_LABELS has drifted from web/finals.html:\n"
        f"  screen: {on_screen}\n  driver: {acts.ACT_LABELS}"
    )


def test_the_screen_still_has_the_controls_the_driver_presses():
    src = FINALS.read_text(encoding="utf-8")
    for element_id in ("introGo", "gNext", "gact", "gdots", "gtitle", "gbody", "guide"):
        assert f'id="{element_id}"' in src, (
            f"the driver presses or reads #{element_id} and web/finals.html no longer "
            "has it; the browser test would fail with a less obvious message"
        )


# ---------------------------------------------------------------------------
# Mutation grading of the assertion.  No browser needed: these feed the checker
# the states a broken screen would produce and require it to reject each one.
# ---------------------------------------------------------------------------

def _good(label: str, dots: int) -> dict:
    return {"guideVisible": True, "act": label, "dots": dots,
            "title": "제목", "body": "본문", "view": "view-live", "introHidden": True}


def test_the_advance_assertion_accepts_a_real_advance():
    acts._assert_advanced(_good("1막 · 발견", 1), _good("2막 · 시간과 도로망", 2),
                          "2막 · 시간과 도로망")


def test_the_advance_assertion_fails_when_the_act_did_not_change():
    """The failure mode this row exists for: the press did nothing.

    `#gNext`'s handler throwing, the button being covered, or the demo having
    exited all leave the previous act on screen.  A screenshot would still be
    written and would still look like a real screen.
    """
    same = _good("1막 · 발견", 1)
    with pytest.raises(AssertionError, match="did not change"):
        acts._assert_advanced(same, _good("1막 · 발견", 1), "1막 · 발견")


def test_the_advance_assertion_fails_on_a_half_applied_transition():
    """Label moved, scene did not: the dots are the independent witness."""
    with pytest.raises(AssertionError, match="progress dots"):
        acts._assert_advanced(_good("1막 · 발견", 1),
                              _good("2막 · 시간과 도로망", 1), "2막 · 시간과 도로망")


def test_the_advance_assertion_fails_on_the_wrong_act():
    """Changed, but to the wrong act — e.g. a press that skipped one.

    Added after this lap's reviewer mutation-graded the checker and found this
    branch alive: `act != expected_label` survived deletion because every other
    test that moved the label also expected the label it moved to.
    """
    with pytest.raises(AssertionError, match="act label is"):
        acts._assert_advanced(_good("1막 · 발견", 1),
                              _good("3막 · 경로 비교", 3), "2막 · 시간과 도로망")


def test_the_advance_assertion_fails_on_an_empty_title():
    """The other branch the reviewer found unkilled."""
    blank = _good("2막 · 시간과 도로망", 2) | {"title": ""}
    with pytest.raises(AssertionError, match="caption title is empty"):
        acts._assert_advanced(_good("1막 · 발견", 1), blank, "2막 · 시간과 도로망")


def test_the_advance_assertion_fails_on_an_empty_caption():
    blank = _good("2막 · 시간과 도로망", 2) | {"body": ""}
    with pytest.raises(AssertionError, match="caption body is empty"):
        acts._assert_advanced(_good("1막 · 발견", 1), blank, "2막 · 시간과 도로망")


def test_the_advance_assertion_fails_when_the_dialog_is_gone():
    gone = _good("4막 · 판단", 4) | {"guideVisible": False}
    with pytest.raises(AssertionError, match="not visible"):
        acts._assert_advanced(_good("3막 · 경로 비교", 3), gone, "4막 · 판단")


def test_the_advance_assertion_fails_when_the_demo_left_the_live_view():
    off = _good("3막 · 경로 비교", 3) | {"view": "view-system"}
    with pytest.raises(AssertionError, match="left the live view"):
        acts._assert_advanced(_good("2막 · 시간과 도로망", 2), off, "3막 · 경로 비교")


# ---------------------------------------------------------------------------
# The optional-media rule, which is the one place this gate deliberately
# tolerates a missing file.  It must stay narrow.
# ---------------------------------------------------------------------------

def test_only_an_unfilled_slot_is_optional():
    """Every one of these is genuinely absent from the index, checked here."""
    tracked = acts.tracked_demo_media()
    for name in ("intro-forest-loop.mp4", "ambient-documentary.mp3",
                 "ui-soft-click.wav", "ui-map-ping.wav"):
        assert name not in tracked, (
            f"{name} is now COMMITTED under web/demo-media/, so it is no longer an "
            "unfilled slot and this gate must stop tolerating its absence"
        )
        assert acts._is_optional_media(f"file:///x/web/demo-media/{name}")


def test_a_tracked_asset_is_never_optional():
    """A committed file must load.  Losing one is a defect, not an unfilled slot.

    This is the test that keeps the tolerance from becoming "ignore missing files",
    which would have made the gate agree with a booth laptop that lost its fonts.
    """
    tracked = acts.tracked_demo_media()
    assert "intro-poster.webp" in tracked and "README.md" in tracked, (
        "web/demo-media/'s committed files are the premise of the whole rule; the "
        f"index now holds {sorted(tracked)}"
    )
    assert not acts._is_optional_media("file:///x/web/demo-media/intro-poster.webp")
    assert not acts._is_optional_media("file:///x/web/demo-media/README.md")
    assert not acts._is_optional_media(
        "file:///x/web/assets/fonts/Pretendard-arrow.subset.woff2")
    assert not acts._is_optional_media("file:///x/web/finals.html")


def test_the_rule_reads_the_index_and_not_a_list_of_extensions():
    """The regression this lap's reviewer blocked, kept as a test.

    The first version tolerated a hardcoded extension list whose comment claimed
    those were the extensions `.gitignore` excludes.  `.gitignore` excludes only
    `*.mp4 *.mov *.avi`, so `.mp3`/`.wav` were tolerated on a false premise — and
    `web/finals.html` references five committable `.wav` UI-sound slots.  A rule
    driven by the index cannot drift from the tree that way: a `.wav` committed
    tomorrow stops being optional the moment it is committed, with no edit here.
    """
    fake_tracked = frozenset({"ui-soft-click.wav", "intro-poster.webp"})
    assert not acts._is_optional_media(
        "file:///x/web/demo-media/ui-soft-click.wav", fake_tracked)
    assert acts._is_optional_media(
        "file:///x/web/demo-media/ui-map-ping.wav", fake_tracked)
    # And nothing outside demo-media/ is reachable by the rule at all.
    assert not acts._is_optional_media(
        "file:///x/web/assets/fonts/IBMPlexMono-Regular.woff2", frozenset())


# ---------------------------------------------------------------------------
# The real browser.  Skipped, never downloaded (CHARTER §4b: no test reaches the
# network).  In CI the `finals-acts` job installs nothing and runs this.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(acts.find_chrome() is None,
                    reason="no Chromium on this machine; this gate never downloads one")
def test_the_four_acts_advance_in_a_real_browser(tmp_path):
    report = acts.run(tmp_path)

    assert [a["act"] for a in report["acts"]] == acts.ACT_LABELS
    assert [a["dots"] for a in report["acts"]] == [1, 2, 3, 4]
    assert report["console_errors"] == []
    assert report["offsite_requests"] == [], (
        "the finals screen must open with Wi-Fi off; it requested: "
        f"{report['offsite_requests']}"
    )
    assert report["requests_total"] > 0

    for entry in report["acts"]:
        shot = tmp_path / entry["screenshot"]
        assert shot.exists(), f"no screenshot for {entry['act']}"
        # A blank or error page compresses tiny.  The real screen is a map plus a
        # hazard field and runs to hundreds of kB; 60 kB is a floor, not a target.
        assert shot.stat().st_size > 60_000, (
            f"{shot.name} is {shot.stat().st_size} bytes, which is too small to be "
            "the rendered screen — the act probably advanced onto a blank panel"
        )
        assert shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    written = json.loads((tmp_path / "report.json").read_text(encoding="utf-8")) \
        if (tmp_path / "report.json").exists() else None
    assert written is None or written["acts"] == report["acts"]
