"""Source-derived full-fit membership and bounded schedule verification.

This helper never trains, forecasts, or reads model/heldout outputs. It derives
all intended fit samples from the frozen split, source timestamps, cutoff
availability and the original UTC 12h reconstruction recipe. It then compares
those identities with complete source-recomputed cache lists. Zero-window
Korean events remain explicit ledger entries, never selected away.

Historical pure fits did not log epoch sample IDs. Their evidence is labelled
SOURCE_DERIVED_SCHEDULE_INFERENCE, using exact immutable producer source,
effective final argument values, authenticated complete sample membership and
recorded full counts/optimizer steps with no skips. That is not an observed
runtime schedule. Newly instrumented mixed fits require actual runtime IDs.

After all seven full fits and a fresh cache audit, run this command before
MODEL_SELECTION.json is frozen. Add its path/SHA identity as selection's
fit_coverage field. Builder verification rederives this entire artifact.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import fields
from collections import Counter
from functools import lru_cache
import hashlib
import importlib.metadata
import gzip
import json
import math
from pathlib import Path
import pickle
import re
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))
VARIANTS = ("base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base")
SCHEMA = "wfg.forecast-fit-coverage/1"
SAMPLES_SCHEMA = "wfg.forecast-fit-samples/1"
RUNTIME_SCHEMA = "wfg.forecast-fit-runtime-membership/1"
FIXED_VARIANT_POLICY = {
    "base": dict(prior="free", frame="none", d4=False),
    "d4": dict(prior="free", frame="none", d4=True),
    "d4_wind": dict(prior="free", frame="wind", d4=True),
    "ellipse": dict(prior="ellipse", frame="none", d4=False),
    "burnout": dict(prior="free", frame="none", d4=False, residence_hours=6.0),
    "burnout_spotting": dict(prior="free", frame="none", d4=False, residence_hours=6.0, spotting_radius=15),
    "mixed_base": dict(prior="free", frame="none", d4=False, mixed=True),
}
UNSUPPORTED_POLICY_SHA256 = "c9999a137ceb5d679a108b262aba8a977053875853f824ab2878448536953dcb"



def intended_phase(variant, stage, fold=None, seed=0):
    """Fixed current numerical phase. Historical directories never select it."""
    if variant not in VARIANTS or stage not in ("fold", "final") or seed != 0:
        raise ValueError("Intended phases require a registered variant, stage and seed0")
    if stage == "fold" and str(fold) not in ("2020", "2021", "2022"):
        raise ValueError("Intended development folds are exactly 2020, 2021 and 2022")
    if stage == "final" and fold is not None:
        raise ValueError("Final phases have no development fold")
    suffix = "_flaming_only" if variant == "burnout_spotting" else ("_utc_fixed" if stage == "fold" and variant == "mixed_base" else "")
    stem = f"{variant}_fold{fold}_seed0" if stage == "fold" else f"{variant}_seed0"
    job = f"fold_{fold}_{variant}" if stage == "fold" else f"final_{variant}"
    return dict(variant=variant, stage=stage, fold=str(fold) if stage == "fold" else None, seed=0,
                phase_id=stem + suffix, artifact_suffix=suffix, job_suffix=job + suffix,
                result=f"{'folds' if stage == 'fold' else 'final'}/{stem}{suffix}/result.json",
                spotting_source_mode="flaming_only" if variant == "burnout_spotting" else "not_applicable")


def current_phase_identity():
    return dict(schema="wfg.forecast-intended-phases/1", spotting_source_mode="flaming_only",
                phases=[intended_phase(v, "fold", fold) for fold in ("2020", "2021", "2022") for v in VARIANTS]
                       + [intended_phase(v, "final") for v in VARIANTS])


def phase_metadata(variant, stage, fold=None):
    return intended_phase(variant, stage, fold)


def validate_phase_identity(value):
    if value != current_phase_identity():
        raise ValueError("The exact current flaming-only phase identity is required")



def development_events(root):
    split = json.loads(_inside(root, "research/forecast-v2/SPLIT.json").read_text())
    folds = split.get("development_folds", {}).get("folds", {})
    if not isinstance(folds, dict) or set(folds) != {"2020", "2021", "2022"} or any(
            not isinstance(events, list) or not events or any(not isinstance(e, str) or not e for e in events)
            or len(events) != len(set(events)) for events in folds.values()):
        raise ValueError("Development requires the exact three nonempty distinct frozen fold lists")
    ordered = [e for events in folds.values() for e in events]
    if len(ordered) != len(set(ordered)) or set(ordered) != set(split["fit"]["us_perimeter_and_kriged"]):
        raise ValueError("Development folds must partition every intended US fit fire without overlap")
    return folds


def _provided_option(command, name):
    values = []
    for index, token in enumerate(command):
        if token == name:
            if index + 1 >= len(command) or command[index + 1].startswith("--"):
                raise ValueError("Effective fit argument has no value: " + name)
            values.append(command[index + 1])
        elif token.startswith(name + "="):
            values.append(token[len(name) + 1:])
    return values[-1] if values else None


def _effective_option(root, source, command, name):
    explicit = _provided_option(command, name)
    if explicit is not None:
        return explicit, "EXPLICIT_LAST_ARGUMENT"
    pipeline = _source_blob(root, "research/forecast-v2/scripts/pipeline.py", source.get("research/forecast-v2/scripts/pipeline.py"))
    calls = [n for n in ast.walk(_function(pipeline, "main")) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "add_argument"
             and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == name]
    defaults = [keyword.value for call in calls for keyword in call.keywords if keyword.arg == "default"]
    if len(calls) != 1 or len(defaults) != 1:
        raise ValueError("An effective argument needs its exact immutable argparse default: " + name)
    return str(ast.literal_eval(defaults[0])), "IMMUTABLE_ARGPARSE_DEFAULT"


def development_budget(root, receipt, result, expected_count=None):
    command, source = receipt.get("command", []), receipt.get("source_sha256", {})
    effective = {name: _effective_option(root, source, command, "--" + name.replace("_", "-")) for name in
                 ("epochs", "seed", "max_fit_intervals_per_fire", "intervals_per_epoch", "samples_per_step", "hidden", "lr")}
    fixed = dict(epochs=3, seed=0, max_fit_intervals_per_fire=3, samples_per_step=1, hidden=16)
    try:
        if any(int(effective[name][0]) != value for name, value in fixed.items()) or float(effective["lr"][0]) != .003:
            raise ValueError("Development requires fixed effective LAST budgets and model policy")
        cap = int(effective["intervals_per_epoch"][0])
    except (TypeError, ValueError) as error:
        raise ValueError("Development requires fixed effective LAST budgets and model policy") from error
    count = result.get("train_samples") if expected_count is None else expected_count
    if type(count) is not int or count < 1 or cap < 0 or (cap and cap < count):
        raise ValueError("Development interval cap must be zero or provably NONBINDING_CAP")
    if "--balance" not in command or any(token.startswith("--balance=") for token in command):
        raise ValueError("Development requires the frozen balanced training flag")
    variant = result["variant"]
    spec = FIXED_VARIANT_POLICY[variant]
    configuration = result.get("configuration", {})
    required_configuration = dict(architecture="StructuredKernelModel", kernel_size=9, hidden_channels=16, dropout=0.,
        prior=spec["prior"], frame=spec["frame"], residence_hours=spec.get("residence_hours"),
        spotting_radius=spec.get("spotting_radius", 0), wind_adjustment_factor=.4)
    if (result.get("hidden") != 16 or result.get("spec") != spec
            or any(configuration.get(key) != value for key, value in required_configuration.items())):
        raise ValueError("Development result must retain the exact fixed model configuration")
    return dict(effective_arguments={name: value for name, (value, _) in effective.items()},
                argument_origins={name: origin for name, (_, origin) in effective.items()},
                interval_cap_status="UNRESTRICTED_CAP_ZERO" if cap == 0 else "NONBINDING_CAP", balanced=True)


def comparison_suffix(attempt):
    if type(attempt) is not int or attempt < 0:
        raise ValueError("Comparison attempt must be a nonnegative integer")
    return f"_a{attempt:02d}" if attempt >= 5 else ""


def comparison_case_relative(index, suffix):
    if type(index) is not int or index not in range(12) or (suffix and (
            re.fullmatch(r"_a[0-9]{2,}", suffix) is None or int(suffix[2:]) < 5
            or suffix != comparison_suffix(int(suffix[2:])))):
        raise ValueError("Comparison artifacts require a fixed case index and validated attempt suffix")
    return f"meanfield_vs_mc/case_{index:02d}{suffix}"

def phase_result(root, run, variant, stage, fold=None):
    """Authenticate the exact intended result and its immutable execution phase."""
    phase = intended_phase(variant, stage, fold)
    path = _inside(root, Path(run) / phase["result"])
    result = json.loads(path.read_text())
    if (result.get("variant") != variant or result.get("seed") != 0
            or (stage == "fold" and str(result.get("fold")) != str(fold))):
        raise ValueError("Intended phase result names a different variant, fold or seed")
    if stage == "fold":
        split = json.loads(_inside(root, "research/forecast-v2/SPLIT.json").read_text())
        folds = split.get("development_folds", {}).get("folds", {})
        expected = folds.get(str(fold))
        observed = result.get("validation_per_fire", {})
        if (set(folds) != {"2020", "2021", "2022"} or not isinstance(expected, list) or not expected
                or any(not isinstance(event, str) or not event for event in expected)
                or len(expected) != len(set(expected)) or not isinstance(observed, dict)
                or set(observed) != set(expected)
                or ("validation_events" in result and result["validation_events"] != expected)):
            raise ValueError("Development validation fire membership must exactly match the frozen SPLIT fold and declared validation_events")
    matches = []
    for candidate in (root / "research/forecast-v2/executions").glob(f"*_{phase['job_suffix']}.json"):
        receipt = json.loads(candidate.read_text())
        output = Path(receipt.get("output", ""))
        output = output if output.is_absolute() else root / output
        recorded_run = _provided_option(receipt.get("command", []), "--run")
        same_phase = output.resolve() == path or (recorded_run is not None and output == Path(recorded_run) / phase["result"])
        if same_phase and receipt.get("output_sha256") == sha(path):
            matches.append((candidate, receipt))
    if len(matches) != 1 or matches[0][1].get("exit_code") != 0:
        raise ValueError("Exactly one successful immutable receipt for the intended phase is required")
    receipt_path, receipt = matches[0]
    command = receipt.get("command", [])
    if (stage not in command or _option(command, "--variant") != variant or _option(command, "--seed") != "0"
            or (stage == "fold" and _option(command, "--fold") != str(fold))):
        raise ValueError("Execution command differs from the intended phase")
    if stage == "fold":
        folds = development_events(root)
        train_events = [event for key, events in folds.items() if key != str(fold) for event in events]
        if (result.get("train_events") != train_events or result.get("validation_events") != folds[str(fold)]
                or type(result.get("validation_samples")) is not int or result["validation_samples"] < 1):
            raise ValueError("Development must name every actual frozen training and validation event and positive sample counts")
        development_budget(root, receipt, result)
        history = result.get("fit", {}).get("history", [])
        if len(history) != 3 or any(row.get("epoch") != index or type(row.get("optimizer_steps")) is not int
                or row["optimizer_steps"] < 1 or not isinstance(row.get("skipped_unsupported_intervals"), list)
                or row["optimizer_steps"] + len(row["skipped_unsupported_intervals"]) != result["train_samples"]
                for index, row in enumerate(history, 1)):
            raise ValueError("Development requires all three complete recorded epoch/optimizer/skip counts")
    source_contract = None
    if variant == "burnout_spotting":
        if (result.get("intended_phase") != phase or result.get("spotting_source_mode") != "flaming_only"
                or _option(command, "--artifact-suffix") != phase["artifact_suffix"]
                or not re.fullmatch(r"a(?:0[5-9]|[1-9][0-9]+)_" + re.escape(phase["job_suffix"]), receipt.get("job", ""))
                or receipt_path.stem != receipt.get("job")):
            raise ValueError("Corrected spotting requires fresh attempt5-or-later flaming-only phase metadata and arguments")
        source_contract = spotting_source_contract(root, receipt.get("source_sha256", {}))
    return path, result, receipt_path, receipt, source_contract


def development_selection(root, run):
    """Equal-fire criterion over exact SPLIT memberships checked by phase_result."""
    folds = json.loads(_inside(root, "research/forecast-v2/SPLIT.json").read_text())["development_folds"]["folds"]
    values, records = {}, {}
    for variant in VARIANTS:
        scores = []
        for fold in ("2020", "2021", "2022"):
            path, result, receipt, _, contract = phase_result(root, run, variant, "fold", fold)
            observed = result.get("validation_per_fire", {})
            if not observed or any(type(s.get("brier")) not in (int, float) or not math.isfinite(s["brier"])
                                   or not 0 <= s["brier"] <= 1 for s in observed.values()):
                raise ValueError("Every intended development fold requires finite per-fire Brier values")
            scores.extend(observed[event]["brier"] for event in folds[fold])
            records[intended_phase(variant, "fold", fold)["phase_id"]] = dict(result=identity(root, path), execution=identity(root, receipt),
                validation_events=folds[fold], source_contract=contract)
        values[variant] = sum(scores) / len(scores)
    return values, records


def validate_selection_phase(root, run, selection):
    validate_phase_identity(selection.get("current_phase"))
    values, development = development_selection(root, run)
    if selection.get("selected_variant") != min(VARIANTS, key=lambda name: (values[name], VARIANTS.index(name))):
        raise ValueError("Selection primary differs from the fixed intended development minimum and tie order")
    if selection.get("development_brier") != values or selection.get("development_phases") != development:
        raise ValueError("Selection must use exactly the authenticated intended development paths")
    if set(selection.get("checkpoints", {})) != set(VARIANTS):
        raise ValueError("Selection requires all intended final checkpoint identities")
    for variant, declared in selection["checkpoints"].items():
        expected = (Path(run) / intended_phase(variant, "final")["result"]).with_name("checkpoint.pt")
        if _inside(root, declared["path"]) != expected.resolve() or sha(expected) != declared["sha256"]:
            raise ValueError("Selection checkpoint differs from its exact intended final path and bytes")
    _, spot_result, _, _, contract = phase_result(root, run, "burnout_spotting", "final")
    if spot_result.get("checkpoint_sha256") != selection["checkpoints"]["burnout_spotting"]["sha256"]:
        raise ValueError("Corrected spotting result, receipt and selected checkpoint identities differ")
    development_hash = authenticate_development_coverage(root, run, selection, development)
    return dict(current_phase=current_phase_identity(), development_phases=development, spotting_source_contract=contract,
                development_coverage_sha256=development_hash)


def saved_registry_admission(root, run, selection_path, selection, registry_path):
    """Authenticate an existing freeze on every assessment/resume, without rebuild."""
    root, run = Path(root).resolve(), Path(run).resolve()
    path = _inside(root, registry_path)
    registry = json.loads(path.read_text())
    phase = validate_selection_phase(root, run, selection)
    validate_phase_identity(registry.get("current_phase"))
    if (registry.get("schema") != "wfg.forecast-blind-registry/1" or registry.get("status") != "FROZEN"
            or registry.get("selection") != identity(root, selection_path)
            or registry.get("selected_model") != selection["selected_variant"] + "_seed0"
            or registry.get("development_phases") != phase["development_phases"]
            or registry.get("spotting_source_contract") != phase["spotting_source_contract"]
            or registry.get("development_coverage_sha256") != phase["development_coverage_sha256"]
            or registry.get("fit_coverage") != selection.get("fit_coverage")
            or registry.get("baselines") != selection.get("baselines")
            or registry.get("logistic") != selection.get("baselines", {}).get("logistic")):
        raise ValueError("Current assessment requires the exact saved source/model/selection registry freeze")
    models = registry.get("models", {})
    if set(models) != {"c651_mc", *(v + "_seed0" for v in VARIANTS)} or any(
            models[v + "_seed0"] != selection["checkpoints"][v] for v in VARIANTS):
        raise ValueError("Saved registry must bind the exact eight-model current assessment set")
    dilation = json.loads(_inside(root, registry["baselines"]["dilation_choice"]["path"]).read_text())
    if registry.get("best_dilation_hours_per_cell") != dilation.get("best_hours_per_cell"):
        raise ValueError("Saved registry dilation choice differs from the exact executed fitted baseline")
    for item in [*models.values(), *registry["baselines"].values()]:
        if identity(root, item["path"]) != item:
            raise ValueError("Saved registry checkpoint or baseline bytes changed")
    required = {str(p.relative_to(root)) for p in (root / "forecast/wildfire").rglob("*") if p.is_file() and p.suffix in (".py", ".json")}
    required |= {str(p.relative_to(root)) for p in (root / "research/forecast-v2/scripts").glob("*.py")}
    required |= {"research/forecast-v2/SPLIT.json", "research/forecast-v2/RUN_PROTOCOL.json",
                 "research/forecast-v2/RUN_PROTOCOL_EXTENSION_2.json", "forecast/pyproject.toml", "forecast/documents/preregistration_blind_test.md"}
    source = registry.get("producer_source_sha256", {})
    if not required <= source.keys() or any(sha(_inside(root, name)) != digest for name, digest in source.items()):
        raise ValueError("Saved registry complete executed source closure changed")
    if registry.get("unsupported_interval_policy") != unsupported_policy(root):
        raise ValueError("Saved registry must bind the prior immutable unsupported interval policy")
    if registry.get("dependency_versions") != {name: importlib.metadata.version(name) for name in
            ("numpy", "pandas", "torch", "rasterio", "pyproj", "shapely", "pyshp", "scipy", "scikit-learn")}:
        raise ValueError("Saved registry requires the exact registered direct dependency versions")
    for variant in VARIANTS:
        result, _, execution, _, _ = phase_result(root, run, variant, "final")
        if (registry.get("final_results", {}).get(variant) != identity(root, result)
                or registry.get("final_executions", {}).get(variant) != identity(root, execution)):
            raise ValueError("Saved registry final result or immutable producer receipt changed")
    coverage = registry["fit_coverage"]
    if identity(root, coverage["path"]) != coverage:
        raise ValueError("Saved complete fit coverage bytes changed")
    return dict(development_coverage_sha256=phase["development_coverage_sha256"], registry=identity(root, path), c651_sha256=models["c651_mc"]["sha256"], current_phase=phase["current_phase"], spotting_source_contract=phase["spotting_source_contract"])

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as target:
        target.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _inside(root, relative):
    path = Path(relative)
    lexical = path if path.is_absolute() else root / path
    if any(p.is_symlink() for p in (lexical.absolute(), *lexical.absolute().parents)):
        raise ValueError("Fit evidence and source paths cannot have symlink components")
    path = lexical.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Fit evidence paths require existing files within their declared root")
    return path


def identity(root, path):
    path = _inside(root, path)
    return dict(path=str(path.relative_to(root.resolve())), sha256=sha(path))


def _stamp(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("Fit case timestamps require explicit finite UTC instants")
    return stamp.tz_convert("UTC")


def descriptor(event, kind, cutoff, endpoint):
    cutoff, endpoint = _stamp(cutoff), _stamp(endpoint)
    if kind not in ("perimeter", "kriged") or not isinstance(event, str) or not event or endpoint <= cutoff:
        raise ValueError("Fit cases require an event, source kind and strictly ordered endpoints")
    case = dict(event=event, kind=kind, cutoff=cutoff.isoformat(), endpoint=endpoint.isoformat())
    return dict(case_id=object_sha(case), **case)


def sample_descriptor(sample):
    cutoff = _stamp(sample.t1)
    if sample.kind == "perimeter":
        if "t2" not in sample.meta:
            raise ValueError("Every cached perimeter sample requires its exact source endpoint identity")
        endpoint = _stamp(sample.meta["t2"])
        if float(sample.hours) != (endpoint - cutoff).total_seconds() / 3600:
            raise ValueError("The consumed perimeter duration differs from its exact source interval identity")
    else:
        endpoint = cutoff + pd.Timedelta(hours=float(sample.hours))
    return descriptor(sample.event_id, sample.kind, cutoff, endpoint)


def case_id(sample):
    return sample_descriptor(sample)["case_id"]


def sample_list_identity(samples):
    """Match the producer's exact field/value identity, independent of file bytes."""
    digest = hashlib.sha256()
    for sample in samples:
        for field in fields(sample):
            value = getattr(sample, field.name, None)
            digest.update(field.name.encode())
            if isinstance(value, np.ndarray):
                value = np.ascontiguousarray(value)
                digest.update(str((value.shape, str(value.dtype))).encode())
                digest.update(value.tobytes())
            else:
                digest.update(json.dumps(value, sort_keys=True, default=lambda v: v.item()).encode())
    return digest.hexdigest()


def capture_sample_manifest(samples, *, regime, producer_source_sha256, input_sha256):
    """Call on the actual ordered training list immediately before fitting."""
    if regime not in ("perimeter", "mixed"):
        raise ValueError("The full-fit regime must be perimeter or mixed")
    cases = [sample_descriptor(sample) for sample in samples]
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("The actual training input list contains duplicated fit case IDs")
    return dict(schema=SAMPLES_SCHEMA, capture="RUNTIME_BEFORE_FIT", regime=regime,
                sample_count=len(cases), sample_cases=cases, ordered_ids_sha256=object_sha(ids),
                membership_sha256=object_sha(sorted(ids)), sample_values_sha256=sample_list_identity(samples),
                producer_source_sha256=producer_source_sha256, input_sha256=input_sha256)


def producer_sources(root):
    root = Path(root).resolve()
    files = {p for p in (root / "forecast/wildfire").rglob("*") if p.is_file() and p.suffix in (".py", ".json")}
    files |= {root / p for p in ("research/forecast-v2/scripts/pipeline.py", "research/forecast-v2/scripts/run_campaign.py",
                                 "research/forecast-v2/scripts/audit_fit_coverage.py", "research/forecast-v2/RUN_PROTOCOL.json",
                                 "research/forecast-v2/RUN_PROTOCOL_EXTENSION_2.json")}
    return {str(_inside(root, p).relative_to(root)): sha(p) for p in sorted(files)}


def _split(root):
    path = _inside(root, "research/forecast-v2/SPLIT.json")
    split = json.loads(path.read_text())
    us, kr = (split["fit"][name] for name in ("us_perimeter_and_kriged", "korean_kriged_only"))
    if (not isinstance(us, list) or not us or not isinstance(kr, list)
            or any(not isinstance(e, str) or not e for e in us + kr)
            or len(set(us + kr)) != len(us + kr)):
        raise ValueError("The frozen split needs distinct intended US and Korean fit identities")
    return path, us, kr


def expected_membership(model_root, input_root):
    """Derive cases without growth, loss, model validity or quality exclusions."""
    root, inputs = Path(model_root).resolve(), Path(input_root).resolve()
    split_path, us, kr = _split(root)
    pins = {}

    def pin(relative):
        path = _inside(inputs, relative)
        pins[str(path.relative_to(inputs))] = sha(path)
        return path

    catalog = json.loads(pin("environment/events.json").read_text())
    by_id = {e["id"]: e for e in catalog}
    if len(by_id) != len(catalog) or any(event not in by_id for event in us):
        raise ValueError("Every intended US fit fire must appear exactly once in the source catalog")
    perimeter_path = pin("perimeters/PERIMETER_MANIFEST.json")
    perimeter_manifest = json.loads(perimeter_path.read_text())
    perimeter, kriged = [], []
    ledger = dict(perimeter={}, kriged={})
    # Pin the actual fit-source closure without opening any heldout region.
    for path in (inputs / "environment").iterdir():
        if path.is_file():
            pin(str(path.relative_to(inputs)))
    for event in us + kr:
        for folder in (inputs / "environment/regions" / event, inputs / "environment/quality_flags" / event):
            for path in folder.rglob("*"):
                if path.is_file():
                    pin(str(path.relative_to(inputs)))
    for event in us:
        metadata = by_id[event]
        path = pin(f"perimeters/{event}/states.npz")
        if perimeter_manifest.get("events", {}).get(event, {}).get("states_sha256") != sha(path):
            raise ValueError("Intended full perimeter states differ from their pinned source manifest")
        with np.load(path, allow_pickle=False) as data:
            times = [_stamp(str(t)) for t in data["times"]]
        if any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("Prepared perimeter timestamps must be strictly ordered and distinct")
        start, end = _stamp(metadata["start_utc"]), _stamp(metadata["end_utc"])
        cases = []
        for a, b in zip(times, times[1:]):
            exact = 0 < b.value - a.value <= 48 * 3600 * 10**9
            producer = 0 < (b - a).total_seconds() / 3600 <= 48 + 1e-9
            if exact != producer:
                raise ValueError("Whole-artifact HOLD: exact <=48h eligibility disagrees with the immutable producer duration predicate")
            if exact and start <= a.floor("h") <= end:
                cases.append(descriptor(event, "perimeter", a, b))
        perimeter.extend(cases)
        ledger["perimeter"][event] = dict(sample_count=len(cases), cases=cases,
                                          rule="consecutive distinct source surveys <=48h; cutoff catalog availability")
    for event in us + kr:
        region = inputs / "environment/regions" / event
        if not region.exists():
            ledger["kriged"][event] = dict(sample_count=0, cases=[], reason="REGION_ABSENT_UNDER_EXISTING_RECIPE")
            continue
        if event not in by_id:
            raise ValueError("An existing intended kriged region requires source catalog metadata")
        import rasterio
        arrival_path = pin(f"environment/regions/{event}/arrival_time_hours.tif")
        pin(f"environment/regions/{event}/kriging_std_hours.tif")
        with rasterio.open(arrival_path) as source:
            arrival = source.read(1, masked=True).filled(np.nan).astype(np.float64)
        finite = np.isfinite(arrival)
        cases = []
        if finite.any():
            metadata = by_id[event]
            t0, start, end = (_stamp(metadata[name]) for name in ("t0_utc", "start_utc", "end_utc"))
            for proposed in np.arange(math.floor(np.nanmin(arrival)), math.ceil(np.nanmax(arrival)), 12.0):
                cutoff = (t0 + pd.Timedelta(hours=float(proposed))).floor("h")
                elapsed = (cutoff - t0).total_seconds() / 3600
                if not start <= cutoff <= end or not (finite & (arrival <= elapsed)).any():
                    continue
                cases.append(descriptor(event, "kriged", cutoff, cutoff + pd.Timedelta(hours=12)))
        kriged.extend(cases)
        ledger["kriged"][event] = dict(sample_count=len(cases), cases=cases,
                                       reason=None if cases else "ZERO_WINDOWS_UNDER_EXISTING_UTC_RECIPE",
                                       rule="frozen 12h proposed cadence, UTC floor, cutoff availability and initial.any only")
    extraction = pin("EXTRACTION_MANIFEST.json")
    frozen_protocol = json.loads(_inside(root, "research/forecast-v2/RUN_PROTOCOL.json").read_text())
    if frozen_protocol.get("data_manifest_sha256") != sha(extraction):
        raise ValueError("Complete fit source inputs differ from the immutable run-protocol extraction manifest")
    source_pins = {row["path"]: row["sha256"] for row in json.loads(extraction.read_text())["members"]}
    if any(entry.get("reason") == "REGION_ABSENT_UNDER_EXISTING_RECIPE"
           and any(name.startswith(f"environment/regions/{event}/") for name in source_pins)
           for event, entry in ledger["kriged"].items()):
        raise ValueError("An intended kriged source region is missing despite pinned archive member identities")
    if any(source_pins.get(name) != value for name, value in pins.items() if name.startswith("environment/")):
        raise ValueError("A source used to derive complete fit membership differs from the pinned extraction bytes")
    if (inputs / "BASELINE_TERRAIN_MANIFEST.json").is_file():
        pin("BASELINE_TERRAIN_MANIFEST.json")
    all_cases = perimeter + kriged
    if len({c["case_id"] for c in all_cases}) != len(all_cases):
        raise ValueError("Source-derived full-fit membership contains duplicate identities")
    return dict(split=identity(root, split_path), intended_us_fit_events=us, intended_kriged_fit_events=us + kr,
                ledger=ledger, perimeter_cases=perimeter, mixed_cases=all_cases,
                input_sha256=dict(sorted(pins.items())),
                perimeter_membership_sha256=object_sha(sorted(c["case_id"] for c in perimeter)),
                mixed_membership_sha256=object_sha(sorted(c["case_id"] for c in all_cases)))


def _source_blob(root, relative, expected):
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Immutable fit phase sources require exact SHA-256 identities")
    current = _inside(root, relative)
    if sha(current) == expected:
        return current.read_bytes().decode("utf-8")
    snapshot = root / "research/forecast-v2/source_snapshots" / expected / Path(relative).name
    if snapshot.is_file() and sha(snapshot) == expected:
        return snapshot.read_bytes().decode("utf-8")
    compressed = snapshot.with_name(snapshot.name + ".gz")
    if compressed.is_file():
        original = gzip.decompress(compressed.read_bytes())
        if hashlib.sha256(original).hexdigest() != expected:
            raise ValueError("Compressed immutable source snapshot differs from the recorded original bytes")
        return original.decode("utf-8")
    listing = subprocess.run(["git", "rev-list", "--all", "--", relative], cwd=root, capture_output=True, text=True)
    commits = listing.stdout.splitlines() if listing.returncode == 0 else []
    for commit in commits:
        value = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=root, capture_output=True)
        if value.returncode == 0 and hashlib.sha256(value.stdout).hexdigest() == expected:
            return value.stdout.decode()
    raise ValueError("Exact immutable fit producer source is unavailable: " + relative)


@lru_cache(maxsize=32)
def _tree(source):
    return ast.parse(source)


@lru_cache(maxsize=4096)
def _dump(node):
    return ast.dump(node, include_attributes=False)


@lru_cache(maxsize=128)
def _expression(expression):
    return _dump(ast.parse(expression, mode="eval").body)


@lru_cache(maxsize=128)
def _function(source, name):
    nodes = [n for n in ast.walk(_tree(source)) if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(nodes) != 1:
        raise ValueError("Expected one exact producer function: " + name)
    return nodes[0]


def _same(node, expression):
    return _dump(node) == _expression(expression)


def _literal(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        return {_literal(k): _literal(v) for k, v in zip(node.keys, node.values)}
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict"
            and not node.args and all(k.arg is not None for k in node.keywords)):
        return {k.arg: _literal(k.value) for k in node.keywords}
    raise ValueError("Fit regime policy must be an explicit literal source table")



def spotting_source_contract(root, source):
    """Bind the corrected law to preserved producer bytes, not a caller label."""
    functions = {"forecast/wildfire/survival.py": "sample_forecast",
                 "forecast/wildfire/meanfield.py": "propagate_mean_field",
                 "forecast/wildfire/burnout.py": "flaming_source"}
    nodes, hashes = {}, {}
    for relative, name in functions.items():
        blob = _source_blob(root, relative, source.get(relative))
        node = _function(blob, name)
        current = _function((root / relative).read_text(), name)
        if _dump(node) != _dump(current):
            raise ValueError("Immutable spotting producer differs from the current flaming-only source contract")
        nodes[name] = node
        hashes[name] = object_sha(_dump(node))
    sample = nodes["sample_forecast"]
    modes = [n.value for n in ast.walk(sample) if isinstance(n, ast.Assign)
             and any(ast.unparse(t) == "spotting.source_mode" for t in n.targets)]
    calls = [n for n in ast.walk(sample) if isinstance(n, ast.Call) and _same(n.func, "propagate_mean_field")]
    if len(modes) != 1 or not _same(modes[0], '"flaming_only"') or len(calls) != 1 or not any(
            k.arg == "extra_rate_fn" and _same(k.value, "spotting") for k in calls[0].keywords):
        raise ValueError("Immutable sample_forecast must set and execute spotting.source_mode flaming_only")
    propagate = nodes["propagate_mean_field"]
    if not any(isinstance(n, ast.Assign) and any(ast.unparse(t) == "extra_source" for t in n.targets)
               and _same(n.value, "burnout.flaming_source(clean, age0, history[j], clock, current=states[j])") for n in ast.walk(propagate)) or not any(
               isinstance(n, ast.Call) and _same(n, "extra_rate_fn(extra_source, k)") for n in ast.walk(propagate)):
        raise ValueError("Immutable mean-field producer must pass the flaming-only occupancy to the extra callback")
    return dict(schema="wfg.forecast-spotting-source/1", source_mode="flaming_only",
                source_sha256={relative: source[relative] for relative in functions}, ast_sha256=hashes,
                evidence="IMMUTABLE_SOURCE_CONTRACT_CHECKED_NOT_RUNTIME_ATTESTATION")

def _normalized_input_recipe(node, name, *, pure):
    """Only known custody insertions and a proven-unconsumed mixed branch.

    Raw source identities remain preserved. Membership/value cache audits remain
    mandatory; normalization does not attest that old runs enforced new checks.
    """
    node = ast.parse(ast.unparse(node)).body[0]
    applied = []
    if name == "perimeter_samples":
        custody = ast.parse('''manifest_path = perimeters / "PERIMETER_MANIFEST.json"
manifest = json.loads(manifest_path.read_text())
states_path = perimeters / event / "states.npz"
if sha256(states_path) != manifest["events"][event]["states_sha256"]:
    raise ValueError("Perimeter reference identity differs from its source manifest")
data = np.load(states_path, allow_pickle=False)
''').body
        if [_dump(n) for n in node.body[:len(custody)]] == [_dump(n) for n in custody]:
            node.body[:len(custody)] = ast.parse('data = np.load(perimeters / event / "states.npz")').body
            applied.append("EXACT_CURRENT_PERIMETER_CUSTODY_PREFIX")
    if name == "kriged_samples":
        custody = ast.parse('''if hasattr(env, "_verify_sources"):
    env._verify_sources(event)
''').body[0]
        if len(node.body) > 1 and _dump(node.body[1]) == _dump(custody):
            node.body.pop(1)
            applied.append("EXACT_CURRENT_KRIGED_CUSTODY_CHECK")
    if name == "fit_samples" and pure:
        body = [n for n in node.body if not (isinstance(n, ast.If) and _same(n.test, "mixed"))]
        if len(body) != len(node.body):
            node.body = body
            applied.append("MIXED_FALSE_BRANCH_NOT_CONSUMED_BY_THIS_VARIANT")
    return node, applied


def _input_recipe_contract(pipeline, current_pipeline, variant, table):
    pure = variant in table and not table[variant].get("mixed", False)
    records = {}
    for name in ("fit_samples", "available", "perimeter_samples", "kriged_samples", "build_model"):
        old, current = _function(pipeline, name), _function(current_pipeline, name)
        consumed = name != "kriged_samples" or not pure
        record = dict(consumed=consumed, immutable_ast_sha256=object_sha(_dump(old)),
                      current_ast_sha256=object_sha(_dump(current)))
        if consumed:
            a, old_steps = _normalized_input_recipe(old, name, pure=pure)
            b, new_steps = _normalized_input_recipe(current, name, pure=pure)
            if _dump(a) != _dump(b):
                raise ValueError("Frozen producer consumed input recipe differs: " + name)
            record.update(normalized_ast_sha256=object_sha(_dump(a)), immutable_normalization=old_steps,
                          current_normalization=new_steps)
        else:
            headers = []
            for definition in (old, current):
                header = ast.parse(ast.unparse(definition)).body[0]
                header.body = [ast.Pass()]
                headers.append(_dump(header))
            if headers[0] != headers[1]:
                raise ValueError("Frozen producer unconsumed definition header differs: " + name)
            record["definition_header_ast_sha256"] = object_sha(headers[0])
            record["nonconsumption_proof"] = "Fixed variant table and exact command train call resolve mixed=False; validation is mixed=False"
        records[name] = record
    return dict(variant=variant, resolved_mixed=not pure if variant in table else None, functions=records,
                evidence="SOURCE_RECIPE_EQUIVALENCE_CONDITIONAL_ON_MANDATORY_AUTHENTICATED_MEMBERSHIP_AND_CACHE_VALUES")


def _schedule_contract(root, source, stage="final", variant=None):
    """Bounded source checks for full permutations and the recorded skip paths."""
    pipeline = _source_blob(root, "research/forecast-v2/scripts/pipeline.py", source["research/forecast-v2/scripts/pipeline.py"])
    survival = _source_blob(root, "forecast/wildfire/survival.py", source["forecast/wildfire/survival.py"])
    current_pipeline = (root / "research/forecast-v2/scripts/pipeline.py").read_text()
    tables = [n for n in _tree(pipeline).body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "VARIANTS" for t in n.targets)]
    if len(tables) != 1:
        raise ValueError("The immutable producer must identify the full mixed/perimeter regime table")
    table = _literal(tables[0].value)
    if (table != FIXED_VARIANT_POLICY or table["mixed_base"].get("mixed") is not True
            or any(table[name].get("mixed", False) for name in VARIANTS if name != "mixed_base")):
        raise ValueError("The producer's mixed extra-source regime differs from the intended fit policy")
    recipe = _input_recipe_contract(pipeline, current_pipeline, variant, table)
    final = _function(pipeline, "command_" + stage)
    required_origins = {"spec": "VARIANTS[args.variant]",
                        "train_events": 'available(args, SPLIT["fit"]["us_perimeter_and_kriged"])',
                        "train": 'fit_samples(args, train_events, env, mixed=spec.get("mixed", False))'}
    if stage == "fold":
        required_origins.update(folds='SPLIT["development_folds"]["folds"]',
            train_events='available(args, [e for f, ev in folds.items() if f != args.fold for e in ev])',
            validation_events='available(args, folds[args.fold])', validation='fit_samples(args, validation_events, env, mixed=False)')
    for target, expression in required_origins.items():
        values = [n.value for n in ast.walk(final) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == target for t in n.targets)]
        if len(values) != 1 or not _same(values[0], expression):
            raise ValueError("The immutable final producer does not consume its entire declared full-fit source list")
    calls = [n for n in ast.walk(final) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "fit_mean_field"]
    if len(calls) != 1:
        raise ValueError("One direct full-fit producer call is required")
    if len(calls[0].args) != 3 or not _same(calls[0].args[1], "train") or not _same(calls[0].args[2], "validation" if stage == "fold" else "[]"):
        raise ValueError("Full fit must consume its entire prepared train list without a validation-based stopping set")
    keywords = {k.arg: k.value for k in calls[0].keywords}
    for name, value in {"validate_each_epoch": "False", "intervals_per_epoch": "args.intervals_per_epoch or None",
                        "samples_per_step": "args.samples_per_step", "epochs": "args.epochs", "learning_rate": "args.lr",
                        "seed": "args.seed", "d4": 'spec["d4"]', "balance": "balance", "biome_channels": "channels"}.items():
        if name not in keywords or not _same(keywords[name], value):
            raise ValueError("Producer full-fit budget or selection call differs from the source-inference contract")
    if stage == "fold":
        for name, expression in {"scores": "evaluate_samples(model, validation)",
                "per_fire": "{e: evaluate_samples(model, [s for s in validation if s.event_id == e]) for e in validation_events}"}.items():
            assignments = [node for node in final.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
            if len(assignments) != 1 or not _same(assignments[0].value, expression):
                raise ValueError("Immutable fold evaluation must directly consume the entire validation list and every declared fire")
        record = [node.value for node in final.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "record" for target in node.targets)]
        if len(record) != 1 or not isinstance(record[0], ast.Call):
            raise ValueError("Immutable fold must directly record its complete actual input membership and fit result")
        recorded = {keyword.arg: keyword.value for keyword in record[0].keywords}
        for name, expression in {"train_events": "train_events", "validation_events": "validation_events",
                "train_samples": "len(train)", "validation_samples": "len(validation)", "validation": "scores",
                "validation_per_fire": "per_fire", "fit": "result"}.items():
            if name not in recorded or not _same(recorded[name], expression):
                raise ValueError("Immutable fold result substitutes counters or validation metrics for its actual prepared lists")
        for name in ("evaluate_samples", "endpoint_brier", "sample_tensors"):
            if _dump(_function(survival, name)) != _dump(_function((root / "forecast/wildfire/survival.py").read_text(), name)):
                raise ValueError("Immutable validation producer differs from the audited complete sample evaluation recipe")
        evaluation = _function(survival, "evaluate_samples")
        if not any(isinstance(n, ast.For) and _same(n.iter, "samples") for n in ast.walk(evaluation)):
            raise ValueError("Validation source must evaluate every prepared sample")
        if not any(isinstance(n, ast.Call) and _same(n, "evaluate_samples(model, validation)") for n in ast.walk(final)):
            raise ValueError("Fold result must evaluate its entire independently derived validation list")
    fitting = _function(survival, "fit_mean_field")
    assignments = [n for n in ast.walk(fitting) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "order" for t in n.targets)]
    if len(assignments) != 2 or not any(_same(n.value, "rng.permutation(len(train))") for n in assignments) or not any(
            _same(n.value, "order[:intervals_per_epoch]") for n in assignments):
        raise ValueError("Historical source does not establish the frozen full permutation and optional cap")
    loops = {n.target.id: n for n in ast.walk(fitting) if isinstance(n, ast.For) and isinstance(n.target, ast.Name)}
    for name, value in {"epoch": "range(1, epochs + 1)", "start": "range(0, len(order), samples_per_step)",
                        "index": "order[start:start + samples_per_step]"}.items():
        if name not in loops or not _same(loops[name].iter, value):
            raise ValueError("Historical source does not establish one pass over the complete epoch membership")
    if loops["start"] not in list(ast.walk(loops["epoch"])) or loops["index"] not in list(ast.walk(loops["start"])):
        raise ValueError("Historical full-fit loops are not nested in the required epoch/sample order")
    sample_assignments = [n for n in ast.walk(loops["index"]) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "sample" for t in n.targets)]
    if (not any(_same(n.value, "train[index]") for n in sample_assignments)
            or any(not _same(n.value, "train[index]") and not (isinstance(n.value, ast.Call)
                       and isinstance(n.value.func, ast.Name) and n.value.func.id == "augment") for n in sample_assignments)
            or any(isinstance(n, ast.Name) and n.id == "train" and isinstance(n.ctx, ast.Store) for n in ast.walk(fitting))):
        raise ValueError("Historical training must select the actual indexed member without altering the input list")
    parents = {child: node for node in ast.walk(fitting) for child in ast.iter_child_nodes(node)}
    allowed = {ast.dump(ast.parse(value, mode="eval").body, include_attributes=False)
               for value in ("float(w) <= 0", "w_total <= 0", "not validate_each_epoch")}
    for node in [n for n in ast.walk(fitting) if isinstance(n, ast.Continue)]:
        ancestor = parents[node]
        while not isinstance(ancestor, ast.If) and ancestor in parents:
            ancestor = parents[ancestor]
        if not isinstance(ancestor, ast.If) or ast.dump(ancestor.test, include_attributes=False) not in allowed:
            raise ValueError("Unaccounted historical training skip path prevents complete schedule inference")
    for node in [n for n in ast.walk(fitting) if isinstance(n, ast.Break)]:
        ancestor = parents[node]
        while not isinstance(ancestor, ast.If) and ancestor in parents:
            ancestor = parents[ancestor]
        if not isinstance(ancestor, ast.If) or not _same(ancestor.test, "validation and stale >= patience"):
            raise ValueError("Unaccounted historical early stopping prevents a full-epoch coverage inference")
    return dict(input_recipe=recipe, pipeline_sha256=source["research/forecast-v2/scripts/pipeline.py"],
                survival_sha256=source["forecast/wildfire/survival.py"],
                fit_mean_field_ast_sha256=object_sha(ast.dump(fitting, include_attributes=False)),
                evidence="BOUNDED_SOURCE_CONTRACT_CHECKED")


def _option(command, name):
    value = _provided_option(command, name)
    if value is None:
        raise ValueError("Effective fit argument is missing: " + name)
    return value


def _execution(root, run, variant):
    path, result, receipt_path, receipt, _ = phase_result(root, run, variant, "final")
    return path, result, receipt_path, receipt


def _cache_lists(root, cache_root, audit, expected):
    sample_rows = [row for row in audit.get("records", []) if row.get("kind") == "sample-list"]
    rows = {Path(row["cache"]).resolve(): row for row in sample_rows}
    if len(rows) != len(sample_rows):
        raise ValueError("Source-recomputed cache evidence cannot contain duplicated cache identities")
    groups, files = {}, {}
    for kind, ledger in expected["ledger"].items():
        for event, entry in ledger.items():
            if kind == "kriged" and entry.get("reason") == "REGION_ABSENT_UNDER_EXISTING_RECIPE":
                groups[(kind, event)] = []
                continue
            prefix = "perimeter_crop" if kind == "perimeter" else "kriged_utc_v2"
            path = _inside(cache_root, f"samples/{prefix}_first0_{event}.pkl")
            row = rows.get(path)
            if (row is None or row.get("status") != "MATCHES_RECOMPUTED_SOURCES"
                    or row.get("cache_sha256") != sha(path)):
                raise ValueError("Every complete fit cache requires exact source-recomputed cache-audit evidence")
            samples = pickle.loads(path.read_bytes())
            value_identity = sample_list_identity(samples)
            if (row.get("cached_value_identity") != value_identity or row.get("recomputed_value_identity") != value_identity
                    or row.get("samples") != len(samples)):
                raise ValueError("Cached sample values differ from their authenticated source-recomputed identity")
            actual = [sample_descriptor(s) for s in samples]
            if actual != entry["cases"]:
                raise ValueError("Actual cached full sample identities differ from independently derived source membership")
            groups[(kind, event)] = samples
            files[str(path.relative_to(cache_root))] = dict(sha256=sha(path), sample_values_sha256=value_identity,
                                                           sample_count=len(samples), case_ids=[c["case_id"] for c in actual])
    perimeter = [s for event in expected["intended_us_fit_events"] for s in groups[("perimeter", event)]]
    mixed = perimeter + [s for event in expected["intended_kriged_fit_events"] for s in groups[("kriged", event)]]
    return perimeter, mixed, files



def unsupported_policy(root):
    path = _inside(root, "research/forecast-v2/RUN_PROTOCOL_EXTENSION_2.json")
    if sha(path) != UNSUPPORTED_POLICY_SHA256:
        raise ValueError("Unsupported-interval admission requires the exact prior immutable extension2 policy")
    return identity(root, path)



def unsupported_source_reason(sample):
    """Input-only mixed_base K9/cutoff-repeat envelope, never an optimizer replay."""
    from scipy.ndimage import minimum_filter
    initial, mask = np.asarray(sample.initial), np.asarray(sample.score_mask, dtype=bool)
    environment = np.asarray(sample.environment)
    weights = np.asarray(sample.label_weight, dtype=np.float32)
    if (environment.ndim != 3 or environment.shape[1:] != initial.shape or mask.shape != initial.shape
            or weights.shape != initial.shape or not np.isin(initial, [0, 1]).all()
            or sample.weather != "cutoff_repeated" or not np.isfinite(weights[mask]).all() or (weights[mask] < 0).any()):
        raise ValueError("Narrow unsupported-source classification requires binary initial state, repeated cutoff inputs and finite nonnegative weights")
    positive = mask & (weights > 0)
    if not positive.any():
        return dict(classification="ZERO_FINITE_POSITIVE_REFERENCE_WEIGHT_FROM_AUTHENTICATED_SOURCE", reference_positive_weight_cells=0)
    known = np.isfinite(environment).all(axis=0)
    # boundary='zero' means outside-grid state and covariates are known.
    context = minimum_filter(known, size=9, mode="constant", cval=1)
    valid = np.ones(initial.shape, dtype=bool)
    hours = float(sample.hours)
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError("Unsupported support recurrence requires a positive finite duration")
    whole = int(math.floor(hours + 1e-12))
    steps = whole + int(hours - whole > 1e-9)
    for _ in range(steps):
        following = valid & ((initial == 1) | (context & minimum_filter(valid, size=9, mode="constant", cval=1)))
        if np.array_equal(following, valid):
            break
        valid = following
    if (positive & valid).any():
        raise ValueError("Logged unsupported sample retains positive source weight under the narrow conservative support envelope")
    return dict(classification="EMPTY_REPEATED_CUTOFF_ENVIRONMENT_SUPPORT", reference_positive_weight_cells=int(positive.sum()),
                supported_positive_weight_cells=0, recurrence_steps=steps,
                support_mask_sha256=hashlib.sha256(np.ascontiguousarray(valid).tobytes()).hexdigest(),
                evidence="SOURCE_DERIVED_CONSERVATIVE_POSITIVE_KERNEL_ENVELOPE_NOT_PER_OPTIMIZER_MASK_REPLAY",
                numeric_limit="Finite floating-point softplus can underflow to zero; actual runtime skip records are observed evidence, this envelope is source inference.")


def mixed_support_contract(root, source):
    """Scope the input-only recurrence to the exact immutable mixed_base recipe."""
    models = _source_blob(root, "forecast/wildfire/models.py", source.get("forecast/wildfire/models.py"))
    meanfield = _source_blob(root, "forecast/wildfire/meanfield.py", source.get("forecast/wildfire/meanfield.py"))
    survival = _source_blob(root, "forecast/wildfire/survival.py", source.get("forecast/wildfire/survival.py"))
    pipeline = _source_blob(root, "research/forecast-v2/scripts/pipeline.py", source.get("research/forecast-v2/scripts/pipeline.py"))
    specs = [n for n in _tree(pipeline).body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VARIANTS" for t in n.targets)]
    if len(specs) != 1 or _literal(specs[0].value).get("mixed_base") != dict(prior="free", frame="none", d4=False, mixed=True):
        raise ValueError("Unsupported-source envelope is restricted to the exact mixed_base no-frame/no-extra regime")
    nodes = []
    methods = {}
    for class_name, method in [("EnvironmentConditionedConvolution", "_features"), ("EnvironmentConditionedConvolution", "__init__"),
                               ("StructuredKernelModel", "_positive"), ("StructuredKernelModel", "_structured"),
                               ("StructuredKernelModel", "kernel_rates"), ("StructuredKernelModel", "__init__")]:
        def pick(blob):
            cls = next(n for n in _tree(blob).body if isinstance(n, ast.ClassDef) and n.name == class_name)
            return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
        node = pick(models)
        if _dump(node) != _dump(pick((root / "forecast/wildfire/models.py").read_text())):
            raise ValueError("Immutable local-kernel producer differs from the audited conservative support contract")
        nodes.append(node)
        methods[(class_name, method)] = node
    positive = methods[("StructuredKernelModel", "_positive")]
    if len([n for n in ast.walk(positive) if isinstance(n, ast.Return)]) != 1 or not any(
            isinstance(n, ast.Return) and _same(n.value, "F.softplus(logits)") for n in ast.walk(positive)):
        raise ValueError("Conservative support requires the fixed finite softplus local-kernel law")
    features = methods[("EnvironmentConditionedConvolution", "_features")]
    for expression in ("available & torch.isfinite(environmental_data)",
                       "F.pad(known, (radius,) * 4, value=1.0 if boundary == 'zero' else 0.0)",
                       "F.avg_pool2d(known, self.kernel_size, stride=1) == 1"):
        if not any(isinstance(n, ast.Assign) and _same(n.value, expression) for n in ast.walk(features)):
            raise ValueError("Conservative support requires the fixed local known-context and boundary law")
    build = _function(pipeline, "build_model")
    constructors = [n for n in ast.walk(build) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "StructuredKernelModel"]
    if len(constructors) != 1 or len(constructors[0].args) < 2 or not _same(constructors[0].args[1], "9"):
        raise ValueError("Conservative support is restricted to the intended K9 constructor")
    for blob, relative, name in [(models, "forecast/wildfire/models.py", "new_burn_probability"),
                               (meanfield, "forecast/wildfire/meanfield.py", "_probe_valid"),
                               (meanfield, "forecast/wildfire/meanfield.py", "model_kernel_components"),
                               (survival, "forecast/wildfire/survival.py", "step_durations"),
                               (pipeline, "research/forecast-v2/scripts/pipeline.py", "build_model")]:
        node = _function(blob, name)
        if _dump(node) != _dump(_function((root / relative).read_text(), name)):
            raise ValueError("Immutable support recipe differs from the exact audited local K9 producer")
        nodes.append(node)
    for name, expression in {"observed_burns": "known & (clean == 1)", "following": "masks[j] & (observed_burns | rate_valid)"}.items():
        values = [n.value for n in ast.walk(_function(meanfield, "propagate_mean_field")) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
        if len(values) != 1 or not _same(values[0], expression):
            raise ValueError("Immutable recursive validity envelope differs from the source-derived support law")
    return dict(regime="mixed_base_free_frame_none_K9_no_extra_cutoff_repeated_zero_boundary",
                source_sha256={name: source[name] for name in ("forecast/wildfire/models.py", "forecast/wildfire/meanfield.py",
                    "forecast/wildfire/survival.py", "research/forecast-v2/scripts/pipeline.py")},
                checked_ast_sha256=object_sha([_dump(node) for node in nodes]),
                evidence="SOURCE_DERIVED_CONSERVATIVE_POSITIVE_KERNEL_CONTRACT_NOT_RECORDED_PER_OPTIMIZER_MASKS")

def unsupported_sample_evidence(sample, cache_files):
    """Bind a logged skip to source-derived unsupported inputs without model replay."""
    case = sample_descriptor(sample)
    classification = unsupported_source_reason(sample)
    matches = [(name, row) for name, row in cache_files.items() if case["case_id"] in row["case_ids"]]
    if len(matches) != 1:
        raise ValueError("Every unsupported sample must have one exact complete source-recomputed cache identity")
    name, row = matches[0]
    return dict(case=case, sample_values_sha256=sample_list_identity([sample]),
                cache=dict(path=name, sha256=row["sha256"], sample_values_sha256=row["sample_values_sha256"]),
                **classification, reason="no_supported_positive_weight_cells")


def runtime_membership_contract(root, source):
    blob = _source_blob(root, "forecast/wildfire/survival.py", source["forecast/wildfire/survival.py"])
    fitter = _function(blob, "fit_mean_field")
    helper_relative = "research/forecast-v2/scripts/audit_fit_coverage.py"
    helper = _source_blob(root, helper_relative, source.get(helper_relative))
    for name in ("case_id", "sample_descriptor", "descriptor", "object_sha"):
        if _dump(_function(helper, name)) != _dump(_function((root / helper_relative).read_text(), name)):
            raise ValueError("Actual runtime IDs require the exact immutable canonical sample identity helper")
    pipeline = _source_blob(root, "research/forecast-v2/scripts/pipeline.py", source.get("research/forecast-v2/scripts/pipeline.py"))
    callback = 'dict(runtime_case_id_fn=coverage.case_id, runtime_object_sha_fn=coverage.object_sha, runtime_sample_manifest_sha256=fit_input_manifest["sha256"])'
    if not any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "runtime" for t in n.targets)
               and _same(n.value, callback) for n in ast.walk(_function(pipeline, "command_final"))):
        raise ValueError("Actual runtime membership must use the canonical case ID and manifest callbacks")
    ids = [n.value for n in ast.walk(fitter) if isinstance(n, ast.Assign)
           and any(isinstance(t, ast.Name) and t.id == "original_case_id" for t in n.targets)]
    if len(ids) != 1 or not _same(ids[0], "runtime_case_id_fn(sample)"):
        raise ValueError("Actual runtime IDs must identify the original consumed indexed sample")
    expressions = ("runtime_case_id_fn(sample)", "attempted_ids.append(original_case_id)",
                   "skipped_ids.append(original_case_id)", "dict(event=sample.event_id, cutoff=sample.t1, reason='no_supported_positive_weight_cells')")
    for expression in expressions:
        if not any(_same(n, expression) for n in ast.walk(fitter) if isinstance(n, ast.Call)):
            raise ValueError("Actual runtime membership source lacks the bound attempted-ID/unsupported logging contract")
    loop = next((n for n in ast.walk(fitter) if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == "index"), None)
    if loop is None:
        raise ValueError("Runtime attempted IDs require the actual original indexed sample loop")
    attempts = [n.lineno for n in ast.walk(loop) if isinstance(n, ast.Call) and _same(n, "attempted_ids.append(original_case_id)")]
    augmentations = [n.lineno for n in ast.walk(loop) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "augment"]
    if len(attempts) != 1 or (augmentations and attempts[0] >= min(augmentations)):
        raise ValueError("Runtime attempted IDs must be recorded before any augmentation")
    return dict(survival_sha256=source["forecast/wildfire/survival.py"], evidence="BOUNDED_IMMUTABLE_RUNTIME_LOGGING_SOURCE_CHECKED")


def _development_cache_lists(cache_root, audit, expected, mixed):
    """Authenticate first3 lists against both independent cases and full source values."""
    rows = {Path(row["cache"]).resolve(): row for row in audit.get("records", []) if row.get("kind") == "sample-list"}
    full = {}
    for sample in mixed:
        full.setdefault((sample.kind, sample.event_id), []).append(sample)
    groups, files = {}, {}
    for kind, ledger in expected["ledger"].items():
        for event, entry in ledger.items():
            if kind == "kriged" and entry.get("reason") == "REGION_ABSENT_UNDER_EXISTING_RECIPE":
                groups[(kind, event)] = []
                continue
            prefix = "perimeter_crop" if kind == "perimeter" else "kriged_utc_v2"
            path = _inside(cache_root, f"samples/{prefix}_first3_{event}.pkl")
            row = rows.get(path)
            if row is None or row.get("status") != "MATCHES_RECOMPUTED_SOURCES" or row.get("cache_sha256") != sha(path):
                raise ValueError("Every first3 development cache requires exact source-recomputed cache-audit evidence")
            samples = pickle.loads(path.read_bytes())
            actual = [sample_descriptor(sample) for sample in samples]
            value_identity = sample_list_identity(samples)
            if (actual != entry["cases"][:3] or value_identity != sample_list_identity(full.get((kind, event), [])[:3])
                    or row.get("samples") != len(samples) or row.get("cached_value_identity") != value_identity
                    or row.get("recomputed_value_identity") != value_identity):
                raise ValueError("Development first3 cache identities/values differ from the exact independent source prefix and full-source list")
            groups[(kind, event)] = samples
            files[str(path.relative_to(cache_root))] = dict(sha256=sha(path), sample_values_sha256=value_identity,
                sample_count=len(samples), case_ids=[case["case_id"] for case in actual])
    return groups, files


def _membership_record(samples):
    cases = [sample_descriptor(sample) for sample in samples]
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Independently derived development membership cannot repeat sample identities")
    return dict(sample_count=len(ids), cases=cases, ordered_ids_sha256=object_sha(ids), membership_sha256=object_sha(sorted(ids)),
                sample_values_sha256=sample_list_identity(samples), evidence="SOURCE_DERIVED_COMPLETE_INPUT_MEMBERSHIP_NOT_RUNTIME_IDS")


def _historical_development_epochs(root, variant, source, train, history, cache_files):
    ids = [case_id(sample) for sample in train]
    proofs = []
    support = None
    if variant == "mixed_base":
        support = mixed_support_contract(root, source)
        for sample in train:
            try:
                proofs.append(unsupported_sample_evidence(sample, cache_files))
            except ValueError as error:
                if "retains positive source weight" not in str(error):
                    raise
    expected = Counter((proof["case"]["event"], proof["case"]["cutoff"]) for proof in proofs)
    skipped_ids = {proof["case"]["case_id"] for proof in proofs}
    optimized = [value for value in ids if value not in skipped_ids]
    epochs = []
    for index, row in enumerate(history, 1):
        logs = row["skipped_unsupported_intervals"]
        actual = Counter()
        for entry in logs:
            if set(entry) != {"event", "cutoff", "reason"} or entry["reason"] != "no_supported_positive_weight_cells":
                raise ValueError("Historical development skip needs its exact source-bound event/cutoff/reason")
            actual[(entry["event"], _stamp(entry["cutoff"]).isoformat())] += 1
        if actual != expected or not optimized or row["optimizer_steps"] != len(optimized):
            raise ValueError("Historical development optimizer/skip logs do not prove a complete source-derived epoch")
        epochs.append(dict(epoch=index, optimizer_steps=row["optimizer_steps"], actual_logged_skips=logs,
            source_derived_skipped_samples=proofs, source_derived_optimized_case_ids=optimized,
            evidence="SOURCE_DERIVED_ID_ACCOUNTING_FROM_COMPLETE_LOOP_AND_EVENT_CUTOFF_LOGS_NO_RUNTIME_CASE_IDS"))
    return dict(coverage_status="FULL_INPUT_SOURCE_INFERRED_WITH_LOGGED_UNSUPPORTED" if proofs else "FULL_OPTIMIZER_COVERAGE_SOURCE_INFERRED",
                epochs=epochs, unsupported_support_source_contract=support)


def development_coverage(root, inputs, caches, run, audit, expected, mixed):
    folds = development_events(root)
    groups, files = _development_cache_lists(caches, audit, expected, mixed)
    records = {}
    for fold, validation_events in folds.items():
        train_events = [event for key, events in folds.items() if key != fold for event in events]
        for variant in VARIANTS:
            phase = intended_phase(variant, "fold", fold)
            path, result, receipt_path, receipt, spotting = phase_result(root, run, variant, "fold", fold)
            source, command = receipt["source_sha256"], receipt["command"]
            if (Path(_option(command, "--work")).resolve() != caches or Path(_option(command, "--run")).resolve() != run
                    or Path(_option(command, "--data-root")).resolve() != inputs / "environment"
                    or Path(_option(command, "--perimeters")).resolve() != inputs / "perimeters"
                    or _option(command, "--data-manifest-sha256") != expected["input_sha256"]["EXTRACTION_MANIFEST.json"]):
                raise ValueError("Development coverage requires the actual authenticated source/cache/run argument identities")
            train = [sample for event in train_events for sample in groups[("perimeter", event)]]
            if variant == "mixed_base":
                train += [sample for event in train_events + expected["intended_kriged_fit_events"][len(expected["intended_us_fit_events"]):]
                          for sample in groups[("kriged", event)]]
            validation = [sample for event in validation_events for sample in groups[("perimeter", event)]]
            if (not train or not validation or any(not groups[("perimeter", event)] for event in validation_events)
                    or result["train_samples"] != len(train) or result["validation_samples"] != len(validation)):
                raise ValueError("Development counts must equal every independently derived first3 training and validation sample")
            budget = development_budget(root, receipt, result, expected_count=len(train))
            contract = _schedule_contract(root, source, stage="fold", variant=variant)
            epochs = _historical_development_epochs(root, variant, source, train, result["fit"]["history"], files)
            records[phase["phase_id"]] = dict(intended_phase=phase, fit_result=identity(root, path), execution=identity(root, receipt_path),
                train_events=train_events, validation_events=validation_events, budget=budget,
                training=_membership_record(train), validation=_membership_record(validation), source_schedule_contract=contract,
                producer_source_sha256=source, spotting_source_contract=spotting,
                schedule_evidence="SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED", runtime_membership=None,
                **epochs)
    return records, files


def authenticate_development_coverage(root, run, selection, development_phases):
    """Replay frozen phase identities without requiring original training data locations."""
    declared = selection.get("fit_coverage", {})
    path = _inside(root, declared.get("path", ""))
    if identity(root, path) != declared:
        raise ValueError("Development admission requires the exact frozen fit-coverage artifact")
    record = json.loads(path.read_text())
    phases = record.get("development", {})
    if (record.get("schema") != SCHEMA or record.get("status") != "PASS_COMPLETE_FIT_MEMBERSHIP"
            or set(phases) != set(development_phases) or len(phases) != 21
            or selection.get("development_coverage_sha256") != object_sha(phases)):
        raise ValueError("All21 independently derived development memberships must be frozen into model selection")
    expected = record.get("expected", {})
    split_path, us, kr = _split(root)
    if (expected.get("split") != identity(root, split_path) or expected.get("intended_us_fit_events") != us
            or expected.get("intended_kriged_fit_events") != us + kr):
        raise ValueError("Frozen development proof must bind the same complete source-derived SPLIT inventory")
    for name, phase in phases.items():
        current = development_phases[name]
        if (phase.get("fit_result") != current["result"] or phase.get("execution") != current["execution"]
                or phase.get("validation_events") != current["validation_events"]
                or phase.get("schedule_evidence") != "SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED"
                or phase.get("runtime_membership") is not None):
            raise ValueError("Frozen development membership no longer binds the exact intended producer phases")
        intended = phase["intended_phase"]
        _, result, _, receipt, _ = phase_result(root, run, intended["variant"], "fold", intended["fold"])
        folds = development_events(root)
        train_events = [event for fold, events in folds.items() if fold != intended["fold"] for event in events]
        validation_events = folds[intended["fold"]]
        ledger = expected["ledger"]
        train_cases = [case for event in train_events for case in ledger["perimeter"][event]["cases"][:3]]
        if intended["variant"] == "mixed_base":
            train_cases += [case for event in train_events + kr for case in ledger["kriged"][event]["cases"][:3]]
        validation_cases = [case for event in validation_events for case in ledger["perimeter"][event]["cases"][:3]]
        for role, cases in (("training", train_cases), ("validation", validation_cases)):
            evidence = phase.get(role, {})
            ids = [case["case_id"] for case in cases]
            if (not ids or evidence.get("cases") != cases or evidence.get("sample_count") != len(ids)
                    or evidence.get("ordered_ids_sha256") != object_sha(ids)
                    or evidence.get("membership_sha256") != object_sha(sorted(ids))
                    or len(ids) != len(set(ids)) or not isinstance(evidence.get("sample_values_sha256"), str)
                    or re.fullmatch(r"[0-9a-f]{64}", evidence["sample_values_sha256"]) is None):
                raise ValueError("Frozen development proof must preserve every source-derived training/validation case identity")
        if (result["train_samples"] != len(train_cases) or result["validation_samples"] != len(validation_cases)
                or phase.get("train_events") != train_events
                or phase.get("budget") != development_budget(root, receipt, result, expected_count=len(train_cases))):
            raise ValueError("Frozen development counts/budgets disagree with the independently audited source membership")
    return object_sha(phases)

def audit_coverage(model_root, input_root, cache_root, run_root, cache_audit_path):
    root, inputs, caches, run = (Path(p).resolve() for p in (model_root, input_root, cache_root, run_root))
    expected = expected_membership(root, inputs)
    policy = unsupported_policy(root)
    cache_audit_path = _inside(root, cache_audit_path)
    audit = json.loads(cache_audit_path.read_text())
    if (audit.get("status") != "PASS_NO_CONSUMED_VALUES_CHANGED" or audit.get("producer_unchanged_during_audit") is not True
            or audit.get("mismatches") != []):
        raise ValueError("A passing source-recomputed cache audit is required for full fit coverage")
    _source_blob(root, "research/forecast-v2/scripts/pipeline.py", audit["producer_sha256"])
    _source_blob(root, "research/forecast-v2/scripts/audit_caches.py", audit["audit_script_sha256"])
    perimeter, mixed, cache_files = _cache_lists(root, caches, audit, expected)
    development, development_cache_files = development_coverage(root, inputs, caches, run, audit, expected, mixed)
    variants = {}
    for variant in VARIANTS:
        result_path, result, receipt_path, receipt = _execution(root, run, variant)
        if (result.get("train_events") != expected["intended_us_fit_events"]
                or result.get("seed") != 0 or result.get("epochs") != 3):
            raise ValueError("Every final result must name the exact complete intended US fit set in frozen order")
        command = receipt.get("command", [])
        effective = {name: _option(command, "--" + name.replace("_", "-")) for name in
                     ("variant", "seed", "epochs", "max_fit_intervals_per_fire", "intervals_per_epoch", "samples_per_step")}
        if (effective != dict(variant=variant, seed="0", epochs="3", max_fit_intervals_per_fire="0",
                              intervals_per_epoch="0", samples_per_step="1")):
            raise ValueError("Coverage requires the effective LAST full-fit arguments, one sample per optimizer step and no cap")
        if (Path(_option(command, "--work")).resolve() != caches
                or Path(_option(command, "--run")).resolve() != run
                or Path(_option(command, "--data-root")).resolve() != inputs / "environment"
                or Path(_option(command, "--perimeters")).resolve() != inputs / "perimeters"
                or _option(command, "--data-manifest-sha256") != expected["input_sha256"]["EXTRACTION_MANIFEST.json"]):
            raise ValueError("Source inputs, complete caches and result root must be the actual effective execution arguments")
        source = receipt.get("source_sha256", {})
        contract = _schedule_contract(root, source, variant=variant)
        spotting_contract = spotting_source_contract(root, source) if variant == "burnout_spotting" else None
        samples = mixed if variant == "mixed_base" else perimeter
        cases = expected["mixed_cases" if variant == "mixed_base" else "perimeter_cases"]
        ids = [c["case_id"] for c in cases]
        history = result.get("fit", {}).get("history", [])
        if (not ids or result.get("train_samples") != len(ids) or len(history) != 3
                or any(row.get("epoch") != i or type(row.get("optimizer_steps")) is not int
                       or row["optimizer_steps"] <= 0 or not isinstance(row.get("skipped_unsupported_intervals"), list)
                       for i, row in enumerate(history, 1))):
            raise ValueError("Full recorded sample/epoch counts and positive optimizer updates must agree with complete source membership")
        runtime = None
        unsupported = []
        runtime_contract = None
        support_contract = None
        coverage_status = "FULL_OPTIMIZER_COVERAGE"
        if variant != "mixed_base" and any(row["optimizer_steps"] != len(ids) or row["skipped_unsupported_intervals"] for row in history):
            raise ValueError("Historical pure schedule inference requires complete optimizer counts without unobserved skipped IDs")
        input_manifest = None
        evidence = "SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED"
        if variant == "mixed_base":
            runtime_contract = runtime_membership_contract(root, source)
            support_contract = mixed_support_contract(root, source)
            if result.get("intended_kriged_fit_events") != expected["intended_kriged_fit_events"]:
                raise ValueError("Mixed full fit must explicitly retain every intended US and Korean kriged event, including zero-window keys")
            declaration = result.get("fit_input_manifest", {})
            path = _inside(root, declaration["path"])
            if sha(path) != declaration["sha256"]:
                raise ValueError("Mixed prefit sample manifest bytes changed")
            manifest = json.loads(path.read_text())
            actual_manifest = capture_sample_manifest(samples, regime="mixed", producer_source_sha256=source,
                                                      input_sha256=expected["input_sha256"])
            if manifest != actual_manifest:
                raise ValueError("Runtime prefit input manifest differs from the complete authenticated sample list/source identity")
            input_manifest = identity(root, path)
            runtime = result.get("fit", {}).get("runtime_membership", {})
            epochs = runtime.get("epochs", [])
            if (runtime.get("schema") != RUNTIME_SCHEMA or runtime.get("sample_manifest_sha256") != sha(path) or len(epochs) != 3):
                raise ValueError("New mixed full fits require an actual runtime membership ledger bound to their prefit input manifest")
            samples_by_id = {case_id(sample): sample for sample in samples}
            for i, row in enumerate(epochs, 1):
                attempted, skipped = row.get("attempted_case_ids", []), row.get("skipped_case_ids", [])
                if (row.get("epoch") != i or len(attempted) != len(ids) or len(set(attempted)) != len(ids) or set(attempted) != set(ids)
                        or row.get("attempted_case_ids_sha256") != object_sha(attempted)
                        or len(skipped) != len(set(skipped)) or not set(skipped) <= set(attempted)):
                    raise ValueError("Actual mixed epoch membership omitted, repeated or invented an intended source sample")
                optimized = [value for value in attempted if value not in set(skipped)]
                history_row = history[i - 1]
                if (not optimized or row.get("optimizer_steps") != len(optimized)
                        or history_row["optimizer_steps"] != len(optimized)):
                    raise ValueError("Runtime attempted-minus-skipped membership must equal the positive recorded optimizer update count")
                logged = history_row["skipped_unsupported_intervals"]
                proofs = [unsupported_sample_evidence(samples_by_id[value], cache_files) for value in skipped]
                if len(logged) != len(proofs) or any(set(entry) != {"event", "cutoff", "reason"}
                        or entry["event"] != proof["case"]["event"]
                        or _stamp(entry["cutoff"]) != _stamp(proof["case"]["cutoff"])
                        or entry["reason"] != proof["reason"] for entry, proof in zip(logged, proofs)):
                    raise ValueError("Every actual skipped ID must match its exact source sample, history event/cutoff/reason and logging order")
                unsupported.append(dict(epoch=i, optimized_case_ids=optimized, optimized_case_ids_sha256=object_sha(optimized),
                    optimized_identity_evidence="DERIVED_ATTEMPTED_MINUS_RUNTIME_SKIPPED_IDS_WITH_SOURCE_LOOP_AND_COUNT_PROOF_NOT_RUNTIME_LOGGED",
                    skipped_samples=proofs))
            if any(row["skipped_samples"] for row in unsupported):
                coverage_status = "FULL_INPUT_ATTEMPTED_WITH_LOGGED_UNSUPPORTED"
            evidence = "RUNTIME_ATTEMPTED_IDS_BOUND_TO_IMMUTABLE_SOURCE_AND_PREFIT_INPUT_MANIFEST"
        checkpoint = dict(path=str(result_path.with_name("checkpoint.pt").relative_to(root)), sha256=result["checkpoint_sha256"])
        variants[variant] = dict(checkpoint=checkpoint, regime="mixed" if variant == "mixed_base" else "perimeter", fit_result=identity(root, result_path),
                                 execution=identity(root, receipt_path), effective_arguments=effective,
                                 intended_phase=intended_phase(variant, "final"), spotting_source_contract=spotting_contract,
                                 producer_source_sha256=source, source_schedule_contract=contract,
                                 sample_count=len(ids), membership_sha256=object_sha(sorted(ids)),
                                 sample_values_sha256=sample_list_identity(samples), input_manifest=input_manifest,
                                 schedule_evidence=evidence, runtime_membership=runtime, runtime_logging_source_contract=runtime_contract, unsupported_support_source_contract=support_contract,
                                 coverage_status=coverage_status, epoch_optimized_and_unsupported=unsupported,
                                 recorded_epochs=[dict(epoch=r["epoch"], optimizer_steps=r["optimizer_steps"],
                                                       skipped_unsupported_intervals=r["skipped_unsupported_intervals"]) for r in history])
    return dict(schema=SCHEMA, status="PASS_COMPLETE_FIT_MEMBERSHIP", current_phase=current_phase_identity(), unsupported_interval_policy=policy, expected=expected, variants=variants,
                development=development, development_cache_files=development_cache_files,
                source_sha256=producer_sources(root), cache_audit=identity(root, cache_audit_path), cache_files=cache_files,
                cache_audit_source_sha256=dict(pipeline=audit["producer_sha256"], audit_caches=audit["audit_script_sha256"]),
                input_root=str(inputs), cache_root=str(caches), run_root=str(run),
                limitations=["Historical pure schedules are source-derived inference, not retrospectively observed runtime IDs.",
                             "Complete attempted membership and exact source-bound logged unsupported cases establish input accounting, not scientific efficacy.",
                             "No model checkpoint or heldout forecast/score is read by this coverage audit.",
                             "Unsupported support envelopes are source-derived conservative classifications; no per-optimizer numerical masks were logged or replayed."])


def verify_coverage(model_root, run_root, declared):
    root, run = Path(model_root).resolve(), Path(run_root).resolve()
    if not isinstance(declared, dict) or set(declared) != {"path", "sha256"}:
        raise ValueError("Model selection requires an exact complete fit-coverage artifact identity")
    path = _inside(root, declared["path"])
    if sha(path) != declared["sha256"]:
        raise ValueError("Frozen full-fit coverage artifact bytes changed")
    recorded = json.loads(path.read_text())
    if recorded.get("schema") != SCHEMA or recorded.get("status") != "PASS_COMPLETE_FIT_MEMBERSHIP" or Path(recorded["run_root"]).resolve() != run:
        raise ValueError("A passing complete full-fit membership audit is required")
    current = audit_coverage(root, recorded["input_root"], recorded["cache_root"], run, recorded["cache_audit"]["path"])
    if current != recorded:
        raise ValueError("Fit coverage no longer matches source-derived inputs, exact artifacts, receipts or immutable producer phases")
    return identity(root, path), recorded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model-root", "input-root", "cache-root", "run-root", "cache-audit", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    value = audit_coverage(args.model_root, args.input_root, args.cache_root, args.run_root, args.cache_audit)
    write_new(args.out, value)
    print(json.dumps(dict(status=value["status"], artifact=str(args.out), sha256=sha(args.out))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
