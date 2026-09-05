"""The 주소정보누리집 subset: manifest, files and registry agree (laptop raw bundle not needed).

**WFG-075, 2026-09-04.** This file used to assert `man["sigungu_cd"] == "47920"` as a
correctness property of a subset labelled 영덕. It passed, every lap, on data that is not
영덕's: the filter constant was mis-labelled and the geometry is outside the 영덕 box on both
axes.

The property the suite ought to have held -- that the subset is *in* 영덕 -- is written here as
its own `xfail(strict=True)` test, so the record of what was and was not enforced survives and
a correct re-cut (NH-022) turns it green and the suite red. The manifest/extractor agreement it
used to be bundled with stays a passing test, because that one was never broken. The rest are
the containment: they fail if the correction is dropped from the registry or the document.

**Re-cut 2026-09-04 (NH-022, laptop):** the subset is now cut on 47770 and verified by address and
by set containment; the xfail marker is gone and the registry entries read SCOPE CORRECTED.
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "processed" / "external" / "juso_yeongdeok"
# The canonical 영덕 box the forecast and the router run on (config/default.yaml:83).
YEONGDEOK_BBOX = (129.25, 36.30, 129.55, 36.60)


def _manifest() -> dict:
    return json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))


def test_the_manifest_records_the_code_the_subset_was_actually_cut_on():
    """Still enforced, and deliberately not folded into the xfail below.

    The first draft of this fix appended the (failing) geometry assertion to this
    (passing) one and xfailed the pair, which silently stopped enforcing a property
    that was never broken: that the manifest records the same 시군구 code the
    extractor used. Independent review caught it. The two are separate tests, and
    this one is written against the script rather than the literal "47920" so a
    correct re-cut (NH-022) leaves it passing instead of red.
    """
    src = (REPO / "scripts" / "extract_juso_yeongdeok.py").read_text(encoding="utf-8")
    m = re.search(r'^SIGUNGU\s*=\s*"(\d{5})"', src, re.M)
    assert m, "extract_juso_yeongdeok.py no longer declares SIGUNGU"
    assert _manifest()["sigungu_cd"] == m.group(1)


def test_the_subset_lies_inside_the_yeongdeok_box():
    """Was xfail(strict) until the re-cut (NH-022, 2026-09-04). 영덕군 is larger than the routing
    canvas, so the rule is set containment: every non-empty layer's centroid inside the box and at
    least half its points inside; and every agency road address names 영덕군."""
    lo0, la0, lo1, la1 = YEONGDEOK_BBOX
    man = _manifest()
    assert man["sigungu_cd"] == "47770" and man["bbox_check"]["result"] == "pass"
    for layer, info in man["layers"].items():
        if not info["count"]:
            continue
        gj = json.loads((OUT / f"{layer}.geojson").read_text(encoding="utf-8"))
        pts = [feat["geometry"]["coordinates"][:2] for feat in gj["features"]]
        inside = sum(lo0 <= x <= lo1 and la0 <= y <= la1 for x, y in pts) / len(pts)
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        assert inside >= 0.5 and lo0 <= cx <= lo1 and la0 <= cy <= la1, (layer, inside, cx, cy)
    for feat in json.loads((OUT / "minwon_agencies.geojson").read_text(encoding="utf-8"))["features"]:
        assert "영덕군" in feat["properties"]["road_address"]


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


def test_every_registry_entry_carries_the_scope_correction():
    """WFG-075 (a): the correction is on the entries, not only in a document."""
    nums = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))["numbers"]
    keys = [k for k in nums if k.startswith("juso_yeongdeok_")]
    assert len(keys) == 8, keys
    for k in keys:
        e = nums[k]
        assert e["caveat"].startswith("SCOPE CORRECTED"), k
        assert "NH-022" in e["caveat"] and "WFG-075" in e["caveat"], k
        assert e["scope_status"].startswith("corrected"), k


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
    assert "NH-022" in head
    assert "45 km" not in head.split("킬로미터 거리는 여기에 쓰지 않는다")[0], (
        "an unregistered distance must not be asserted before the sentence that withdraws it")
    assert "WFG-066" in head, "the document must say why the correct county is not written down"
