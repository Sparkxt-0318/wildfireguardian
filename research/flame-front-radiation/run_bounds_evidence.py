"""Reproduce numerical and geometry-bound controls, not a routing campaign."""
import csv
import gzip
import hashlib
import importlib.util
import json
import io
import math
from pathlib import Path
import platform
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"experimental/flame-front-radiation/src"))
import wfg_flamefront as W
from wfg_flamefront.geometric_bounds import quad_bound


def _hash(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run():
    legacy_path=HERE/"numerical_history/solidflame_f9fa03290.py"
    spec=importlib.util.spec_from_file_location("legacy_solidflame",legacy_path)
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    tau=np.array([[0.,1.],[0.,1.]]);member={"ignition_time_s":tau};grid=(20.,0.,0.,0.,20.,0.);fuel={"wind_xy":(2.,1.)}
    point=[350354922136235.44,-25174391049238.09];time=.1
    segments=W.front_segments(tau,time,grid,11.52,fuel=fuel)
    old=sum(legacy.rectangle_flux(point,s.start_xy,s.end_xy,s.flame_height_m,100.,tip_shift_xy=s.tip_shift_xy) for s in segments)
    new=float(W.flux_at_points([point],[time],member,grid,fuel)[0,0])
    box=(point[0],point[0],point[1],point[1]);bounds=W.flux_enclosure(box,(time,time),member,grid,fuel)
    _,proof=quad_bound(0,0,tau,grid,fuel,box)
    rows=[]
    for x in (100.,1000.,10000.):
        box=(x,x+10,-30.,-20.);low,upper=W.flux_enclosure(box,(.1,.8),member,grid,fuel)
        q=float(W.flux_at_points([[x+5,-25.]],[.4],member,grid,fuel)[0,0])
        rows.append({"box_x_min_m":x,"box_x_max_m":x+10,"box_y_min_m":-30,"box_y_max_m":-20,"interval_start_s":.1,"interval_end_s":.8,"point_flux_kw_m2":q,"upper_kw_m2":upper,"previous_coarse_upper_kw_m2":math.nextafter(400.,math.inf)})
    with (HERE/"BOUND_BOXES.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
    changes=[]
    historical=HERE/"numerical_history/f9fa03290"
    for table,key,value in (("MODEL_TABLE.csv",None,"flux_kw_m2"),("TORNADO.csv","parameter","flux_kw_m2"),("INCOMPARABLE_DIAGNOSTICS.csv",None,"model_kw_m2")):
        oldrows=list(csv.DictReader(io.StringIO(gzip.decompress((historical/(table+".gz")).read_bytes()).decode())))
        newrows=list(csv.DictReader((HERE/"physics_validation"/table).open()))
        assert len(oldrows)==len(newrows)
        deltas=[]
        for index,(a,b) in enumerate(zip(oldrows,newrows)):
            if key:assert a[key]==b[key]
            old_value=float(a[value]);new_value=float(b[value]);delta=abs(new_value-old_value)
            deltas.append((delta,delta/abs(old_value) if old_value else 0.))
        changes.append({"table":table,"rows":len(deltas),"changed_values":sum(delta!=0 for delta,_ in deltas),"max_absolute_change_kw_m2":max(d for d,_ in deltas),"max_relative_change":max(r for _,r in deltas)})
    old_qa=json.loads((historical/"FIGURE_QA.json").read_text());new_qa=json.loads((HERE/"physics_validation/FIGURE_QA.json").read_text())
    figure_changes={name:{kind:old_qa["figures"][name][kind]!=new_qa["figures"][name][kind] for kind in ("png_sha256","svg_sha256")} for name in old_qa["figures"]}
    result={"status":"PASS_MODEL_BOUND_CONTROLS","scope":"numerical evaluator and declared finite-panel bounds only","physics_gate":"UNRESOLVED_DO_NOT_RUN_ROUTING","routing_executions":0,"seed":20261030,"host":platform.platform(),"python":sys.version,"numpy":np.__version__,"command":"python research/flame-front-radiation/run_bounds_evidence.py","legacy_source_sha256":_hash(legacy_path),"counterexample":{"ignition_time_s":tau.tolist(),"grid":grid,"wind_xy":fuel["wind_xy"],"point":point,"time_s":time,"old_point_kw_m2":old,"new_point_kw_m2":new,"new_enclosure_kw_m2":bounds,"old_value_exceeds_new_model_upper":old>bounds[1],"new_value_enclosed":bounds[0]<=new<=bounds[1],"area_upper_exact":str(proof["area_upper"]),"distance2_lower_exact":str(proof["distance2_lower"]),"cone_proved":proof["cone_proved"]},"distance_boxes":rows,"prior_table_changes":changes,"prior_figure_byte_changes":figure_changes,"prior_results_directory":"numerical_history/f9fa03290","source_sha256":{str(p.relative_to(ROOT)):_hash(p) for p in sorted((ROOT/"experimental/flame-front-radiation/src/wfg_flamefront").glob("*.py"))},"limits":["whole-quad hulls do not necessarily converge to point geometry under spatial/time refinement","coarse fallback retained outside the proved angular cone","zero lower bound retained","no physical fit, mission experiment or field validation","point values are directed lower approximations before explicit orientation-envelope fallback"]}
    assert result["counterexample"]["old_value_exceeds_new_model_upper"] and result["counterexample"]["new_value_enclosed"]
    assert all(r["point_flux_kw_m2"]<=r["upper_kw_m2"] for r in rows)
    (HERE/"BOUND_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


if __name__=="__main__":print(json.dumps(run(),indent=2))
