"""Run the parent kit's own tests (experimental/window-routing/tests/*, byte-unchanged) against a built v2 kit.

A temporary tree mirrors the parent layout: tests/ copied unchanged, SOURCE_SHA256.json copied, and stack/ holding
exactly the parent's 52 sealed paths, each COPIED from the v2 kit. Behavioural tests must pass. The two provenance
tests (test_18 and the inherited 'changes only five files') compare against the PARENT's sealed hashes, so on v2 they
are expected to fail exactly on the v2 overlay files; this runner checks that the differing set equals the overlay set
and nothing else.
  python -B run_parent_tests.py KIT_V2
"""
import hashlib, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARENT = REPO / 'experimental/window-routing'
PROVENANCE = {'test_18_repository_stack_matches_verified_source_hashes',
              'test_copy_changes_only_five_files_and_retains_prior_kernel_repair'}
# Step 2 (STEP2_ACCEPTANCE (a)): whole_road runs the identical checker call inside a forked, measured child. The parent's
# AST-identity test cannot hold; it is replaced by an exact test modulo the declared wrapper, which must pass.
REPLACED = {'test_general_check_first_preserves_mandatory_checker_and_limits':
            'tests/test_build_v2.py Sealed.test_step2_whole_road_is_parent_check_wrapped'}
kit = Path(sys.argv[1]).resolve()
sealed = json.loads((PARENT / 'SOURCE_SHA256.json').read_text())
overlay = {('stack/' + str(Path(p).relative_to('stack-v2'))) for p in json.loads((HERE.parent / 'SOURCE_SHA256.json').read_text())}
tmp = Path(tempfile.mkdtemp(prefix='v2parent_'))
shutil.copytree(PARENT / 'tests', tmp / 'tests'); shutil.copyfile(PARENT / 'SOURCE_SHA256.json', tmp / 'SOURCE_SHA256.json')
for rel in sealed:
    src = kit / Path(rel).relative_to('stack'); dst = tmp / rel
    dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, dst)
differ = {rel for rel, h in sealed.items() if hashlib.sha256((tmp / rel).read_bytes()).hexdigest() != h}
p = subprocess.run([sys.executable, '-B', str(tmp / 'tests/test_full_checker_window.py'), '-v'], cwd=tmp,
                   capture_output=True, text=True)
shutil.rmtree(tmp, ignore_errors=True)
out = p.stdout + p.stderr
failed = set(re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M))
ran = re.search(r'Ran (\d+) tests', out)
report = {'tests_run': int(ran.group(1)) if ran else None, 'failed': sorted(failed),
          'files_differing_from_parent_seal': sorted(differ), 'overlay_files': sorted(overlay & set(sealed)),
          'replaced': REPLACED}
rp = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'tests.test_build_v2.Sealed.test_step2_whole_road_is_parent_check_wrapped'],
                    cwd=HERE.parent, capture_output=True, text=True)
report['replacement_tests_pass'] = rp.returncode == 0
report['ok'] = failed <= (PROVENANCE | set(REPLACED)) and differ == (overlay & set(sealed)) and report['replacement_tests_pass']
print(json.dumps(report, indent=1))
if not report['ok']:
    print(out[-4000:])
sys.exit(0 if report['ok'] else 1)
