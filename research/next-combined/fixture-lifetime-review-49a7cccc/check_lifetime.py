"""Independent tiny fixture-lifetime controls, no actual study inputs or plotting."""
from pathlib import Path
import ast, copy, gzip, hashlib, importlib, importlib.util, json, subprocess, sys

BASE = Path(__file__).resolve().parents[2]
REPO = BASE / 'work/track-1b'
OWN = Path(__file__).resolve().parent
PIN = '49a7ccccc92b567e2c52ca91f92ae1efd88898ec'
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'forecast'))
import pytest
ready = importlib.import_module('forecast.tests.test_report_readiness')
protocol = importlib.import_module('forecast.tests.test_blind_forecast_protocol')
checks=[]
def check(name, condition):
    checks.append({'check':name,'pass':bool(condition)})
    if not condition: raise AssertionError(name)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def refuses(name, function):
    try: function()
    except ValueError as error:
        checks.append({'check':name,'pass':True,'reason':str(error)})
    else: check(name, False)

expected = {
 'forecast/tests/test_report_readiness.py':'2b76b959738ee702bca38466da2b5d43882bcdd87eff72c947022aa6de905e6a',
 'forecast/tests/test_report_ablation.py':'8e249210abb5ed2111e3be86fcba0500e06355ebd593ed0668b9383fd5d2581f',
 'research/forecast-v2/scripts/audit_fit_coverage.py':'65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536',
 'research/forecast-v2/review/report_fixture_catalog_lifetime_v1/FIXTURE_LIFETIME.patch.gz':'6d737af2b9801ac97e6ccd94b7d7bca6ec65308708ad61f1869fa2e264a8157c',
 'research/forecast-v2/review/report_fixture_catalog_lifetime_v1/MANIFEST.json':'52631a932ec62945b021c464ad40fea8a212445b5c8fa49353bd200b4b743285',
}
check('git_head_exact',subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==PIN)
for relative, digest in expected.items(): check('pin:'+relative,sha(REPO/relative)==digest)
for relative in ('forecast/tests/test_report_readiness.py','forecast/tests/test_report_ablation.py','research/forecast-v2/scripts/audit_fit_coverage.py','research/forecast-v2/scripts/report.py'):
    check('live_matches_git_blob:'+relative,(REPO/relative).read_bytes()==subprocess.check_output(['git','show',PIN+':'+relative],cwd=REPO))
    if '/scripts/' in relative:
        check('production_unchanged_by_lifetime_commit:'+relative,subprocess.check_output(['git','show',PIN+'^:'+relative],cwd=REPO)==(REPO/relative).read_bytes())
manifest=json.loads((REPO/'research/forecast-v2/review/report_fixture_catalog_lifetime_v1/MANIFEST.json').read_text())
check('manifest_patch_payload_sha',hashlib.sha256(gzip.decompress((REPO/'research/forecast-v2/review/report_fixture_catalog_lifetime_v1/FIXTURE_LIFETIME.patch.gz').read_bytes())).hexdigest()==manifest['patch_sha256'])
callers=[]
for relative in ('forecast/tests/test_report_readiness.py','forecast/tests/test_report_ablation.py'):
    tree=ast.parse((REPO/relative).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='build_fixture':
            callers.append((relative,node.lineno))
            check('caller_has_explicit_monkeypatch:%s:%d'%(relative,node.lineno),any(k.arg=='monkeypatch' for k in node.keywords))
check('all_nine_callers',len(callers)==9)

report=ready.load_report()
production_before=copy.deepcopy(report.F._RECIPE_SOURCE_VERSIONS)
current_before=copy.deepcopy(report.F._RECIPE_CURRENT_BASELINE)
catalog_before=copy.deepcopy(protocol._SYNTHETIC_RECIPE_VERSIONS)
captured={}
original_fit=protocol.freeze_inputs.__wrapped__
def capture(freezer, root, metadata_patch):
    captured['freezer']=freezer
    captured['comparator_sha_before']=freezer.C651_SHA
    captured['verifier_before']=freezer.verified_fit_coverage
    answer=original_fit(freezer,root,metadata_patch)
    key=str(answer[0].resolve())
    captured['key']=key
    captured['original_entry']=protocol._SYNTHETIC_RECIPE_VERSIONS[key]
    captured['original_snapshot']=copy.deepcopy(captured['original_entry'])
    return answer
with pytest.MonkeyPatch.context() as instrumentation:
    instrumentation.setattr(protocol.freeze_inputs,'__wrapped__',capture)
    with pytest.MonkeyPatch.context() as lifetime:
        fixture=ready.build_fixture(report,OWN/'synthetic',monkeypatch=lifetime)
        key=captured['key']
        entry=protocol._SYNTHETIC_RECIPE_VERSIONS[key]
        check('catalog_registered_after_internal_context',key in protocol._SYNTHETIC_RECIPE_VERSIONS)
        check('catalog_value_exact_precaptured_snapshot',entry==captured['original_snapshot'])
        check('catalog_deepcopy_root',entry is not captured['original_entry'])
        check('catalog_deepcopy_current',entry['current'] is not captured['original_entry']['current'])
        check('catalog_deepcopy_versions',entry['versions'] is not captured['original_entry']['versions'])
        digest=next(iter(entry['versions']))
        check('catalog_deepcopy_nested_phase_list',entry['versions'][digest] is not captured['original_entry']['versions'][digest])
        check('temporary_comparator_mock_restored',captured['freezer'].C651_SHA==captured['comparator_sha_before'])
        check('temporary_verifier_mock_restored',captured['freezer'].verified_fit_coverage is captured['verifier_before'])
        captured['original_entry']['current']['independent_mutation']='not present in frozen entry'
        captured['original_entry']['versions'][digest].append('not-a-phase')
        check('old_entry_mutation_does_not_change_frozen_catalog',entry==captured['original_snapshot'])
        phase=report.F.intended_phase('base','fold','2020')['phase_id']
        source=report.F.producer_sources(fixture.root)
        accepted=report.F._verified_producer_version(fixture.root,source,phase)
        check('positive_fixture_verified',accepted['closure_sha256']==report.F.object_sha(source))
        check('production_versions_restored_after_positive',report.F._RECIPE_SOURCE_VERSIONS==production_before)
        check('production_current_baseline_restored_after_positive',report.F._RECIPE_CURRENT_BASELINE==current_before)
        path=REPO/'research/forecast-v2/scripts/audit_fit_coverage.py'
        spec=importlib.util.spec_from_file_location('independent_unwrapped_auditor',path)
        fresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(fresh)
        check('fresh_production_has_no_fixture_boundary',not getattr(fresh,'_synthetic_recipe_bound',False))
        refuses('fresh_production_refuses_fixture_while_catalog_present',lambda:fresh._verified_producer_version(fixture.root,source,phase))
        pipeline=fixture.root/'research/forecast-v2/scripts/pipeline.py'
        old=pipeline.read_bytes();pipeline.write_bytes(old+b'\n# independent post-freeze source mutation\n')
        changed=report.F.producer_sources(fixture.root)
        refuses('post_freeze_source_mutation_refused',lambda:report.F._verified_producer_version(fixture.root,changed,phase))
        check('frozen_catalog_unchanged_by_source_mutation',entry==captured['original_snapshot'])
        check('production_versions_restored_after_refusal',report.F._RECIPE_SOURCE_VERSIONS==production_before)
        check('production_current_baseline_restored_after_refusal',report.F._RECIPE_CURRENT_BASELINE==current_before)
        pipeline.write_bytes(old)
        report.F._verified_producer_version(fixture.root,source,phase)
    check('catalog_exact_pretest_state_after_teardown',protocol._SYNTHETIC_RECIPE_VERSIONS==catalog_before)
    check('fixture_key_absent_after_teardown',key not in protocol._SYNTHETIC_RECIPE_VERSIONS)
    refuses('same_fixture_no_admission_after_teardown',lambda:report.F._verified_producer_version(fixture.root,source,phase))
    check('production_versions_exact_pretest_state',report.F._RECIPE_SOURCE_VERSIONS==production_before)
    check('production_current_baseline_exact_pretest_state',report.F._RECIPE_CURRENT_BASELINE==current_before)
check('instrumentation_restored',protocol.freeze_inputs.__wrapped__ is original_fit)
for relative,digest in expected.items(): check('source_still_pinned:'+relative,sha(REPO/relative)==digest)
result={'status':'PASS_TEST_FIXTURE_LIFETIME_ONLY','source_head':PIN,'checks':checks,'passed':sum(c['pass'] for c in checks),'total':len(checks),'pins':{p:sha(REPO/p) for p in expected},'report_sha256':sha(REPO/'research/forecast-v2/scripts/report.py'),'limits':['No plotting, full suite, fits, actual input arrays, checkpoints, forecasts or heldout evidence accessed.','Tiny fixture arrays and dummy checkpoint byte strings are test constructions only.','No actual coverage or registry clearance is claimed.']}
(OWN/'CHECKS.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('status','source_head','passed','total','report_sha256')},indent=2))
