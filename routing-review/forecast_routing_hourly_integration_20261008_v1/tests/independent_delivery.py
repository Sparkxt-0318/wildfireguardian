"""Independently check saved construction radiation and every finite witness.

Does not import author constructor, bridge, router or delivery route checker.
Input REPORT.json directories must also contain constructed_arrays.npz.
"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from independent_reference import witness, rectangular_source_sum, cell, edge_spans, integrate


def visited_witness_cells(graph, request, legs, destination):
    """Own route geometry, without importing the delivered occupancy builder."""
    nodes={n["id"]:n for n in graph["nodes"]}
    edges={e["id"]:e for e in graph["edges"]}
    cells=set()
    if "node" in request["position"]:
        n=nodes[request["position"]["node"]]
        cells.add(cell(graph,n["x"],n["y"]))
    for leg in legs:
        if leg["kind"]=="WAIT":
            n=nodes[leg["node"]]
            cells.add(cell(graph,n["x"],n["y"]))
        elif leg["kind"]=="EDGE":
            cells.update(c for c,_,_ in edge_spans(graph,edges[leg["edge"]],leg["start"],leg["end"],leg["from_fraction"],leg["to_fraction"]))
    n=nodes[destination]
    cells.add(cell(graph,n["x"],n["y"]))
    return cells


def check_report(path,graph):
    report=json.loads(path.read_text())
    md=report["native_metadata"]
    with np.load(path.parent/"constructed_arrays.npz",allow_pickle=False) as packet:
        arrays={name:packet[name] for name in packet.files}
    flux,flame,support=(arrays[k] for k in ("flux_w_m2","flame_contact","support"))
    S,K,H,W=flux.shape
    ids=["construction:"+md["construction_id"][:20]+":"+str(i) for i in range(S)]
    flip=md["affine_transform"][4]<0
    def flatten(x):
        x=x[:,::-1,:] if flip else x
        return x.reshape(K,H*W).tolist()
    hazard={"dt":md["dt_s"],"valid_from":md["breakpoints_s"][0],"valid_until":md["breakpoints_s"][-1],"members":[{"id":ids[s],"breakpoints":md["breakpoints_s"],"flux":flatten(np.where(support[s],flux[s],0)/1000),"flame":flatten(flame[s]),"support":flatten(support[s])} for s in range(S)]}
    rows=[]
    visited_cells=set()
    for row in report["rows"]:
        result=row["result"]
        req=row["request"]
        issue=None
        if "node" in req["position"]:
            n=next(n for n in graph["nodes"] if n["id"]==req["position"]["node"])
            stats,codes=integrate(hazard,[(cell(graph,n["x"],n["y"]),req["departure"],req["departure"])],req["incurred"],include_dose=False)
            known_failure="FLAME_CONTACT" in codes or any(s["peak"]>req["budgets"]["peak"] or s["dose"]>req["budgets"]["dose"][mid] for mid,s in stats.items())
            issue={"codes":sorted(codes),"known_issue_failure":bool(known_failure),"stats":{mid:{"dose":float(s["dose"]),"peak":s["peak"]} for mid,s in stats.items()}}
        if result.get("destination") is not None and result.get("legs") is not None:
            visited_cells.update(visited_witness_cells(graph,req,result["legs"],result["destination"]))
            checked=witness(graph,hazard,row["request"],result["legs"],result["destination"])
            equality=True
            if checked["ok"]:
                for mid,value in checked["per_member"].items():
                    equality &= abs(value["dose"]-result["per_member"][mid]["dose"])<=1e-9
                    equality &= value["peak"]==result["per_member"][mid]["peak"]
                equality &= checked["arrival"]==result["arrival"]
            rows.append({"iteration":row["iteration"],"primary_status_preserved":result["status"],"independent_issue":issue,"independent_witness":checked,"dose_peak_arrival_agree":bool(equality),"passes":checked["ok"] and equality})
        else:
            issue_agrees=result["status"]!="AT_ISSUE_FAILURE" or (issue is not None and issue["known_issue_failure"])
            timeout_stays_unresolved=result["status"]!="TIMEOUT" or "unresolved" in row.get("proof_level","").lower()
            rows.append({"iteration":row["iteration"],"primary_status_preserved":result["status"],"independent_issue":issue,"independent_witness":"NO_FINITE_WITNESS","passes":bool(issue_agrees and timeout_stays_unresolved),"interpretation":"No witness is not proof of infeasibility; primary status retained"})
    radiation=[]
    if report["mode"]=="research":
        config=md["construction"]["assumptions"]
        events=arrays["ignition_time_s"]
        current=arrays["current_active"]
        edges=arrays["time_edges_s"]
        frozen_receivers=[(0,0),(H//2,W//2),(H-1,W-1)]
        witness_receivers=sorted({(H-1-c//W if flip else c//W,c%W) for c in visited_cells})
        receivers=list(dict.fromkeys(frozen_receivers+witness_receivers))
        density=config["fuel_load_kg_m2"]*config["consumed_fraction"]*config["heat_of_combustion_j_kg"]/config["burning_duration_s"]
        for s in range(S):
            for k,(left,right) in enumerate(zip(edges[:-1],edges[1:])):
                # Independent direct event intersection of [A,A+T) with bin.
                union=(np.maximum(events[s],left)<np.minimum(events[s]+config["burning_duration_s"],right))
                if max(left,0)<min(right,config["initial_remaining_s"]):union |= current
                expected=rectangular_source_sum(union,md["affine_transform"],density,config["radiative_fraction"],config["emission_height_m"]-config["receiver_height_m"],receivers,config["atmospheric_transmissivity"])
                observed=np.array([flux[s,k,r,c] for r,c in receivers])
                guard=1e-8*max(1,float(flux[s,k].max())) if union.any() else 0
                residual=observed-expected
                passed=bool(np.all(residual>=-1e-6) and np.all(residual<=guard*1.01+1e-6) and np.array_equal(flame[s,k],union))
                radiation.append({"member":s,"interval":k,"receivers_native_rc":receivers,"frozen_probe_receivers_native_rc":frozen_receivers,"post_outcome_all_witness_receivers_native_rc":witness_receivers,"direct_W_m2":expected.tolist(),"stored_W_m2":observed.tolist(),"difference_W_m2":residual.tolist(),"declared_numerical_guard_W_m2":guard,"passes":passed})
    return {"report":str(path),"report_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"mode":report["mode"],"assumption_id":report["assumption_id"],"rows":rows,"radiation_rows":radiation,"witness_cell_count":len(visited_cells),"passes":all(r["passes"] for r in rows+radiation)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports",nargs="*",type=Path)
    parser.add_argument("--panel-rows",type=Path)
    parser.add_argument("--allow-partial",action="store_true",help="Development audit only; never a release-complete gate")
    parser.add_argument("--graph",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    D=Path(__file__).resolve().parents[1]
    graphpath=args.graph or D/"sample/uljin_graph.json"
    graph=json.loads(graphpath.read_text());graph=graph.get("graph",graph)
    paths=[]
    for p in args.reports:
        if p.is_dir(): paths.extend(sorted(p.rglob("REPORT.json")))
        else:paths.append(p)
    panel=None
    if args.panel_rows:
        master=json.loads(args.panel_rows.read_text())
        freeze_path=D/"EXPERIMENT_FREEZE_V3.json"
        freeze=json.loads(freeze_path.read_text())
        freeze_sha=hashlib.sha256(freeze_path.read_bytes()).hexdigest()
        queries={q["id"]:q["request_template"] for q in freeze["queries"]}
        variants={v["id"]:v for v in freeze["variants"]}
        expected_cases={f"{cutoff.replace('-','').replace(':','')}_{variant}_{query}" for cutoff in freeze["forecast_cutoffs"] for variant in variants for query in queries}
        seen=set();checks=[]
        for row in master:
            case=row["case"]
            path=D/row["report_path"]
            paths.append(path)
            mdreport=json.loads(path.read_text())
            assumptions=mdreport["native_metadata"]["construction"]["assumptions"]
            cfg={"version":"wfg.hazard.construction/1","variant":row["variant"]}
            cfg.update(freeze["default_construction"])
            cfg.update({k:v for k,v in variants[row["variant"]].items() if k!="id"})
            cfg["horizon_s"]=cfg.pop("forecast_horizon_s")
            state=cfg.pop("initial_state")
            cfg["current_state"]="known_burned_active" if state=="known_burned_active_assumption" else state
            if cfg["current_state"]=="cold":cfg["initial_remaining_s"]=0.0
            expectedq=queries[row["query"]]
            query_agrees=True
            for queryrow in mdreport["rows"]:
                q=queryrow["request"]
                query_agrees &= all(q[key]==expectedq[key] for key in ("position","incoming_edge","departure","horizon","destinations","objective","exposure_scope","limits","solver"))
                query_agrees &= q["budgets"]["peak"]==expectedq["budgets"]["peak"]
                query_agrees &= all(value==next(iter(expectedq["budgets"]["dose"].values())) for value in q["budgets"]["dose"].values())
                query_agrees &= all(value==0 for value in q["incurred"].values())
            check={"case":case,"unique_and_frozen":case in expected_cases and case not in seen,"source_guard":row.get("code_unchanged") is True,"experiment_hash_matches":row["experiment_sha256"]==freeze_sha,"config_matches":row["config"]==cfg==assumptions,"query_matches":bool(query_agrees),"exit_success":row["exit_code"]==0,"mode_and_class":mdreport["mode"]=="research" and mdreport["native_metadata"]["evidence_class"]=="RESEARCH_CONSTRUCTION","checkpoint_matches":mdreport["forecast"]["checkpoint_sha256"]==hashlib.sha256((D/"sample/checkpoint.pt").read_bytes()).hexdigest(),"statuses_match":row["statuses"]==[r["result"]["status"] for r in mdreport["rows"]]}
            check["passes"]=all(v for k,v in check.items() if k not in ("case","passes"))
            checks.append(check);seen.add(case)
        missing=sorted(expected_cases-seen)
        graph_matches=freeze["graph_sha256"]==hashlib.sha256(graphpath.read_bytes()).hexdigest() and freeze["source_graph_revision"]==graph["revision"]
        panel={"rows_source":str(args.panel_rows),"rows_sha256":hashlib.sha256(args.panel_rows.read_bytes()).hexdigest(),"expected_cases":len(expected_cases),"actual_cases":len(master),"missing_cases":missing,"case_checks":checks,"graph_matches":graph_matches,"complete":not missing,"passes":graph_matches and all(c["passes"] for c in checks) and (not missing or args.allow_partial),"development_partial":args.allow_partial}
    rows=[check_report(p,graph) for p in paths]
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result={"schema":"independent-native-witness-review/1","timestamp":stamp,"graph_revision":graph["revision"],"graph_sha256":hashlib.sha256(graphpath.read_bytes()).hexdigest(),"report_count":len(rows),"finite_witness_count":sum(sum(r["independent_witness"]!="NO_FINITE_WITNESS" for r in item["rows"]) for item in rows),"radiation_check_count":sum(len(item["radiation_rows"]) for item in rows),"radiation_receiver_evaluations":sum(sum(len(r["receivers_native_rc"]) for r in item["radiation_rows"]) for item in rows),"post_outcome_witness_receiver_evaluations":sum(sum(len(r["post_outcome_all_witness_receivers_native_rc"]) for r in item["radiation_rows"]) for item in rows),"witness_cell_count_summed_across_reports":sum(item["witness_cell_count"] for item in rows),"status_counts":dict(Counter(r["primary_status_preserved"] for item in rows for r in item["rows"])),"passes":bool(rows) and all(item["passes"] for item in rows) and (panel is None or panel["passes"]),"panel":panel,"rows":rows}
    destination=args.output or D/"evidence"/("independent_native_checks_"+stamp+".json")
    destination.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","panel")},indent=2))
    print("Report:",destination)
    return 0 if result["passes"] else 1


if __name__=="__main__":raise SystemExit(main())
