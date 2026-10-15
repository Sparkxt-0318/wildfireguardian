"""Verify byte identities of the published scientific source and assets; no numerical work."""
from pathlib import Path
import hashlib,json,ast
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((R/'docs/PUBLICATION_SOURCE_MANIFEST.json').read_text())
for row in manifest['files']:
 p=R/row['published_path']
 if not p.is_file() or sha(p)!=row['sha256']:raise SystemExit('Identity mismatch: '+str(p))
identity=json.loads((R/'docs/RELEASE_IDENTITY.json').read_text())
ck=R/'forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt'
assert sha(ck)==identity['checkpoint_sha256']
review=json.loads((R/'research/routing/FINAL_REVIEW.json').read_text())
assert review['status']=='ACCEPTED_BOUNDED_RESEARCH_WITH_STATED_LIMITS'
assert review['by_arm']['RDA_CAND']['both_repetitions_resolved_missions']==20
assert review['by_arm']['RDA_CAND']['both_repetitions_checked_route_missions']==15
assert review['by_arm']['RDA_CAND']['both_repetitions_scoped_refusal_missions']==5
for folder in ['integration','forecast/wildfire','hardware','tools']:
 for p in (R/folder).rglob('*.py'):
  ast.parse(p.read_text(),filename=str(p))
# Local recordings and the privacy-circle secret must never be included in a release.
for p in (R/'hardware').rglob('*'):
 if p.is_file() and (p.name=='zone_secret' or '.chrome-profile' in p.parts or 'devices' in p.parts or 'logs' in p.parts):raise SystemExit('Private runtime file: '+str(p))
print('PASS: '+str(len(manifest['files']))+' copied source/artifact hashes, checkpoint, accepted scores, Python syntax and privacy exclusions')
