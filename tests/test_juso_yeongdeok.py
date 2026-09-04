"""The 영덕 주소정보누리집 subset: manifest, files and registry agree (laptop raw bundle not needed)."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "processed" / "external" / "juso_yeongdeok"


def test_manifest_counts_match_files():
    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert man["sigungu_cd"] == "47920"
    for layer, info in man["layers"].items():
        gj = json.loads((OUT / f"{layer}.geojson").read_text(encoding="utf-8"))
        assert len(gj["features"]) == info["count"], layer


def test_registry_keys_match_manifest():
    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    nums = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))["numbers"]
    for layer, info in man["layers"].items():
        e = nums[f"juso_yeongdeok_{layer}_count"]
        assert e["value"] == info["count"] and e["arm"] == "external" and e["agency"]


def test_it_is_not_the_building_layer():
    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert "NOT the 도로명주소 건물" in man["what"]
