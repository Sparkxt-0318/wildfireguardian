from pathlib import Path
import ast,json,pprint
v=Path(__file__).parent;p=v/'repo/research/forecast-v2/scripts/audit_fit_coverage.py'
s=p.read_text();inv=json.loads((v/'WHOLE_CLOSURE_INVENTORY.json').read_text())
current='88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67'
baseline=next(row['source_sha256'] for row in inv['profiles'].values() if row['source_sha256']['research/forecast-v2/scripts/pipeline.py']==current)
profiles={sha:row['phases'] for sha,row in inv['profiles'].items()}
versions={row['source_sha256']['research/forecast-v2/scripts/pipeline.py']:sorted(set(next(r['phase'].split('_fold')[0] if '_fold' in r['phase'] else r['phase'].split('_seed')[0] for r in inv['phases'] if r['closure_sha256']==sha) for _ in [0])) for sha,row in inv['profiles'].items()}
# Explicit variants from actual phase names; preserve the full closure phase restriction below.
versions={}
for row in inv['phases']:
 phase=row['phase'];variant=phase.split('_fold')[0] if '_fold' in phase else phase.split('_seed')[0]
 versions.setdefault(row['pipeline_sha256'],set()).add(variant)
versions={sha:sorted(values) for sha,values in versions.items()}
constants='''# Closed immutable producer versions, pending independent review. Membership/cache
# authentication remains mandatory; these pins do not assert universal equivalence.
_RECIPE_PIPELINE_VERSIONS = '''+pprint.pformat(versions,width=110,sort_dicts=True)+'''\n_RECIPE_SOURCE_VERSIONS = '''+pprint.pformat(profiles,width=110,sort_dicts=True)+'''\n_RECIPE_CURRENT_BASELINE = '''+pprint.pformat(baseline,width=110,sort_dicts=True)+'''\n\n'''
s=s.replace('def _normalized_input_recipe(',constants+'def _normalized_input_recipe(',1)
old='''        body = [n for n in node.body if not (isinstance(n, ast.If) and _same(n.test, "mixed"))]
'''
new='''        branches = [n for n in node.body if isinstance(n, ast.If) and _same(n.test, "mixed")]
        if len(branches) != 1 or branches[0].orelse:
            raise ValueError("Pure mixed-branch proof requires the exact known branch without an else")
        body = [n for n in node.body if n is not branches[0]]
'''
assert old in s;s=s.replace(old,new,1)
anchor='''    pure = variant in table and not table[variant].get("mixed", False)
'''
new='''    immutable_sha = hashlib.sha256(pipeline.encode("utf-8")).hexdigest()
    current_sha = hashlib.sha256(current_pipeline.encode("utf-8")).hexdigest()
    if (current_sha != "'''+current+'''" or immutable_sha not in _RECIPE_PIPELINE_VERSIONS
            or variant not in _RECIPE_PIPELINE_VERSIONS[immutable_sha]):
        raise ValueError("Unreviewed whole-pipeline source version; no recipe compatibility is admitted")
'''+anchor
assert anchor in s;s=s.replace(anchor,new,1)
# Keep the proof explicitly version-bound instead of implying five-function closure equivalence.
s=s.replace('return dict(variant=variant, resolved_mixed=', 'return dict(immutable_pipeline_sha256=immutable_sha, current_pipeline_sha256=current_sha, variant=variant, resolved_mixed=',1)
insert='''def _auditor_numeric_surface(source):
    """Exclude only this reviewed auditor repair, retaining every other declaration."""
    tree = ast.parse(source)
    repair_names = {"_normalized_input_recipe", "_input_recipe_contract", "_auditor_numeric_surface",
                    "_verified_producer_version", "_schedule_contract", "development_coverage", "audit_coverage"}
    repair_constants = {"_RECIPE_PIPELINE_VERSIONS", "_RECIPE_SOURCE_VERSIONS", "_RECIPE_CURRENT_BASELINE"}
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.FunctionDef) and node.name in repair_names or
        isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in repair_constants for t in node.targets))]
    return _dump(tree)


def _verified_producer_version(root, source, phase_id):
    """Recompute every declared source byte, reject unknown complete versions.

    This permits only the enumerated producer phases on independently authenticated
    actual cached inputs. It is neither universal equivalence nor runtime replay.
    """
    declared = object_sha(source)
    if declared not in _RECIPE_SOURCE_VERSIONS or phase_id not in _RECIPE_SOURCE_VERSIONS[declared]:
        raise ValueError("Unreviewed whole-producer source closure or intended phase")
    actual = {}
    for relative, expected in source.items():
        original = _source_blob(root, relative, expected)
        actual[relative] = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if object_sha(actual) != declared:
        raise ValueError("Actual immutable producer bytes differ from their reviewed version")
    auditor = "research/forecast-v2/scripts/audit_fit_coverage.py"
    for relative, expected in _RECIPE_CURRENT_BASELINE.items():
        if relative == auditor:
            continue
        if sha(_inside(root, relative)) != expected:
            raise ValueError("Unreviewed current producer dependency: " + relative)
    original_auditor = _source_blob(root, auditor, _RECIPE_CURRENT_BASELINE[auditor])
    if _auditor_numeric_surface(original_auditor) != _auditor_numeric_surface(_inside(root, auditor).read_text()):
        raise ValueError("Current auditor changed a numerical/member identity dependency outside the recipe repair")
    protocol_path = "research/forecast-v2/RUN_PROTOCOL.json"
    protocol = json.loads(_source_blob(root, protocol_path, _RECIPE_CURRENT_BASELINE[protocol_path]))
    if sha(_inside(root, "research/forecast-v2/SPLIT.json")) != protocol.get("split_sha256"):
        raise ValueError("Whole producer recipe requires the protocol-pinned SPLIT bytes")
    return dict(closure_sha256=declared, verified_source_files=len(actual), intended_phase=phase_id,
                current_baseline_sha256=object_sha(_RECIPE_CURRENT_BASELINE),
                evidence="EXACT_IMMUTABLE_PRODUCER_VERSIONS_CONDITIONAL_ON_AUTHENTICATED_ACTUAL_INPUT_CACHE_VALUES")


'''
s=s.replace('def _schedule_contract(root, source, stage="final", variant=None):',insert+'def _schedule_contract(root, source, stage="final", variant=None, phase_id=None):',1)
s=s.replace('''    pipeline = _source_blob(root, "research/forecast-v2/scripts/pipeline.py", source["research/forecast-v2/scripts/pipeline.py"])
''','''    producer_version = _verified_producer_version(root, source, phase_id)
    pipeline = _source_blob(root, "research/forecast-v2/scripts/pipeline.py", source["research/forecast-v2/scripts/pipeline.py"])
''',1)
s=s.replace('return dict(input_recipe=recipe, pipeline_sha256=', 'return dict(producer_version=producer_version, input_recipe=recipe, pipeline_sha256=',1)
s=s.replace('_schedule_contract(root, source, stage="fold", variant=variant)', '_schedule_contract(root, source, stage="fold", variant=variant, phase_id=phase["phase_id"])')
s=s.replace('_schedule_contract(root, source, variant=variant)', '_schedule_contract(root, source, variant=variant, phase_id=intended_phase(variant, "final")["phase_id"])')
p.write_text(s)
