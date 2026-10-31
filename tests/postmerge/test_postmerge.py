"""Independent post-merge regressions; no study/model training or result edits."""
from pathlib import Path
from types import SimpleNamespace
import ast, hashlib, importlib.util, sys
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2]
for name in ("sipp-routing","synthetic-truth","flame-front-radiation"):
    sys.path.insert(0,str(ROOT/"experimental"/name/"src"))
from wfg_synthetic_truth.scoring import score_decision,summarize
from wfg_flamefront.law_v2 import flux_at_points,flux_enclosure,UnsupportedGeometry
from wfg_sipp import sipp,frontend

@pytest.mark.parametrize("oracle",["checked_route","model_no_route","unresolved"])
def test_unfinished_is_neither_a_refusal_nor_a_safe_route(oracle):
    ref=dict(scope="full_policy",outcome=oracle,arrival_s=1)
    row=score_decision(dict(outcome="unresolved"),evaluator=lambda _:pytest.fail("No journey exists"),
        clairvoyant=ref,cutoff="fixture",truth_source="holdout_trajectory",forecast_source="fixture",mission="fixture")
    assert row["false_refusal"] is None and row["false_safe"] is None
    summary=summarize([row]);assert summary["unresolved"]==1
    assert summary["false_refusal"]["denominator"]==summary["false_safe"]["denominator"]==0

@pytest.mark.parametrize("value",[np.array([np.nan]),np.zeros((1,2)),np.full((2,2),np.nan),np.full((2,2),np.inf)])
@pytest.mark.parametrize("api",["point","enclosure"])
def test_bad_explicit_extinction_cannot_be_replaced_with_default(value,api):
    member=dict(ignition_time_s=np.array([[0.,1.],[0.,1.]]),extinction_breakpoint_s=value)
    with pytest.raises(UnsupportedGeometry,match="extinction"):
        if api=="point":flux_at_points([[-100,0]],[.5],member,(1,0,0,0,1,0))
        else:flux_enclosure((-101,-100,0,1),(0,.5),member,(1,0,0,0,1,0))

def instance():
    return sipp.make_instance(n_nodes=1,tail=[],head=[],D=[],origin=0,start_state=0,forbidden=set(),
        waitable=[True],edge_block={},wait_block={},accept={0:[(0,10)]},departure=0,horizon=10)

@pytest.mark.parametrize("clock",[(0,2),(0,.5,2)])
def test_expired_initial_goal_never_publishes(monkeypatch,clock):
    ticks=iter(clock);last=clock[-1]
    monkeypatch.setattr(sipp,"time",SimpleNamespace(perf_counter=lambda:next(ticks,last)))
    assert sipp.solve(instance(),deadline=1)["status"]=="TIMEOUT"

@pytest.mark.parametrize("status",["ROUTE","NO_ROUTE","UNRESOLVED"])
def test_frontend_final_gate_covers_all_result_branches(monkeypatch,status):
    ticks=iter([0.,2.]);monkeypatch.setattr(frontend,"time",SimpleNamespace(perf_counter=lambda:next(ticks,2.)))
    monkeypatch.setattr(frontend,"_sipp_plan",lambda *a,**k:dict(status=status,complete=True,metrics={}))
    result=frontend.sipp_plan({},None,None,wall_s=1)
    assert result["status"]=="UNRESOLVED" and result["complete"] is False

@pytest.mark.parametrize("budget",[0,-1,float("nan"),float("inf"),True])
def test_invalid_frontend_allowance_refused(budget):
    with pytest.raises(ValueError):frontend.sipp_plan({},None,None,wall_s=budget)

def recipe():
    p=ROOT/"research/forecast-v2/scripts/audit_fit_coverage.py"
    spec=importlib.util.spec_from_file_location("independent_postmerge_recipe",p)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod

def test_callback_profile_is_exact_and_preserves_historical_pin():
    mod=recipe();p=ROOT/"forecast/wildfire/rollout.py";text=p.read_text()
    original=text.replace("    trajectory_callback=None,\n","").replace("                if trajectory_callback is not None:\n                    trajectory_callback(block, states[:size] == 1, k + 1)\n","")
    assert hashlib.sha256(original.encode()).hexdigest()==mod._RECIPE_CURRENT_BASELINE["forecast/wildfire/rollout.py"]
    assert mod._verified_producer_version(ROOT,mod._RECIPE_CURRENT_BASELINE,"burnout_spotting_seed0_flaming_only")["verified_source_files"]==61

@pytest.mark.parametrize("victim",["forecast/wildfire/rollout.py","forecast/wildfire/models.py"])
def test_new_profile_does_not_accept_other_dependency_changes(monkeypatch,victim):
    mod=recipe();old=mod.sha
    monkeypatch.setattr(mod,"sha",lambda p:"0"*64 if str(p).endswith(victim) else old(p))
    with pytest.raises(ValueError,match="Unreviewed current producer dependency"):
        mod._verified_producer_version(ROOT,mod._RECIPE_CURRENT_BASELINE,"burnout_spotting_seed0_flaming_only")
