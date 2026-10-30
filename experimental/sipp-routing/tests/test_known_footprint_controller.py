"""Tiny controller, identity and original-source admission controls only."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

import test_known_footprint as original

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("_known_contact_campaign_tests", ROOT / "research/sipp-routing/run_known_footprint_campaign.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def test_exact_fixed_job_matrix_and_ABBA_order():
    rows = driver.jobs([dict(mission="m%d" % i, region="tiny") for i in range(20)])
    assert len(rows) == 320 and len({(r["mission"], r["K"], r["repetition"], r["method"]) for r in rows}) == 320
    for offset in range(0, 320, 4):
        assert [(r["repetition"], r["method"]) for r in rows[offset:offset+4]] == [(1,"sweep"),(1,"sipp"),(2,"sipp"),(2,"sweep")]


@pytest.mark.parametrize("args,expected", [((1,10,10),None), ((30,10,10),"DEADLINE_AFTER_EXIT"),
    ((1,10,3073),"RSS_LIMIT_AFTER_EXIT"), ((1,10,None),"MISSING_FINAL_PEAK_RSS"),
    ((1,10,float("nan")),"INVALID_FINAL_RESOURCE_EVIDENCE"), ((1,10,10,"EARLIER"),"EARLIER")])
def test_post_exit_guards(args, expected):
    assert driver.completion_stop(*args) == expected


def test_owned_tiny_child_cleaned_and_checked_after_exit(tmp_path):
    result = tmp_path / "child.json"
    code = "import json,pathlib;pathlib.Path(%r).write_text(json.dumps({'reported_peak_rss_mib':10,'fixture':True}))" % str(result)
    value, control = driver.controlled([sys.executable, "-I", "-c", code], result)
    assert value["fixture"] and control["stop"] is None and control["exit_code"] == 0 and control["owned_group_absent"]


def _binding(tmp_path):
    raw, graph, request = original.fixture()
    raw = dict(raw, trajectory_first_burn_hour=np.full((1024,3,3),-1,dtype=np.int16),
               new_burn_probability=np.zeros((3,3)), probability_valid=np.ones((3,3),bool),
               rate_per_h=np.zeros((3,3)),rate_valid=np.ones((3,3),bool))
    CT = original.bridge.v1.CT
    cutoff = "2025-01-01T00:00:00Z"
    settings = original.bridge.v1.settings_for(3970.4642815249267)
    clock = CT.derived_clock(1735689600)
    raw = CT.embed_clock(raw,clock,"KFS_02",3970.4642815249267,5179)
    npz = tmp_path / "FORECAST_fixture.npz"
    np.savez_compressed(npz,**raw)
    record_path = tmp_path / "RECORD.json"
    driver.dump(record_path,dict(npz=npz.name,npz_sha256=driver.sha(npz),event="KFS_02",cutoff_utc=cutoff,
        epsg=5179,checkpoint_sha256=CT.CHECKPOINT_SHA256,policy=CT.POLICY,clock=clock,
        cell_burning_duration_s=dict(value=3970.4642815249267),trajectory_count=1024,trajectory_horizon_hours=1))
    driver.dump(tmp_path / "graph.json",graph)
    driver.dump(tmp_path / "request.json",request)
    driver.dump(tmp_path / "NATIVE_METADATA.json",dict(settings=settings,time_origin=cutoff,
        construction=dict(parent_forecast=dict(cutoff_utc=cutoff),assumptions=dict(initial_remaining_s=0))))
    for name in ("REPORT.json","HAZARD.json","constructed_arrays.npz"):
        (tmp_path / name).write_bytes(b"tiny-unused-original-packet-fixture")
    input_pins={name:driver.sha(tmp_path / name) for name in ("NATIVE_METADATA.json","REPORT.json","HAZARD.json","constructed_arrays.npz")}
    input_pins.update(graph=driver.sha(tmp_path / "graph.json"),request=driver.sha(tmp_path / "request.json"))
    return dict(original_case=dict(graph=str(tmp_path/"graph.json"),request=str(tmp_path/"request.json"),packet=str(tmp_path),input_sha256=input_pins),
        domain=dict(event="KFS_02",cutoff=cutoff,existing_integer_window=None,grid_shape=[3,3],affine=[1.,0.,0.,0.,-1.,3.]),
        window=dict(npz=str(npz),npz_sha256=driver.sha(npz),record_sha256=driver.sha(record_path),shape=[1024,3,3],
            first32_prefix_sha256=hashlib.sha256(raw["trajectory_first_burn_hour"][:32].tobytes()).hexdigest()),
        topology=dict(source=dict(record=str(record_path),source_epsg=5179,
            combined_south_up_mask_sha256=hashlib.sha256(np.zeros((3,3),bool).tobytes()).hexdigest())))


def test_original_source_positive_and_corrupt_prefix_refusal(tmp_path):
    binding = _binding(tmp_path)
    source, request, raw_request = driver.original_source(binding,4)
    assert source.trajectory_indices == (0,1,2,3) and source.shape == (3,3) and source.seed == 20261008
    assert json.loads(raw_request)==request
    binding["window"]["first32_prefix_sha256"]="0"*64
    with pytest.raises(ValueError,match="PREFIX_BYTES"):
        driver.original_source(binding,4)


@pytest.mark.parametrize("change,reason", [("hash","SHA256_CHANGED"),("seed","FIXED_SOURCE_SETTINGS"),
    ("window","REGIONAL_GRID_BINDING"),("clock","REQUEST_AND_FORECAST_CUTOFF")])
def test_original_source_pin_clock_settings_and_grid_refuse(tmp_path,change,reason):
    binding = _binding(tmp_path)
    if change=="hash":
        binding["window"]["npz_sha256"]="0"*64
    elif change=="seed":
        path=tmp_path/"NATIVE_METADATA.json"
        md=driver.load(path);md["settings"]["seed"]=1;driver.dump(path,md)
        binding["original_case"]["input_sha256"]["NATIVE_METADATA.json"]=driver.sha(path)
    elif change=="window":
        binding["domain"]["affine"][2]=1
    else:
        path=tmp_path/"request.json"
        request=driver.load(path);request["as_of"]="2025-01-01T01:00:00Z";driver.dump(path,request)
        binding["original_case"]["input_sha256"]["request"]=driver.sha(path)
    with pytest.raises(ValueError,match=reason):
        driver.original_source(binding,4)
