"""The finals presentation screen (web/finals.html).

The screen is a build artifact; every test that reads it is skipped when it
has not been built (same convention as the operator screens). What is pinned
here:

- the strict offline / dash gates pass on the built file;
- every displayed count is byte-consistent with the canonical artifacts
  (the screen is a presentation layer, never a source of numbers);
- the Yeongdeok coverage caveat rides along, region facts do not leak
  across regions, and retired-lineage figures do not appear;
- the four outcome buckets stay triple-encoded (colour + shape + glyph);
- media is optional by construction and motion preferences are honoured.
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
    check_dashes, check_dashes_in_scripts, check_offline,
)

FINALS = REPO / "web" / "finals.html"
TEMPLATE = REPO / "scripts" / "finals.template.html"

pytestmark = pytest.mark.skipif(
    not FINALS.exists(), reason="web/finals.html not built (make finals)")


def _text() -> str:
    return FINALS.read_text(encoding="utf-8")


def _payload() -> dict:
    m = re.search(
        r'<script id="data" type="application/json">(.*?)</script>',
        _text(), re.S)
    assert m, "embedded data payload not found"
    return json.loads(m.group(1))


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------


def test_the_screen_is_fully_offline_in_strict_mode():
    text = _text()
    assert check_offline(text) == []


def test_no_em_or_en_dash_survives_anywhere():
    text = _text()
    assert check_dashes(text, html=True) == []
    assert check_dashes_in_scripts(text) == []
    # the payload blind spot (docs'd in check_screen_assets) is closed at the
    # source: the builder normalises the whole JSON blob
    m = re.search(r'<script id="data"[^>]*>(.*?)</script>', text, re.S)
    assert "—" not in m.group(1) and "–" not in m.group(1)


def test_no_placeholder_leaks_into_the_built_page():
    marker = "/*__" + "DATA" + "__*/"
    assert marker not in _text()
    assert marker in TEMPLATE.read_text(encoding="utf-8")


def test_fonts_are_the_vendored_relative_files():
    text = _text()
    assert "assets/fonts/IBMPlexSansKR-Regular.woff2" in text
    assert "assets/fonts/IBMPlexMono-Regular.woff2" in text
    assert "assets/fonts/Pretendard-arrow.subset.woff2" in text


def test_reduced_motion_is_honoured_and_lang_is_korean():
    text = _text()
    assert "prefers-reduced-motion" in text
    assert '<html lang="ko">' in text


# --------------------------------------------------------------------------
# data integrity: the screen repeats the artifacts, never invents
# --------------------------------------------------------------------------


def _canonical_counts(region: str) -> dict:
    name = ("real_roads_real_hazard_canonical.json" if region == "yeongdeok_2025"
            else f"real_roads_real_hazard_{region}.json")
    data = json.loads((REPO / "data" / "processed" / name)
                      .read_text(encoding="utf-8"))
    return data["arms"]["slope_digraph_canonical"]["counts"]


def test_every_region_count_matches_its_canonical_artifact():
    payload = _payload()
    for region, rp in payload["regions"].items():
        want = _canonical_counts(region)
        for key, value in want.items():
            assert rp["counts"].get(key, 0) == value, (region, key)
        assert rp["n_scanned"] == sum(want.values()), region


def test_comparison_facts_come_from_the_committed_table():
    payload = _payload()
    table = json.loads((REPO / "data" / "processed" /
                        "multi_region_comparison.json").read_text(encoding="utf-8"))
    rows = {r["region"]: r for r in table["regions"]}
    assert payload["region_order"] == table["region_order"]
    for region, rp in payload["regions"].items():
        row = rows[region]
        assert rp["fa_only_pct"] == row["future_aware_only_safe_pct"], region
        assert rp["coverage_pct"] == round(
            row["envelope_coverage_final_slice"] * 100.0, 1), region
        assert rp["label"] == row["label_kr"], region
        assert rp["shelter_pois"] == row["shelter_pois"], region


def test_the_yeongdeok_coverage_caveat_rides_along():
    rp = _payload()["regions"]["yeongdeok_2025"]
    assert "32.6" in rp["coverage_note"]
    assert "편향의 방향" in rp["coverage_note"]


def test_region_facts_do_not_leak_across_regions():
    payload = _payload()
    # each region's fa-only percentage is unique in this dataset; make sure
    # no region record carries another region's value
    values = {r: p["fa_only_pct"] for r, p in payload["regions"].items()}
    assert len(set(values.values())) == len(values)
    # weather basis lines are region-specific strings from each run's scope
    lines = {r: p["weather_line"] for r, p in payload["regions"].items()}
    assert len(set(lines.values())) == len(lines)


def test_derived_road_states_are_internally_coherent():
    payload = _payload()
    for region, rp in payload["regions"].items():
        tr, tc = rp["roads"]["tr"], rp["roads"]["tc"]
        assert len(tr) == len(tc) == len(rp["roads"]["lens"]), region
        for a, b in zip(tr, tc):
            if b >= 0:
                assert a >= 0 and a <= b, region  # risk precedes closure
        loss = rp["loss"]["n"]
        assert all(x <= y for x, y in zip(loss, loss[1:])), region
        assert loss[-1] <= rp["loss"]["total_n"], region
        # the derivation thresholds are the pipeline's own
        assert payload["p_closed"] == 0.5 and payload["p_risk"] == 0.3


def test_the_flagship_pair_is_an_honest_contrast():
    payload = _payload()
    for region, rp in payload["regions"].items():
        rt = rp["routes"][rp["flagship"]]
        assert rt["naive"]["enters"] is True, region
        assert rt["fa"]["enters"] is False, region


def test_buckets_stay_triple_encoded():
    buckets = _payload()["buckets"]
    assert len(buckets) == 4
    assert len({b["shape"] for b in buckets}) == 4
    assert len({b["mark"] for b in buckets}) == 4
    assert len({b["fill"] for b in buckets}) == 4


# --------------------------------------------------------------------------
# claims discipline
# --------------------------------------------------------------------------


def _has_token(text: str, token: str) -> bool:
    pattern = r"(?<![\d.,])" + re.escape(token) + r"(?![\d])"
    return re.search(pattern, text) is not None


def test_retired_lineage_figures_do_not_appear():
    text = _text()
    for token in ("0.867", "0.8667", "0.834", "0.8340", "0.874", "0.8745",
                  "138619", "2731"):
        assert not _has_token(text, token), token
    for word in ("XGBoost", "Chen", "Guestrin", "multi-scale"):
        assert word not in text, word


def test_forbidden_framings_do_not_appear():
    # registry caveats quoted in the payload may NAME a forbidden framing in
    # order to negate it ("carries no 'lives saved' reading") — that is the
    # rule text, not a claim. Scan the page with caveat fields removed.
    text = re.sub(r'"caveat":".*?(?<!\\)"', '"caveat":""', _text())
    for phrase in ("정확도 89", "89% accurate", "실시간 예보",
                   "lives saved", "명을 구했", "구조했습니다",
                   "소방서가 없습니다", "deadline-first rescues",
                   "우선순위가 검증", "최초로", "처음으로"):
        assert phrase not in text, phrase
    # pooled must never be presented as the fold mean
    assert "pooled AUC 0.890" not in text


def test_the_negative_ordering_result_is_stated_not_hidden():
    text = _text()
    assert "모서리" in text          # corner-not-boundary quote
    assert "이기는" in text or "존재하지 않" in text


def test_media_is_optional_by_construction():
    text = _text()
    # the intro must carry its no-media fallback, and nothing may fetch()
    assert "introFallback" in text
    assert "fetch(" not in text


def test_provenance_is_on_screen():
    payload = _payload()
    for region, rp in payload["regions"].items():
        assert rp["prov"]["run"], region
        assert rp["prov"]["npz_sha16"], region
        assert rp["prov"]["walk_snap"].startswith("osm-walk_"), region
