"""The 주소정보누리집 subset: manifest, files and registry agree (laptop raw bundle not needed).

**WFG-075, 2026-09-04.** This file used to assert `man["sigungu_cd"] == "47920"` as a
correctness property of a subset labelled 영덕. It passed, every lap, on data that is not
영덕's: the filter constant was mis-labelled and the geometry sits about 45 km away. The
assertion is kept and marked `xfail`, not deleted, so the record of what was enforced
survives; it flips back to a passing assertion when NH-022 re-cuts the subset with a code
read off 행정표준코드. The tests below it are the containment: they fail if the correction
is ever dropped from the registry or the document.
"""
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "processed" / "external" / "juso_yeongdeok"
# The canonical 영덕 box the forecast and the router run on (config/default.yaml:83).
YEONGDEOK_BBOX = (129.25, 36.30, 129.55, 36.60)


def _manifest() -> dict:
    return json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.xfail(
    strict=True,
    reason="WFG-075/NH-022: 47920 is labelled 영덕군 and its geometry is not in 영덕. Kept as "
           "the record of what this suite enforced; re-cut on the laptop makes it pass again.",
)
def test_the_subset_is_cut_on_yeongdeoks_sigungu_code():
    man = _manifest()
    assert man["sigungu_cd"] == "47920"
    lo0, la0, lo1, la1 = YEONGDEOK_BBOX
    for layer in man["layers"]:
        gj = json.loads((OUT / f"{layer}.geojson").read_text(encoding="utf-8"))
        for feat in gj["features"]:
            x, y = feat["geometry"]["coordinates"]
            assert lo0 <= x <= lo1 and la0 <= y <= la1, layer


def test_manifest_counts_match_files():
    man = _manifest()
    for layer, info in man["layers"].items():
        gj = json.loads((OUT / f"{layer}.geojson").read_text(encoding="utf-8"))
        assert len(gj["features"]) == info["count"], layer


def test_registry_keys_match_manifest():
    man = _manifest()
    nums = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))["numbers"]
    for layer, info in man["layers"].items():
        e = nums[f"juso_yeongdeok_{layer}_count"]
        assert e["value"] == info["count"] and e["arm"] == "external" and e["agency"]


def test_it_is_not_the_building_layer():
    assert "NOT the 도로명주소 건물" in _manifest()["what"]


def test_not_one_point_is_inside_the_yeongdeok_box():
    """The measurement WFG-075 rests on, re-run from the committed files every suite."""
    lo0, la0, lo1, la1 = YEONGDEOK_BBOX
    total = inside = 0
    for layer in _manifest()["layers"]:
        gj = json.loads((OUT / f"{layer}.geojson").read_text(encoding="utf-8"))
        for feat in gj["features"]:
            x, y = feat["geometry"]["coordinates"]
            total += 1
            inside += lo0 <= x <= lo1 and la0 <= y <= la1
    assert total == 239, f"the committed subset holds 239 points, found {total}"
    assert inside == 0, (
        f"{inside} of {total} points are now inside the 영덕 box. If the subset was re-cut "
        "(NH-022), delete this test and un-xfail test_the_subset_is_cut_on_yeongdeoks_sigungu_code."
    )


def test_every_registry_entry_carries_the_scope_correction():
    """WFG-075 (a): the correction is on the entries, not only in a document."""
    nums = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))["numbers"]
    keys = [k for k in nums if k.startswith("juso_yeongdeok_")]
    assert len(keys) == 8, keys
    for k in keys:
        e = nums[k]
        assert e["caveat"].startswith("SCOPE WRONG, DO NOT USE AS 영덕 DATA"), k
        assert "NH-022" in e["caveat"] and "WFG-075" in e["caveat"], k
        assert e["scope_status"].startswith("wrong"), k
        assert e["forbidden_phrasings"], k


def test_the_wrong_label_is_kept_as_the_record():
    """WFG-075: annotate, never edit. The claim that was made stays visible beside its correction."""
    nums = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))["numbers"]
    for k, e in nums.items():
        if k.startswith("juso_yeongdeok_"):
            assert "영덕군" in e["scope"] and e["sample"] == "영덕군", k


def test_the_document_opens_on_the_correction():
    """WFG-075 (b): a reader who stops after the first screen still learns the file is wrong."""
    text = (REPO / "docs" / "juso_yeongdeok.md").read_text(encoding="utf-8")
    head = text.split("**What this is.**")[0]
    assert "정정 (2026-09-04, WFG-075)" in head
    assert "NH-022" in head and "45 km" in head
    assert "WFG-066" in head, "the document must say why the correct county is not written down"
