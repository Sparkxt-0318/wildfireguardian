"""Audit global-wind availability on the exact spotting development/fit inputs.

Only already source-authenticated 2020 to 2023 perimeter sample caches enter;
no endpoint labels, held-out data or forecast-quality scores are inspected.
"""
import argparse
import ast
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import subprocess
import sys
import numpy as np
import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "forecast"))
from wildfire.survival import sample_tensors


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_blob(relative, expected):
    snapshot = REPO / "research/forecast-v2/source_snapshots" / expected / Path(relative).name
    if snapshot.exists() and sha(snapshot) == expected:
        return snapshot.read_text()
    compressed = snapshot.with_name(snapshot.name + ".gz")
    if compressed.is_file():
        original = gzip.decompress(compressed.read_bytes())
        if hashlib.sha256(original).hexdigest() == expected:
            return original.decode("utf-8")
    commits = subprocess.check_output(["git", "rev-list", "--all", "--", relative], cwd=REPO, text=True).splitlines()
    for commit in commits:
        process = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=REPO, capture_output=True)
        if process.returncode == 0 and hashlib.sha256(process.stdout).hexdigest() == expected:
            return process.stdout.decode()
    raise ValueError("Exact phase source bytes cannot be recovered: " + relative + ":" + expected)


def function_ast(source, name):
    matches = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise ValueError("Expected one exact source function: " + name)
    return ast.dump(matches[0], include_attributes=False)


def literal_table(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        return {literal_table(k): literal_table(v) for k, v in zip(node.keys, node.values)}
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict"
            and not node.args and all(k.arg is not None for k in node.keywords)):
        return {k.arg: literal_table(k.value) for k in node.keywords}
    raise ValueError("Variant policy must contain only literal dicts and constants")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve the existing input-support audit; choose a new receipt path")
    audit_path = REPO / "research/forecast-v2/CACHE_AUDIT.json"
    audit = json.loads(audit_path.read_text())
    if audit["status"] != "PASS_NO_CONSUMED_VALUES_CHANGED":
        raise ValueError("Verified input/cache equality is required first")
    rows = []
    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current_source = (REPO / "forecast/wildfire/survival.py").read_text()
        transform = function_ast(current_source, "sample_tensors")
        phases = []
        for phase in [f"a03_fold_{year}_burnout_spotting" for year in (2020, 2021, 2022)] + ["a03_final_burnout_spotting"]:
            receipt_path = REPO / "research/forecast-v2/executions" / (phase + ".json")
            receipt = json.loads(receipt_path.read_text())
            if receipt["exit_code"] != 0 or sha(Path(receipt["output"])) != receipt["output_sha256"]:
                raise ValueError("Spotting phase is not an authenticated successful fit")
            pipeline_source = source_blob("research/forecast-v2/scripts/pipeline.py", receipt["source_sha256"]["research/forecast-v2/scripts/pipeline.py"])
            assignments = [node for node in ast.parse(pipeline_source).body if isinstance(node, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == "VARIANTS" for t in node.targets)]
            if len(assignments) != 1:
                raise ValueError("Missing frozen variant policy")
            table = literal_table(assignments[0].value)
            if table["burnout_spotting"]["d4"]:
                raise ValueError("Unexpected augmentation requires a separate transformed-input audit")
            old_source = source_blob("forecast/wildfire/survival.py", receipt["source_sha256"]["forecast/wildfire/survival.py"])
            if function_ast(old_source, "sample_tensors") != transform:
                raise ValueError("Consumed sample tensor transformation changed across phase sources")
            old_tree = ast.parse(old_source)
            fitting = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == "fit_mean_field")
            calls = [n for n in ast.walk(fitting) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                     and n.func.id == "sample_forecast"]
            if len(calls) != 1 or any(k.arg == "environment" for k in calls[0].keywords):
                raise ValueError("Unexpected environment override requires a separate consumed-tensor audit")
            result = json.loads(Path(receipt["output"]).read_text())
            model_source = source_blob("forecast/wildfire/models.py", receipt["source_sha256"]["forecast/wildfire/models.py"])
            spot_method_ast = function_ast(model_source, "spot_rate")
            phases.append(dict(phase=phase, receipt_sha256=sha(receipt_path),
                producer_source_sha256=receipt["source_sha256"], d4_augmentation=False,
                tensor_transform_ast_equal=True, explicit_environment_override=False,
                global_wind_method_ast_sha256=hashlib.sha256(spot_method_ast.encode()).hexdigest(),
                train_events=result["train_events"], validation_events=result.get("validation_events", []),
                declared_train_samples=result["train_samples"], declared_validation_samples=result.get("validation_samples", 0)))
        for record in audit["records"]:
            path = Path(record["cache"])
            if record["kind"] != "sample-list" or not path.name.startswith("perimeter_crop_first"):
                continue
            if record["status"] != "MATCHES_RECOMPUTED_SOURCES" or sha(path) != record["cache_sha256"]:
                raise ValueError("Previously source-authenticated sample cache changed")
            samples = pickle.loads(path.read_bytes())
            for sample in samples:
                # Fixed SOURCE_CHANNELS expansion order: temperature, east/north wind,
                # slope, tree cover, then fourteen biome indicators.
                actual = sample_tensors(sample)["environment"]
                if not np.array_equal(actual[0].numpy(), sample.environment, equal_nan=True):
                    raise ValueError("Actual pre-cleaning model tensor differs from the source-authenticated crop")
                missing = ~torch.isfinite(actual[:, [1, 2]])
                rows.append(dict(cache=path.name, event=sample.event_id, cutoff=sample.t1,
                    shape=list(sample.initial.shape), missing_wind_values=int(missing.sum()),
                    actual_preclean_tensor_shape=list(actual.shape),
                    crop=None if sample.meta.get("crop") is None else [int(v) for v in sample.meta["crop"]],
                    raw_crop_sha256=hashlib.sha256(np.ascontiguousarray(sample.environment).tobytes()).hexdigest(),
                    produced_tensor_sha256=hashlib.sha256(actual.contiguous().numpy().tobytes()).hexdigest(),
                    wind_fully_known=not bool(missing.any())))
        for phase in phases:
            full = phase["phase"] == "a03_final_burnout_spotting"
            prefix = "perimeter_crop_first0_" if full else "perimeter_crop_first3_"
            training = [r for r in rows if r["cache"].startswith(prefix) and r["event"] in phase["train_events"]]
            validation = [r for r in rows if r["cache"].startswith(prefix) and r["event"] in phase["validation_events"]]
            if len(training) != phase["declared_train_samples"] or len(validation) != phase["declared_validation_samples"]:
                raise ValueError("Audited produced tensors do not cover the exact phase sample counts")
            phase.update(audited_train_samples=len(training), audited_validation_samples=len(validation),
                         missing_wind_train_samples=sum(not r["wind_fully_known"] for r in training),
                         missing_wind_validation_samples=sum(not r["wind_fully_known"] for r in validation))
        fcntl.flock(lock, fcntl.LOCK_UN)
    result = dict(scope="Actual source-authenticated spotting development and final-fit covariates only",
        source_cache_audit_sha256=sha(audit_path), rows=rows, samples=len(rows),
        phases=phases, sample_tensor_source_sha256=sha(REPO / "forecast/wildfire/survival.py"),
        wind_reduction_span="Actual pre-cleaning cropped sample tensor; no wind padding enters the domain-mean reduction",
        exterior_scenario="Source convolution pads outside cropped grid with known unburned zero; local kernel environmental zero padding is an explicit scenario, not missing observed wind",
        missing_wind_samples=sum(not r["wind_fully_known"] for r in rows),
        interpretation="No label/outcome/model score inspected; global wind support is an input contract, not a tuning decision")
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(samples=result["samples"], missing_wind_samples=result["missing_wind_samples"])))


if __name__ == "__main__":
    main()
