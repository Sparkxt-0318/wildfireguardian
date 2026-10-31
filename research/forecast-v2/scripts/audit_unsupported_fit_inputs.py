"""Corroborate logged mixed-fit skips with independently reconstructed support.

This reads authenticated fit inputs and final mixed weights, never heldout
data or forecast-quality scores. A final-checkpoint mask comparison is not a
replay of unlogged intermediate optimizer states. Exact runtime attempted and
skipped IDs remain the evidence of what each training epoch actually visited.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import torch
import torch.nn.functional as functional

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))
import audit_fit_coverage as coverage
import pipeline
from wildfire.survival import sample_forecast, sample_tensors, step_durations


def array_sha(value):
    value = np.ascontiguousarray(value)
    return hashlib.sha256(str((value.shape, str(value.dtype))).encode() + value.tobytes()).hexdigest()


def positive_rate_support(sample):
    """Mixed-base K9 envelope from raw masks, using max-pooled missingness.

    This is a source-derived positive-offset support contract. Floating-point
    softplus underflow is not assumed impossible. Its full mask is separately
    compared with the actual final checkpoint, and kernel positivity checked.
    """
    if sample.weather != "cutoff_repeated":
        raise ValueError("Only the frozen repeated-cutoff input policy is classified")
    known = torch.from_numpy(np.isfinite(sample.environment).all(axis=0))[None, None]
    initial = torch.from_numpy(sample.initial.astype(bool))[None, None]

    def all_known(mask):
        missing = functional.pad((~mask).float(), (4,) * 4, value=0.)
        return functional.max_pool2d(missing, 9, stride=1) == 0

    context = all_known(known)
    valid = torch.ones_like(initial)
    for _ in step_durations(sample.hours):
        following = valid & (initial | (context & all_known(valid)))
        if torch.equal(following, valid):
            break
        valid = following
    return valid[0, 0].numpy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input-root", "cache-root", "run-root", "cache-audit", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve the prior unsupported-input audit")
    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        expected = coverage.expected_membership(REPO, args.input_root)
        cache_audit = json.loads(args.cache_audit.read_text())
        if (cache_audit.get("status") != "PASS_NO_CONSUMED_VALUES_CHANGED"
                or cache_audit.get("mismatches") != [] or not cache_audit.get("producer_unchanged_during_audit")):
            raise ValueError("A fresh passing source-recomputed cache audit is required")
        _, samples, cache_files = coverage._cache_lists(REPO, args.cache_root.resolve(), cache_audit, expected)
        result_path, result, receipt_path, receipt = coverage._execution(REPO, args.run_root.resolve(), "mixed_base")
        manifest_path = REPO / result["fit_input_manifest"]["path"]
        if coverage.sha(manifest_path) != result["fit_input_manifest"]["sha256"]:
            raise ValueError("Actual prefit input manifest bytes changed")
        manifest = json.loads(manifest_path.read_text())
        if coverage.sample_list_identity(samples) != manifest["sample_values_sha256"]:
            raise ValueError("Authenticated full samples differ from actual prefit values")
        runtime = result["fit"]["runtime_membership"]
        if (runtime.get("schema") != coverage.RUNTIME_SCHEMA or len(runtime["epochs"]) != 3
                or len(result["fit"]["history"]) != 3 or runtime["sample_manifest_sha256"] != coverage.sha(manifest_path)):
            raise ValueError("Three exact actual runtime epochs must bind the original prefit manifest")
        cases = {coverage.case_id(sample): sample for sample in samples}
        if len(cases) != len(samples):
            raise ValueError("Full fit cases must have unique identities")
        skipped = set()
        epochs = []
        for row, history in zip(runtime["epochs"], result["fit"]["history"]):
            attempted, unavailable = row["attempted_case_ids"], row["skipped_case_ids"]
            if (len(attempted) != len(cases) or set(attempted) != set(cases)
                    or len(unavailable) != len(set(unavailable)) or not set(unavailable) <= set(cases)
                    or len(unavailable) != len(history["skipped_unsupported_intervals"])
                    or row["optimizer_steps"] != len(attempted) - len(unavailable)):
                raise ValueError("Runtime membership is not an exact attempted/unsupported partition")
            for case_id, reason in zip(unavailable, history["skipped_unsupported_intervals"]):
                sample = cases[case_id]
                if reason != dict(event=sample.event_id, cutoff=sample.t1, reason="no_supported_positive_weight_cells"):
                    raise ValueError("Observed skipped IDs and history reasons differ")
            skipped.update(unavailable)
            epochs.append(dict(epoch=row["epoch"], attempted=len(attempted), unsupported_ids=unavailable,
                               optimizer_steps=row["optimizer_steps"]))
        checkpoint = result_path.with_name("checkpoint.pt")
        if coverage.sha(checkpoint) != result["checkpoint_sha256"]:
            raise ValueError("The actual final checkpoint bytes changed")
        model = pipeline.load_structured(checkpoint)
        if (model.kernel_size != 9 or model.frame != "none" or model.spotting_radius
                or model.residence_hours is not None):
            raise ValueError("Classification is restricted to the intended mixed-base local family")
        rows = []
        for case_id in sorted(skipped):
            sample = cases[case_id]
            tensors = sample_tensors(sample)
            support = positive_rate_support(sample)
            with torch.no_grad():
                _, actual = sample_forecast(model, sample, tensors=tensors)
                environment = tensors["environment"]
                features = torch.isfinite(environment)
                rates = model.kernel_rates(torch.where(features, environment, 0), features, boundary="zero")
            finite = torch.isfinite(rates).all(dim=-3, keepdim=True)
            positive = rates[..., model.off_center.flatten().bool(), :, :]
            if bool((finite.expand_as(positive) & (positive <= 0)).any()):
                raise ValueError("Final numerical kernel positivity is not established")
            if not np.array_equal(support, actual.numpy()):
                raise ValueError("Independent source envelope differs from the final model validity")
            weight = np.asarray(sample.label_weight)
            eligible = sample.score_mask & np.isfinite(weight) & (weight > 0)
            if (eligible & support).any():
                raise ValueError("A logged unsupported case has supported positive weight")
            rows.append(dict(case=coverage.sample_descriptor(sample), reference_positive_weight_cells=int(eligible.sum()),
                             supported_positive_weight_cells=0, support_sha256=array_sha(support),
                             final_model_support_sha256=array_sha(actual.numpy()), final_kernel_positive=True,
                             classification="EMPTY_REPEATED_CUTOFF_ENVIRONMENT_SUPPORT"))
        value = dict(schema="wfg.forecast-unsupported-fit-inputs/1", status="PASS_SOURCE_ENVELOPE_AND_FINAL_MASK_MATCH",
                     sample_count=len(samples), distinct_unsupported_cases=len(rows), epochs=epochs, cases=rows,
                     fit_result=coverage.identity(REPO, result_path), execution=coverage.identity(REPO, receipt_path),
                     prefit_input_manifest=coverage.identity(REPO, manifest_path), checkpoint=coverage.identity(REPO, checkpoint),
                     actual_phase_producer_source_sha256=receipt["source_sha256"],
                     cache_audit=coverage.identity(REPO, args.cache_audit), cache_files=cache_files,
                     script_sha256=coverage.sha(HERE), source_sha256=coverage.producer_sources(REPO),
                     limitations=["Actual attempted/skipped IDs are runtime evidence; optimized membership is their source-derived complement.",
                                  "The final-checkpoint mask match does not reconstruct unlogged per-optimizer mask or parameter states.",
                                  "The positive-offset source envelope is not a universal floating-point softplus positivity theorem.",
                                  "No quality score, endpoint error or heldout input is read or used for this classification."])
        coverage.write_new(args.out, value)
        fcntl.flock(lock, fcntl.LOCK_UN)
    print(json.dumps(dict(status=value["status"], distinct_unsupported_cases=len(rows))))


if __name__ == "__main__":
    main()
