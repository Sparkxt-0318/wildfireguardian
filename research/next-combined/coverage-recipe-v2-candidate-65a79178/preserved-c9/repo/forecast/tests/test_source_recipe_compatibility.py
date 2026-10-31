"""Pure synthetic source equivalence, conditional on authenticated input values."""
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd
import pytest


def module():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/audit_fit_coverage.py"
    spec = importlib.util.spec_from_file_location("recipe_compatibility_fixture", path)
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value; spec.loader.exec_module(value)
    return value


@pytest.fixture
def recipe():
    value = module()
    source = (Path(value.__file__).with_name("pipeline.py")).read_text()
    return value, source


def without_custody(source):
    begin = source.index('    manifest_path = perimeters / "PERIMETER_MANIFEST.json"', source.index('def perimeter_samples'))
    end = source.index('    times = ', begin)
    source = source[:begin] + '    data = np.load(perimeters / event / "states.npz")\n' + source[end:]
    source = source.replace('    if hasattr(env, "_verify_sources"):\n        env._verify_sources(event)\n', '', 1)
    return source


def check(recipe, immutable, variant):
    F, current = recipe
    return F._input_recipe_contract(immutable, current, variant, F.FIXED_VARIANT_POLICY)


@pytest.mark.parametrize("variant", ["base", "mixed_base"])
def test_exact_source_and_exact_known_custody_insertions_preserve_consumed_recipe(recipe, variant):
    F, current = recipe
    exact = check(recipe, current, variant)
    historical = check(recipe, without_custody(current), variant)
    assert exact["functions"]["available"]["immutable_ast_sha256"] == exact["functions"]["available"]["current_ast_sha256"]
    assert historical["functions"]["perimeter_samples"]["current_normalization"] == ["EXACT_CURRENT_PERIMETER_CUSTODY_PREFIX"]
    assert "CONDITIONAL" in historical["evidence"]
    assert historical["functions"]["kriged_samples"]["consumed"] is (variant == "mixed_base")


def old_utc_and_key(source):
    return without_custody(source).replace('kriged_utc_v2_first', 'kriged_first').replace(
        '        t = (hour - t0).total_seconds() / 3600\n', '', 1)


def test_real_unfloored_utc_label_recipe_is_never_waived_for_a_mixed_fit(recipe):
    F, current = recipe
    old = old_utc_and_key(current)
    pure = check(recipe, old, "base")
    assert pure["functions"]["kriged_samples"]["consumed"] is False
    with pytest.raises(ValueError, match="consumed input recipe differs: fit_samples"):
        check(recipe, old, "mixed_base")
    old_new_key = old.replace('kriged_first', 'kriged_utc_v2_first')
    with pytest.raises(ValueError, match="consumed input recipe differs: kriged_samples"):
        check(recipe, old_new_key, "mixed_base")


@pytest.mark.parametrize("mutation", ["available_subset", "model_hidden", "perimeter_subset", "endpoint", "crop", "custody_side_effect"])
def test_real_consumed_event_sample_model_or_label_changes_still_refuse(recipe, mutation):
    F, current = recipe
    changes = {
        "available_subset": ('return [e for e in events if e in known', 'return [e for e in events[:1] if e in known'),
        "model_hidden": ('StructuredKernelModel(len(names), 9, hidden, 0.0', 'StructuredKernelModel(len(names), 9, 1, 0.0'),
        "perimeter_subset": ('for i, j, hours in consecutive_intervals(times, 48.0):', 'for i, j, hours in consecutive_intervals(times, 24.0):'),
        "endpoint": ('initial, endpoint = states[i], states[j]', 'initial, endpoint = states[i], states[i]'),
        "crop": ('result.append(cropped(sample) if crop else sample)', 'result.append(sample)'),
        "custody_side_effect": ('    data = np.load(states_path, allow_pickle=False)', '    states_path = perimeters / event / "other.npz"\n    data = np.load(states_path, allow_pickle=False)'),
    }
    before, after = changes[mutation]
    assert before in current
    with pytest.raises(ValueError, match="consumed input recipe differs"):
        check(recipe, current.replace(before, after, 1), "base")


def extracted(F, source, name, namespace):
    code = "from __future__ import annotations\n" + ast.unparse(F._function(source, name))
    exec(compile(code, "synthetic_source_only", "exec"), namespace)
    return namespace[name]


def test_legacy_mixed_cache_key_and_utc_code_are_not_executed_in_pure_fit(recipe, tmp_path):
    F, current = recipe
    args = SimpleNamespace(max_fit_intervals_per_fire=3, work=tmp_path, perimeters=tmp_path,
                           data_root=tmp_path)
    all_calls = []
    for source in (old_utc_and_key(current), current):
        calls = []
        def loader(work, name, builder):
            calls.append(name); return builder()
        def kriged(*args, **kwargs): pytest.fail("Pure recipe reached an unconsumed kriged branch")
        function = extracted(F, source, "fit_samples", dict(load_or_build=loader,
            perimeter_samples=lambda *args, **kwargs: ["first", "second", "third"], kriged_samples=kriged,
            SPLIT=dict(fit=dict(korean_kriged_only=["KR_SYNTHETIC"]))))
        assert function(args, ["US_SYNTHETIC"], object(), mixed=False) == ["first", "second", "third"]
        all_calls.append(calls)
    assert all_calls == [["perimeter_crop_first3_US_SYNTHETIC"]] * 2


def sample_namespace():
    from wildfire.survival import PerimeterSample, consecutive_intervals, ages_from_states, kriging_weight
    return dict(np=np, pd=pd, Path=Path, json=json, math=math, PerimeterSample=PerimeterSample,
                consecutive_intervals=consecutive_intervals, ages_from_states=ages_from_states, kriging_weight=kriging_weight,
                cropped=lambda value: value,
                sha256=lambda path: hashlib.sha256(path.read_bytes()).hexdigest())


def environment():
    return SimpleNamespace(available_at=lambda *args: True, at=lambda *args: np.ones((2, 2, 2)),
                           residence=lambda *args: np.full((2, 2), 6.), _verify_sources=lambda *args: None)


def test_current_and_historical_perimeter_functions_reproduce_identical_authenticated_samples(recipe, tmp_path):
    F, current = recipe
    event = "US_SYNTHETIC"; path = tmp_path / event / "states.npz"; path.parent.mkdir()
    states = np.zeros((3, 2, 2), bool); states[:, 0, 0] = True; states[1:, 0, 1] = True
    np.savez_compressed(path, times=np.array(["2020-01-01T00:00:00Z", "2020-01-01T12:00:00Z", "2020-01-02T00:00:00Z"]), states=states)
    manifest = dict(events={event: dict(states_sha256=hashlib.sha256(path.read_bytes()).hexdigest())})
    (tmp_path / "PERIMETER_MANIFEST.json").write_text(json.dumps(manifest))
    samples = []
    for source in (without_custody(current), current):
        function = extracted(F, source, "perimeter_samples", sample_namespace())
        samples.append(function(event, tmp_path, environment(), crop=True, max_intervals=3))
    assert len(samples[0]) == len(samples[1]) == 2
    assert F.sample_list_identity(samples[0]) == F.sample_list_identity(samples[1])


def test_unfloored_utc_recipe_has_an_actual_synthetic_counterexample_not_a_naming_only_difference(recipe, tmp_path):
    import rasterio
    from affine import Affine
    F, current = recipe
    event = "KR_SYNTHETIC"; region = tmp_path / "regions" / event; region.mkdir(parents=True)
    for filename, array in [("arrival_time_hours.tif", np.array([[0., .25], [11.75, 13.]], dtype=np.float32)),
                             ("kriging_std_hours.tif", np.ones((2, 2), dtype=np.float32))]:
        with rasterio.open(region / filename, "w", driver="GTiff", count=1, height=2, width=2, dtype="float32",
                           transform=Affine(375, 0, 500000, 0, -375, 5000000), crs="EPSG:32610") as out:
            out.write(array, 1)
    (tmp_path / "events.json").write_text(json.dumps([dict(id=event, t0_utc="2020-01-01T00:30:00Z",
        start_utc="2019-12-31T23:00:00Z", end_utc="2020-01-03T00:00:00Z")]))
    outputs = []
    for source in (old_utc_and_key(current), current):
        function = extracted(F, source, "kriged_samples", sample_namespace())
        outputs.append(function(event, tmp_path, environment()))
    assert len(outputs[0]) == 2 and len(outputs[1]) == 1
    assert F.sample_list_identity(outputs[0]) != F.sample_list_identity(outputs[1])
    with pytest.raises(ValueError): check(recipe, old_utc_and_key(current), "mixed_base")


@pytest.mark.parametrize("change", ["default", "default_side_effect", "decorator", "returns", "annotation"])
def test_unused_kriged_body_does_not_waive_definition_time_header_effects(recipe, change):
    F, current = recipe
    original = F._function(current, "kriged_samples")
    definition = ast.parse(ast.unparse(original)).body[0]
    if change == "default": definition.args.kw_defaults[0] = ast.Constant(11.)
    if change == "default_side_effect": definition.args.kw_defaults[0] = ast.Call(ast.Name("unlogged_definition_effect", ast.Load()), [], [])
    if change == "decorator": definition.decorator_list = [ast.Name("unlogged_decorator", ast.Load())]
    if change == "returns": definition.returns = ast.Name("DifferentReturnAnnotation", ast.Load())
    if change == "annotation": definition.args.args[0].annotation = ast.Name("DifferentArgumentAnnotation", ast.Load())
    lines = current.splitlines(keepends=True)
    changed = ''.join(lines[:original.lineno - 1]) + ast.unparse(definition) + '\n' + ''.join(lines[original.end_lineno:])
    with pytest.raises(ValueError, match="unconsumed definition header differs: kriged_samples"):
        check(recipe, changed, "base")


def test_custody_equivalence_is_conditional_and_legacy_did_not_enforce_the_new_manifest_check(recipe, tmp_path):
    F, current = recipe
    event = "US_SYNTHETIC"; path = tmp_path / event / "states.npz"; path.parent.mkdir()
    states = np.zeros((2, 2, 2), bool); states[:, 0, 0] = True
    np.savez_compressed(path, times=np.array(["2020-01-01T00:00:00Z", "2020-01-01T12:00:00Z"]), states=states)
    (tmp_path / "PERIMETER_MANIFEST.json").write_text(json.dumps(dict(events={event: dict(states_sha256="0" * 64)})))
    old = extracted(F, without_custody(current), "perimeter_samples", sample_namespace())
    guarded = extracted(F, current, "perimeter_samples", sample_namespace())
    assert len(old(event, tmp_path, environment(), crop=True)) == 1
    with pytest.raises(ValueError, match="Perimeter reference identity differs"):
        guarded(event, tmp_path, environment(), crop=True)
    proof = check(recipe, without_custody(current), "base")
    assert proof["evidence"] == "SOURCE_RECIPE_EQUIVALENCE_CONDITIONAL_ON_MANDATORY_AUTHENTICATED_MEMBERSHIP_AND_CACHE_VALUES"
