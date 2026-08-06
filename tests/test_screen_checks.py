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


#: Empty, and it is meant to stay empty.
#:
#: `demo/wildfire_demo.html` used to pull IBM Plex Sans KR and Mono from Google
#: Fonts — two preconnects and a stylesheet. In a hall with no network the page
#: fell back to a system face, and a fallback face is worst at exactly what that
#: page is full of. PHASE 21 vendored the fonts (web/assets/fonts/, SIL OFL,
#: subset to KS X 1001) and the three requests are gone.
#:
#: Anything added here is a screen that reaches the network. There should never
#: be one.
KNOWN_OFFLINE_VIOLATIONS: dict[str, int] = {}


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


#: Empty, and meant to stay empty.
#:
#: PHASE 21 fixed all of them at the GENERATOR as well as in the built file, so
#: a rebuild cannot reintroduce them: scripts/build_operator_screen.py no longer
#: contains an EM dash in any string that reaches the screen. The replacements
#: are the approved ones — a colon for a clause break, a middle dot for a list,
#: a tilde for a range (0.10~0.30 band labels).
#:
#: This matters more than tidiness now: the shipped subset has NO EM or EN dash
#: glyph, so any that came back would render as tofu in front of a judge.
KNOWN_DASHES: dict[str, int] = {}


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


def test_the_palette_now_passes_wcag_everywhere_it_is_measured():
    """It did not, until PHASE 21.

    #64748b measured 3.46:1 against a 4.5:1 body-text bar and is now #7c8ba1 at
    4.75:1 — the closest colour to the original that clears AA, chosen from a
    measured ladder rather than by eye.
    """
    rep = palette_report()
    fails = [r for r in rep["pairs"] if r["grade"] == "FAIL"]
    assert not fails, (
        "contrast regressed: "
        + "; ".join(f"{r['name']} {r['ratio']}:1 needs {r['required']}:1"
                    for r in fails))
    dim = next(r for r in rep["pairs"] if r["name"] == "흐린 텍스트")
    assert dim["fg"] == "#7c8ba1" and dim["ratio"] >= 4.5


def test_the_blue_is_never_used_as_a_text_colour():
    """#2563eb clears the 3:1 non-text bar and would FAIL as body text.

    Audited across the generator: it appears as a legend dot, a map marker and
    an active-button background (white on it measures 5.17:1). If it is ever
    set as a `color:`, this is the reminder that it does not qualify.
    """
    from check_screen_assets import contrast
    assert contrast("#2563eb", "#16202b") < AA_NORMAL
    gen = (REPO / "scripts" / "build_operator_screen.py")
    if gen.exists():
        for line in gen.read_text(encoding="utf-8").splitlines():
            if "#2563eb" in line and "color:#2563eb" in line.replace(" ", ""):
                pytest.fail(f"#2563eb used as a text colour: {line.strip()}")


def test_the_report_says_out_loud_what_it_could_not_measure():
    """The gap that matters: no font is vendored, so no glyph was measured."""
    rep = palette_report()
    blob = " ".join(rep["not_measured"]).lower()
    assert "advance width" in blob or "advance widths" in blob
    assert "no font is vendored" in blob
    assert any("alone" in c.lower() for c in rep["caveats"]), (
        "contrast passing must never be read as 'colour alone is enough'")


def test_the_vendored_faces_are_present_and_licensed():
    """PHASE 21 vendored them, so the assumption became a measurement."""
    d = REPO / "web" / "assets" / "fonts"
    if not d.exists():
        pytest.skip("no fonts vendored")
    assert list(d.glob("*.woff2")), "no web fonts in web/assets/fonts"
    licences = list(d.glob("LICENSE-*"))
    assert len(licences) >= 2, (
        f"vendored fonts without their licences: {[q.name for q in licences]} — "
        "both faces are SIL OFL and the licence must travel with the binary")
    for lic in licences:
        assert "SIL OPEN FONT LICENSE" in lic.read_text(encoding="utf-8").upper()


def _face(name: str):
    from fontTools.ttLib import TTFont
    p = REPO / "web" / "assets" / "fonts" / name
    if not p.exists():
        pytest.skip(f"{name} not vendored")
    return TTFont(str(p), lazy=False)


def _advance(font, ch: str):
    cmap = {}
    for t in font["cmap"].tables:
        if t.isUnicode():
            cmap.update(t.cmap)
    g = cmap.get(ord(ch))
    return None if g is None else font["hmtx"][g][0]


def test_the_digits_of_the_shipped_face_share_an_advance_width():
    """IBM Plex's figures are tabular by default — measured, not assumed."""
    f = _face("IBMPlexSansKR-Regular.woff2")
    widths = {d: _advance(f, d) for d in "0123456789"}
    assert None not in widths.values()
    assert len(set(widths.values())) == 1, (
        f"digits are not uniform: {widths} — the screen would need "
        "font-variant-numeric: tabular-nums and it would have to be verified")


def test_the_banned_dashes_are_not_even_in_the_shipped_subset():
    """Better than a rule: the shipped face cannot render them at all.

    The subset was built from Latin + KS X 1001 + the punctuation this project
    actually uses, and the EM and EN dash were deliberately left out. A stray
    dash therefore renders as tofu — loudly, in front of everyone — instead of
    quietly nudging a numeric column out of line.

    The width justification for banning them was measured on the FULL faces and
    is recorded in docs/font_measurement.json: EM dash 1.30x a digit in IBM Plex
    Sans KR and 1.61x in Pretendard.
    """
    f = _face("IBMPlexSansKR-Regular.woff2")
    for ch, name in (("\u2014", "EM dash"), ("\u2013", "EN dash")):
        assert _advance(f, ch) is None, (
            f"{name} is now IN the shipped subset — either it was added back on "
            "purpose, in which case re-argue the ban, or the subset character "
            "set drifted")


def test_the_tilde_is_exactly_a_digit_wide_so_a_range_is_column_safe():
    for name in ("IBMPlexSansKR-Regular.woff2", "IBMPlexMono-Regular.woff2"):
        f = _face(name)
        assert _advance(f, "~") == _advance(f, "0"), (
            f"{name}: tilde is no longer digit-width; 125~530 would shift its "
            "row inside a numeric column")


def test_the_arrow_is_absent_from_plex_and_is_why_a_subset_face_is_shipped():
    """The measured fact the CSS depends on. If it changes, drop the subset."""
    for name in ("IBMPlexSansKR-Regular.woff2", "IBMPlexMono-Regular.woff2"):
        assert _advance(_face(name), "\u2192") is None, (
            f"{name} now has U+2192 — delete Pretendard-arrow.subset.woff2 and "
            "the @font-face that borrows it, because it is no longer needed")
    arrow = _face("Pretendard-arrow.subset.woff2")
    assert _advance(arrow, "\u2192") is not None, (
        "the borrowed-arrow face does not contain the arrow it exists for")


def test_the_arrow_is_wider_than_a_digit_so_it_stays_out_of_numeric_columns():
    """Why the table rule is 'split the column', not 'use an arrow'."""
    arrow = _advance(_face("Pretendard-arrow.subset.woff2"), "\u2192")
    digit = _advance(_face("IBMPlexSansKR-Regular.woff2"), "0")
    plex_upem = _face("IBMPlexSansKR-Regular.woff2")["head"].unitsPerEm
    pret_upem = _face("Pretendard-arrow.subset.woff2")["head"].unitsPerEm
    arrow_em, digit_em = arrow / pret_upem, digit / plex_upem
    assert arrow_em > digit_em, (
        f"arrow {arrow_em:.3f} em vs digit {digit_em:.3f} em — the arrow is "
        "safe in PROSE and unsafe inside a tabular-nums column, which is why "
        "tables split into Before / After columns instead")
