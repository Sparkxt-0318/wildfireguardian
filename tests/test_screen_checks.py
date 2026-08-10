"""PHASE 21 STEP 1 — the three gates, and the gates on the gates.

A checker nobody checked is a checker that passes everything. So the contrast
maths is verified against values that can be computed by hand, and each
detector is shown to fire on a positive case AND to stay quiet on a negative
one — because a detector that always fires is as useless as one that never
does.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from check_screen_assets import (  # noqa: E402
    AA_LARGE, AA_NORMAL, AAA_NORMAL, NON_TEXT, SVG_NS, XLINK_NS, ContrastPair,
    check_contrast, check_dashes, check_dashes_in_scripts, check_offline,
    contrast, palette_report, relative_luminance,
)

#: ⚠ `outputs/live/screens/**` IS IN SCOPE, and it is in scope for a reason that
#: does NOT extend to the rest of `outputs/`.
#: `docs/operator_screen.md` line 11 gives the demonstration command as
#: `open outputs/live/screens/uiseong_andong_2025/operator_screen.html`, and
#: line 25 calls that region 시연용 — "this is the demo". Those files are shown
#: to judges, so they are shipped screens whatever directory they live in.
#:
#: The gate is deliberately NOT widened past them. `outputs/dispatch*/**` and
#: `outputs/live/replay/**` hold **297** and **593** dash findings (measured
#: 2026-08-07, 475 files in total), and almost all of them come from
#: `delivery.printable`'s live heading constants — text that is PRINTED ON
#: PAPER, in whatever full font the PDF renderer uses, as a section heading with
#: no numeric column to misalign. Neither half of the dash rule's rationale
#: applies there. See `docs/screen_gate_scope.md`.
#: ⚠ Both globs, not one. `*/*.html` alone matched only the per-region
#: directories and silently excluded the two TOP-LEVEL siblings — the
#: four-minute-talk demo variant and the manual-trigger screen — which is
#: exactly how both shipped for months with pre-PHASE-21 EN-dash band labels
#: while "every shipped screen passes the dash gate" was true of the list.
SHIPPED_SCREENS = sorted(
    list((REPO / "demo").glob("*.html"))
    + list((REPO / "outputs" / "live" / "screens").glob("*/*.html"))
    + list((REPO / "outputs" / "live" / "screens").glob("*.html")))


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


# ---------------------------------------------------------------------------
# 6. The PHASE-22 operator console
# ---------------------------------------------------------------------------

CONSOLE = REPO / "web" / "console.html"
console_only = pytest.mark.skipif(not CONSOLE.exists(),
                                  reason="run scripts/build_console.py first")


@console_only
def test_the_console_reaches_nothing_but_its_own_origin():
    """It MAY call /api. It may not call a host.

    The relaxation is narrow and is the only place it is used: the demo screens
    stay under the strict rule, asserted separately below.
    """
    found = check_offline(CONSOLE.read_text(encoding="utf-8"),
                          allow_same_origin_fetch=True)
    assert not found, "\n".join(f"line {f.line}: {f.detail}" for f in found)


@console_only
def test_the_console_still_fails_the_strict_rule_and_that_is_expected():
    """Proof the relaxation is doing something, rather than the file being inert.

    If this ever passes, the console has stopped calling its own API and the
    live-calculation button is dead.
    """
    strict = check_offline(CONSOLE.read_text(encoding="utf-8"))
    assert strict, "the console no longer fetches anything — is live mode gone?"
    assert all("fetch(" in f.detail or "fetch" in f.excerpt for f in strict), (
        f"strict mode found something OTHER than a fetch: "
        f"{[f.detail for f in strict]}")


@console_only
def test_the_console_carries_no_banned_dash_anywhere_it_shows():
    src = CONSOLE.read_text(encoding="utf-8")
    found = check_dashes(src) + check_dashes_in_scripts(src)
    assert not found, "\n".join(f"line {f.line}: {f.detail}" for f in found)


@console_only
def test_the_console_shows_all_three_honesty_items():
    """Checked as STRINGS ON THE PAGE, not as intentions."""
    src = CONSOLE.read_text(encoding="utf-8")
    assert "기상 자료" in src
    assert "보행망 커버리지" in src
    assert "최종 판단은 현장에서" in src


@console_only
def test_the_standing_line_is_byte_identical_to_the_a4_sheets_constant():
    """Imported at build time, never retyped. One sentence, two surfaces."""
    import sys as _sys
    _sys.path.insert(0, str(REPO / "src"))
    from wildfireguardian.delivery.printable import FOOTER_LINES
    assert FOOTER_LINES[0] in CONSOLE.read_text(encoding="utf-8"), (
        "the console's standing line has drifted from the A4 sheet's constant")


@console_only
def test_the_console_loads_no_web_font_and_no_map_tile():
    src = CONSOLE.read_text(encoding="utf-8").lower()
    for token in ("googleapis", "gstatic", "jsdelivr", "unpkg",
                  "tile.openstreetmap", "basemap", "mapbox", "leaflet"):
        assert token not in src, token
    assert "assets/fonts/ibmplexsanskr-regular.woff2" in src, (
        "the console must reference the VENDORED font, not a system fallback")


@console_only
def test_the_console_respects_reduced_motion():
    assert "prefers-reduced-motion" in CONSOLE.read_text(encoding="utf-8")


@console_only
def test_every_bucket_has_a_shape_and_a_label_not_only_a_colour():
    """Colour is not a channel on its own — colour blindness, projectors, and
    the photocopier a 이장 uses all remove it."""
    import sys as _sys
    _sys.path.insert(0, str(REPO / "scripts"))
    from build_console import BUCKETS
    assert len(BUCKETS) == 4
    shapes = {b["shape"] for b in BUCKETS}
    assert len(shapes) == 4, f"two buckets share a shape: {shapes}"
    for b in BUCKETS:
        assert b["ko"] and b["mark"] and b["fill"].startswith("#")


@console_only
def test_the_console_palette_meets_wcag_where_it_is_used():
    import sys as _sys
    _sys.path.insert(0, str(REPO / "scripts"))
    from build_console import BUCKETS
    for b in BUCKETS:
        r = contrast(b["fill"], "#0b0f14")
        assert r >= NON_TEXT, f"{b['ko']} {b['fill']} is {r:.2f}:1 on the map base"
    # The focus ring is the one a keyboard user depends on.
    assert contrast("#fbbf24", "#16202b") >= NON_TEXT


# ---------------------------------------------------------------------------
# 6-b. The unclicked start, and refusals an operator can read
#
# The defect these pin, found by pressing the button on 2026-08-07: the console
# submitted the hazard field's t=0 core when nothing had been clicked, and for
# `yeongdeok_2025` that coordinate lies 2,472 m OUTSIDE the walk bbox. The gate
# refused it, correctly, 422 every time — and the screen printed
# 「제출 거절 (HTTP 422)」 and nothing else. Both halves are faults: an offer that
# cannot be honoured, and a refusal an operator cannot act on.
# ---------------------------------------------------------------------------

_DATA_BLOCK = re.compile(
    r'<script id="data" type="application/json">(.*?)</script>', re.S)


def console_payload() -> dict:
    """The inlined build payload, read back out of the shipped file."""
    m = _DATA_BLOCK.search(CONSOLE.read_text(encoding="utf-8"))
    assert m, "the console has no inlined data block"
    return json.loads(m.group(1))


def console_regions() -> dict:
    """Every region inlined in the shipped console."""
    return console_payload()["regions"]


@console_only
def test_the_console_agrees_with_the_gate_about_every_default_start():
    """One definition of servable, asked of the function the API gates on.

    The console may still SHOW an unservable default — it is where the fire
    actually was, and hiding that would hide the coverage limitation. What it
    may not do is disagree with the server about whether it can be run.

    Checked for EVERY inlined region. Yeongdeok's core is outside its walk bbox
    and the other two are inside theirs, so this also pins that the console is
    not special-casing one region by name.
    """
    import sys as _sys
    _sys.path.insert(0, str(REPO / "src"))
    from wildfireguardian.service.params import check_in_region

    regions = console_regions()
    assert len(regions) >= 2, "the switcher should carry more than one region"
    for region, payload in regions.items():
        start = payload["default_start"]
        lat, lon = start["latlon"]
        truth = check_in_region(region, lat, lon)
        assert start["servable"] is bool(truth["inside_registered_region"]), (
            f"{region}: the console's verdict on its own default start "
            "disagrees with check_in_region, which POST /api/jobs refuses on")


@console_only
def test_every_unservable_default_start_is_measured_and_explained():
    import sys as _sys
    _sys.path.insert(0, str(REPO / "src"))
    from wildfireguardian.service.params import check_in_region

    unservable = {r: p for r, p in console_regions().items()
                  if not p["default_start"]["servable"]}
    assert unservable, (
        "no region has an unservable default start any more — if that is a "
        "real change, this test and the note it guards should go together")
    for region, payload in unservable.items():
        start = payload["default_start"]
        lat, lon = start["latlon"]
        assert isinstance(start["offset_m"], int) and start["offset_m"] > 0, (
            f"{region}: how far outside is a MEASUREMENT, not an adjective")
        assert check_in_region(region, lat, lon)["reason_ko"] \
            in start["note_ko"], (
            f"{region}: the note must carry the service's own sentence "
            "verbatim, not a second copy of it that can drift")
        assert "클릭" in start["note_ko"], (
            f"{region}: a refusal the operator cannot act on is half an "
            "answer; the note must say what to do instead")


@console_only
def test_the_button_does_not_offer_a_run_the_gate_is_certain_to_refuse():
    src = CONSOLE.read_text(encoding="utf-8")
    assert any(not p["default_start"]["servable"]
               for p in console_regions().values())
    assert "applyDefaultStartGate()" in src, (
        "nothing disables the button for an unservable default start")
    assert "run.disabled = true" in src
    # And the submit path refuses to send it even if the button is reached by
    # some other route.
    assert "if (!CLICK && !START.servable)" in src


# ---------------------------------------------------------------------------
# 6-c. Runtime region switching, in ONE build artifact
# ---------------------------------------------------------------------------


@console_only
def test_all_registered_regions_are_inlined_in_the_one_file():
    """⚠ One artifact, not three.

    Three built files would mean keeping track of which is current, and this
    project has already paid for that once. A per-region fetch was measured and
    rejected for a different reason: it would read a replay run directory at
    runtime, which is the thing that went missing in api_layer.md §1.12.
    """
    import sys as _sys
    _sys.path.insert(0, str(REPO / "src"))
    from wildfireguardian.service.params import known_regions

    payload = console_payload()
    assert set(payload["regions"]) == set(known_regions())
    assert payload["default_region"] in payload["regions"]
    assert list(payload["region_order"]) == list(payload["regions"])


@console_only
def test_the_console_still_opens_with_nothing_else_present():
    """The data is INLINE. No region is fetched, so file:// still works."""
    src = CONSOLE.read_text(encoding="utf-8")
    assert '<script id="data" type="application/json">' in src
    for banned in ("regions.json", "/api/regions/data", "fetch(`/api/console"):
        assert banned not in src, f"{banned}: a region is being fetched"


@console_only
def test_the_honesty_items_are_per_region_and_not_one_regions_values():
    """⚠ Coverage was the literal 32.6 in the builder.

    Right for Yeongdeok, and silently wrong for the other two the moment the
    console could switch. Every one of these is now read per region, and the
    three coverage figures must differ.
    """
    regions = console_regions()
    covers = {r: p["honesty"]["coverage_pct"] for r, p in regions.items()}
    assert len(set(covers.values())) == len(covers), (
        f"two regions share a coverage figure: {covers}")
    weather = {r: p["honesty"]["weather"] for r, p in regions.items()}
    assert len(set(weather.values())) == len(weather), (
        f"two regions share a weather basis: {weather}")
    for region, p in regions.items():
        assert region in p["honesty"]["hazard_fixed"], (
            f"{region}: the fixed-surface caution names the wrong region")
        assert p["precomputed"]["hazard_sha256"], region


@console_only
def test_coverage_matches_the_committed_multi_region_table():
    """Read, never typed. The table is the artifact that owns all three."""
    table = json.loads(
        (REPO / "data" / "processed" / "multi_region_comparison.json")
        .read_text(encoding="utf-8"))
    want = {row["region"]: round(row["envelope_coverage_final_slice"] * 100, 1)
            for row in table["regions"]}
    got = {r: p["honesty"]["coverage_pct"] for r, p in console_regions().items()}
    assert got == {k: v for k, v in want.items() if k in got}, (got, want)


@console_only
def test_counts_match_the_committed_multi_region_table():
    """A rebuild that quietly changed a region's counts would show here."""
    table = json.loads(
        (REPO / "data" / "processed" / "multi_region_comparison.json")
        .read_text(encoding="utf-8"))
    want = {row["region"]: (row["both_safe"], row["future_aware_only_safe"],
                            row["no_safe_route"], row["fa_exceeds_budget"])
            for row in table["regions"]}
    for region, p in console_regions().items():
        c = p["counts"]
        got = (c["both_safe"], c["naive_into_FA_safe"], c["no_safe_route"],
               c["fa_exceeds_budget"])
        assert got == want[region], f"{region}: {got} != {want[region]}"


@console_only
def test_a_region_with_no_depots_says_so_instead_of_showing_a_blank_table():
    """⚠ An empty responder side reads as a broken screen unless it is stated."""
    src = CONSOLE.read_text(encoding="utf-8")
    zero = [r for r, p in console_regions().items()
            if not p["responder"]["available"]]
    assert zero, "no region has zero depots any more; check the snapshot"
    for region in zero:
        note = console_regions()[region]["responder"]["status_ko"]
        assert note.strip(), f"{region}: nothing to show in place of the table"
        assert note in src, f"{region}: the statement never reaches the page"
        assert "OSM에 매핑된" in note
        assert "3,926" in note, "the wider bbox's six must be stated"
        assert "919" in note, "the walk bbox's area must be stated"
    assert "구조자 측 산출 없음" in src


@console_only
def test_the_depot_statement_never_says_a_region_has_no_fire_stations():
    """HANDOFF_ROUND3.md rule 11, enforced on the console as on the screens."""
    src = CONSOLE.read_text(encoding="utf-8")
    for banned in ("의성·안동에는 소방서가 없", "의성안동에는 소방서가 없",
                   "소방서가 없습니다."):
        assert banned not in src, banned


@console_only
def test_the_responder_note_survived_dash_normalisation_intact():
    """⚠ The source constant carries an EM dash the shipped font cannot draw.

    `_dash_safe` replaces the punctuation on the way to THIS screen only, so the
    generated `outputs/live/screens/**` screens keep the string
    `tests/test_operator_screen.py` pins verbatim. What must survive is the
    content, so it is checked here rather than assumed.
    """
    for region, p in console_regions().items():
        note = p["responder"]["status_ko"]
        assert "—" not in note and "–" not in note, (
            f"{region}: a banned dash reached the console's responder note")


@console_only
def test_switching_regions_resets_the_chosen_ignition_point():
    """A coordinate belongs to the region it was chosen in.

    Yeongdeok's walk bbox and Uiseong-Andong's do not overlap, so carrying a
    point across would leave the header showing one the new region cannot route
    from.
    """
    src = CONSOLE.read_text(encoding="utf-8")
    body = src[src.index("function mountRegion("):]
    body = body[:body.index("\n}")]
    for call in ("clearPoint()", "clearReject()", "applyDefaultStartGate()",
                 "renderResponderNote()", "setProjection()"):
        assert call in body, f"mountRegion does not call {call}"


@console_only
def test_the_dispatch_table_cannot_silently_clip_a_column():
    """⚠ The 1366x768 defect: 548 px of table in a 519 px pane, 29 px gone.

    `overflow:hidden` on the wrapper meant no scrollbar and no ellipsis — the
    구분 column simply stopped. `table-layout:fixed` makes the table exactly as
    wide as the pane, so the shortfall is spent on the one column that can
    ellipsise.
    """
    src = CONSOLE.read_text(encoding="utf-8")
    assert "table-layout:fixed" in src.replace(" ", ""), (
        "without fixed layout the nowrap cells set a min-content width and the "
        "last column is clipped at 1366x768")


@console_only
def test_every_status_code_the_console_prints_is_accompanied_by_a_sentence():
    """A bare HTTP number on screen is the defect, even when the refusal is right.

    Checked structurally: every place the console prints a status code, it must
    have shown the server's own wording first.
    """
    src = CONSOLE.read_text(encoding="utf-8")
    assert "function serverReason(" in src, (
        "nothing unwraps FastAPI's `detail` into a readable sentence")
    sites = list(re.finditer(r"stopLive\(`[^`]*HTTP \$\{", src))
    assert sites, "no status code is printed at all — has live mode gone?"
    for m in sites:
        window = src[max(0, m.start() - 500):m.start()]
        assert "showReject(" in window, (
            "a status code is printed with no sentence beside it at offset "
            f"{m.start()}")


# ---------------------------------------------------------------------------
# 7. One region's value, typed into a string every region reads
#
# The same defect three times in three files, and every one of them was CORRECT
# ON YEONGDEOK — which is why all three survived review. `check_region_literals`
# is scoped to the operator-facing builders and is demonstrated below to fail on
# each of the three as they were actually written.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO / "scripts"))
from check_region_literals import (  # noqa: E402
    KNOWN_REGION_LITERALS, check_repo, check_text, over_the_ratchet,
)

#: The three, reproduced verbatim from the commits that introduced them.
THE_THREE_DEFECTS: dict[str, tuple[str, str]] = {
    "build_operator_screen legend": (
        '      <b style="margin-top:7px">보행망 범위 (커버리지 32.6%)</b>',
        ".html"),
    "build_console payload": (
        '            "coverage_pct": 32.6,   # 보행망 커버리지',
        ".py"),
    "scope coverage caveat": (
        '    "영덕 수치는 정본 화재 핵심의 32.6 %만 덮는 보행망에서 '
        '산출되었습니다. "', ".py"),
}


@pytest.mark.parametrize("name", list(THE_THREE_DEFECTS))
def test_the_region_literal_check_catches_all_three(name):
    """⚠ The bar this checker was built to clear.

    It is not complete and does not try to be. It has to catch the shape these
    three had; anything beyond that is a bonus.
    """
    line, suffix = THE_THREE_DEFECTS[name]
    found = check_text(line, "probe" + suffix, suffix=suffix)
    assert found, f"{name}: the check does not fire on the original defect"


def test_the_check_stays_quiet_on_the_patterns_that_are_the_FIX():
    """A detector that always fires is as useless as one that never does.

    Each of these is the correct pattern the fix uses, and must not be flagged.
    """
    quiet = [
        ('    "yeongdeok_2025": 32.6,   # 보행망 커버리지', ".py"),
        ('COVERAGE_PCT = {"uiseong_andong_2025": 99.2}  # 커버리지', ".py"),
        ("    el('f-cov').textContent = `${D.honesty.coverage_pct}%`;", ".html"),
        ('    return f"{label} 수치는 {cov} %만 덮는 보행망에서"', ".py"),
        ("  # 영덕 was 32.6 % here and that is what made it survive", ".py"),
        ("  // 보행망 커버리지 32.6% used to be hardcoded here", ".html"),
    ]
    for line, suffix in quiet:
        found = check_text(line, "probe" + suffix, suffix=suffix)
        assert not found, f"false positive on the FIX pattern: {line!r} -> {found}"


def test_the_tree_carries_no_region_literal_above_the_recorded_floor():
    over = over_the_ratchet(check_repo())
    assert not over, "\n".join(
        f"{f.path}:{f.line} {f.what}\n    {f.excerpt}" for f in over)


def test_the_ratchet_floor_is_not_stale():
    """If a file improved below its allowance, lower it. A stale floor is a
    ceiling, and this repo already ratchets dashes and offline violations."""
    by_file: dict[str, int] = {}
    for f in check_repo():
        by_file[f.path] = by_file.get(f.path, 0) + 1
    for path, allowed in KNOWN_REGION_LITERALS.items():
        actual = by_file.get(path, 0)
        assert actual == allowed, (
            f"{path}: recorded floor {allowed}, actual {actual} — "
            "lower KNOWN_REGION_LITERALS so the floor holds the improvement")


# ---------------------------------------------------------------------------
# 8. LABEL_NEAR — a retired claim stated with no caveat nearby
#
# Added after the same defect turned up in five documents in one day, including
# MODEL_CARD.md, which the README calls the canonical source of truth and which
# carried a section headed "Headline finding (severity ≫ wind direction)" months
# after that conclusion was withdrawn.
# ---------------------------------------------------------------------------

from check_forbidden import (  # noqa: E402
    KNOWN_NEAR_UNLABELLED, LABEL_NEAR, NEAR_LABEL, NEAR_WINDOW, over_near_ratchet,
    pattern_for, scan, tracked_files,
)

#: Reproduced from the commits that introduced them, exactly as written.
THE_RETIRED_CLAIMS: dict[str, str] = {
    "MODEL_CARD section heading": "## Headline finding (severity ≫ wind direction)",
    "MODEL_CARD ratio": (
        "fire-weather **severity** importance 0.102 vs `wind_alignment` 0.0023 "
        "— a **44×**"),
    "baselines rationale": (
        "wind-direction interpretability** (the 44× permutation-importance ratio)"),
    "slope 2x2 table row": "| 거리 최소화 (현행, 기본값) | 440 / 17 / 3 | 440 / 17 / 3 |",
    "walk_bbox counts": "459 / 438 / 18 / 3 counts are correct for the origins",
}


@pytest.mark.parametrize("name", list(THE_RETIRED_CLAIMS))
def test_label_near_fires_on_every_retired_claim_as_written(name):
    """⚠ The bar this rule was built to clear: would it have caught them."""
    line = THE_RETIRED_CLAIMS[name]
    fired = any(pattern_for(tok, kind).search(line)
                for tok, kind, _why in LABEL_NEAR)
    assert fired, f"{name}: no LABEL_NEAR token matches the line as written"


def test_the_ratio_pattern_excludes_the_physics_models_different_ratios():
    """⚠ The first version ended in \\b and matched NOTHING for the × form.

    `×` is not a word character, so the boundary could never hold before the
    `**` in `**44×**` — only the ASCII `44x` spelling matched, and the rule
    silently passed the MODEL_CARD line it was written for.
    """
    rx = pattern_for("44×", "ratio")
    assert rx.search("importance 0.0023 — a **44×**"), (
        "the × form must match; a trailing \\b breaks it")
    assert rx.search("a 44x ratio"), "the ASCII form must match too"
    for other in ("| B drought-only | 3.34 | **1.44×** |",
                  "multiplicative (1.44 × 12.76 = 18.3×)"):
        assert not rx.search(other), (
            f"{other!r}: the physics model's LFMC x wind ratios are a different "
            "quantity and must not be flagged")


def test_the_label_vocabulary_does_not_accept_bare_canonical():
    """⚠ A baseline row reading 'hist_gbm (canonical reference)' eight lines up
    silenced a real finding in docs/baselines.md. Only the CONTRASTIVE usage
    counts."""
    lab = re.compile(NEAR_LABEL)
    assert not lab.search("| hist_gbm (canonical reference) | 0.890 | 0.905 |"), (
        "bare 'canonical' must not count as a caveat")
    for good in ("on the canonical field Yeongdeok's core advances fastest",
                 "정본 장에서는 414 / 42 / 2", "제출 시점 기록입니다",
                 "this claim is withdrawn as not established",
                 "a single point estimate whose spread was never measured"):
        assert lab.search(good), f"{good!r} should count as a caveat"


def test_the_tree_states_no_retired_claim_above_the_recorded_floor():
    _hard, _label, near, _sup, _skips = scan(tracked_files())
    over = over_near_ratchet(near)
    assert not over, "\n".join(
        f"{h['file']}:{h['line']} [{h['token']}] {h['why']}\n    {h['text']}"
        for h in over)


def test_the_near_ratchet_floor_is_not_stale():
    """A stale floor is a ceiling. Same rule as the dash and region ratchets."""
    _hard, _label, near, _sup, _skips = scan(tracked_files())
    by_file: dict[str, int] = {}
    for h in near:
        by_file[h["file"]] = by_file.get(h["file"], 0) + 1
    for rel, allowed in KNOWN_NEAR_UNLABELLED.items():
        actual = by_file.get(rel, 0)
        assert actual == allowed, (
            f"{rel}: recorded floor {allowed}, actual {actual} — lower "
            "KNOWN_NEAR_UNLABELLED so the floor holds the improvement")


def test_the_window_is_documented_as_measured_not_chosen():
    src = (REPO / "scripts" / "check_forbidden.py").read_text(encoding="utf-8")
    assert NEAR_WINDOW == 10
    assert "MEASURED, NOT CHOSEN" in src
    scope = (REPO / "docs" / "forbidden_check_scope.md").read_text(encoding="utf-8")
    assert "What LABEL_NEAR CANNOT do" in scope, (
        "the limitation must be recorded: a check that people read as safety is "
        "worse than no check")
