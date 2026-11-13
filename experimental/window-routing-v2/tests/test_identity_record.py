"""Identity record (IDENTITY_RECORD_ACCEPTANCE, pre-stated tests a and b) on a built v2 kit (WFG_V2_KIT).

(a) A real job records, for contact_first, mission_contract and hybrid_checker, a path inside the kit and a sha256
    equal to the kit manifest's entry for that file.
(b) A scratch copy of the kit with contact_first.py deliberately modified (a comment line appended) records that
    module's OWN hash: equal to the modified file's sha256, different from the manifest's entry. The other two
    modules still equal the manifest.
Each job runs in a fresh interpreter (tools/run_one_job.py), so the two kits never share imported modules.
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
REPO = HERE.parents[2]
KIT = Path(os.environ['WFG_V2_KIT']).resolve() if os.environ.get('WFG_V2_KIT') else None
DATA = Path(os.environ.get('WFG_DATA_ROUTING', REPO / 'data/routing')).resolve()
MISSION = ('uljin_2022', '20220304T120000Z_FW2')      # runs the whole-road check in about 7 s
MODS = {'contact_first': 'routing_candidate/baseline/contact_first.py',
        'mission_contract': 'routing_candidate/baseline/mission_contract.py',
        'hybrid_checker': 'routing_candidate/baseline/hybrid_checker.py'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest(kit):
    m = json.loads((kit / 'CANDIDATE_MANIFEST.json').read_text())
    return m.get('files', m)


def run(kit):
    out = Path(tempfile.mkdtemp(prefix='v2idrec_')) / 'job'
    p = subprocess.run([sys.executable, '-B', str(V2 / 'tools/run_one_job.py'), str(kit), str(DATA), MISSION[0],
                        MISSION[1], str(out), '81'], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-3000:]
    run.last = json.loads((out / 'RESULT.json').read_text())
    return run.last


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class IdentityRecord(unittest.TestCase):
    def test_a_recorded_hashes_equal_manifest(self):
        rec = run(KIT).get('checker_identity')
        self.assertIsNotNone(rec, 'RESULT has no checker_identity')
        res = run.last
        q = json.loads((KIT / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
        self.assertEqual(rec['checker_module_override'], q.get('checker_module'))   # 'adaptive_checker' in this kit
        if q.get('checker_module'):
            self.assertEqual((res.get('checker_module') or {}).get('module'), q['checker_module'])
            self.assertIn(q['checker_module'], rec['checker_class_mro'])
        self.assertIn('hybrid_checker', rec['checker_class_mro'])   # the recorded hybrid_checker is on the checking path
        man = manifest(KIT)
        for name, rel in MODS.items():
            e = rec[name]
            self.assertTrue(e.get('imported'), (name, e))
            self.assertEqual(Path(e['path']).resolve(), (KIT / rel).resolve(), name)
            self.assertEqual(e['sha256'], man[rel], name)

    def test_b_modified_copy_records_its_own_hash(self):
        scratch = Path(tempfile.mkdtemp(prefix='v2idrec_kit_')) / 'kit'
        shutil.copytree(KIT, scratch, symlinks=True)
        target = scratch / MODS['contact_first']
        if target.is_symlink():
            data = target.read_bytes(); target.unlink(); target.write_bytes(data)
        with target.open('a') as f:
            f.write('\n# identity-record test: deliberately modified copy\n')
        rec = run(scratch).get('checker_identity')
        man = manifest(KIT)
        e = rec['contact_first']
        self.assertEqual(Path(e['path']).resolve(), target.resolve())
        self.assertEqual(e['sha256'], sha(target))
        self.assertNotEqual(e['sha256'], man[MODS['contact_first']])
        for name in ('mission_contract', 'hybrid_checker'):
            self.assertEqual(rec[name]['sha256'], man[MODS[name]], name)
            self.assertEqual(Path(rec[name]['path']).resolve(), (scratch / MODS[name]).resolve(), name)


if __name__ == '__main__':
    unittest.main()
