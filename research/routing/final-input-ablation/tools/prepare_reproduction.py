"""Make a fresh, identity-checked ablation workspace without copying scored records.

Run from the extracted complete evidence archive:
python prepare_reproduction.py --dest /absolute/workspace/outputs/ablation_reproduction
"""
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, sys, shlex

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--dest',type=Path,required=True)
    a=ap.parse_args();source=a.source.resolve();dest=a.dest.resolve()
    if dest.exists(): ap.error('Destination already exists; existing attempts are never overwritten.')
    if dest.parent.name!='outputs': ap.error('Use <workspace>/outputs/<new-study-label>; the frozen runner derives the workspace from this layout.')
    freeze=json.loads((source/'FREEZE.json').read_text())
    review=json.loads((source/'review/PRE_RUN_REVIEW.json').read_text())
    assert review['PASS'] and review['freeze_sha256']==sha(source/'FREEZE.json')
    for name, expected in freeze['files'].items():
        p=Path(name)
        assert not p.is_absolute() and '..' not in p.parts
        assert sha(source/p)==expected, f'Source identity mismatch: {p}'
    auxiliary=['FREEZE.json','GRADING_FREEZE.json','POLICY_TRANSFORMS.json','grade_all.py','run_grading.py',
               'write_report.py','STUDY_README.md','REPRODUCE.md',
               'review/PRE_RUN_REVIEW.json','review/PRE_RUN_REVIEW.md']
    grading=json.loads((source/'GRADING_FREEZE.json').read_text())
    for name, expected in grading['files'].items():
        p=Path(name)
        assert not p.is_absolute() and '..' not in p.parts
        assert sha(source/name)==expected, f'Grader identity mismatch: {name}'
    required=set(freeze['files'])|set(grading['files'])|set(auxiliary)
    for name in required: assert (source/name).is_file(),name
    dest.mkdir(parents=True)
    for name in sorted(required):
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name,p)
    # Verification uses the original bytes. A fresh run writes separate records.
    for name, expected in freeze['files'].items(): assert sha(dest/name)==expected,name
    for name, expected in grading['files'].items(): assert sha(dest/name)==expected,name
    lease=dest.parent/'SHARED_HEAVY_TIMING_LOCK.json'
    if not lease.exists():
        # Exclusive creation; never replace an existing record or release a lease.
        try:
            with lease.open('x') as f:
                json.dump({'status':'FREE','released_by':'fresh-workspace-initialization',
                    'initialized_for':'fresh ablation reproduction workspace',
                    'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},f,indent=2)
        except FileExistsError: pass
    py=shlex.quote(sys.executable)
    launch=shlex.quote(str(dest/'study/runner/run_ablation.py'))
    receipt={'status':'FRESH_SOURCE_COPY_VERIFIED','source':str(source),'destination':str(dest),
             'freeze_sha256':sha(dest/'FREEZE.json'),'frozen_files':len(freeze['files']),
             'raw_scored_records_copied':False,'shared_lease_replaced_or_released':False,
             'native_required_for_timed_reproduction':True,
             'reporting_note':'Stop at fresh execution/grading. The preserved write_report.py is tied to the original campaign and must not generate claims for a new unreviewed run. A new independent review and report are required.',
             'commands':[f'/usr/bin/caffeinate -i -s {py} -I -B {launch} --python {py} --stage preflight',
                         f'/usr/bin/caffeinate -i -s {py} -I -B {launch} --python {py} --stage primary',
                         f'/usr/bin/caffeinate -i -s {py} -I -B {shlex.quote(str(dest/"run_grading.py"))} {py}']}
    (dest/'REPRODUCTION_SETUP.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__': main()
