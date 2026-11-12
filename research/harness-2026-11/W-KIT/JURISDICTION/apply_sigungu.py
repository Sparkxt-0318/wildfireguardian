"""Writes the delivered 시·군 labels (labels.json from label_sigungu.py) into the planner's places.geojson files.

Each origin of planner/public/data/regions/{uiseong_andong_2025,yeongdeok_2025}/places.geojson gets
`sigungu: {ko, status, reason, source}`. The run stops when:
  - the labels are a FIXTURE run;
  - their places_input sha256 does not match places_input.json;
  - an origin has no label, or a label names a place that is not an origin.
Nothing else in the files changes: same key order, compact separators, UTF-8.

If planner/tools/extract_places.py regenerates the place files, the labels are gone. The issuer contact line then
fails closed (not established) until this script is run again.

    python3.12 apply_sigungu.py labels.json [--check]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGIONS = ("uiseong_andong_2025", "yeongdeok_2025")


def apply(labels_path: Path) -> dict[Path, str]:
    doc = json.loads(labels_path.read_text(encoding="utf-8"))
    if doc.get("fixture") is not False:
        sys.exit("STOP: labels are a FIXTURE run (or unmarked)")
    pin = hashlib.sha256((HERE / "places_input.json").read_bytes()).hexdigest()
    if doc.get("places_input_sha256") != pin:
        sys.exit(f"STOP: labels were made from places_input {doc.get('places_input_sha256')}, not {pin}")
    labels = doc["labels"]
    out: dict[Path, str] = {}
    used: set[str] = set()
    for region in REGIONS:
        p = REPO / "planner/public/data/regions" / region / "places.geojson"
        fc = json.loads(p.read_text(encoding="utf-8"))
        for f in fc["features"]:
            pr = f["properties"]
            pr.pop("sigungu", None)
            if pr["role"] != "origin":
                continue
            lab = labels.get(pr["id"])
            if lab is None:
                sys.exit(f"STOP: origin {pr['id']} ({region}) has no label")
            pr["sigungu"] = {"ko": lab["ko"], "status": lab["status"], "reason": lab["reason"], "source": lab["source"]}
            used.add(pr["id"])
        out[p] = json.dumps(fc, ensure_ascii=False, separators=(",", ":")) + "\n"
    extra = set(labels) - used
    if extra:
        sys.exit(f"STOP: {len(extra)} labels name no origin: {sorted(extra)[:5]}")
    return out


def main() -> int:
    files = apply(Path(sys.argv[1]))
    check = "--check" in sys.argv
    bad = [str(p) for p, body in files.items() if check and p.read_text(encoding="utf-8") != body]
    if not check:
        for p, body in files.items():
            p.write_text(body, encoding="utf-8")
    if bad:
        print("differs:\n" + "\n".join(bad), file=sys.stderr)
        return 1
    print(f"{'checked' if check else 'wrote'} {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
