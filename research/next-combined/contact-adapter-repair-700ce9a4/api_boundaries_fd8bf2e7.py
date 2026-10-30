"""Small synthetic API boundary probes; no native graph or study execution."""
import importlib.util
import json
from pathlib import Path
import sys
from fractions import Fraction as F
sys.dont_write_bytecode=True
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parent / "audit-1c"
for relative in ("experimental/sipp-routing/src","experimental/scenario-members/src","experimental/synthetic-truth/src"):
    sys.path.insert(0,str(REPO / relative))
spec=importlib.util.spec_from_file_location("contact_boundary_fixture", REPO / "experimental/sipp-routing/tests/test_known_footprint.py")
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
kf=fixture.kf
results={"commit":"fd8bf2e78532b76d2dd2cfd094d3499def90fc23","scope":"Tiny synthetic fixtures only; no real source arrays, graph, mission or campaign."}

raw,graph,request=fixture.fixture()
for method in ("sipp","sweep"):
    assert kf.plan_contact_route(graph,request,fixture.source(raw),method=method)["status"]==kf.CHECKED
raw["heat__initial_active_burning_probability"][2,1]=1
raw["heat__initial_remaining_burning_duration_s"][2,1]=100
s=fixture.source(raw)
results["contradictory_initial_activity"]={"known_burned":float(raw["source_burned_area"][2,1]),"known_active":float(raw["heat__initial_active_burning_probability"][2,1]),"source_R":str(s.R),"represented_current":bool(s.current_native[2,1]),"methods":{method:kf.plan_contact_route(graph,request,s,method=method)["status"] for method in ("sipp","sweep")},"raw_checker":kf.check_contact_route(graph,request,s,[fixture.leg()],"b")["ok"]}
forecast=dict(raw,new_burn_probability=np.zeros((3,3)),probability_valid=np.ones((3,3),dtype=bool),rate_per_h=np.zeros((3,3)),rate_valid=np.ones((3,3),dtype=bool))
try:
    fixture.bridge.construct(forecast,cutoff_utc="2025-01-01T00:00:00Z",epsg=5179,settings=fixture.bridge.v1.settings_for(3970.4642815249267))
    results["contradictory_initial_activity"]["existing_bridge"]="ACCEPTED"
except Exception as error:
    results["contradictory_initial_activity"]["existing_bridge"]=f"{type(error).__name__}: {error}"

raw,graph,request=fixture.fixture()
graph["nodes"][1]["x"]=1.5
graph["nodes"].append(dict(id="c",x=2.5,y=.5,waitable=True))
graph["edges"]=[dict(id="ab",u="a",v="b",travel_ticks=1),dict(id="ac",u="a",v="c",travel_ticks=2)]
request["destinations"]=[dict(node="b",dwell=1.5,open_intervals=[[0,3600]]),dict(node="c",dwell=0,open_intervals=[[0,3600]])]
for method in ("sipp","sweep"):
    result=kf.plan_contact_route(graph,request,fixture.source(raw),method=method)
    assert result["status"]==kf.CHECKED and result["arrival"]==1 and result["destination"]=="b"
s=fixture.source(raw,member_valid_until_s=[F(5,2),F(5,2)])
checked=kf.check_contact_route(graph,request,s,[fixture.leg(end=1)],"b")
assert checked["ok"] and checked["arrival"]==1
results["fractional_support_clock"]={"earlier_raw_checked_witness":{"arrival":checked["arrival"],"finish":checked["finish_including_dwell"]},"methods":{}}
for method in ("sipp","sweep"):
    result=kf.plan_contact_route(graph,request,s,method=method)
    results["fractional_support_clock"]["methods"][method]={k:result.get(k) for k in ("status","arrival","destination","effective_search_horizon_s","restricted_problem_optimality")}

raw,graph,request=fixture.fixture()
s=fixture.source(raw,cutoff_utc="2025-01-01T00:00:00.000000001Z")
results["nanosecond_clock_binding"]={"source_cutoff":s.cutoff_utc,"request_as_of":request["as_of"],"parsed_equal":kf._utc(s.cutoff_utc)==kf._utc(request["as_of"]),"methods":{method:kf.plan_contact_route(graph,request,s,method=method)["status"] for method in ("sipp","sweep")}}
(HERE / "api_boundaries_fd8bf2e7.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps(results))
