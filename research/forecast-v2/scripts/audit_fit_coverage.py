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
import hashlib
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
                                 "research/forecast-v2/scripts/audit_fit_coverage.py", "research/forecast-v2/RUN_PROTOCOL.json")}
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
            if 0 < b.value - a.value <= 48 * 3600 * 10**9 and start <= a.floor("h") <= end:
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
        return current.read_text()
    snapshot = root / "research/forecast-v2/source_snapshots" / expected / Path(relative).name
    if snapshot.is_file() and sha(snapshot) == expected:
        return snapshot.read_text()
    listing = subprocess.run(["git", "rev-list", "--all", "--", relative], cwd=root, capture_output=True, text=True)
    commits = listing.stdout.splitlines() if listing.returncode == 0 else []
    for commit in commits:
        value = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=root, capture_output=True)
        if value.returncode == 0 and hashlib.sha256(value.stdout).hexdigest() == expected:
            return value.stdout.decode()
    raise ValueError("Exact immutable fit producer source is unavailable: " + relative)


def _function(source, name):
    nodes = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(nodes) != 1:
        raise ValueError("Expected one exact producer function: " + name)
    return nodes[0]


def _same(node, expression):
    return ast.dump(node, include_attributes=False) == ast.dump(ast.parse(expression, mode="eval").body, include_attributes=False)


def _literal(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        return {_literal(k): _literal(v) for k, v in zip(node.keys, node.values)}
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict"
            and not node.args and all(k.arg is not None for k in node.keywords)):
        return {k.arg: _literal(k.value) for k in node.keywords}
    raise ValueError("Fit regime policy must be an explicit literal source table")


def _schedule_contract(root, source):
    """Bounded source checks for full permutations and the recorded skip paths."""
    pipeline = _source_blob(root, "research/forecast-v2/scripts/pipeline.py", source["research/forecast-v2/scripts/pipeline.py"])
    survival = _source_blob(root, "forecast/wildfire/survival.py", source["forecast/wildfire/survival.py"])
    current_pipeline = (root / "research/forecast-v2/scripts/pipeline.py").read_text()
    for name in ("fit_samples", "available"):
        if ast.dump(_function(pipeline, name), include_attributes=False) != ast.dump(_function(current_pipeline, name), include_attributes=False):
            raise ValueError("Frozen producer fit input selection differs from the audited full-sample recipe")
    tables = [n for n in ast.parse(pipeline).body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "VARIANTS" for t in n.targets)]
    if len(tables) != 1:
        raise ValueError("The immutable producer must identify the full mixed/perimeter regime table")
    table = _literal(tables[0].value)
    if (set(table) != set(VARIANTS) or table["mixed_base"].get("mixed") is not True
            or any(table[name].get("mixed", False) for name in VARIANTS if name != "mixed_base")):
        raise ValueError("The producer's mixed extra-source regime differs from the intended fit policy")
    final = _function(pipeline, "command_final")
    required_origins = {"spec": "VARIANTS[args.variant]",
                        "train_events": 'available(args, SPLIT["fit"]["us_perimeter_and_kriged"])',
                        "train": 'fit_samples(args, train_events, env, mixed=spec.get("mixed", False))'}
    for target, expression in required_origins.items():
        values = [n.value for n in ast.walk(final) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == target for t in n.targets)]
        if len(values) != 1 or not _same(values[0], expression):
            raise ValueError("The immutable final producer does not consume its entire declared full-fit source list")
    calls = [n for n in ast.walk(final) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "fit_mean_field"]
    if len(calls) != 1:
        raise ValueError("One direct full-fit producer call is required")
    if len(calls[0].args) != 3 or not _same(calls[0].args[1], "train") or not _same(calls[0].args[2], "[]"):
        raise ValueError("Full fit must consume its entire prepared train list without a validation-based stopping set")
    keywords = {k.arg: k.value for k in calls[0].keywords}
    for name, value in {"validate_each_epoch": "False", "intervals_per_epoch": "args.intervals_per_epoch or None",
                        "samples_per_step": "args.samples_per_step", "epochs": "args.epochs"}.items():
        if name not in keywords or not _same(keywords[name], value):
            raise ValueError("Producer full-fit budget or selection call differs from the source-inference contract")
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
    return dict(pipeline_sha256=source["research/forecast-v2/scripts/pipeline.py"],
                survival_sha256=source["forecast/wildfire/survival.py"],
                fit_mean_field_ast_sha256=object_sha(ast.dump(fitting, include_attributes=False)),
                evidence="BOUNDED_SOURCE_CONTRACT_CHECKED")


def _option(command, name):
    indices = [i for i, value in enumerate(command) if value == name]
    if not indices or indices[-1] + 1 >= len(command):
        raise ValueError("Effective fit argument is missing: " + name)
    return command[indices[-1] + 1]


def _execution(root, run, variant):
    result_path = _inside(root, run / "final" / f"{variant}_seed0/result.json")
    matches = []
    for path in (root / "research/forecast-v2/executions").glob(f"*_final_{variant}.json"):
        record = json.loads(path.read_text())
        output = Path(record.get("output", ""))
        output = output if output.is_absolute() else root / output
        if output.resolve() == result_path and record.get("output_sha256") == sha(result_path):
            matches.append((path, record))
    if len(matches) != 1 or matches[0][1].get("exit_code") != 0:
        raise ValueError("Complete fit coverage requires one exact successful execution receipt")
    path, receipt = matches[0]
    return result_path, json.loads(result_path.read_text()), path, receipt


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


def audit_coverage(model_root, input_root, cache_root, run_root, cache_audit_path):
    root, inputs, caches, run = (Path(p).resolve() for p in (model_root, input_root, cache_root, run_root))
    expected = expected_membership(root, inputs)
    cache_audit_path = _inside(root, cache_audit_path)
    audit = json.loads(cache_audit_path.read_text())
    if (audit.get("status") != "PASS_NO_CONSUMED_VALUES_CHANGED" or audit.get("producer_unchanged_during_audit") is not True
            or audit.get("mismatches") != []):
        raise ValueError("A passing source-recomputed cache audit is required for full fit coverage")
    _source_blob(root, "research/forecast-v2/scripts/pipeline.py", audit["producer_sha256"])
    _source_blob(root, "research/forecast-v2/scripts/audit_caches.py", audit["audit_script_sha256"])
    perimeter, mixed, cache_files = _cache_lists(root, caches, audit, expected)
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
        contract = _schedule_contract(root, source)
        samples = mixed if variant == "mixed_base" else perimeter
        cases = expected["mixed_cases" if variant == "mixed_base" else "perimeter_cases"]
        ids = [c["case_id"] for c in cases]
        history = result.get("fit", {}).get("history", [])
        if (not ids or result.get("train_samples") != len(ids) or len(history) != 3
                or any(row.get("epoch") != i or row.get("optimizer_steps") != len(ids)
                       or row.get("skipped_unsupported_intervals") != [] for i, row in enumerate(history, 1))):
            raise ValueError("Full recorded sample/epoch/optimizer counts and no-skips must agree with complete source membership")
        runtime = None
        input_manifest = None
        evidence = "SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED"
        if variant == "mixed_base":
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
            for i, row in enumerate(epochs, 1):
                attempted = row.get("attempted_case_ids", [])
                if (row.get("epoch") != i or len(attempted) != len(ids) or set(attempted) != set(ids)
                        or row.get("attempted_case_ids_sha256") != object_sha(attempted)
                        or row.get("skipped_case_ids") != [] or row.get("optimizer_steps") != len(ids)):
                    raise ValueError("Actual mixed epoch membership omitted, repeated or skipped an intended source sample")
            evidence = "RUNTIME_ATTEMPTED_IDS_BOUND_TO_IMMUTABLE_SOURCE_AND_PREFIT_INPUT_MANIFEST"
        checkpoint = dict(path=str(result_path.with_name("checkpoint.pt").relative_to(root)), sha256=result["checkpoint_sha256"])
        variants[variant] = dict(checkpoint=checkpoint, regime="mixed" if variant == "mixed_base" else "perimeter", fit_result=identity(root, result_path),
                                 execution=identity(root, receipt_path), effective_arguments=effective,
                                 producer_source_sha256=source, source_schedule_contract=contract,
                                 sample_count=len(ids), membership_sha256=object_sha(sorted(ids)),
                                 sample_values_sha256=sample_list_identity(samples), input_manifest=input_manifest,
                                 schedule_evidence=evidence, runtime_membership=runtime,
                                 recorded_epochs=[dict(epoch=r["epoch"], optimizer_steps=r["optimizer_steps"],
                                                       skipped_unsupported_intervals=r["skipped_unsupported_intervals"]) for r in history])
    return dict(schema=SCHEMA, status="PASS_COMPLETE_FIT_MEMBERSHIP", expected=expected, variants=variants,
                source_sha256=producer_sources(root), cache_audit=identity(root, cache_audit_path), cache_files=cache_files,
                cache_audit_source_sha256=dict(pipeline=audit["producer_sha256"], audit_caches=audit["audit_script_sha256"]),
                input_root=str(inputs), cache_root=str(caches), run_root=str(run),
                limitations=["Historical pure schedules are source-derived inference, not retrospectively observed runtime IDs.",
                             "Exact case membership and no-skip counts establish the declared input schedule, not scientific efficacy.",
                             "No model checkpoint or heldout forecast/score is read by this coverage audit."])


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
