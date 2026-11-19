"""OSM way -> Overture 2026-10-21.0 road name / ref / class (as kcf-roadcut amendment 2(b)). -> roadnames.json
Usage: python3 roadnames.py overture_segments.parquet"""
import json, re, sys
from pathlib import Path
import pyarrow.parquet as pq
ROOT = Path(__file__).resolve().parents[2]
ways = set()
for r in ["yeongdeok_2025", "uiseong_andong_2025"]:
    for e in json.loads((ROOT / f"data/routing/graphs/{r}/graph.json").read_text())["edges"]:
        m = re.search(r"(\d+)", str(e.get("source_way")))
        if m: ways.add(int(m.group(1)))
t = pq.read_table(sys.argv[1], columns=["subtype", "class", "names", "routes", "sources"]).to_pylist()
out = {}
for x in t:
    if x["subtype"] != "road": continue
    nm = (x["names"] or {}).get("primary")
    refs = sorted({r.get("ref") for r in (x["routes"] or []) if r.get("ref")})
    for s in x["sources"] or []:
        m = re.match(r"w(\d+)", s.get("record_id") or "")
        if m and int(m.group(1)) in ways:
            out[m.group(1)] = {"name": nm, "refs": refs, "class": x["class"]}
Path("roadnames.json").write_text(json.dumps(out, ensure_ascii=False, sort_keys=True))
print(len(ways), "graph ways;", len(out), "joined;", sum(1 for v in out.values() if v["name"] or v["refs"]), "with name/ref")
