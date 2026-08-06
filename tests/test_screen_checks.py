"""PHASE 21 STEP 1 — the three gates, and the gates on the gates.

A checker nobody checked is a checker that passes everything. So the contrast
maths is verified against values that can be computed by hand, and each
detector is shown to fire on a positive case AND to stay quiet on a negative
one — because a detector that always fires is as useless as one that never
does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from check_screen_assets import (  # noqa: E402
    AA_LARGE, AA_NORMAL, AAA_NORMAL, NON_TEXT, SVG_NS, XLINK_NS, ContrastPair,
    check_contrast, check_dashes, check_offline, contrast, palette_report,
    relative_luminance,
)

SHIPPED_SCREENS = sorted((REPO / "demo").glob("*.html"))


# ---------------------------------------------------------------------------
# 1. The contrast maths
# ---------------------------------------------------------------------------


def test_luminance_of_the_two_endpoints():
    assert relative_luminance("#000000") == pytest.approx(0.0)
    assert relative_luminance("#ffffff") == pytest.approx(1.0)


def test_black_on_white_is_the_maximum_ratio():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0, abs=1e-6)
    assert contrast("#ffffff", "#000000") == pytest.approx(21.0, abs=1e-6), (
        "the ratio is symmetric; a checker that depended on argument order "
        "would pass or fail on which colour the author happened to write first")


def test_a_colour_against_itself_is_one_to_one():
    assert contrast("#3a7bd5", "#3a7bd5") == pytest.approx(1.0)


def test_shorthand_and_alpha_forms_parse():
    assert relative_luminance("#fff") == pytest.approx(relative_luminance("#ffffff"))
    assert relative_luminance("#ffffff80") == pytest.approx(
        relative_luminance("#ffffff")), "alpha is ignored, as documented"


def test_a_known_mid_pair_matches_the_hand_computation():
    # #767676 on white is the canonical WCAG AA boundary example: 4.54:1.
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


def test_the_thresholds_are_the_wcag_ones():
    assert (AA_NORMAL, AA_LARGE, AAA_NORMAL, NON_TEXT) == (4.5, 3.0, 7.0, 3.0)


def test_a_failing_pair_is_reported_and_a_passing_one_is_not():
    bad = ContrastPair("too pale", "#999999", "#ffffff")          # 2.85:1
    good = ContrastPair("fine", "#111111", "#ffffff")
    assert check_contrast([bad]), "a 2.85:1 body-text pair must be reported"
    assert not check_contrast([good])


def test_the_non_text_bar_is_lower_and_is_applied_only_where_asked():
    dot = ContrastPair("map dot", "#dc2626", "#0b0f14", non_text=True)
    same_as_text = ContrastPair("same colour as text", "#dc2626", "#0b0f14")
    assert not check_contrast([dot]), "3.98:1 clears the 3:1 non-text bar"
    assert check_contrast([same_as_text]), (
        "the same colour used for TEXT must fail the 4.5:1 bar — the point of "
        "the distinction is that it is not automatic")


# ---------------------------------------------------------------------------
# 2. The dash gate
# ---------------------------------------------------------------------------


def test_both_dashes_are_caught():
    assert check_dashes("<p>6.12 — 1.71</p>")
    assert check_dashes("<p>125 – 530 m</p>")


def test_the_approved_replacements_pass():
    for ok in ("<p>6.12 → 1.71</p>", "<p>125~530 m</p>", "<p>가 · 나 · 다</p>",
               "<p>Before / After</p>", "<p>hyphen-joined</p>"):
        assert not check_dashes(ok), ok


def test_a_dash_inside_script_or_style_or_a_comment_is_not_visible_text():
    """The rule is about what a reader sees, not about the bytes in the file."""
    for hidden in ('<script>const s = "a — b";</script>',
                   "<style>/* a — b */</style>",
                   "<!-- a — b -->"):
        assert not check_dashes(hidden), hidden
    assert check_dashes("<p>a — b</p>"), "...but visible text still fails"


def test_stripping_preserves_line_numbers():
    html = '<p>ok</p>\n<script>\n\n"—"\n</script>\n<p>x — y</p>'
    found = check_dashes(html)
    assert len(found) == 1
    assert found[0].line == 6, (
        "a finding that reports the wrong line sends the reader to the wrong "
        "place, which is worse than no line number")


# ---------------------------------------------------------------------------
# 3. The offline gate
# ---------------------------------------------------------------------------


def test_an_external_resource_is_caught():
    for bad in ('<link href="https://fonts.googleapis.com/css?family=X">',
                '<script src="http://cdn.example.com/a.js"></script>',
                "<style>@import url(https://x.example/y.css);</style>",
                '<img srcset="https://tiles.example/1.png">'):
        assert check_offline(bad), bad


def test_every_way_of_reaching_the_network_is_caught():
    for bad in ("fetch('/api/x')", "new XMLHttpRequest()",
                "new WebSocket('ws://x')", "new EventSource('/s')",
                "navigator.sendBeacon('/b')", "navigator.serviceWorker"):
        assert check_offline(bad), bad


def test_the_svg_namespace_is_the_one_permitted_url():
    assert not check_offline(f'<svg xmlns="{SVG_NS}">'), (
        "the SVG namespace is an identifier, never dereferenced; the PHASE-8 "
        "screen already depends on this exemption")
    assert check_offline(f'<script src="{SVG_NS}/evil.js">')


def test_a_self_contained_page_passes():
    page = (f'<svg xmlns="{SVG_NS}"></svg>'
            "<style>body{background:#0b0f14}</style>"
            "<script>const n = 458;</script>")
    assert not check_offline(page)


# ---------------------------------------------------------------------------
# 4. The gates applied to what is actually shipped
# ---------------------------------------------------------------------------


#: ⚠ A KNOWN, UNFIXED DEFECT — recorded so it cannot be forgotten, not excused.
#:
#: `demo/wildfire_demo.html` pulls IBM Plex Sans KR and IBM Plex Mono from
#: Google Fonts at load time: two preconnects and one stylesheet. In a hall with
#: no network — which is the situation the whole offline design exists for — the
#: page renders in a fallback face, and Korean text is exactly what a fallback
#: face handles worst.
#:
#: It is pinned rather than fixed here because fixing it means vendoring a font
#: (a new binary asset and a licence decision) and editing a committed demo
#: page. Both are the owner's calls. `demo/operator_screen.html`, the PHASE-8
#: screen, is already clean and stays hard-asserted.
KNOWN_OFFLINE_VIOLATIONS: dict[str, int] = {"wildfire_demo.html": 3}


@pytest.mark.skipif(not SHIPPED_SCREENS, reason="no demo HTML in the tree")
@pytest.mark.parametrize("path", SHIPPED_SCREENS, ids=lambda p: p.name)
def test_every_shipped_screen_is_fully_offline(path):
    """The hard one. A competition hall may have no network at all."""
    found = check_offline(path.read_text(encoding="utf-8"))
    allowed = KNOWN_OFFLINE_VIOLATIONS.get(path.name, 0)
    detail = "\n".join(f"  line {f.line}: {f.detail}" for f in found)
    assert len(found) <= allowed, (
        f"{path.name} makes {len(found)} external requests, was {allowed}:\n"
        f"{detail}")
    if len(found) < allowed:
        pytest.fail(
            f"{path.name} improved to {len(found)} — lower "
            "KNOWN_OFFLINE_VIOLATIONS so the ratchet holds the new floor")


def test_the_phase8_operator_screen_has_no_known_violations_to_excuse():
    """The screen the demonstration actually uses is held to zero, hard."""
    assert "operator_screen.html" not in KNOWN_OFFLINE_VIOLATIONS
    p = REPO / "demo" / "operator_screen.html"
    if p.exists():
        assert not check_offline(p.read_text(encoding="utf-8"))


#: EM dashes currently present in visible text of the committed screens.
#: ⚠ PINNED, NOT ACCEPTED. Both sit in prose (a <title> and a status line), not
#: in a numeric column, so neither can break tabular-nums today. They are
#: recorded as a RATCHET: the count may fall, never rise. Editing the committed
#: screen is a decision for whoever owns the demo — `docs/HANDOFF_ROUND3.md`
#: treats shipped demo assets as things you do not quietly regenerate.
KNOWN_DASHES: dict[str, int] = {"operator_screen.html": 2,
                                "wildfire_demo.html": 1}


@pytest.mark.skipif(not SHIPPED_SCREENS, reason="no demo HTML in the tree")
@pytest.mark.parametrize("path", SHIPPED_SCREENS, ids=lambda p: p.name)
def test_the_dash_count_in_shipped_screens_never_rises(path):
    n = len(check_dashes(path.read_text(encoding="utf-8")))
    allowed = KNOWN_DASHES.get(path.name, 0)
    assert n <= allowed, (
        f"{path.name} now has {n} banned dashes in visible text, was "
        f"{allowed}. New screen text must use → ~ · / instead.")
    if n < allowed:
        pytest.fail(
            f"{path.name} improved to {n} banned dashes — lower KNOWN_DASHES "
            "so the ratchet holds the new floor")


# ---------------------------------------------------------------------------
# 5. The palette audit reports what it did NOT measure
# ---------------------------------------------------------------------------


def test_the_palette_report_names_the_current_failure():
    rep = palette_report()
    fails = [r for r in rep["pairs"] if r["grade"] == "FAIL"]
    assert fails, (
        "the audit found no failure — if the palette was fixed, update this "
        "test rather than deleting it")
    assert any(r["fg"] == "#64748b" for r in fails), (
        "#64748b on #16202b measures 3.46:1 against a 4.5:1 bar")


def test_the_report_says_out_loud_what_it_could_not_measure():
    """The gap that matters: no font is vendored, so no glyph was measured."""
    rep = palette_report()
    blob = " ".join(rep["not_measured"]).lower()
    assert "advance width" in blob or "advance widths" in blob
    assert "no font is vendored" in blob
    assert any("alone" in c.lower() for c in rep["caveats"]), (
        "contrast passing must never be read as 'colour alone is enough'")


def test_no_font_is_vendored_yet_so_the_glyph_claim_stays_unproven():
    skip = {".git", ".venv", "venv", "node_modules", "__pycache__",
            "site-packages"}
    fonts = [p for p in REPO.rglob("*")
             if p.suffix.lower() in (".woff", ".woff2", ".ttf", ".otf")
             and not skip & set(p.parts)]
    if fonts:
        pytest.fail(
            f"a font is now vendored ({[f.name for f in fonts][:3]}) — measure "
            "the arrow/tilde advance widths against a digit and delete this "
            "test, because the assumption it guards is now checkable")
