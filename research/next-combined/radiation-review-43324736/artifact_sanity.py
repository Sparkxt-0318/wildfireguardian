"""Read-only fixed-fixture and retained-artifact comparisons."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1] / "audit-1a"
sys.path.insert(0, str(ROOT / "experimental/flame-front-radiation/src"))
from wfg_flamefront import law_v2 as W

research = ROOT / "research/flame-front-radiation"
recorded = json.loads((research / "BOUND_RESULTS.json").read_text())
case = recorded["counterexample"]
point = case["point"]
member = {"ignition_time_s": case["ignition_time_s"]}
fuel = {"wind_xy": case["wind_xy"]}
t = case["time_s"]
q = float(W.flux_at_points([point], [t], member, case["grid"], fuel)[0,0])
bound = W.flux_enclosure([point[0],point[0],point[1],point[1]], [t,t], member, case["grid"], fuel)
assert q == case["new_point_kw_m2"] and list(bound) == case["new_enclosure_kw_m2"]
assert 0 < q <= bound[1] < case["old_point_kw_m2"]

tables = []
for name, key in (("MODEL_TABLE.csv", "flux_kw_m2"), ("TORNADO.csv", "flux_kw_m2"), ("INCOMPARABLE_DIAGNOSTICS.csv", "model_kw_m2")):
    current = list(csv.DictReader((research / "physics_validation" / name).open()))
    old = list(csv.DictReader(io.StringIO(gzip.decompress((research / "numerical_history/f9fa03290" / (name+".gz")).read_bytes()).decode())))
    assert len(current) == len(old)
    differences = [abs(float(a[key])-float(b[key])) for a,b in zip(current,old)]
    for a,b in zip(current,old):
        assert a.keys() == b.keys()
        # Check unchanged scenario and provenance columns, allowing only derived
        # flux, baseline and model/reference ratio columns to differ.
        for column in a:
            if column not in (key, "baseline_kw_m2", "ratio"):
                assert a[column] == b[column], (name, column, a[column], b[column])
    tables.append({"table":name,"rows":len(current),"changed_flux_values":sum(d != 0 for d in differences),"max_absolute_flux_change_kw_m2":max(differences)})

figures = []
for stem in ("fig01_flux_vs_distance", "fig02_parameter_sweep"):
    for suffix in ("png", "svg"):
        name = stem+"."+suffix
        current = (research / "physics_validation" / name).read_bytes()
        old = (research / "numerical_history/f9fa03290" / name).read_bytes()
        assert current == old
        item = {"name": name,"byte_identical":True,"sha256":hashlib.sha256(current).hexdigest()}
        if suffix == "png":
            assert current[:8] == b"\x89PNG\r\n\x1a\n"
            item["pixel_dimensions"] = struct.unpack(">II",current[16:24])
        figures.append(item)

result = {"status":"PASS","scope":"One fixed public counterexample, existing CSV arithmetic differences and byte comparisons; not an experimental or physical validation.","source_commit":"43324736fc5301a0444b01b918ef14a0372b1ec3","counterexample":{"point_kw_m2":q,"enclosure_kw_m2":bound},"tables":tables,"figures":figures}
Path(__file__).with_suffix(".json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result))
