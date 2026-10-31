"""Fixed contact K campaign ledger, custody checks and descriptive figures."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CHECKED = "CHECKED_CONTACT_ROUTE_WITHIN_KNOWN_FOOTPRINT"
KS = (4,8,16,32)
COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def csv_write(path, rows, columns):
    with Path(path).open("w") as stream:
        writer = csv.DictWriter(stream, columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def analyze(folder):
    rows = [json.loads(s) for s in (folder/"EXECUTIONS.jsonl").read_text().splitlines()]
    bundle = json.loads((folder/"BUNDLE.json").read_text())
    planned = json.loads((folder/"JOBS.json").read_text())
    summary = json.loads((folder/"RESULTS.json").read_text())
    if len(rows)!=320 or len(planned)!=320 or [r["job_index"] for r in rows]!=list(range(320)):
        raise ValueError("COMPLETE_ORDERED_FIXED_320_RECORDS_REQUIRED")
    for key, values in (("K",set(KS)),("method",{"sweep","sipp"}),("repetition",{1,2})):
        if {r[key] for r in rows}!=values:
            raise ValueError("FIXED_FACTOR_LEVELS_CHANGED:"+key)
    source_heads = {r["source_phase_head"] for r in rows}
    if source_heads!={bundle["source_phase_head"]}:
        raise ValueError("MIXED_EXECUTED_SOURCE_PHASES")
    for path, expected in {**bundle["protocol"]["source_pins"], **bundle["protocol"]["evidence_pins"]}.items():
        if sha(ROOT/path)!=expected:
            raise ValueError("SOURCE_OR_PRIOR_EVIDENCE_CHANGED:"+path)
    if sha(ROOT/"research/sipp-routing/KNOWN_FOOTPRINT_K_PROTOCOL.json")!=bundle["protocol_sha256"]:
        raise ValueError("PROTOCOL_BYTES_CHANGED")
    input_pins={}
    for binding in bundle["bindings"]:
        case=binding["original_case"]
        for key in ("graph","request"):
            input_pins[case[key]]=case["input_sha256"][key]
        for name in ("NATIVE_METADATA.json","REPORT.json","HAZARD.json","constructed_arrays.npz"):
            input_pins[str(Path(case["packet"])/name)]=case["input_sha256"][name]
        input_pins[binding["window"]["npz"]]=binding["window"]["npz_sha256"]
        input_pins[binding["topology"]["source"]["record"]]=binding["window"]["record_sha256"]
    for path,expected in input_pins.items():
        if sha(path)!=expected:
            raise ValueError("POST_RUN_ORIGINAL_INPUT_BYTES_CHANGED:"+path)
    dump(folder/"POST_RUN_INPUT_CUSTODY.json",dict(status="PASS_ORIGINAL_INPUT_BYTES_PRESERVED",sha256=input_pins,
        scope="Full current original input file hashes after all rows; no rerun, graph parse or additional planner."))
    repair=json.loads((ROOT/"research/sipp-routing/KNOWN_FOOTPRINT_ADAPTER_REPAIR_RECEIPT.json").read_text())
    for path,expected in {**repair["preserved_evidence_sha256"],**repair["reviewed_artifacts_preserved_sha256"]}.items():
        if sha(ROOT/path)!=expected:
            raise ValueError("IMMUTABLE_PRIOR_EVIDENCE_CHANGED:"+path)
    unsupported_missions={b["original_case"]["mission"] for b in bundle["bindings"] if b["unsupported_endpoints"]}
    if len(unsupported_missions)!=14:
        raise ValueError("ORIGINAL_UNKNOWN_ENDPOINT_SCOPE_CHANGED")
    posthoc=[]
    for row, job in zip(rows,planned):
        if any(row[k]!=job[k] for k in job):
            raise ValueError("JOB_ORDER_OR_IDENTITY_CHANGED")
        if row["mission"] in unsupported_missions:
            if row["status"]==CHECKED or row["search_started"] or row["solver_metrics"] is not None or row["planner_wall_s"] is not None:
                raise ValueError("UNSUPPORTED_ENDPOINT_COST_OR_CLAIM_LEAK")
        if row["control"]["stop"] is None and row.get("original_request_utf8"):
            request=json.loads(row["original_request_utf8"])
            if request!=row["original_request"]:
                raise ValueError("ORIGINAL_REQUEST_HISTORY_CHANGED")
            binding=next(b for b in bundle["bindings"] if b["original_case"]["mission"]==row["mission"])
            if hashlib.sha256(row["original_request_utf8"].encode()).hexdigest()!=binding["original_case"]["input_sha256"]["request"]:
                raise ValueError("ORIGINAL_REQUEST_TEXT_BYTES_CHANGED")
        if row["status"]==CHECKED:
            if not row.get("independent_recheck",{}).get("ok"):
                raise ValueError("RETURNED_ROUTE_LACKS_PASSING_ORIGINAL_DATA_RECHECK")
            if row["planner_claim"]["original_request"]!=row["original_request"]:
                raise ValueError("PUBLIC_PLANNER_HISTORY_CHANGED")
            checked=row["independent_recheck"]
            if len(checked["per_member"])!=row["K"] or any(not m["contact_pass"] for m in checked["per_member"]):
                raise ValueError("INCOMPLETE_MEMBER_CONTACT_RECHECK")
            if checked["finish_including_dwell"]>3600 or any(row[k] is not None for k in ("peak","dose","risk")):
                raise ValueError("SOURCE_CLOCK_OR_CONTACT_ONLY_SCOPE_CHANGED")
            posthoc.append(dict(job_index=row["job_index"],mission=row["mission"],K=row["K"],method=row["method"],
                repetition=row["repetition"],source_phase_head=row["source_phase_head"],source=row["source"],
                original_request_sha256=hashlib.sha256(row["original_request_utf8"].encode()).hexdigest(),
                independent_recheck=row["independent_recheck"]))
    pairs=[]
    for mission in dict.fromkeys(r["mission"] for r in rows):
        for K in KS:
            for rep in (1,2):
                a=next(r for r in rows if (r["mission"],r["K"],r["repetition"],r["method"])==(mission,K,rep,"sweep"))
                b=next(r for r in rows if (r["mission"],r["K"],r["repetition"],r["method"])==(mission,K,rep,"sipp"))
                joint=all(r["search_started"] and r["control"]["stop"] is None and r["control"]["exit_code"]==0
                          and r.get("search_status") in ("FOUND","EXHAUSTED","CONDITIONAL_OPTIMUM","CHECKED_ROUTE","PROVEN_INFEASIBLE","DISCONNECTED") for r in (a,b))
                checked=all(r["status"]==CHECKED for r in (a,b))
                if a.get("source",{}).get("raw_array_sha256")!=b.get("source",{}).get("raw_array_sha256"):
                    raise ValueError("METHODS_CONSUMED_DIFFERENT_RAW_ARRAYS")
                if a.get("planner_claim") and b.get("planner_claim"):
                    if a["planner_claim"]["support_barriers"]!=b["planner_claim"]["support_barriers"]:
                        raise ValueError("METHODS_CONSUMED_DIFFERENT_SUPPORT_BARRIERS")
                if mission in unsupported_missions:
                    verdict="BOTH_PRESEARCH_UNSUPPORTED_ENDPOINTS"
                elif checked and a["arrival"]==b["arrival"]:
                    verdict="MATCHED_CHECKED_CONTACT_ARRIVAL"
                elif joint and all(r["status"]!=CHECKED and r.get("search_status") in ("EXHAUSTED","PROVEN_INFEASIBLE","DISCONNECTED") for r in (a,b)):
                    verdict="MATCHED_RESTRICTED_EXHAUSTION"
                elif not joint:
                    verdict="UNRESOLVED_OR_PRESEARCH_CONTACT_FAILURE"
                else:
                    verdict="CONTACT_OUTCOME_OR_ARRIVAL_DISAGREEMENT"
                pairs.append(dict(mission=mission,K=K,repetition=rep,verdict=verdict,joint_search_complete=joint,
                    sweep_status=a["status"],sipp_status=b["status"],sweep_arrival=a.get("arrival"),sipp_arrival=b.get("arrival"),
                    sweep_planner_wall_s=a.get("planner_wall_s"),sipp_planner_wall_s=b.get("planner_wall_s"),
                    sweep_complete_child_wall_s=a["complete_child_wall_s"],sipp_complete_child_wall_s=b["complete_child_wall_s"],
                    planner_ratio_sipp_over_sweep=b["planner_wall_s"]/a["planner_wall_s"] if joint and verdict in ("MATCHED_CHECKED_CONTACT_ARRIVAL","MATCHED_RESTRICTED_EXHAUSTION") else None,
                    complete_child_ratio_sipp_over_sweep=b["complete_child_wall_s"]/a["complete_child_wall_s"] if joint and verdict in ("MATCHED_CHECKED_CONTACT_ARRIVAL","MATCHED_RESTRICTED_EXHAUSTION") else None))
    csv_write(folder/"PAIRS.csv",pairs,list(pairs[0]))
    flat=[]
    for r in rows:
        m=r.get("solver_metrics") or {}
        flat.append(dict(**{k:r.get(k) for k in ("job_index","mission","region","K","method","repetition","status","reason","arrival","search_started","admission_wall_s","planner_wall_s","complete_child_wall_s")},
                         sipp_expansions=m.get("expansions"),sipp_pieces=m.get("pieces"),sweep_states_reached=m.get("states_reached"),
                         sweep_seconds=m.get("sweep_seconds"),blocked_edges=m.get("blocked_edges"),control_stop=r["control"]["stop"],
                         peak_rss_mib=r["control"]["reported_peak_rss_mib"],independent_recheck_ok=(r.get("independent_recheck") or {}).get("ok")))
    csv_write(folder/"EXECUTIONS.csv",flat,list(flat[0]))
    with (folder/"INDEPENDENT_RECHECKS.jsonl").open("w") as stream:
        for row in posthoc:stream.write(json.dumps(row,allow_nan=False)+"\n")
    joint=[p for p in pairs if p["planner_ratio_sipp_over_sweep"] is not None]
    search=[r for r in rows if r["search_started"]]
    metric_repeat_mismatches=[]
    for r in search:
        if r["repetition"]!=1:continue
        r2=next(x for x in rows if (x["mission"],x["K"],x["method"],x["repetition"])==(r["mission"],r["K"],r["method"],2))
        key="expansions" if r["method"]=="sipp" else "states_reached"
        if (r["solver_metrics"] or {}).get(key)!=(r2["solver_metrics"] or {}).get(key):
            metric_repeat_mismatches.append(dict(mission=r["mission"],K=r["K"],method=r["method"],counter=key))
    analysis=dict(schema="wfg.next.known-contact-K-analysis/1",source_phase_head=bundle["source_phase_head"],
        producer_sha256=sha(__file__),record_count=len(rows),pairs=len(pairs),missions=20,
        execution_statuses=dict(collections.Counter(r["status"] for r in rows)),pair_verdicts=dict(collections.Counter(p["verdict"] for p in pairs)),
        unsupported_endpoint_missions=14,unsupported_endpoint_records=sum(r["mission"] in unsupported_missions for r in rows),
        search_started_records=len(search),checked_route_records=len(posthoc),independent_original_data_rechecks_passed=len(posthoc),
        control_refusals=dict(collections.Counter(r["control"]["stop"] for r in rows if r["control"]["stop"])),
        all_owned_groups_absent=all(r["control"]["owned_group_absent"] for r in rows),
        joint_checked_search_pairs=sum(p["verdict"]=="MATCHED_CHECKED_CONTACT_ARRIVAL" for p in joint),
        joint_complete_search_pairs=len(joint),counter_repeat_mismatches=metric_repeat_mismatches,
        median_planner_ratio_sipp_over_sweep=float(np.median([p["planner_ratio_sipp_over_sweep"] for p in joint])) if joint else None,
        median_complete_child_ratio_sipp_over_sweep=float(np.median([p["complete_child_ratio_sipp_over_sweep"] for p in joint])) if joint else None,
        sipp_slower_planner_pairs=sum(p["planner_ratio_sipp_over_sweep"]>1 for p in joint),
        source_clock=dict(seed=20261008,timing="uniform",H_s=3600,T_s=3970.4642815249267),
        source_and_protocol_hashes_match=True,original_request_history_bytes_preserved=True,
        shared_original_array_and_support_barrier_digests_match=True,
        prior_35_evidence_and_4_review_artifacts_byte_preserved=True,
        post_run_original_input_files_checked=len(input_pins),
        max_complete_child_wall_s=max(r["complete_child_wall_s"] for r in rows),
        max_reported_child_peak_rss_mib=max(r["control"]["reported_peak_rss_mib"] for r in rows),
        host=bundle["host"],python=bundle["python"],numpy=bundle["numpy"],scope=summary["scope"],
        limits="Two repetitions are paired verification repeats, not independent missions/fires. Thermal history/peak/dose/risk unknown; restricted failures are unresolved about the original unknown domain. Source T>H limits multi-interval fragmentation expectations.")
    analysis["by_K"]=[dict(K=K,records=sum(r["K"]==K for r in rows),
        checked_routes=sum(r["K"]==K and r["status"]==CHECKED for r in rows),
        search_started=sum(r["K"]==K and r["search_started"] for r in rows),
        matched_checked_pairs=sum(p["K"]==K and p["verdict"]=="MATCHED_CHECKED_CONTACT_ARRIVAL" for p in pairs),
        matched_restricted_exhaustion_pairs=sum(p["K"]==K and p["verdict"]=="MATCHED_RESTRICTED_EXHAUSTION" for p in pairs)) for K in KS]
    mission_table=[]
    for mission in dict.fromkeys(r["mission"] for r in search):
        entries=[]
        for K in KS:
            selected=[r for r in rows if r["mission"]==mission and r["K"]==K]
            if all(r["status"]==CHECKED for r in selected) and len({r["arrival"] for r in selected})==1:
                entries.append(str(selected[0]["arrival"]))
            elif all(r.get("search_status") in ("EXHAUSTED","PROVEN_INFEASIBLE","DISCONNECTED") for r in selected):
                entries.append("restricted exhaustion")
            else:
                entries.append("unresolved, see ledger")
        mission_table.append("| "+mission+" | "+" | ".join(entries)+" |")
    dump(folder/"ANALYSIS.json",analysis)
    figures=folder/"figures";figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8,"axes.spines.top":False,"axes.spines.right":False,"savefig.facecolor":"white"})
    def save(fig,name):
        fig.savefig(figures/(name+".png"),dpi=300)
        fig.savefig(figures/(name+".svg"))
        plt.close(fig)
    if joint:
        fig,axes=plt.subplots(1,2,figsize=(7.2,3.1))
        for K,color in zip(KS,COLORS):
            items=[p for p in joint if p["K"]==K]
            for ax,metric in zip(axes,("planner_wall_s","complete_child_wall_s")):
                ax.scatter([p["sweep_"+metric] for p in items],[p["sipp_"+metric] for p in items],s=18,color=color,label="K = %d"%K,alpha=.8)
        for ax,title in zip(axes,("Contact planner call","Complete child incl. recheck")):
            lo,hi=min(ax.get_xlim()[0],ax.get_ylim()[0]),max(ax.get_xlim()[1],ax.get_ylim()[1])
            lo=max(0,lo);ax.plot([lo,hi],[lo,hi],color="#777777",lw=.8);ax.set_xlim(lo,hi);ax.set_ylim(lo,hi)
            ax.set_xlabel("Sweep time (s)");ax.set_ylabel("SIPP time (s)");ax.set_title(title)
        handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc="lower center",ncol=4,bbox_to_anchor=(.5,.005),frameon=False)
        fig.tight_layout(rect=(0,.12,1,1));save(fig,"fig01_contact_K_time_paired")
    if search:
        missions=list(dict.fromkeys(r["mission"] for r in search))
        fig,axes=plt.subplots(1,2,figsize=(7.2,3.8))
        for mission,color in zip(missions,COLORS):
            for ax,method,counter in zip(axes,("sipp","sweep"),("expansions","states_reached")):
                for rep in (1,2):
                    rs=[r for r in search if r["mission"]==mission and r["method"]==method and r["repetition"]==rep]
                    ax.plot([r["K"] for r in rs],[(r["solver_metrics"] or {}).get(counter,np.nan) for r in rs],
                            color=color,marker="o" if rep==1 else "x",ls="-" if rep==1 else ":",lw=1,ms=3,label=mission if rep==1 else None)
        for ax,label in zip(axes,("SIPP expansions (count)","Sweep states reached (count)")):
            ax.set_yscale("log")
            ax.set_xscale("log",base=2);ax.set_xticks(KS,labels=list(map(str,KS)));ax.set_xlabel("Original saved members K (count)");ax.set_ylabel(label)
        handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc="lower center",ncol=3,bbox_to_anchor=(.5,.005),frameon=False,fontsize=6.5)
        fig.tight_layout(rect=(0,.18,1,1));save(fig,"fig02_states_vs_members")
    fig,ax=plt.subplots(figsize=(3.5,3.0));x=np.arange(4);bottom=np.zeros(4)
    groups=[("Checked local contact",lambda r:r["status"]==CHECKED,"#009E73"),
            ("Unknown endpoints",lambda r:r["mission"] in unsupported_missions,"#999999"),
            ("Other unresolved",lambda r:r["status"]!=CHECKED and r["mission"] not in unsupported_missions,"#E69F00")]
    for label,pred,color in groups:
        values=np.array([sum(r["K"]==K and pred(r) for r in rows) for K in KS]);ax.bar(x,values,bottom=bottom,label=label,color=color);bottom+=values
    ax.set_xticks(x,labels=list(map(str,KS)));ax.set_xlabel("Original saved members K (count)");ax.set_ylabel("Execution records (count)")
    handles,labels=ax.get_legend_handles_labels();fig.legend(handles,labels,loc="lower center",bbox_to_anchor=(.5,.005),frameon=False,fontsize=7)
    fig.tight_layout(rect=(0,.25,1,1));save(fig,"fig03_contact_K_outcomes")
    counts="\n".join("| %s | %d |"%(key,value) for key,value in analysis["pair_verdicts"].items())
    text=f"""# Fixed known-footprint contact K study

{len(rows)} records, {len(pairs)} paired comparisons, {len(posthoc)} independently rechecked local contact routes and {analysis['unsupported_endpoint_records']} presearch unknown-endpoint records. Source phase `{bundle['source_phase_head']}`. Seed 20261008, uniform full-native timing then exact existing crop, original first-K 4/8/16/32, T = 3970.4642815249267 s and H = 3600 s. Original graph/request/export/record/masks and issued history are unchanged.

Host: {bundle['host']}. Python: {bundle['python'].splitlines()[0]}. NumPy: {bundle['numpy']}. Protocol SHA-256: `{bundle['protocol_sha256']}`. BUNDLE.json retains all exact source, evidence and original input hashes. Original-input admission and controller fixture receipts are kept with this run or the adjacent protocol.

Commands from repository root:

```sh
python research/sipp-routing/run_known_footprint_campaign.py --preflight FRESH_PREFLIGHT.json
python research/sipp-routing/run_known_footprint_campaign.py --run FRESH_RUN --preflight-receipt FRESH_PREFLIGHT.json
python research/sipp-routing/analyze_known_footprint_campaign.py --run FRESH_RUN
```

Each mission/K uses ABBA: rep1 sweep,SIPP; rep2 SIPP,sweep. Every child acquires and releases HEAVY separately. The 30 s/3072 MiB guards include imports, admission, planning and a fresh original-data postcheck. Sampled RSS and final elapsed/self-reported peak admission are control evidence, not an instantaneous OS memory cap. Control refusals: {analysis['control_refusals']}. All owned process groups absent: {analysis['all_owned_groups_absent']}.

| Paired outcome | Count |
|---|---:|
{counts}

The six spatially supported missions have these outcomes. Numbers are arrival seconds and agree across both methods/repetitions when present. Restricted exhaustion is unresolved about the original unknown domain.

| Mission | K4 | K8 | K16 | K32 |
|---|---:|---:|---:|---:|
{chr(10).join(mission_table)}

There are {len(joint)} joint completed-search pairs, including matched contact arrivals and matched restricted exhaustion. Their median SIPP/sweep contact-planner time ratio is {analysis['median_planner_ratio_sipp_over_sweep']:.6f}; the complete-child ratio is {analysis['median_complete_child_ratio_sipp_over_sweep']:.6f}. SIPP is slower in {analysis['sipp_slower_planner_pairs']} contact-planner pairs. These host-specific ratios exclude presearch endpoint admission and are descriptive paired measurements, not a universal speedup. Repetitions are verification repeats, not independent missions or fires.

Figure 1, fig01_contact_K_time_paired, compares sweep and SIPP seconds for joint completed-search pairs. The left panel is the contact planner call including support/geometry preparation; the right is the complete child including imports, original-source admission and the separate original-data recheck when a route is returned. Unknown-endpoint admission records are excluded from both comparisons; the diagonal is equal time.

Figure 2, fig02_states_vs_members, reports SIPP expansions and sweep states reached in separate panels because their work units differ. Vertical axes are logarithmic to keep each mission's count range visible. Solid circles are repetition 1 and dotted crosses repetition 2. The original one-hour T>H law combines prefix and tail barriers, so increasing multi-interval fragmentation is not implied by adding members. The plot reports the observed counters; repetition-counter mismatches are {len(metric_repeat_mismatches)}. Missing or capped rows are never inserted as zero states.

Figure 3, fig03_contact_K_outcomes, retains all execution records at each K, including the original 14 unknown-endpoint missions, both methods and both repetitions. Counts are execution bookkeeping, not independent fire samples or estimated risk. The CSV ledger retains every unresolved outcome.

INDEPENDENT_RECHECKS.jsonl saves each fresh original-array/mask/geometry check separately from planner claims. Every returned contact route passed through full dwell inside finite source validity. The controller retained original request UTF8 and history; the private contact relaxation omitted thermal fields explicitly without rebinding them. Source and protocol pins match after the run. Peak, dose, full-policy acceptance and risk remain unknown. Restricted failure is unresolved about the original unknown domain; a returned optimum is conditional on the support-restricted contact problem. No physical safety, global original-domain optimum/refusal or scientific risk conclusion follows.
"""
    (folder/"README.md").write_text(text)
    dump(folder/"OUTPUT_SHA256.json",{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob("*")) if p.is_file() and p.name!="OUTPUT_SHA256.json"})
    print(json.dumps(analysis,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--run",type=Path,required=True)
    analyze(parser.parse_args().run)
