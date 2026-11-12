"""(d) Check each SIPP route witness with the frozen independent journey checker (full policy: contact, peak, dose,
support, dwell) on the frozen HAZARD.json. A relaxation route need not pass; this measures how many do."""
import json, os, sys
from pathlib import Path
HERE = Path(os.path.abspath(__file__)).parent
sys.path.insert(0, str(HERE))
import cases
from wfg_scenario_members.contact import ContactModel
from wfg_sipp.frontend import sipp_plan
from wfg_synthetic_truth.frozen_checker import check_route

rows = []
for c in cases.korean_cases():
    g = json.loads(Path(c["graph"]).read_text()); r = json.loads(Path(c["request"]).read_text())
    hz = json.loads((Path(c["packet"]) / "HAZARD.json").read_text())
    res = sipp_plan(g, r, ContactModel.from_packet(c["packet"]), wall_s=120)
    if res["status"] != "ROUTE":
        continue
    chk = check_route(g, hz, r, res["legs"], res["destination"])
    peak_budget = r["budgets"]["peak"]
    row = dict(mission=c["mission"], arrival=res["arrival"], checker_status=chk["status"], codes=chk["codes"],
               checker_arrival=chk["arrival"], peak_budget=peak_budget,
               max_peak=max((v["peak"] for v in chk["per_member"].values()), default=None))
    rows.append(row); print(json.dumps(row), flush=True)
out = HERE / "results" / ("witness_check_py%d%d.json" % sys.version_info[:2])
out.write_text(json.dumps(rows, indent=1) + "\n")
print(sum(r["checker_status"] == "CHECKED_ROUTE" for r in rows), "of", len(rows), "CHECKED_ROUTE")
