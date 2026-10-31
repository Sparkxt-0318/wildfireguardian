"""Independent synthetic development admission audit; no actual study data/model access."""
import copy, hashlib, importlib.util, json, pickle, platform, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[1]/'audit-1b'
sys.path.insert(0,str(REPO/'forecast'))
sys.path.insert(0,str(REPO/'research/forecast-v2/scripts'))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
t=load('independent_a5_fixture',REPO/'forecast/tests/test_blind_forecast_protocol.py')
observations=[]
def probe(name,fn,refuse=False):
 try:
  v=fn(); ok=not refuse and v is not False; result=dict(state='RETURNED',value=v)
 except (ValueError,KeyError,TypeError,FileNotFoundError,RuntimeError) as e:
  ok=refuse; result=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 observations.append(dict(id=name,pass_check=bool(ok),observed=result))
with tempfile.TemporaryDirectory(prefix="wfg-independent-a5-skips-") as temp,pytest.MonkeyPatch.context() as mp:
 folder=Path(temp).resolve();f=t.freezer.__wrapped__();fixture=t.freeze_inputs.__wrapped__(f,folder,mp)
 m,root,run,inputs,caches,audit_path,_,_=t.supported_skip_fixture(f,fixture,"unknown_environment")
 def audit():return m.audit_coverage(root,inputs,caches,run,audit_path)
 good=audit(); phases=[p for p in good["development"].values() if p["intended_phase"]["variant"]=="mixed_base"]
 probe("source_bound_historical_skip_partition_positive",lambda:len(phases)==3 and all(p["training"]["sample_count"]==15 and p["validation"]["sample_count"]==3 and p["runtime_membership"] is None and all(e["optimizer_steps"]==14 and len(e["source_derived_skipped_samples"])==1 and len(e["source_derived_optimized_case_ids"])==14 and "NO_RUNTIME_CASE_IDS" in e["evidence"] for e in p["epochs"]) for p in phases))
 phase=m.intended_phase("mixed_base","fold","2020");rp=run/phase["result"];ep=root/f"research/forecast-v2/executions/a03_{phase['job_suffix']}.json"
 original=rp.read_bytes();receipt_original=ep.read_bytes()
 for mode in ["unlogged","unknown_reason","duplicate","different_cutoff","unclassified_identity"]:
  result=json.loads(original);row=result["fit"]["history"][0]
  if mode=="unlogged":row["skipped_unsupported_intervals"]=[];row["optimizer_steps"]+=1
  if mode=="unknown_reason":row["skipped_unsupported_intervals"][0]["reason"]="new exclusion"
  if mode=="duplicate":row["skipped_unsupported_intervals"]*=2;row["optimizer_steps"]-=1
  if mode=="different_cutoff":row["skipped_unsupported_intervals"][0]["cutoff"]="2020-01-02T01:00:00Z"
  if mode=="unclassified_identity":row["skipped_unsupported_intervals"][0]["event"]="synthetic_fit"
  rp.write_text(json.dumps(result));receipt=json.loads(receipt_original);receipt["output_sha256"]=sha(rp);ep.write_text(json.dumps(receipt))
  probe("historical_skip_"+mode+"_refused",audit,True);rp.write_bytes(original);ep.write_bytes(receipt_original)
value=dict(source_head=subprocess.check_output(["git","-C",str(REPO),"rev-parse","HEAD"],text=True).strip(),script_sha256=sha(__file__),checks=len(observations),passed=sum(x["pass_check"] for x in observations),observations=observations,actual_study_inputs_or_models_accessed=False,training_executed=False,status="PASS" if all(x["pass_check"] for x in observations) else "HOLD")
Path(__file__).with_suffix(".json").write_text(json.dumps(value,indent=2,allow_nan=False)+"\n");print(json.dumps({k:value[k] for k in ["status","checks","passed"]}));raise SystemExit(0 if value["status"]=="PASS" else 1)
