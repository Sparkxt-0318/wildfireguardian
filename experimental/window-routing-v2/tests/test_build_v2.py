"""Step 0 tests for build_kit_v2.py. Needs a built request-window parent kit: WFG_V2_PARENT=/path/to/window-kit."""
import hashlib, json, os, shutil, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_kit_v2 as B  # noqa: E402

PARENT = Path(os.environ.get('WFG_V2_PARENT', '')).resolve() if os.environ.get('WFG_V2_PARENT') else None
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


@unittest.skipIf(PARENT is None, 'set WFG_V2_PARENT to a built request-window kit')
class BuildV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='v2test_'))
        cls.out = cls.tmp / 'kit-v2'
        cls.man, cls.pm = B.build(cls.out, PARENT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_identity(self):
        ident = json.loads((self.out / 'KIT_IDENTITY.json').read_text())
        self.assertEqual(ident['candidate_id'], B.V2_ID)
        self.assertEqual(ident['parent_candidate_id'], B.PARENT_ID)
        self.assertNotEqual(self.man['candidate_id'], self.pm['candidate_id'])
        self.assertIn('NOT the frozen kit', (self.out / 'README_KIT.md').read_text())

    def test_only_declared_files_differ(self):
        sealed = json.loads((B.HERE / 'SOURCE_SHA256.json').read_text())
        overlay = {str(Path(p).relative_to('stack-v2')) for p in sealed}
        allowed = overlay | {'KIT_IDENTITY.json', 'README_KIT.md', 'CANDIDATE_MANIFEST.json'} | \
            {str(p.relative_to(self.out)) for p in (self.out / 'queues').glob('*.json')}
        for rel, h in self.pm['files'].items():
            if rel not in allowed:
                self.assertEqual(sha(self.out / rel), h, rel)
        for rel in overlay:
            self.assertEqual(sha(self.out / rel), sealed['stack-v2/' + rel])

    def test_manifest_matches_files(self):
        for rel, h in self.man['files'].items():
            self.assertEqual(sha(self.out / rel), h, rel)

    def test_queue_hashes_point_at_v2_worker(self):
        for q in (self.out / 'queues').glob('*.json'):
            for j in json.loads(q.read_text()).get('jobs', []):
                for n, h in (j.get('phaseB_sha256') or {}).items():
                    self.assertEqual(h, sha(self.out / 'phaseB' / n))

    def test_parent_unchanged_after_build(self):
        B.verify_parent(PARENT)

    def test_refuses_existing_output(self):
        with self.assertRaises(FileExistsError):
            B.build(self.out, PARENT)

    def test_refuses_frozen_and_parent_paths(self):
        for bad in [B.REPO / 'integration' / 'kit-v2-x', B.REPO / 'experimental/window-routing' / 'x', PARENT / 'x']:
            with self.assertRaises(ValueError):
                B.build(bad, PARENT)

    def test_refuses_changed_parent(self):
        bad = self.tmp / 'parent-changed'
        shutil.copytree(PARENT, bad)
        f = bad / 'README_KIT.md'; f.write_text(f.read_text() + 'x')
        with self.assertRaises(ValueError):
            B.build(self.tmp / 'never', bad)


class Sealed(unittest.TestCase):
    def test_overlay_sealed(self):
        B.check_sealed()

    def test_worker_overlay_is_parent_plus_declared_hunks_only(self):
        # Step 0: exactly the 3 identity lines. Step 1 (STEP1_ACCEPTANCE): plus the progress-hook lines, each of which
        # must carry a declared marker. No parent line may be removed except the one global statement Step 1 extends.
        parent = (B.REPO / 'experimental/window-routing/stack/phaseB/rda_worker_v1_1.py').read_text().splitlines()
        v2 = (B.HERE / 'stack-v2/phaseB/rda_worker_v1_1.py').read_text().splitlines()
        removed = [l for l in parent if l not in v2]
        self.assertEqual(removed, ['    global STATE, FOLDER, WRITE, ROOT'])
        added = [l for l in v2 if l not in parent]
        ident = [l for l in added if ('kit' in l.lower() or '_kid' in l) and 'Step 1' not in l and '_V2_PROG' not in l]
        self.assertEqual(len(ident), 3, ident)
        markers = ('_prog', '_PROG', 'PROGRESS', 'p[', 'p = ', 'tmp', 'f_', 'm_', 'res_', "'stage'", "'info'", 'return',
                   'try:', 'except', 'pass', 'with open', 'def ', 'global STATE')
        rest = [l for l in added if l not in ident and l.strip()]
        self.assertTrue(all(any(m in l for m in markers) for l in rest), [l for l in rest if not any(m in l for m in markers)])


if __name__ == '__main__':
    unittest.main()
