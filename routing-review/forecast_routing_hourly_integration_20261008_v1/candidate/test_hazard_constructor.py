"""Focused semantics tests for explicit scenario construction."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pytest

from hazard_constructor import (ConstructionConfig, construct_hazard, draw_ignitions,
    interval_enclosures, load_snapshot, mean_uniform_occupancy, radiation_model,
    save_construction, sensitivity_panel)


def snapshot(q=None):
    q = np.array([[0.0, 1.0], [np.nan, 0.5]]) if q is None else np.asarray(q, float)
    arrays = dict(new_burn_probability=q, probability_valid=np.isfinite(q),
                  source_burned_area=np.zeros(q.shape), source_burned_area_valid=np.ones(q.shape, bool),
                  affine_transform=np.array([375.,0,1149000.,0,-375.,1912125.]))
    return arrays, dict(shape=list(q.shape), cutoff_utc="2022-03-04T03:00:00Z", native_snapshot_sha256="test")


def test_strict_preserves_unknown_without_assignment():
    a,m=snapshot()
    r=construct_hazard(a,m,mode="strict")
    assert r["status"] == "UNSUPPORTED"
    assert not r["arrays"]["support"].any()
    assert np.isnan(r["arrays"]["flux_w_m2"]).all()
    assert r["metadata"]["assumptions"] is None
    assert np.isnan(a["new_burn_probability"][1,0])


def test_research_reproducible_and_original_probability_preserved():
    a,m=snapshot()
    r1=construct_hazard(a,m,mode="research")
    r2=construct_hazard(a,m,mode="research")
    for key in r1["arrays"]:
        assert np.array_equal(r1["arrays"][key],r2["arrays"][key])
    assert r1["arrays"]["constructed_probability"][1,0] == .5
    assert np.isnan(a["new_burn_probability"][1,0])
    assert r1["metadata"]["evidence_class"] == "RESEARCH_CONSTRUCTION"
    assert r1["arrays"]["support"].all()


def test_initial_state_disjoint_from_future_event():
    a,m=snapshot(np.ones((2,2)))
    a["source_burned_area"][0,0]=1
    r=construct_hazard(a,m,mode="research")
    assert np.isinf(r["arrays"]["ignition_time_s"][:,0,0]).all()
    assert r["arrays"]["current_active"][0,0]
    assert r["arrays"]["flame_contact"][:,0,0,0].all()
    assert not r["arrays"]["flame_contact"][:,1:,0,0].any()
    assert r["arrays"]["uniform_mean_active_occupancy"][0,0] == 300/3600


def test_interior_event_enclosed_and_exact_half_open_boundaries():
    config=ConstructionConfig()
    model=radiation_model([100,0,0,0,-100,200],config)
    events=np.array([[[100.,300.]]])
    flame,flux=interval_enclosures(events,np.zeros((1,2),bool),0,[0,300,600],100,model)
    assert flame[0,0,0,0] and not flame[0,1,0,0]
    assert not flame[0,0,0,1] and flame[0,1,0,1]
    # Neither endpoint of [0,300) sees the first source at t=100..200.
    interior=model.predict(np.array([[1.,0.]])).incident_heat_flux_w_m2
    assert np.all(flux[0,0] >= interior)


def test_union_enclosure_bounds_overlapping_and_disjoint_sources():
    config=ConstructionConfig()
    model=radiation_model([100,0,0,0,-100,200],config)
    events=np.array([[[25.,175.]]])
    flame,upper=interval_enclosures(events,np.zeros((1,2),bool),0,[0,300],50,model)
    assert flame.all()
    for t in (0,25,50,74.9,75,150,175,200,224.9,225,299.9):
        active=(events[0] <= t) & (events[0]+50 > t)
        exact=model.predict(active.astype(float)).incident_heat_flux_w_m2
        assert np.all(exact <= upper[0,0])


def test_uniform_occupancy_closed_form_and_no_probability_double_count():
    assert mean_uniform_occupancy(.4,3600,300) == pytest.approx(.4*(300-300**2/7200)/3600)
    assert mean_uniform_occupancy(.4,3600,7200) == pytest.approx(.2)
    model=radiation_model([100,0,0,0,-100,100],ConstructionConfig())
    occupancy=mean_uniform_occupancy(np.array([[.4]]),3600,300)
    qflux=model.predict(occupancy).incident_heat_flux_w_m2
    oneflux=model.predict(np.array([[1.]])).incident_heat_flux_w_m2
    assert qflux[0,0] == pytest.approx(oneflux[0,0]*occupancy[0,0],rel=1e-12)


def test_comonotone_occurrences_nested_and_timing_sensitivities():
    q=np.array([[.1,.5,.9]])
    cfg=ConstructionConfig(scenario_count=100,dependence="comonotone")
    events=draw_ignitions(q,cfg)
    active=np.isfinite(events)
    assert np.all(active[:,:,0] <= active[:,:,1])
    assert np.all(active[:,:,1] <= active[:,:,2])
    early=draw_ignitions(np.ones((1,1)),replace(cfg,timing="early"))
    late=draw_ignitions(np.ones((1,1)),replace(cfg,timing="late"))
    assert (early == 0).all()
    assert (late < 3600).all() and (late > 3599).all()


def test_no_horizon_extension_or_unknown_modes():
    a,m=snapshot()
    with pytest.raises(ValueError,match="one-hour"):
        construct_hazard(a,m,mode="research",config=ConstructionConfig(horizon_s=7200))
    with pytest.raises(ValueError,match="mode"):
        construct_hazard(a,m,mode="magic")


@pytest.mark.parametrize("change",["shape","boolean","negative","infinity","masked","affine"])
def test_malformed_native_inputs_rejected(change):
    a,m=snapshot()
    if change == "shape": a["probability_valid"]=np.zeros((1,1),bool)
    if change == "boolean": a["probability_valid"]=a["probability_valid"].astype(int)
    if change == "negative": a["new_burn_probability"][0,0]=-1
    if change == "infinity": a["new_burn_probability"][1,0]=np.inf
    if change == "masked": a["new_burn_probability"]=np.ma.array(a["new_burn_probability"],mask=False)
    if change == "affine": a["affine_transform"]=np.array([1,2])
    with pytest.raises(ValueError): construct_hazard(a,m,mode="research")


def test_numeric_output_no_pickle_and_parent_snapshot_checksum(tmp_path):
    a,m=snapshot()
    r=construct_hazard(a,m,mode="research")
    path=tmp_path/"constructed.npz"
    md=save_construction(r,path)
    with np.load(path,allow_pickle=False) as result:
        assert all(result[key].dtype.kind != "O" for key in result.files)
    assert len(md["payload_sha256"]) == 64
    r["arrays"]["bad"] = np.array([{"object":1}],object)
    with pytest.raises(ValueError,match="no pickle"):
        save_construction(r,tmp_path/"bad.npz")


def test_object_packet_rejected_without_pickle(tmp_path):
    path=tmp_path/"bad.npz"
    np.savez(path,new_burn_probability=np.array([{"a":1}],object))
    path.with_suffix(".json").write_text("{}")
    with pytest.raises(ValueError,match="Object arrays"):
        load_snapshot(path)


def test_native_orientation_retained():
    a,m=snapshot(np.array([[1.,0.],[0.,0.]]))
    r=construct_hazard(a,m,mode="research",config=ConstructionConfig(timing="early",current_state="cold"))
    assert r["arrays"]["flame_contact"][:,0,0,0].all()
    assert not r["arrays"]["flame_contact"][:,0,1,0].any()
    assert r["metadata"]["affine_transform"][4] < 0


def test_sensitivity_assumptions_have_distinct_ids_and_parameters():
    panel=sensitivity_panel()
    assert len(panel)==13
    assert len({config.assumption_id for config in panel.values()})==13
    assert panel["fuel_half"].fuel_load_kg_m2==5
    assert panel["missing_one"].unknown_probability==1
    assert panel["current_short"].initial_remaining_s==150
    assert panel["duration_short"].initial_remaining_s==180


def test_current_residence_cannot_spend_multiple_phase_energy_budgets():
    with pytest.raises(ValueError,match="same combustion phase"):
        ConstructionConfig(initial_remaining_s=900,burning_duration_s=300)
    with pytest.raises(ValueError,match="same combustion phase"):
        ConstructionConfig(initial_remaining_s=300,burning_duration_s=180)


def test_unknown_current_active_alternative_is_disjoint_and_raw_inputs_untouched():
    a,m=snapshot()
    a["source_burned_area_valid"][1,0]=False
    r=construct_hazard(a,m,mode="research",config=ConstructionConfig(unknown_current_state="active"))
    assert r["arrays"]["current_active"][1,0]
    assert r["arrays"]["constructed_probability"][1,0]==0
    assert np.isinf(r["arrays"]["ignition_time_s"][:,1,0]).all()
    assert np.isnan(a["new_burn_probability"][1,0])
    assert not a["source_burned_area_valid"][1,0]


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", __file__]))
