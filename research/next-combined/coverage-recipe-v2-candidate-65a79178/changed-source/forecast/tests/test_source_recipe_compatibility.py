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


@pytest.mark.parametrize("variant", ["d4_wind", "mixed_base"])
def test_exact_source_and_exact_known_custody_insertions_preserve_consumed_recipe(recipe, variant):
    F, current = recipe
    exact = check(recipe, current, variant)
    historical = check(recipe, F._source_blob(F.REPO, "research/forecast-v2/scripts/pipeline.py",
        "80a806e1177592fc4c16c12e78090a942b5cd1d985e644513fa8f401b8cf0439"), variant)
    assert exact["functions"]["available"]["immutable_ast_sha256"] == exact["functions"]["available"]["current_ast_sha256"]
    assert historical["functions"]["perimeter_samples"]["current_normalization"] == ["EXACT_CURRENT_PERIMETER_CUSTODY_PREFIX"]
    assert "CONDITIONAL" in historical["evidence"]
    assert historical["functions"]["kriged_samples"]["consumed"] is (variant == "mixed_base")


def old_utc_and_key(source):
    F = module()
    return F._source_blob(F.REPO, "research/forecast-v2/scripts/pipeline.py",
        "fe2304501159aa7340f305e8eb7a93e4199c59f9bb100f30667f60daeec00978")


def test_real_unfloored_utc_label_recipe_is_never_waived_for_a_mixed_fit(recipe):
    F, current = recipe
    old = old_utc_and_key(current)
    pure = check(recipe, old, "base")
    assert pure["functions"]["kriged_samples"]["consumed"] is False
    with pytest.raises(ValueError, match="whole-pipeline source version"):
        check(recipe, old, "mixed_base")
    old_new_key = old.replace('kriged_first', 'kriged_utc_v2_first')
    with pytest.raises(ValueError, match="whole-pipeline source version"):
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
    with pytest.raises(ValueError, match="whole-pipeline source version"):
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
    with pytest.raises(ValueError, match="whole-pipeline source version"):
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
    proof = check(recipe, old_utc_and_key(current), "base")
    assert proof["evidence"] == "SOURCE_RECIPE_EQUIVALENCE_CONDITIONAL_ON_MANDATORY_AUTHENTICATED_MEMBERSHIP_AND_CACHE_VALUES"


@pytest.mark.parametrize("mutation", ["consumed_else", "loader", "margin", "cropped", "module_reassignment"])
def test_five_independent_review_mutations_are_unknown_whole_producers(recipe, mutation):
    F, current = recipe
    tree = ast.parse(current)
    if mutation == "consumed_else":
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "fit_samples")
        next(n for n in node.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'mixed').orelse = ast.parse('samples = samples[:1]').body
    if mutation == "loader":
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "load_or_build")
        node.body = ast.parse('return builder()[:1]').body
    if mutation == "margin":
        node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MARGIN' for t in n.targets))
        node.value = ast.Constant(0)
    if mutation == "cropped":
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cropped")
        node.body = ast.parse('return sample').body
    if mutation == "module_reassignment": tree.body += ast.parse('perimeter_samples = lambda *a, **k: []').body
    changed = ast.unparse(ast.fix_missing_locations(tree))
    with pytest.raises(ValueError, match="whole-pipeline source version"):
        check(recipe, changed, "base")


def test_consumed_else_is_not_stripped_even_by_the_internal_normalizer(recipe):
    F, current = recipe
    node = ast.parse(ast.unparse(F._function(current, 'fit_samples'))).body[0]
    next(n for n in node.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'mixed').orelse = ast.parse('samples = samples[:1]').body
    with pytest.raises(ValueError, match="without an else"):
        F._normalized_input_recipe(node, 'fit_samples', pure=True)
    args = SimpleNamespace(max_fit_intervals_per_fire=0, work=Path('SYNTHETIC'), perimeters=Path('SYNTHETIC'), data_root=Path('SYNTHETIC'))
    namespace = dict(load_or_build=lambda w, n, builder: builder(), perimeter_samples=lambda *a, **k: ['first','second'])
    fn = extracted(F, ast.unparse(node), 'fit_samples', namespace)
    assert fn(args, ['US_SYNTHETIC'], None, mixed=False) == ['first']
    fn = extracted(F, current, 'fit_samples', namespace)
    assert fn(args, ['US_SYNTHETIC'], None, mixed=False) == ['first','second']


def test_closed_actual_current_source_profile_recomputes_every_source_byte(recipe):
    F, current = recipe
    proof = F._verified_producer_version(F.REPO, F._RECIPE_CURRENT_BASELINE, 'burnout_spotting_seed0_flaming_only')
    assert proof['verified_source_files'] == 61
    assert proof['closure_sha256'] == F.object_sha(F._RECIPE_CURRENT_BASELINE)
    assert 'CONDITIONAL' in proof['evidence']


def test_caller_hash_assertion_cannot_substitute_for_the_actual_source_bytes(recipe, monkeypatch):
    F, current = recipe
    real = F._source_blob
    victim = 'forecast/wildfire/models.py'
    def bad(root, relative, expected):
        blob = real(root, relative, expected)
        return blob + '\n# unexpected actual bytes\n' if relative == victim else blob
    monkeypatch.setattr(F, '_source_blob', bad)
    with pytest.raises(ValueError, match="Actual immutable producer bytes differ"):
        F._verified_producer_version(F.REPO, F._RECIPE_CURRENT_BASELINE, 'burnout_spotting_seed0_flaming_only')


def test_unknown_whole_dependency_version_and_wrong_phase_refuse_before_loading_source(recipe, monkeypatch):
    F, current = recipe
    changed = dict(F._RECIPE_CURRENT_BASELINE); changed['forecast/wildfire/models.py'] = '0' * 64
    monkeypatch.setattr(F, '_source_blob', lambda *a: pytest.fail('Unknown producer reached its source reader'))
    with pytest.raises(ValueError, match="whole-producer source closure"):
        F._verified_producer_version(F.REPO, changed, 'burnout_spotting_seed0_flaming_only')
    with pytest.raises(ValueError, match="whole-producer source closure"):
        F._verified_producer_version(F.REPO, F._RECIPE_CURRENT_BASELINE, 'mixed_base_seed0')


def copied_baseline(F, target):
    import shutil
    for relative in F._RECIPE_CURRENT_BASELINE:
        p = target / relative; p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(F.REPO / relative, p)
    path = target / 'research/forecast-v2/SPLIT.json';shutil.copyfile(F.REPO / 'research/forecast-v2/SPLIT.json',path)
    shutil.copytree(F.REPO / 'research/forecast-v2/source_snapshots', target / 'research/forecast-v2/source_snapshots')


@pytest.mark.parametrize('relative', ['forecast/wildfire/models.py', 'research/forecast-v2/scripts/pipeline.py', 'research/forecast-v2/scripts/audit_fit_coverage.py'])
def test_current_dependency_or_auditor_global_drift_cannot_hide_behind_preserved_historical_bytes(recipe, tmp_path, relative):
    F, current = recipe
    copied_baseline(F, tmp_path)
    path = tmp_path / relative
    path.write_text(path.read_text() + '\nUNREVIEWED_DEFINITION_TIME_VALUE = 1\n')
    with pytest.raises(ValueError, match='Unreviewed current producer dependency|numerical/member identity dependency'):
        F._verified_producer_version(tmp_path, F._RECIPE_CURRENT_BASELINE, 'burnout_spotting_seed0_flaming_only')


def test_known_legacy_cache_loader_matches_only_for_authenticated_complete_values(recipe, tmp_path):
    import pickle
    from wildfire.survival import PerimeterSample
    F, current = recipe
    sample = PerimeterSample('SYNTHETIC', '2020-01-01T00:00:00Z', 1., np.ones((2,2,2)), np.zeros((2,2),bool),
                             np.zeros((2,2),bool), np.ones((2,2),bool), np.ones((2,2)), np.zeros((2,2)))
    samples = [sample]
    path = tmp_path / 'samples/synthetic.pkl';path.parent.mkdir();path.write_bytes(pickle.dumps(samples))
    ns = dict(Path=Path, pickle=pickle, json=json, pd=pd,
        sha256=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),sample_list_identity=F.sample_list_identity)
    calls = []
    def builder(): calls.append(True); return samples
    old = extracted(F, old_utc_and_key(current), 'load_or_build', dict(ns))
    guarded = extracted(F, current, 'load_or_build', dict(ns))
    assert F.sample_list_identity(old(tmp_path,'synthetic',builder)) == F.sample_list_identity(guarded(tmp_path,'synthetic',builder))
    assert len(calls) == 1  # Legacy cache hit never invoked the source builder.
    sample.environment = np.full((2,2,2), 9.)
    corrupt = pickle.loads(path.read_bytes());corrupt[0].environment[:] = -1.;path.write_bytes(pickle.dumps(corrupt))
    assert old(tmp_path,'synthetic',builder)[0].environment[0,0,0] == -1.
    with pytest.raises(ValueError, match='Cached training samples differ'):
        guarded(tmp_path,'synthetic',builder)


def environment_class(F, source):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Environment')
    canonical = ast.parse(source)
    channels = ast.literal_eval(next(n.value for n in canonical.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id == 'SOURCE_CHANNELS' for t in n.targets)))
    namespace = dict(Path=Path, np=np, pd=pd, json=json, SOURCE_CHANNELS=channels,
                     CLASSES={'biome.biome_class': list(range(1,15))},
                     sha256=lambda p: hashlib.sha256(p.read_bytes()).hexdigest())
    exec(compile('from __future__ import annotations\n'+ast.unparse(node),'synthetic-environment-only','exec'),namespace)
    return namespace['Environment'], tuple(channels[:-1]+[f'biome.biome_class={i}' for i in range(1,15)])


@pytest.mark.parametrize('cache_change', [None, 'values', 'schema'])
def test_environment_rewrite_matches_only_authenticated_values_and_channel_schema(recipe, tmp_path, monkeypatch, cache_change):
    import torch
    import wildfire.data as D
    F, current = recipe
    old_cls,names = environment_class(F, old_utc_and_key(current));new_cls,_ = environment_class(F,current)
    root = tmp_path/'inputs/environment';root.mkdir(parents=True)
    event='SYNTHETIC';hour=pd.Timestamp('2020-01-01T00:00:00Z')
    catalog=root/'events.json';catalog.write_text(json.dumps([dict(id=event,start_utc=hour.isoformat(),end_utc=(hour+pd.Timedelta(hours=1)).isoformat())]))
    pins={'environment/events.json':hashlib.sha256(catalog.read_bytes()).hexdigest()}
    raw=np.zeros((len(names),2,2),np.float32);raw[0]=20;raw[1]=3;raw[3]=1;raw[4]=60;raw[5]=1
    calls=[]
    class Dataset:
        channel_names=names
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def __len__(self):return 1
        def __getitem__(self,index):return dict(features=torch.from_numpy(raw[None]),feature_valid=torch.ones((1,*raw.shape),dtype=torch.bool))
    def provider(*args,**kwargs):calls.append(True);return Dataset()
    monkeypatch.setattr(D,'load_data',provider)
    cache=tmp_path/'cache';cache.mkdir();path=cache/f'{event}_20200101T00.npz'
    cached=raw.copy();cached_names=list(names)
    if cache_change=='values':cached+=1
    if cache_change=='schema':cached_names=cached_names[::-1]
    np.savez_compressed(path,raw=cached,names=np.array(cached_names))
    old=old_cls(root,cache);new=new_cls(root,cache,pins)
    old_values=old.at(event,hour)
    assert calls==[]  # Historical Environment.at used cached values directly.
    if cache_change:
        with pytest.raises(ValueError,match='Cached environmental values differ'):
            new.at(event,hour)
        if cache_change=='schema':assert old.names != names
    else:
        np.testing.assert_array_equal(old_values,new.at(event,hour))
        assert old.names==new.names==names and len(calls)==1
        assert old.residence(event) is new.residence(event) is None


def test_a_known_phase_cannot_be_relabelled_pure_to_skip_its_actual_mixed_branch(recipe):
    F,current = recipe
    with pytest.raises(ValueError,match='exact intended phase, variant and stage'):
        F._schedule_contract(F.REPO,F._RECIPE_CURRENT_BASELINE,stage='final',variant='base',phase_id='burnout_spotting_seed0_flaming_only')
