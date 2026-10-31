"""Freeze exact inference and selection identities before any heldout assessment.

This command never opens future source data, forecasts or heldout scores. It
first requires all seven complete final-fit receipts, then reads the frozen
MODEL_SELECTION.json and verifies the selected checkpoint and baseline bytes.
It writes a new registry once, without placeholders for identities already
available. Future input hashes are deliberately outside this pre-source freeze.

READY_FOR_OWNER_REGISTRATION means that local software and model identities are
complete. It does not mean registered, independently verified, or executable on
2026 data. Publisher first-release chronology and public OSF registration must
be independently checked before execution. A caller's string or flag is not
proof of either external fact.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import sys
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import audit_fit_coverage as F
REPO = HERE.parents[3]
VARIANTS = ("base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base")
C651 = "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
C651_SHA = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
INVENTORY_POLICY = "wfg.nirops-first-survey-2026-six-source-availability/1"
SOURCE_CONTRACT = "NIROPS_v1_Incident_C_Inc_Number_UTC_naive_publisher_UTC"
BASELINES = {"logistic": "logistic.pkl", "logistic_parameters": "logistic.json", "dilation_choice": "dilation_choice.json"}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def contained(root, path):
    path = Path(path)
    path = path if path.is_absolute() else root / path
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ValueError("Registry inputs and ancestors cannot be filesystem symlinks")
    path = path.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Registry identities require nonempty existing files within the model root")
    return path


def identity(root, path):
    path = contained(root, path)
    return dict(path=str(path.relative_to(root.resolve())), sha256=sha(path))


def authenticate(root, declared, expected_path=None):
    if not isinstance(declared, dict) or set(declared) != {"path", "sha256"}:
        raise ValueError("An exact path and SHA-256 identity are required")
    if not isinstance(declared["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", declared["sha256"]):
        raise ValueError("Identity hashes must be complete lowercase SHA-256 values, without placeholders")
    actual = identity(root, declared["path"])
    if actual != declared or (expected_path is not None and contained(root, expected_path) != contained(root, actual["path"])):
        raise ValueError("Frozen identity differs from the exact executed checkpoint or baseline bytes")
    return actual


def option(command, name):
    positions = [i for i, item in enumerate(command) if item == name]
    if not positions or positions[-1] + 1 == len(command):
        raise ValueError(f"Final-fit execution must state {name}")
    return command[positions[-1] + 1]


def full_fits(root, run):
    """Check every completed full-fit artifact before opening model selection."""
    results, receipts = {}, {}
    split = json.loads(contained(root, root / "research/forecast-v2/SPLIT.json").read_text())
    fit_events = split["fit"]["us_perimeter_and_kriged"]
    for variant in VARIANTS:
        checkpoint = contained(root, (run / F.intended_phase(variant, "final")["result"]).with_name("checkpoint.pt"))
        path = contained(root, checkpoint.with_name("result.json"))
        result = json.loads(path.read_text())
        if (result.get("variant") != variant or result.get("seed") != 0 or result.get("epochs") != 3
                or result.get("checkpoint_sha256") != sha(checkpoint)
                or result.get("train_samples", 0) < 1 or not result.get("train_events")
                or result["train_events"] != fit_events
                or len(result.get("fit", {}).get("history", [])) != 3):
            raise ValueError(f"Completed fixed-policy full fit required: {variant}")
        _, _, receipt_path, receipt, _ = F.phase_result(root, run, variant, "final")
        command = receipt.get("command", [])
        if (option(command, "--epochs") != "3" or option(command, "--max-fit-intervals-per-fire") != "0"
                or option(command, "--intervals-per-epoch") != "0"):
            raise ValueError(f"Authenticated unrestricted final-fit execution required: {variant}")
        results[variant], receipts[variant] = identity(root, path), identity(root, receipt_path)
    return results, receipts


def verified_fit_coverage(root, run, selection):
    spec = importlib.util.spec_from_file_location("frozen_full_fit_membership", HERE.with_name("audit_fit_coverage.py"))
    coverage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coverage)
    return coverage.verify_coverage(root, run, selection.get("fit_coverage"))


def build_registry(model_root, run_root, selection_path, c651_path):
    root, run = Path(model_root).resolve(), Path(run_root).resolve()
    if not run.is_relative_to(root):
        raise ValueError("The final run directory must remain within the model root")
    fits, executions = full_fits(root, run)
    # Selection is intentionally read only after the seven full fits passed.
    selection_path = contained(root, selection_path)
    selection = json.loads(selection_path.read_text())
    if (selection.get("frozen_before_heldout_scoring") is not True
            or set(selection.get("checkpoints", {})) != set(VARIANTS)
            or set(selection.get("baselines", {})) != set(BASELINES)):
        raise ValueError("The exact seven-model selection and fitted-baseline freeze is required")
    phase_evidence = F.validate_selection_phase(root, run, selection)
    fit_coverage, fit_coverage_record = verified_fit_coverage(root, run, selection)
    F.validate_phase_identity(fit_coverage_record.get("current_phase"))
    for name in ("heldout", "korean2025"):
        folder = run / name
        if folder.exists() and any(p.is_file() for p in folder.rglob("*")):
            raise ValueError("Freeze the registry before any current heldout assessment artifacts exist")
    values = selection.get("development_brier", {})
    if (set(values) != set(VARIANTS)
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values.values())):
        raise ValueError("All seven finite development Brier values are required")
    selected = min(VARIANTS, key=lambda name: (values[name], VARIANTS.index(name)))
    if selection.get("selected_variant") != selected:
        raise ValueError("Primary selection differs from the frozen development minimum and tie order")
    models = {v + "_seed0": authenticate(root, selection["checkpoints"][v], (run / F.intended_phase(v, "final")["result"]).with_name("checkpoint.pt"))
              for v in VARIANTS}
    for variant in VARIANTS:
        if fit_coverage_record["variants"][variant]["checkpoint"] != models[variant + "_seed0"]:
            raise ValueError("Coverage must bind the same exact checkpoint authenticated by model selection")
    comparator = identity(root, c651_path)
    if comparator["sha256"] != C651_SHA:
        raise ValueError("The immutable c651 comparator bytes changed")
    models["c651_mc"] = comparator
    baselines = {name: authenticate(root, selection["baselines"][name], run / "baselines" / filename)
                 for name, filename in BASELINES.items()}
    dilation = json.loads(contained(root, baselines["dilation_choice"]["path"]).read_text())
    rate = dilation.get("best_hours_per_cell")
    if type(rate) is not int or rate not in (1, 2, 4, 8):
        raise ValueError("The frozen training-selected dilation rate must be 1, 2, 4 or 8")
    required = {root / "research/forecast-v2/SPLIT.json", root / "research/forecast-v2/RUN_PROTOCOL.json",
                root / "research/forecast-v2/RUN_PROTOCOL_EXTENSION_2.json",
                root / "forecast/documents/preregistration_blind_test.md", root / "forecast/pyproject.toml"}
    required |= {p for p in (root / "forecast/wildfire").rglob("*") if p.is_file() and p.suffix in (".py", ".json")}
    required |= set((root / "research/forecast-v2/scripts").glob("*.py"))
    scripts = {p.name for p in required if p.suffix == ".py"}
    if not {"pipeline.py", "blind_test.py", "blind_inventory.py", "freeze_registry.py", "audit_fit_coverage.py", "score_cohorts.py", "run_campaign.py"} <= scripts:
        raise ValueError("The complete executed script closure, including raw inventory admission, is required")
    source = {str(contained(root, p).relative_to(root)): sha(p) for p in sorted(required)}
    if not any(name.startswith("forecast/wildfire/") for name in source):
        raise ValueError("The complete forecast Python and JSON source closure is required")
    baseline_execution = contained(root, root / "research/forecast-v2/executions/a03_baselines.json")
    baseline_receipt = json.loads(baseline_execution.read_text())
    if (selection.get("baseline_execution_sha256") != sha(baseline_execution)
            or baseline_receipt.get("exit_code") != 0
            or baseline_receipt.get("output_sha256") != baselines["dilation_choice"]["sha256"]):
        raise ValueError("Baseline selection must bind its successful execution receipt")
    cache_identity = authenticate(root, selection.get("cache_audit"))
    cache_path = contained(root, cache_identity["path"])
    cache = json.loads(cache_path.read_text())
    if (selection.get("cache_audit_sha256") != sha(cache_path) or cache.get("status") != "PASS_NO_CONSUMED_VALUES_CHANGED"
            or cache.get("producer_unchanged_during_audit") is not True):
        raise ValueError("The consumed-input cache audit must pass and bind model selection")
    if fit_coverage_record["cache_audit"] != identity(root, cache_path):
        raise ValueError("Model selection and fit coverage must bind the same source-recomputed cache audit")
    if (set(selection.get("input_manifests_sha256", {})) !=
            {"EXTRACTION_MANIFEST.json", "BASELINE_TERRAIN_MANIFEST.json", "perimeters/PERIMETER_MANIFEST.json"}
            or any(fit_coverage_record["expected"]["input_sha256"].get(path) != value
                   for path, value in selection["input_manifests_sha256"].items())):
        raise ValueError("Model selection and complete fit coverage must bind the same input manifests")
    protocol_path = root / "research/forecast-v2/RUN_PROTOCOL.json"
    if selection.get("protocol_sha256") != sha(protocol_path):
        raise ValueError("Model selection must bind the fixed run protocol")
    frozen = datetime.fromisoformat(selection["frozen_utc"].replace("Z", "+00:00"))
    if frozen.tzinfo is None:
        raise ValueError("Model selection freeze timestamp requires a UTC offset")
    return dict(schema="wfg.forecast-blind-registry/1", status="FROZEN", models=models,
                current_phase=phase_evidence["current_phase"], development_phases=phase_evidence["development_phases"],
                development_coverage_sha256=phase_evidence["development_coverage_sha256"],
                spotting_source_contract=phase_evidence["spotting_source_contract"],
                selected_model=selected + "_seed0", best_dilation_hours_per_cell=rate,
                logistic=baselines["logistic"], baselines=baselines,
                selection=identity(root, selection_path), final_results=fits, final_executions=executions,
                fit_coverage=fit_coverage, unsupported_interval_policy=fit_coverage_record["unsupported_interval_policy"],
                fit_coverage_status={name: row["coverage_status"] for name, row in fit_coverage_record["variants"].items()},
                fit_schedule_evidence={name: row["schedule_evidence"] for name, row in fit_coverage_record["variants"].items()},
                baseline_execution=identity(root, baseline_execution), cache_audit=identity(root, cache_path),
                producer_source_sha256=source,
                dependency_versions={name: importlib.metadata.version(name) for name in
                                     ("numpy", "pandas", "torch", "rasterio", "pyproj", "shapely", "pyshp", "scipy", "scikit-learn")},
                inventory_contract=dict(schema="wfg.nirops-raw-inventory/1", eligibility_policy=INVENTORY_POLICY,
                                        source_contract=SOURCE_CONTRACT, cohort_year_predicate="first survey year; not proven physical ignition year"),
                protocol_status="READY_FOR_OWNER_REGISTRATION", execution_status="NOT_READY_FOR_2026_EXECUTION",
                documentary_clearance_contract=dict(schema="wfg.forecast-blind-documentary-clearance/1",
                                                   decision="HUMAN_ATTESTED_DOCUMENTARY_CLEARANCE",
                                                   pre_run_scope="pre_run_registration_first_release_and_access",
                                                   post_score_scope="post_score_independent_relocated_replay_and_claim",
                                                   machine_authentication=False),
                external_prerequisites=["Independent first-public-release identity and chronology verification",
                                        "Owner public OSF registration of this exact source/model closure before source access",
                                        "Independently reviewed documentary execution clearance"],
                future_inputs_pinned=False, generated_utc=datetime.now(timezone.utc).isoformat())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=REPO)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, default=REPO / "research/forecast-v2/MODEL_SELECTION.json")
    parser.add_argument("--c651", type=Path, default=REPO / C651)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise FileExistsError("Preserve the existing registry; write only a new freeze")
    registry = build_registry(args.model_root, args.run_root, args.selection, args.c651)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as target:
        target.write(json.dumps(registry, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(dict(registry=str(args.out), sha256=sha(args.out), protocol_status=registry["protocol_status"],
                          execution_status=registry["execution_status"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
